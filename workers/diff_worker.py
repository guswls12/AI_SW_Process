"""
diff_worker.py — 폴더 DIFF 추출 백그라운드 워커
  - DiffWorker    : QThread 에서 실행되는 폴더 스캔 + 파일별 변경점 분석 객체
  - ReqDiffWorker : 요구사항 파일 2개(Before/After)를 비교해 변경점 텍스트 추출
UI 의존성 없음 (PyQt 시그널만 사용). Claude API 와 무관.
"""

import os
import difflib

from PyQt6.QtCore import QObject, pyqtSignal

from core.text_io import read_text_lines, read_doc_lines


# ══════════════════════════════════════════════════════════════
#  DiffWorker — 폴더 DIFF 추출 (스캔 + 파일별 분석)
# ══════════════════════════════════════════════════════════════
class DiffWorker(QObject):
    """폴더 모드 DIFF 추출을 백그라운드 스레드에서 실행한다.

    Signals
    -------
    progress(phase: str, cur: int, total: int, name: str)
        진행률 업데이트. phase ∈ {"scan", "build"}.
    done(payload: dict)
        완료 시 결과. keys:
          file_pairs, old_parts, new_parts, diff_parts,
          output_lines, changed_files, total_func_count
    cancelled()
        사용자 중단 요청으로 정상 종료된 경우.
    error(msg: str)
        예외 발생 시 메시지.
    """
    progress  = pyqtSignal(str, int, int, str)
    done      = pyqtSignal(dict)
    cancelled = pyqtSignal()
    error     = pyqtSignal(str)

    _EXTS = ('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')

    def __init__(self, old_folder: str, new_folder: str,
                 ignore_comments: bool = False):
        super().__init__()
        self.old_folder      = old_folder
        self.new_folder      = new_folder
        self.ignore_comments = ignore_comments
        self._cancel_req     = False   # ★ UI 스레드에서 set, 워커 스레드에서 check

    def cancel(self):
        """UI 스레드에서 호출 — 다음 루프 반복에서 워커가 조기 종료한다."""
        self._cancel_req = True

    def run(self):
        try:
            # 지연 import (순환 의존 방지 + 워커 단위 로딩)
            from core.model import (
                diff_stats, find_changed_functions,
                build_unified_diff, strip_comments_from_lines,
            )

            # ── Phase 1: 폴더 스캔 + 파일 읽기 ────────────────
            file_pairs = self._scan_folder_pairs()
            if self._cancel_req:
                self.cancelled.emit(); return
            if not file_pairs:
                self.done.emit({
                    "file_pairs": [], "old_parts": [], "new_parts": [],
                    "diff_parts": [], "output_lines": [],
                    "changed_files": 0, "total_func_count": 0,
                })
                return

            # ── Phase 2: 파일별 변경점 분석 ──────────────────
            old_parts, new_parts, diff_parts, output_lines = [], [], [], []
            changed_files = 0
            total_func_count = 0
            per_file_func_counts: dict = {}
            changed_funcs_acc: list = []   # 매핑 다이얼로그용
            total = len(file_pairs)

            for idx, (rel_path, old_lines, new_lines) in enumerate(file_pairs, 1):
                if self._cancel_req:
                    self.cancelled.emit(); return
                self.progress.emit("build", idx, total, rel_path)

                if self.ignore_comments:
                    old_lines = [l for l in strip_comments_from_lines(old_lines) if l.strip()]
                    new_lines = [l for l in strip_comments_from_lines(new_lines) if l.strip()]
                    file_pairs[idx-1] = (rel_path, old_lines, new_lines)

                n_add, n_del, n_mod = diff_stats(old_lines, new_lines)
                if n_add == 0 and n_del == 0 and n_mod == 0:
                    continue

                changed_files += 1
                sep = f"// ── {rel_path} ──"
                old_parts.append(sep); old_parts.extend(old_lines)
                new_parts.append(sep); new_parts.extend(new_lines)
                diff_parts.append(
                    build_unified_diff(old_lines, new_lines, rel_path, rel_path))

                changed = find_changed_functions(
                    "\n".join(old_lines), "\n".join(new_lines))
                fn_count = sum(1 for cf in changed if cf.name != "__global__")
                total_func_count += fn_count
                per_file_func_counts[rel_path] = fn_count
                # 매핑 다이얼로그용 (파일명, 함수명) 누적
                for cf in changed:
                    changed_funcs_acc.append({
                        "file":     rel_path,
                        "function": cf.name,
                    })
                if changed:
                    output_lines.append(f"── {rel_path} ──")
                    for cf in changed:
                        output_lines.append("")
                        for line in cf.diff_lines:
                            output_lines.append(line)
                    output_lines.append("=" * 60)

            self.done.emit({
                "file_pairs":            file_pairs,
                "old_parts":             old_parts,
                "new_parts":             new_parts,
                "diff_parts":            diff_parts,
                "output_lines":          output_lines,
                "changed_files":         changed_files,
                "total_func_count":      total_func_count,
                "per_file_func_counts":  per_file_func_counts,
                "changed_funcs":         changed_funcs_acc,
            })

        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")

    # ── 폴더 스캔 (진행률 emit 포함) ─────────────────────────

    def _scan_folder_pairs(self) -> list:
        def scan(folder):
            found = {}
            for root, dirs, files in os.walk(folder):
                dirs.sort()
                for fname in sorted(files):
                    if fname.lower().endswith(self._EXTS):
                        full = os.path.join(root, fname)
                        rel  = os.path.relpath(full, folder)
                        found[rel] = full
            return found

        def read_lines(path):
            return read_text_lines(path)

        self.progress.emit("scan", 0, 0, "폴더 스캔 중...")
        old_map = scan(self.old_folder)
        if self._cancel_req: return []
        new_map = scan(self.new_folder)
        if self._cancel_req: return []
        all_rel = sorted(set(old_map) | set(new_map))

        pairs = []
        total = len(all_rel)
        for i, rel in enumerate(all_rel, 1):
            if self._cancel_req:
                return pairs  # 부분 결과라도 반환 — run() 에서 cancelled 처리
            self.progress.emit("scan", i, total, rel)
            old_ls = read_lines(old_map[rel]) if rel in old_map else []
            new_ls = read_lines(new_map[rel]) if rel in new_map else []
            pairs.append((rel, old_ls, new_ls))
        return pairs


# ══════════════════════════════════════════════════════════════
#  ReqDiffWorker — 요구사항 파일 2개 비교 (Before / After)
# ══════════════════════════════════════════════════════════════
class ReqDiffWorker(QObject):
    """요구사항 파일(docx / txt / md) 두 개를 비교해 변경점 텍스트를 추출한다.

    Signals
    -------
    done(result: str)
        추출 완료. 변경점 텍스트 또는 "변경 없음".
    error(msg: str)
        예외 발생 시 메시지.
    """
    done  = pyqtSignal(str, list, list)  # (diff_text, old_lines, new_lines)
    error = pyqtSignal(str)

    def __init__(self, old_path: str, new_path: str):
        super().__init__()
        self.old_path = old_path
        self.new_path = new_path

    def run(self):
        try:
            old_lines = self._read_file(self.old_path)
            new_lines = self._read_file(self.new_path)

            opcodes = difflib.SequenceMatcher(
                None, old_lines, new_lines, autojunk=False
            ).get_opcodes()

            removed, added = [], []
            for op, a0, a1, b0, b1 in opcodes:
                if op in ("replace", "delete"):
                    removed.extend(old_lines[a0:a1])
                if op in ("replace", "insert"):
                    added.extend(new_lines[b0:b1])

            if not removed and not added:
                self.done.emit("변경 없음", old_lines, new_lines)
                return

            parts = ["=== 요구사항 변경점 ===", ""]
            if removed:
                parts.append("【수정 전 / 삭제된 항목】")
                for line in removed:
                    parts.append(f"  - {line}")
                parts.append("")
            if added:
                parts.append("【수정 후 / 추가된 항목】")
                for line in added:
                    parts.append(f"  + {line}")
                parts.append("")
            parts.append(
                f"--- 총 {len(removed)}줄 삭제/변경 전, {len(added)}줄 추가/변경 후 ---"
            )
            self.done.emit("\n".join(parts), old_lines, new_lines)

        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")

    def _read_file(self, path: str) -> list:
        return read_doc_lines(path)
