"""swe_review_controller.py — ② SWE.1 SRS / ③ SWE.2 SAD / ④ SWE.3 SDD 페이지
의 새 워크플로우 (3단계, 2026-06) 컨트롤러.

담당 시그널:
  · change_load_card.load_clicked          → 사양변경 트래커 fetch
  · aspice_checklist.ai_run_clicked        → ChecklistAiWorker 실행
  · change_match_card.upload_clicked       → 매칭 결과 + 체크리스트 CB 업로드
  · (SwePage.diff_requested 는 기존 흐름 — 별도 컨트롤러)

페이지 1개 인스턴스로 ②③④ 모두 처리 (page_key 분기).
"""

import os
import tempfile

from PyQt6.QtCore import QObject, QThread
from PyQt6.QtWidgets import QMessageBox

from integrations.codebeamer import CbFetcher, load_config


class SweReviewController(QObject):
    """SwePage (SRS/SAD/SDD) 의 새 워크플로우 연결.

    Args:
      mw         : MainWindow 인스턴스 (status bar / 다이얼로그 부모용)
      page_key   : 'srs' / 'sad' / 'sdd'
      page       : 해당 SwePage 인스턴스
    """

    def __init__(self, mw, page_key: str, page):
        super().__init__()
        self._mw       = mw
        self._page_key = page_key
        self._page     = page
        # 워커 핸들
        self._fetch_thread = None
        self._fetch_worker = None
        self._ai_thread    = None
        self._ai_worker    = None
        self._upload_thread = None
        self._upload_worker = None
        self._diff_thread  = None
        self._diff_worker  = None

        self._wire()

    # ── 시그널 연결 ──────────────────────────────────────────
    def _wire(self):
        try:
            self._page.change_load_card.load_clicked.connect(self.on_load_changes)
        except Exception:
            pass
        try:
            self._page.aspice_checklist.ai_run_clicked.connect(self.on_ai_run)
        except Exception:
            pass
        # OUTPUT > '🔗 변경점 매칭 결과' 카드의 [📤] — 매칭 결과만 업로드
        try:
            self._page.change_match_card.upload_clicked.connect(self.on_upload_mappings)
        except Exception:
            pass
        # OUTPUT > '🤖 체크리스트 AI 분석 결과' 카드의 [📤] — 체크리스트만 업로드
        try:
            self._page.ai_result_panel.upload_all_requested.connect(self.on_upload_checklist)
            # 항상 활성 — 업로드 시점에 체크리스트 로드 여부 검증
            self._page.ai_result_panel.set_upload_enabled(True)
        except Exception:
            pass
        # 페이지 헤더 [📤 CB 업로드] — 매칭 + 체크리스트 같이 업로드
        try:
            self._page.upload_clicked.connect(self.on_upload_all)
        except Exception:
            pass
        # SAD/SDD 만 — SRS 는 main.py 에서 별도 라우팅 (extras_proxy 경유)
        if self._page_key in ("sad", "sdd"):
            try:
                self._page.diff_requested.connect(self.on_diff_requested)
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────
    #  변경 전/후 문서 DIFF 추출 (SAD/SDD 전용)
    #  SRS 는 기존 _result.req_diff_requested → diff_controller.on_req_diff
    #  경로 사용 (extras_proxy 가 SRS 페이지에만 묶여있어 분리).
    # ──────────────────────────────────────────────────────────
    def on_diff_requested(self):
        """SwePage 의 [📋 DIFF 추출] 버튼 → ReqDiffWorker 실행."""
        import sys
        from workers.diff_worker import ReqDiffWorker

        page = self._page
        old_path = page.get_old_path()
        new_path = page.get_new_path()
        print(f"[DIFF DEBUG] {self._page_key} 추출 시작 — old={old_path!r} new={new_path!r}",
              file=sys.stderr)
        if not old_path or not new_path:
            self._mw._sb.showMessage(
                "⚠  변경 전/후 파일을 모두 선택해주세요.")
            return
        # 동시 실행 방지 — 이전 워커가 살아있으면 중복 실행 막음 (스레드 충돌 방지)
        if self._diff_thread is not None and self._diff_thread.isRunning():
            self._mw._sb.showMessage(
                f"⏳  {self._page_key.upper()} 이전 DIFF 추출이 아직 진행 중입니다.")
            return
        page.set_running(True)
        self._mw._sb.showMessage(
            f"📋  {self._page_key.upper()} 변경점 추출 중...")

        self._diff_thread = QThread()
        self._diff_worker = ReqDiffWorker(old_path, new_path)
        self._diff_worker.moveToThread(self._diff_thread)
        self._diff_thread.started.connect(self._diff_worker.run)
        self._diff_worker.done.connect(self._on_diff_done)
        self._diff_worker.error.connect(self._on_diff_error)
        self._diff_worker.done.connect(self._diff_thread.quit)
        self._diff_worker.error.connect(self._diff_thread.quit)
        # 스레드 종료 시 워커/스레드 객체 deleteLater — gc 타이밍 충돌 방지
        self._diff_thread.finished.connect(self._diff_worker.deleteLater)
        self._diff_thread.finished.connect(self._diff_thread.deleteLater)
        self._diff_thread.start()

    def _on_diff_done(self, text: str, old_lines: list, new_lines: list):
        import sys
        page = self._page
        try:
            page.set_running(False)
        except Exception as e:
            print(f"[DIFF DEBUG] set_running 실패: {type(e).__name__}: {e}",
                  file=sys.stderr)
        n_old = len(old_lines or []); n_new = len(new_lines or [])
        print(f"[DIFF DEBUG] {self._page_key} 추출 완료 — old={n_old} new={n_new} "
              f"text={len(text or '')}자", file=sys.stderr)
        try:
            page.set_diff_text(text)
        except Exception as e:
            print(f"[DIFF DEBUG] set_diff_text 실패: {type(e).__name__}: {e}",
                  file=sys.stderr)
        # ★ 너무 큰 문서는 OUTPUT VIEW 렌더링이 Qt 를 죽일 수 있어 cap
        MAX_RENDER_LINES = 3000
        too_big = (n_old > MAX_RENDER_LINES or n_new > MAX_RENDER_LINES)
        if too_big:
            self._mw._sb.showMessage(
                f"ℹ️  {self._page_key.upper()} 문서가 큽니다 ({n_old}/{n_new}줄) — "
                f"OUTPUT VIEW 는 처음 {MAX_RENDER_LINES}줄만 렌더링.")
            old_lines = (old_lines or [])[:MAX_RENDER_LINES]
            new_lines = (new_lines or [])[:MAX_RENDER_LINES]
        try:
            page.render_diff(old_lines, new_lines)
        except Exception as e:
            print(f"[DIFF DEBUG] render_diff 실패: {type(e).__name__}: {e}",
                  file=sys.stderr)
            self._mw._sb.showMessage(
                f"⚠  {self._page_key.upper()} DIFF 렌더링 실패: "
                f"{type(e).__name__}: {e}")
            return
        if text == "변경 없음":
            self._mw._sb.showMessage(
                f"ℹ️  {self._page_key.upper()} 변경 없음")
        else:
            added   = text.count("\n  + ")
            removed = text.count("\n  - ")
            tail = "" if not too_big else " (대용량 — 일부만 렌더)"
            self._mw._sb.showMessage(
                f"✅  {self._page_key.upper()} DIFF 추출 완료 — "
                f"{added}줄 추가 / {removed}줄 삭제{tail}  "
                f"| OUTPUT 탭 → '변경점 VIEW' 에서 확인하세요.")

    def _on_diff_error(self, msg: str):
        import sys
        print(f"[DIFF DEBUG] {self._page_key} 추출 에러 — {msg}", file=sys.stderr)
        try:
            self._page.set_running(False)
        except Exception:
            pass
        self._mw._sb.showMessage(
            f"⚠  {self._page_key.upper()} DIFF 추출 실패: {msg}")
        QMessageBox.critical(
            self._mw, f"{self._page_key.upper()} DIFF 오류", msg)

    # ──────────────────────────────────────────────────────────
    #  변경점 불러오기 — 사양변경 트래커 fetch
    # ──────────────────────────────────────────────────────────
    def on_load_changes(self):
        """ChangePointLoadCard [📥 변경점 불러오기] — 사양변경 트래커 fetch."""
        mw = self._mw
        proj = getattr(mw, "_project_name", "") or ""
        ver  = getattr(mw, "_project_version", "") or ""
        if not proj or not ver:
            QMessageBox.information(
                mw, "프로젝트 정보 미설정",
                "프로그램 시작 시 표시되는 '프로젝트 정보' 다이얼로그에서\n"
                "프로젝트명/버전을 먼저 입력해주세요.")
            return

        from core import project_state
        # 사양변경 트래커 ID 사용 (이 페이지의 트래커 아님 — 변경점은 ① 사양변경에서 옴)
        spec_tracker = project_state.get_tracker_id(proj, ver, "spec")
        if not spec_tracker:
            QMessageBox.information(
                mw, "① 사양변경 트래커 미설정",
                "변경점은 ① 사양변경 트래커에서 가져옵니다. 프로젝트 정보 "
                "다이얼로그에서 ① 트래커 ID 를 먼저 등록해주세요.")
            return

        cfg = load_config()
        url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                         cfg.get("password",""))
        if not (url and user and pw):
            QMessageBox.warning(
                mw, "Codebeamer 미설정",
                "먼저 사이드바 헤더의 🔌 버튼에서 CB URL/계정/PW 를 설정해주세요.")
            return

        if self._fetch_thread is not None:
            return   # 진행 중 중복 클릭 무시

        from workers.cb_items_worker import CbItemsWorker
        fetcher = CbFetcher(url, user, pw)
        worker = CbItemsWorker(fetcher, spec_tracker)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda msg: mw._sb.showMessage(msg))
        worker.done.connect(self._on_changes_loaded)
        worker.error.connect(self._on_changes_load_error)
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_fetch_thread)
        self._fetch_thread = thread
        self._fetch_worker = worker
        mw._sb.showMessage(
            f"📥  ① 사양변경 트래커 #{spec_tracker} 변경점 조회 중...")
        thread.start()

    def _on_changes_loaded(self, items: list):
        page = self._page
        try:
            page.change_load_card.apply_items(items or [])
            page.change_match_card.apply_items(items or [])
        except Exception as e:
            self._mw._sb.showMessage(f"⚠  결과 표시 실패: {e}")
            return
        self._mw._sb.showMessage(
            f"✅  변경점 {len(items or [])} 건 불러오기 완료 "
            f"— OUTPUT → '변경점 매칭 결과' 탭에서 요구사항 ID 를 입력하세요.")

    def _on_changes_load_error(self, msg: str):
        self._mw._sb.showMessage(f"❌  변경점 조회 실패: {msg[:160]}")
        QMessageBox.warning(
            self._mw, "변경점 조회 실패",
            f"사양변경 트래커 조회 중 오류:\n\n{msg[:400]}")

    def _cleanup_fetch_thread(self):
        try:
            self._fetch_worker.deleteLater() if self._fetch_worker else None
            self._fetch_thread.deleteLater() if self._fetch_thread else None
        except Exception:
            pass
        self._fetch_thread = None
        self._fetch_worker = None

    # ──────────────────────────────────────────────────────────
    #  AI 분석 실행 — 매칭된 No 만 Claude 호출
    # ──────────────────────────────────────────────────────────
    def on_ai_run(self):
        """AspiceChecklistCard [🤖 AI 분석 실행] — 변경된 요구사항 카테고리에
        매칭된 체크리스트 No 만 Claude 에 호출, 나머지는 자동 채움.
        """
        mw = self._mw
        page = self._page

        # 변경 없음 체크 시 — AI 실행 막고 안내
        if page.change_load_card.is_no_change():
            QMessageBox.information(
                mw, "변경 없음 처리",
                "현재 페이지가 '변경 없음' 으로 표시되어 있습니다.\n"
                "AI 분석은 변경 사항이 있을 때만 실행 가능합니다.")
            return

        # 체크리스트 로드 확인
        st = page.aspice_checklist.get_state()
        items = (st or {}).get("items") or []
        if not items:
            QMessageBox.information(
                mw, "체크리스트 미로드",
                "ASPICE 체크리스트 파일을 먼저 [📂 체크리스트 파일 로드] "
                "버튼으로 로드해주세요.")
            return

        # 변경된 요구사항 섹션 → 체크리스트 No 범위 매핑
        # (실제 변경점 매칭은 OUTPUT 의 변경점 매칭 카드에서 사용자가 입력 —
        # 그 결과를 활용해 어떤 카테고리가 영향받았는지 판단)
        mappings = page.change_match_card.get_mappings()
        # req_id prefix → 섹션 매핑 (req_id 의 태그로 카테고리 추정)
        affected_sections = _req_ids_to_sections(mappings)
        from core.checklist_parser import get_no_ranges_for_sections
        target_nos = get_no_ranges_for_sections(affected_sections)

        if not target_nos:
            # 매칭 진단 — 어떤 ID 가 입력됐는지 + 왜 인식 안 됐는지 안내
            all_req_ids = []
            for m in (mappings or []):
                all_req_ids.extend(m.get("req_ids") or [])
            if not all_req_ids:
                detail = "변경점 매칭 결과 탭에 요구사항 ID 가 입력되지 않았습니다."
            else:
                detail = (
                    f"입력된 요구사항 ID: {', '.join(all_req_ids[:10])}"
                    + (" ..." if len(all_req_ids) > 10 else "")
                    + "\n\n인식 가능한 prefix:\n"
                      "  · SwR_IF_*   → 2.3 Requirements (=HSI)\n"
                      "  · SwR_FR_*   → 3.1 Functional Requirement\n"
                      "  · SwR_NFR_*  → 3.2 Non-func Requirement\n"
                      "  · SwR_SFR_*  → 4.1 Safety Functional Req\n"
                      "  · SwR_SNFR_* → 4.2 Safety Non-Functional Req"
                )
            ret = QMessageBox.question(
                mw, "매칭 정보 인식 불가",
                f"{detail}\n\n전체 체크리스트를 AI 분석하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return
            target_nos = {it["no"] for it in items}

        items_to_analyze = [it for it in items if it["no"] in target_nos]
        other_items      = [it for it in items if it["no"] not in target_nos]

        # 컨텍스트 빌드 — 매칭 정보 + 요구사항 DIFF 텍스트 + 메타
        old_doc = (st.get("target_doc") or "")
        # 변경 전 버전 추출 (target_doc 의 '(vX.Y)' 패턴)
        import re as _re
        ver_m = _re.search(r"\(v?([\d.]+)\)", old_doc)
        old_ver = ver_m.group(1) if ver_m else ""

        context_md = _build_context_md(page, mappings)

        # AI 호출 — API key 는 환경변수/설정에서
        cfg = load_config()
        api_key = cfg.get("anthropic_api_key", "") or os.environ.get(
            "ANTHROPIC_API_KEY", "")

        if not api_key:
            QMessageBox.warning(
                mw, "API 키 없음",
                "ANTHROPIC_API_KEY 가 설정되지 않았습니다.\n"
                "환경변수 또는 설정에서 입력해주세요.")
            return

        if self._ai_thread is not None:
            return

        from workers.checklist_ai_worker import (
            ChecklistAiWorker, make_no_change_result,
        )

        # 분석 대상 아닌 항목 자동 채움 — done 시 results 에 병합
        self._other_no_change = [
            (it["no"], make_no_change_result(it["no"], old_ver))
            for it in other_items
        ]

        worker = ChecklistAiWorker(
            items_to_analyze=[
                {"no": it["no"], "content": it["content"]}
                for it in items_to_analyze
            ],
            context_md=context_md,
            old_version=f"v{old_ver}" if old_ver else "이전 버전",
            api_key=api_key,
        )
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda msg: mw._sb.showMessage(msg))
        worker.done.connect(self._on_ai_done)
        worker.error.connect(self._on_ai_error)
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_ai_thread)
        self._ai_thread = thread
        self._ai_worker = worker

        mw._sb.showMessage(
            f"🤖  AI 분석 실행 중 — 대상 {len(items_to_analyze)}개 / "
            f"자동 채움 {len(other_items)}개...")
        thread.start()

    def _on_ai_done(self, results_by_no: dict):
        page = self._page
        # AI 결과 + 자동 채움 결과 병합
        merged = dict(results_by_no or {})
        for no, res in (getattr(self, "_other_no_change", None) or []):
            if no not in merged:
                merged[no] = res
        try:
            page.aspice_checklist.apply_ai_results(merged)
            # OUTPUT 탭 > '🤖 체크리스트 AI 분석 결과' 패널에도 결과 표시
            self._populate_ai_result_panel(merged)
            # OUTPUT 탭 → AI 결과 탭으로 자동 전환
            page.switch_to_ai_result_tab()
        except Exception as e:
            self._mw._sb.showMessage(f"⚠  AI 결과 반영 실패: {e}")
            return
        self._mw._sb.showMessage(
            f"✅  AI 분석 완료 — 체크리스트 {len(merged)}개 항목 갱신")

    def _populate_ai_result_panel(self, merged: dict) -> None:
        """체크리스트 AI 결과 → OUTPUT > AI 결과 패널의 드롭다운 + 마크다운 채움.
        각 체크리스트 No 가 카드 하나, 본문은 content + judge + detail 마크다운.
        """
        page = self._page
        panel = getattr(page, "ai_result_panel", None)
        if panel is None:
            return
        # xlsx 의 items 에서 content 조회용 lookup
        st = page.aspice_checklist.get_state() or {}
        content_by_no = {}
        for it in (st.get("items") or []):
            if isinstance(it, dict):
                content_by_no[it.get("no")] = (it.get("content") or "").strip()

        # 카드 목록 — 정렬된 No 순
        sorted_nos = sorted(merged.keys(),
                            key=lambda n: (str(n), ))
        items_for_panel = []
        for no in sorted_nos:
            content = content_by_no.get(no, "")
            preview = content[:50] + ("..." if len(content) > 50 else "")
            items_for_panel.append({
                "id":   f"no_{no}",
                "name": f"No.{no} — {preview}" if preview else f"No.{no}",
            })
        try:
            panel.set_change_items(items_for_panel)
        except Exception:
            pass

        # 각 카드의 마크다운 본문 채움
        for no in sorted_nos:
            res = merged.get(no) or {}
            judge  = (res.get("judge") or "").strip()  or "—"
            detail = (res.get("detail") or "").strip() or "_(상세 없음)_"
            version = (res.get("version") or "").strip()
            content = content_by_no.get(no, "")
            md = (
                f"## No.{no} 체크리스트 결과\n\n"
                + (f"> **점검 항목**\n>\n> {content}\n\n" if content else "")
                + "| 항목 | 내용 |\n"
                + "|------|------|\n"
                + f"| 판단 | **{judge}** |\n"
                + f"| 적용 버전 | {version or '—'} |\n\n"
                + "### 상세\n\n"
                + detail
            )
            try:
                panel.set_result(f"no_{no}", md)
            except Exception:
                pass
        try:
            panel.set_progress(len(merged), len(merged))
        except Exception:
            pass

    def _on_ai_error(self, msg: str):
        self._mw._sb.showMessage(f"❌  AI 분석 실패: {msg[:160]}")
        QMessageBox.critical(
            self._mw, "AI 분석 실패",
            f"체크리스트 AI 분석 중 오류:\n\n{msg[:400]}")

    def _cleanup_ai_thread(self):
        try:
            self._ai_worker.deleteLater() if self._ai_worker else None
            self._ai_thread.deleteLater() if self._ai_thread else None
        except Exception:
            pass
        self._ai_thread = None
        self._ai_worker = None

    # ──────────────────────────────────────────────────────────
    #  CB 업로드 — 매칭 결과 + 체크리스트 xlsx 첨부
    # ──────────────────────────────────────────────────────────
    # ── 공통 전제조건 검증 + 워커 인프라 ─────────────────────
    def _upload_preflight(self) -> "tuple | None":
        """업로드 3종 공통 — proj/ver/tracker/CB 자격 검증.
        성공 시 (proj, ver, tracker_id, fetcher) 반환, 실패 시 None.
        """
        mw = self._mw
        proj = getattr(mw, "_project_name", "") or ""
        ver  = getattr(mw, "_project_version", "") or ""
        if not proj or not ver:
            QMessageBox.information(
                mw, "프로젝트 정보 미설정",
                "프로그램 시작 시 표시되는 '프로젝트 정보' 다이얼로그에서\n"
                "프로젝트명/버전을 먼저 입력해주세요.")
            return None
        from core import project_state
        tracker_id = project_state.get_tracker_id(proj, ver, self._page_key)
        if not tracker_id:
            QMessageBox.information(
                mw, f"{self._page_key.upper()} 트래커 미설정",
                f"이 페이지의 트래커 ID 가 비어있습니다.\n"
                f"프로젝트 정보 다이얼로그에서 등록해주세요.")
            return None
        cfg = load_config()
        url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                         cfg.get("password",""))
        if not (url and user and pw):
            QMessageBox.warning(
                self._mw, "Codebeamer 미설정",
                "먼저 사이드바 헤더의 🔌 버튼에서 CB URL/계정/PW 를 설정해주세요.")
            return None
        return (proj, ver, tracker_id, CbFetcher(url, user, pw))

    def _build_mapping_items(self, mappings: list) -> list:
        """요구사항 ID 별 변경 매칭 → bulk_items 리스트 (체크리스트 미포함)."""
        page = self._page
        all_maps = mappings or []
        diff_groups = {}
        try:
            diff_groups = page.change_match_card._diff_groups
        except Exception:
            pass
        # 매칭 인덱스 (req_id → change_id)
        req_to_change: dict = {}
        for m in all_maps:
            cid = str(m.get("change_id") or "").strip()
            for rid in (m.get("req_ids") or []):
                rid = str(rid).strip()
                if rid and cid and rid not in req_to_change:
                    req_to_change[rid] = cid
        bulk_items = []
        for i, rid in enumerate(sorted(diff_groups.keys()), start=1):
            grp = diff_groups[rid]
            mark = grp.get("type") or ""
            title = f"{mark} {rid}".strip()
            parent = req_to_change.get(rid, "")
            body_md = _build_per_req_body_md(rid, grp, parent)
            bulk_items.append({
                "idx":            i,
                "title":          title,
                "summary":        title,
                "body_md":        body_md,
                "attachments":    [],
                "parent_item_id": parent,
                "_req_id":        rid,
            })
        return bulk_items

    def _build_checklist_item(self, proj: str, ver: str,
                              mappings: list, st: dict,
                              start_idx: int) -> "dict | None":
        """ASPICE 체크리스트 xlsx 첨부 — bulk_items 1개 dict 반환.
        st 가 없거나 source_path 누락이면 None.
        """
        if not st or not (st.get("source_path") or "").strip():
            return None
        from core.checklist_parser import save_checklist
        tmp_path = os.path.join(
            tempfile.gettempdir(),
            f"aspice_checklist_{self._page_key}_{proj}_{ver}.xlsx")
        try:
            saved = save_checklist(st, tmp_path)
        except Exception as e:
            QMessageBox.critical(
                self._mw, "체크리스트 저장 실패",
                f"체크리스트 xlsx 갱신 중 오류:\n\n{e}")
            return None
        checklist_title = (f"[{self._page_key.upper()}] 체크리스트 검토 결과 "
                           f"({proj} v{ver})")
        return {
            "idx":            start_idx,
            "title":          checklist_title,
            "summary":        checklist_title,
            "body_md":        _build_upload_body_md(self._page, mappings or [], st),
            "attachments":    [saved],
            "parent_item_id": "",
            "_req_id":        "",
        }

    def _start_bulk_upload(self, fetcher, tracker_id: str,
                           proj: str, bulk_items: list, label: str) -> None:
        """공용 — CbBulkUploadWorker 띄우고 시그널 연결."""
        if self._upload_thread is not None:
            return
        if not bulk_items:
            self._mw._sb.showMessage(f"ℹ️  업로드할 항목이 없습니다.")
            return
        self._last_bulk_items = list(bulk_items)
        from workers.cb_bulk_upload_worker import CbBulkUploadWorker
        self._upload_thread = QThread()
        self._upload_worker = CbBulkUploadWorker(
            fetcher, tracker_id, bulk_items,
            project_name=proj,
            attach_md=False, attach_html=False,
            parent_item_id="",
            main_is_hzt=False,
        )
        self._upload_worker.moveToThread(self._upload_thread)
        self._upload_thread.started.connect(self._upload_worker.run)
        self._upload_worker.progress.connect(
            lambda msg: self._mw._sb.showMessage(msg))
        self._upload_worker.done.connect(self._on_bulk_upload_done)
        self._upload_worker.error.connect(self._on_upload_error)
        self._upload_worker.done.connect(self._upload_thread.quit)
        self._upload_worker.error.connect(self._upload_thread.quit)
        self._mw._sb.showMessage(
            f"📤  [{self._page_key.upper()}] {label} 업로드 시작...")
        self._upload_thread.start()

    # ── ① 매칭 결과만 업로드 (변경점 매칭 결과 탭의 [📤]) ────
    def on_upload_mappings(self, mappings: list):
        """OUTPUT > 변경점 매칭 결과 탭의 [📤] — 매칭 결과(req_id 이슈 N개) 만 업로드.
        체크리스트는 같이 안 올림.
        """
        ctx = self._upload_preflight()
        if ctx is None:
            return
        proj, ver, tracker_id, fetcher = ctx
        bulk_items = self._build_mapping_items(mappings)
        if not bulk_items:
            QMessageBox.information(
                self._mw, "매칭 결과 없음",
                "업로드할 요구사항 ID 매칭 결과가 없습니다.\n"
                "DIFF 추출 + 매칭 ID 입력 후 다시 시도해주세요.")
            return
        self._start_bulk_upload(
            fetcher, tracker_id, proj, bulk_items,
            label=f"매칭 {len(bulk_items)}개")

    # ── ② 체크리스트만 업로드 (체크리스트 AI 분석 결과 탭의 [📤]) ──
    def on_upload_checklist(self):
        """OUTPUT > 체크리스트 AI 분석 결과 탭의 [📤] — 체크리스트 1개 이슈만 업로드.
        매칭 결과는 안 올림.
        """
        ctx = self._upload_preflight()
        if ctx is None:
            return
        proj, ver, tracker_id, fetcher = ctx
        page = self._page
        st = page.aspice_checklist.get_state()
        if not st or not (st.get("source_path") or "").strip():
            QMessageBox.warning(
                self._mw, "체크리스트 미로드",
                "ASPICE 체크리스트 파일을 먼저 [📂 체크리스트 파일 로드] 후 "
                "AI 분석을 실행하거나 수동 편집 후 업로드해주세요.")
            return
        # 매핑은 첨부 안 함 — 빈 리스트
        item = self._build_checklist_item(proj, ver, [], st, start_idx=1)
        if item is None:
            return
        self._start_bulk_upload(
            fetcher, tracker_id, proj, [item],
            label="체크리스트 1개")

    # ── ③ 헤더 [📤 CB 업로드] — 매칭 + 체크리스트 같이 ─────
    def on_upload_all(self, mappings: "list | None" = None):
        """페이지 헤더의 [📤 CB 업로드] — 매칭 결과 + 체크리스트 동시 업로드."""
        ctx = self._upload_preflight()
        if ctx is None:
            return
        proj, ver, tracker_id, fetcher = ctx
        page = self._page
        # mappings 인자가 None 이면 페이지에서 직접 수집
        if mappings is None:
            try:
                mappings = page.change_match_card.get_mappings() or []
            except Exception:
                mappings = []
        bulk_items = self._build_mapping_items(mappings)
        # 체크리스트 결과 — AI 분석 실행됐을 때만 추가
        st = page.aspice_checklist.get_state()
        items_for_check = (st or {}).get("items") or []
        analyzed = any(
            ((it.get("judge") or "").strip()
             or (it.get("detail") or "").strip())
            for it in items_for_check
            if isinstance(it, dict)
        )
        if analyzed:
            item = self._build_checklist_item(
                proj, ver, mappings or [], st, start_idx=len(bulk_items) + 1)
            if item is not None:
                bulk_items.append(item)
        n_map = sum(1 for b in bulk_items if (b.get("_req_id") or ""))
        n_chk = len(bulk_items) - n_map
        self._start_bulk_upload(
            fetcher, tracker_id, proj, bulk_items,
            label=f"매칭 {n_map}개 + 체크리스트 {n_chk}개")

    # ── 레거시 호환 — 외부에서 on_upload() 그대로 호출하던 코드 ─
    def on_upload(self, mappings: list):
        self.on_upload_all(mappings)

    def _on_bulk_upload_done(self, info: dict):
        results  = info.get("results", []) or []
        failures = info.get("failures", []) or []
        n_ok, n_fail = len(results), len(failures)

        # 결과 → project_state 의 upload_results[page_key] 에 저장
        # · by_req_id    : 요구사항 ID → 등록된 이슈 ID
        # · by_change_id : 사양변경 ID → [등록된 요구사항 이슈 ID, ...] (parent 로 매칭된 것)
        # · checklist    : 체크리스트 결과 이슈 ID (req_id 없는 마지막 항목)
        try:
            from core import project_state
            mw = self._mw
            proj = getattr(mw, "_project_name", "") or ""
            ver  = getattr(mw, "_project_version", "") or ""
            if proj and ver:
                # idx → bulk_item dict (자체 키 _req_id 조회용)
                idx_to_item = {}
                for it in (self._last_bulk_items or []):
                    idx_to_item[int(it.get("idx") or 0)] = it
                by_req: dict = {}
                by_change: dict = {}
                checklist_id = ""
                for r in results:
                    iid    = str(r.get("item_id") or "").strip()
                    parent = str(r.get("parent_item_id") or "").strip()
                    src    = idx_to_item.get(int(r.get("idx") or 0)) or {}
                    rid    = str(src.get("_req_id") or "").strip()
                    if rid and iid:
                        by_req[rid] = iid
                        if parent:
                            by_change.setdefault(parent, []).append(iid)
                    elif iid and not rid and not parent:
                        # 체크리스트 결과 (req_id 없음 + parent 없음)
                        checklist_id = iid

                st = project_state.load_state(proj, ver) or {}
                ur = st.get("upload_results") or {}
                if not isinstance(ur, dict):
                    ur = {}
                page_data = ur.get(self._page_key) or {}
                if not isinstance(page_data, dict):
                    page_data = {}
                page_data["by_req_id"]    = by_req
                page_data["by_change_id"] = by_change
                if checklist_id:
                    page_data["checklist"] = checklist_id
                ur[self._page_key] = page_data
                st["upload_results"] = ur
                project_state.save_state(proj, ver, st)
        except Exception as e:
            self._mw._sb.showMessage(
                f"⚠  업로드 결과 저장 실패: {str(e)[:120]}")

        if n_fail == 0:
            self._mw._sb.showMessage(
                f"✅  매칭 {n_ok}개 모두 등록 완료")
        else:
            self._mw._sb.showMessage(
                f"⚠  매칭 등록 — 성공 {n_ok} / 실패 {n_fail}")
        from view.ui_dialog import SuccessDialog, ErrorDialog
        from PyQt6.QtWidgets import QDialog
        import webbrowser
        if n_fail == 0 and results:
            primary_url = results[0]["url"]
            dlg = SuccessDialog(
                self._mw,
                title=f"[{self._page_key.upper()}] 매칭 일괄 등록 완료",
                headline=f"{n_ok}개 이슈가 각 변경점의 하위로 등록되었습니다.",
                link_url=primary_url,
                primary_label="열기", secondary_label="닫기",
            )
            if dlg.exec() == QDialog.DialogCode.Accepted:
                try:
                    webbrowser.open(primary_url)
                except Exception:
                    pass
        else:
            lines = []
            for r in results:
                lines.append(f"  ✓ {r.get('title', '')} → {r.get('url', '')}")
            for f in failures:
                lines.append(f"  ✗ {f.get('title', '')} — {str(f.get('error',''))[:120]}")
            ErrorDialog(
                self._mw,
                title="매칭 일괄 등록 결과",
                headline=f"{n_ok}개 성공 / {n_fail}개 실패",
                detail="\n".join(lines),
            ).exec()
        self._upload_thread = None
        self._upload_worker = None

    def _on_upload_done(self, info: dict):
        item_id = info.get("item_id", "")
        url     = info.get("url", "")
        self._mw._sb.showMessage(
            f"✅  CB 업로드 완료 — 새 이슈 #{item_id}")
        from view.ui_dialog import SuccessDialog
        import webbrowser
        from PyQt6.QtWidgets import QDialog
        dlg = SuccessDialog(
            self._mw,
            title=f"[{self._page_key.upper()}] CB 업로드 완료",
            headline=f"새 이슈 #{item_id} 가 생성되었습니다.\n"
                     f"ASPICE 체크리스트 xlsx 가 첨부되었습니다.",
            link_url=url,
            primary_label="브라우저에서 열기",
            secondary_label="닫기",
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and url:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        self._upload_thread = None
        self._upload_worker = None

    def _on_upload_error(self, msg: str):
        self._mw._sb.showMessage(f"❌  CB 업로드 실패: {msg[:160]}")
        from view.ui_dialog import ErrorDialog
        ErrorDialog(
            self._mw,
            title="CB 업로드 실패",
            headline="체크리스트 결과 업로드 중 오류가 발생했습니다.",
            detail=str(msg),
        ).exec()
        self._upload_thread = None
        self._upload_worker = None


# ══════════════════════════════════════════════════════════════
#  헬퍼
# ══════════════════════════════════════════════════════════════
def _req_ids_to_sections(mappings: list) -> set:
    """매핑된 요구사항 ID 들 → 영향받은 요구사항 섹션 (목차 번호) 집합.

    ID prefix (SwR_IF_ / SwR_FR_ / SwR_NFR_ / SwR_SFR_ / SwR_SNFR_) 로
    카테고리 추정:
      · SwR_IF_*   → '2.3 Requirements (=HSI)'
      · SwR_FR_*   → '3.1 Functional Requirement'
      · SwR_NFR_*  → '3.2 Non-func Requirement'
      · SwR_SFR_*  → '4.1 Safety Functional Req'
      · SwR_SNFR_* → '4.2 Safety Non-Functional Req'
    """
    import re as _re
    sections: set = set()
    for m in mappings or []:
        for rid in (m.get("req_ids") or []):
            rid_u = str(rid or "").strip().upper()
            if "_IF_" in rid_u or "_HSI_" in rid_u:
                sections.add("2.3 Requirements (=HSI)")
            elif "_FR_" in rid_u and "_NFR_" not in rid_u:
                sections.add("3.1 Functional Requirement")
            elif "_NFR_" in rid_u:
                sections.add("3.2 Non-func Requirement")
            elif "_SFR_" in rid_u or "_SAFETY_FR" in rid_u:
                sections.add("4.1 Safety Functional Req")
            elif "_SNFR_" in rid_u or "_SAFETY_NFR" in rid_u:
                sections.add("4.2 Safety Non-Functional Req")
    return sections


def _build_context_md(page, mappings: list) -> str:
    """AI 호출에 전달할 컨텍스트 마크다운 생성."""
    parts = []
    # 매칭 결과
    parts.append("## 변경점 ↔ 요구사항 ID 매칭")
    if mappings:
        for m in mappings:
            req_ids = ", ".join(m.get("req_ids") or []) or "(미매핑)"
            parts.append(
                f"- #{m.get('change_id')} {m.get('change_name')} → {req_ids}")
    else:
        parts.append("(매핑 정보 없음)")
    # 요구사항 DIFF (있으면)
    try:
        diff_text = page.change_match_card.get_req_diff()
    except Exception:
        diff_text = ""
    if diff_text.strip():
        parts.append("\n## 요구사항 DIFF (ID 별 정렬)")
        # 너무 길면 자름 — 토큰 절약
        parts.append(diff_text[:8000])
    return "\n\n".join(parts)


def _build_per_req_body_md(req_id: str, grp: dict, parent_change_id: str) -> str:
    """요구사항 ID 1개당 본문 — 변경 전/후 + 매칭된 사양변경 정보."""
    lines = []
    mark = (grp or {}).get("type") or ""
    lines.append(f"# {mark} {req_id}")
    lines.append("")
    if parent_change_id:
        lines.append(f"**매칭된 사양변경**: #{parent_change_id} (상위 항목)")
    else:
        lines.append("**매칭된 사양변경**: (없음)")
    lines.append("")
    before = (grp or {}).get("before") or ""
    after  = (grp or {}).get("after")  or ""
    if before:
        lines.append("## 변경 전")
        lines.append("```")
        lines.append(before)
        lines.append("```")
    if after:
        lines.append("## 변경 후")
        lines.append("```")
        lines.append(after)
        lines.append("```")
    return "\n".join(lines)


def _build_per_change_body_md(change_id: str, change_name: str,
                              req_ids: list, diff_groups: dict,
                              checklist_state: dict) -> str:
    """매핑 한 건당 본문 마크다운 — 변경점 정보 + 요구사항 ID 별 DIFF + 체크리스트 요약."""
    lines = []
    lines.append(f"# 변경점 #{change_id} — 요구사항 매칭 결과")
    lines.append("")
    if change_name:
        lines.append(f"**변경점 제목**: {change_name}")
    lines.append(f"**상위 변경점 트래커**: #{change_id}")
    lines.append(f"**매칭 요구사항**: {', '.join(req_ids) if req_ids else '(없음)'}")
    lines.append("")
    # 요구사항 ID 별 변경 전/후
    if req_ids and diff_groups:
        lines.append("## 요구사항별 변경 내용")
        lines.append("")
        for rid in req_ids:
            grp = diff_groups.get(rid)
            if not grp:
                lines.append(f"### {rid}")
                lines.append("(요구사항 DIFF 데이터 없음)")
                lines.append("")
                continue
            tp = grp.get("type") or ""
            lines.append(f"### {tp} {rid}")
            if grp.get("before"):
                lines.append("**[변경 전]**")
                lines.append("```")
                lines.append(grp["before"])
                lines.append("```")
            if grp.get("after"):
                lines.append("**[변경 후]**")
                lines.append("```")
                lines.append(grp["after"])
                lines.append("```")
            lines.append("")
    # 체크리스트 요약 (선택)
    items = (checklist_state or {}).get("items") or []
    if items:
        from collections import Counter
        counts = Counter(it.get("judge") or "(미판정)" for it in items)
        lines.append("## 체크리스트 판정 요약")
        lines.append("")
        for k in ("OK", "OK But", "NG", "N/A", "(미판정)"):
            if counts.get(k):
                lines.append(f"- {k}: {counts[k]}")
        lines.append("")
        lines.append("> 상세 결과는 첨부된 ASPICE 체크리스트 xlsx 를 참조하세요.")
    return "\n".join(lines)


def _build_upload_body_md(page, mappings: list, checklist_state: dict) -> str:
    """CB 업로드 본문 마크다운 — 매칭 결과 + 체크리스트 요약."""
    lines = []
    lines.append(f"# ASPICE 체크리스트 검토 결과")
    lines.append("")

    # 변경 없음 체크
    if page.change_load_card.is_no_change():
        cmt = page.change_load_card.get_no_change_comment()
        lines.append(f"> ℹ️ **변경 없음** — {cmt or '(코멘트 없음)'}")
        lines.append("")
        lines.append("이 페이지의 요구사항/아키텍처/상세설계는 본 PR 에서 "
                     "변경되지 않았습니다. ⑧⑨ 단계에서 N/A 처리.")
        return "\n".join(lines)

    # 매칭 결과 표
    lines.append("## 변경점 ↔ 요구사항 ID 매칭")
    lines.append("")
    if mappings:
        lines.append("| 변경점 | 요구사항 ID |")
        lines.append("|---|---|")
        for m in mappings:
            req_ids = ", ".join(m.get("req_ids") or []) or "-"
            lines.append(
                f"| #{m.get('change_id')} {m.get('change_name')} | {req_ids} |")
    else:
        lines.append("(매칭 정보 없음)")
    lines.append("")

    # 체크리스트 요약 — 판정 분포
    items = (checklist_state or {}).get("items") or []
    from collections import Counter
    counts = Counter(it.get("judge") or "(미판정)" for it in items)
    lines.append("## 체크리스트 판정 분포")
    lines.append("")
    lines.append("| 판정 | 건수 |")
    lines.append("|---|---|")
    for k in ("OK", "OK But", "NG", "N/A", "(미판정)"):
        if counts.get(k):
            lines.append(f"| {k} | {counts[k]} |")
    lines.append("")
    lines.append("> 상세 결과는 첨부된 ASPICE 체크리스트 xlsx 파일을 참조하세요.")
    return "\n".join(lines)
