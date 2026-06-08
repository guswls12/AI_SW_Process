"""diff_controller.py — DIFF 워커 라이프사이클 제어 (단일 파일 / 폴더 / 요구사항).

main.py 의 _on_diff, _on_req_diff*, _start_folder_diff_worker, _on_diff_*,
_build_folder_code_parts 를 한곳에 모은다.

MainWindow 는 본 컨트롤러를 보유하고 시그널만 연결한다 — 컨트롤러는
result_panel / input_panel / status_bar / 자기 자신을 부모 다이얼로그용으로
MainWindow 로부터 받아 사용한다.

공개 속성 (AI / Export 컨트롤러가 읽음):
  old_lines: list      — 마지막 DIFF 추출의 수정 전 라인 (병합본)
  new_lines: list      — 마지막 DIFF 추출의 수정 후 라인 (병합본)
  changed_text: str    — 변경점 요약 텍스트 (AI 분석에 전달)
"""

from PyQt6.QtCore import QThread, Qt
from PyQt6.QtWidgets import QMessageBox

from core.model import (
    diff_func_analysis, diff_stats, find_changed_functions,
    build_unified_diff, strip_comments_from_lines,
)
from workers.diff_worker import DiffWorker, ReqDiffWorker
from view.ui_dialog import DiffLoadingDialog


class DiffController:
    def __init__(self, main_window):
        self._mw = main_window

        # 공개 상태 — AI/Export 가 참조
        self.old_lines: list = []
        self.new_lines: list = []
        self.changed_text: str = ""
        # 매핑 다이얼로그용 변경 함수 정보 — DIFF 추출 시 같이 채워짐
        # 포맷: [{"file": "App_BMS.c", "function": "App_BMS_IC_Init"}, ...]
        # 단일/폴더 모드 모두 통일된 형태로 보유
        self.changed_funcs: list[dict] = []

        # 폴더 DIFF 워커 상태
        self._diff_thread = None
        self._diff_worker = None
        self._diff_dlg    = None
        self._diff_params: dict = {}

        # 요구사항 DIFF 워커 상태
        self._req_thread = None
        self._req_worker = None

    # ──────────────────────────────────────────────────────────
    #  ① DIFF 추출 진입점 — _input.diff_clicked 시그널 슬롯
    # ──────────────────────────────────────────────────────────
    def on_diff(self, params: dict):
        self._mw._result.clear()

        if params.get("mode") == "folder":
            # ── 폴더 모드: 백그라운드 워커 + 로딩 다이얼로그 ──
            self._start_folder_worker(params)
            return

        # ── 단일 파일 모드 ─────────────────────────────────
        old_lines = params["old_lines"]
        new_lines = params["new_lines"]

        self.old_lines = old_lines
        self.new_lines = new_lines

        single_fname    = params.get("single_filename", "")
        ignore_comments = params.get("ignore_comments", False)

        # ★ 함수 분석에 사용할 코드 — DIFF VIEW 트리와 AI 입력(changed_text) 이
        #   SAME 입력을 받도록 통일.
        #   ignore_comments=True 면 양쪽 모두 주석 제거된 코드 사용.
        #   (이전엔 DIFF VIEW 만 주석 제거 → AI 변경점 요약과 함수 목록 불일치 버그)
        if ignore_comments:
            old_for_analysis = strip_comments_from_lines(old_lines)
            new_for_analysis = strip_comments_from_lines(new_lines)
            func_list = diff_func_analysis(old_for_analysis, new_for_analysis)
            self._mw._result.render_diff(old_lines, new_lines, func_list,
                                         old_cmp=old_for_analysis,
                                         new_cmp=new_for_analysis,
                                         filename=single_fname)
        else:
            old_for_analysis = old_lines
            new_for_analysis = new_lines
            func_list = diff_func_analysis(old_for_analysis, new_for_analysis)
            self._mw._result.render_diff(old_lines, new_lines, func_list,
                                         filename=single_fname)

        # ★ 변경점 텍스트 보관 (UI 표시 X, AI 분석 입력용)
        #   diff_func_analysis 와 동일 입력 사용 → DIFF VIEW 와 AI 변경점 요약의
        #   함수 목록이 일치.
        changed = find_changed_functions(
            "\n".join(old_for_analysis), "\n".join(new_for_analysis))
        # 매핑 다이얼로그용 변경 함수 dict 리스트 (단일 파일 모드)
        self.changed_funcs = [
            {"file": single_fname or "(단일 파일)",
             "function": cf.name}
            for cf in changed
        ]
        func_count   = sum(1 for cf in changed if cf.name != "__global__")
        global_count = sum(1 for cf in changed if cf.name == "__global__")
        parts = []
        if global_count: parts.append("전역 영역 변경점 있음")
        if func_count:   parts.append(f"변경된 함수 {func_count}개")
        output_lines = [", ".join(parts) if parts else "변경 없음", "=" * 60]
        for cf in changed:
            output_lines.append("")
            for line in cf.diff_lines:
                output_lines.append(line)
            output_lines.append("")
            output_lines.append("=" * 60)
        self.changed_text = "\n".join(output_lines)

        n_add, n_del, n_mod = diff_stats(old_lines, new_lines)
        self._mw._sb.showMessage(
            f"🔀  DIFF 추출 완료  |  +{n_add} 추가  -{n_del} 삭제  ~{n_mod} 수정  "
            f"|  변경 함수 {len(func_list)}개  "
            f"— '🤖 AI 분석 실행' 버튼을 눌러 분석을 시작하세요.")

    # ──────────────────────────────────────────────────────────
    #  ② 요구사항 DIFF — _result.req_diff_requested 시그널 슬롯
    # ──────────────────────────────────────────────────────────
    def on_req_diff(self):
        ep = self._mw._result.extras_panel
        old_path = ep.get_req_old_path()
        new_path = ep.get_req_new_path()
        if not old_path or not new_path:
            self._mw._sb.showMessage("⚠  요구사항 수정 전/후 파일을 모두 선택해주세요.")
            return

        ep.set_req_diff_running(True)
        self._mw._sb.showMessage("📋  요구사항 변경점 추출 중...")

        self._req_thread = QThread()
        self._req_worker = ReqDiffWorker(old_path, new_path)
        self._req_worker.moveToThread(self._req_thread)
        self._req_thread.started.connect(self._req_worker.run)
        self._req_worker.done.connect(
            lambda text, old, new: self._on_req_done(text, old, new))
        self._req_worker.error.connect(self._on_req_error)
        self._req_worker.done.connect(self._req_thread.quit)
        self._req_worker.error.connect(self._req_thread.quit)
        self._req_thread.start()

    def _on_req_done(self, text: str, old_lines: list, new_lines: list):
        ep = self._mw._result.extras_panel
        ep.set_req_diff_running(False)
        ep.set_req_diff_text(text)
        self._mw._result.set_req_diff(old_lines, new_lines)
        if text == "변경 없음":
            self._mw._sb.showMessage("ℹ️  요구사항 변경 없음")
        else:
            added   = text.count("\n  + ")
            removed = text.count("\n  - ")
            self._mw._sb.showMessage(
                f"✅  요구사항 DIFF 추출 완료 — {added}줄 추가 / {removed}줄 삭제  "
                f"| '변경점VIEW' 탭 → '요구사항 변경점 VIEW'에서 확인하세요.")

    def _on_req_error(self, msg: str):
        self._mw._result.extras_panel.set_req_diff_running(False)
        self._mw._sb.showMessage(f"⚠  요구사항 DIFF 추출 실패: {msg}")
        QMessageBox.critical(self._mw, "요구사항 DIFF 오류", msg)

    # ──────────────────────────────────────────────────────────
    #  ③ 폴더 DIFF 워커 오케스트레이션
    # ──────────────────────────────────────────────────────────
    def _start_folder_worker(self, params: dict):
        """폴더 DIFF 추출을 백그라운드 스레드에서 실행하고 로딩 다이얼로그를 띄운다."""
        self._mw._sb.showMessage("📂  폴더 분석 준비 중...")
        self._mw._input.set_diff_running(True)

        # 로딩 다이얼로그
        self._diff_dlg = DiffLoadingDialog(self._mw)

        # 워커 스레드 구성
        self._diff_thread = QThread()
        self._diff_worker = DiffWorker(
            old_folder      = params["old_folder"],
            new_folder      = params["new_folder"],
            ignore_comments = params.get("ignore_comments", False),
        )
        self._diff_worker.moveToThread(self._diff_thread)

        # _on_done 에서 원본 params 를 활용하기 위해 보관
        self._diff_params = params

        # 시그널 연결
        self._diff_thread.started.connect(self._diff_worker.run)
        self._diff_worker.progress.connect(self._on_progress)
        self._diff_worker.done.connect(self._on_done)
        self._diff_worker.cancelled.connect(self._on_cancelled)
        self._diff_worker.error.connect(self._on_error)
        self._diff_worker.done.connect(self._diff_thread.quit)
        self._diff_worker.cancelled.connect(self._diff_thread.quit)
        self._diff_worker.error.connect(self._diff_thread.quit)
        # 다이얼로그 중단 버튼 → 워커 cancel
        # ★ DirectConnection: 워커의 run() 이 동기 실행 중이라 워커 스레드의
        #   이벤트 루프가 막혀있음. QueuedConnection 으로는 cancel() 슬롯이
        #   run() 종료 전에 절대 실행되지 않으므로, UI 스레드에서 직접 호출해
        #   _cancel_req 플래그를 즉시 set 한다 (bool 대입은 GIL 보호로 안전).
        self._diff_dlg.cancel_requested.connect(
            self._diff_worker.cancel,
            Qt.ConnectionType.DirectConnection,
        )

        self._diff_thread.start()
        self._diff_dlg.show()

    def _on_progress(self, phase: str, cur: int, total: int, name: str):
        if self._diff_dlg is not None:
            self._diff_dlg.update_progress(phase, cur, total, name)

    def _on_done(self, payload: dict):
        # 다이얼로그 닫기 + 버튼 복구
        if self._diff_dlg is not None:
            self._diff_dlg.accept()
            self._diff_dlg = None
        self._mw._input.set_diff_running(False)

        params = self._diff_params
        file_pairs       = payload["file_pairs"]
        old_parts        = payload["old_parts"]
        new_parts        = payload["new_parts"]
        diff_parts       = payload["diff_parts"]
        output_lines     = payload["output_lines"]
        changed_files         = payload["changed_files"]
        total_func_count      = payload["total_func_count"]
        per_file_func_counts  = payload.get("per_file_func_counts", {})

        if not file_pairs:
            self._mw._sb.showMessage("⚠  소스 파일을 찾을 수 없습니다.")
            return

        # UI 렌더링 (메인 스레드)
        self._mw._result.render_folder(file_pairs, per_file_func_counts)

        # params 업데이트 — AI 버튼 클릭 시 사용
        params["file_pairs"] = file_pairs
        params["old_code"]   = "\n".join(old_parts)
        params["new_code"]   = "\n".join(new_parts)
        params["diff_code"]  = "\n".join(diff_parts)
        self.changed_text    = "\n".join(output_lines) if output_lines else "변경 없음"
        self.old_lines       = old_parts
        self.new_lines       = new_parts
        # 매핑 다이얼로그용 변경 함수 dict 리스트 (폴더 모드)
        self.changed_funcs   = payload.get("changed_funcs", []) or []

        # view 쪽 _last_params 에도 file_pairs 주입 (AI 실행 시 필요)
        self._mw._input.set_folder_pairs(file_pairs)
        self._mw._input.enable_ai()

        self._mw._sb.showMessage(
            f"🔀  DIFF 추출 완료  |  전체 {len(file_pairs)}개 파일  "
            f"|  변경 {changed_files}개 파일  |  변경 함수 {total_func_count}개  "
            f"— 파일을 클릭해 상세 DIFF를 확인하세요.")

    def _on_error(self, msg: str):
        if self._diff_dlg is not None:
            self._diff_dlg.accept()
            self._diff_dlg = None
        self._mw._input.set_diff_running(False)
        self._mw._sb.showMessage(f"⚠  DIFF 추출 실패: {msg}")
        QMessageBox.critical(self._mw, "DIFF 추출 오류", msg)

    def _on_cancelled(self):
        """사용자가 중단 버튼을 눌러 워커가 정상 종료된 경우."""
        if self._diff_dlg is not None:
            self._diff_dlg.accept()
            self._diff_dlg = None
        self._mw._input.set_diff_running(False)
        # 결과 뷰는 이미 on_diff 시작 시 clear() 된 상태라 그대로 둠
        self._mw._sb.showMessage("⚠  DIFF 추출이 사용자 요청으로 중단되었습니다.")

    # ──────────────────────────────────────────────────────────
    #  ④ 폴더 모드 코드 파트 조립 헬퍼 (AI 컨트롤러도 호출)
    # ──────────────────────────────────────────────────────────
    def build_folder_code_parts(
        self,
        file_pairs: list,
        skip_unchanged: bool = False,
        ignore_comments: bool = False,
    ) -> tuple:
        """폴더 모드에서 파일 목록을 받아 AI/DIFF 용 코드 파트를 조립한다.

        Returns:
            (old_parts, new_parts, diff_parts, output_lines, changed_files, total_func_count)
        """
        old_parts, new_parts, diff_parts, output_lines = [], [], [], []
        changed_files = 0
        total_func_count = 0

        for rel_path, old_lines, new_lines in file_pairs:
            if ignore_comments:
                old_lines = strip_comments_from_lines(old_lines)
                new_lines = strip_comments_from_lines(new_lines)
            if skip_unchanged:
                n_add, n_del, n_mod = diff_stats(old_lines, new_lines)
                if n_add == 0 and n_del == 0 and n_mod == 0:
                    continue
            changed_files += 1
            sep = f"// ── {rel_path} ──"
            old_parts.append(sep); old_parts.extend(old_lines)
            new_parts.append(sep); new_parts.extend(new_lines)
            diff_parts.append(build_unified_diff(old_lines, new_lines, rel_path, rel_path))
            changed = find_changed_functions(
                "\n".join(old_lines), "\n".join(new_lines))
            fn_count = sum(1 for cf in changed if cf.name != "__global__")
            total_func_count += fn_count
            if changed:
                output_lines.append(f"── {rel_path} ──")
                for cf in changed:
                    output_lines.append("")
                    for line in cf.diff_lines:
                        output_lines.append(line)
                output_lines.append("=" * 60)

        return old_parts, new_parts, diff_parts, output_lines, changed_files, total_func_count
