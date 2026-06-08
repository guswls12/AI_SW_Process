"""srs_review_v2_controller.py — SRS 검토 워크플로우 컨트롤러.

2026-06-04 재설계된 흐름 전용 (구 12항목 체크리스트 검증 컨트롤러는 제거됨):

  ── 흐름 (사진 5단계) ─────────────────────────────────────
  1. Tab2 [📥 변경점 목록 불러오기]    → CbFetcher → CbHistoricalSubTab.change_list 렌더
  2. Tab2 [📥 과거차 목록 불러오기]    → CbFetcher → historical_list 렌더
  3. Tab3 체크리스트/검토/회의록 작성 → (이 컨트롤러 외부)
  4. Tab3 [🤖 AI 인사이트 실행]      → (Phase 3-3 — 추가 예정, 현재는 placeholder)

Phase 3-1 범위 (이번 단계):
  - fetch 흐름 2개만 동작 (변경점 / 과거차)
  - AI 실행은 Phase 3-2/3-3 에서 워커 + 결과 라우팅 추가
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QInputDialog, QDialog

from integrations.codebeamer import (
    CbFetcher, load_config, save_config, parse_tracker_id_from_url,
)
from integrations.codebeamer.dialogs import _FetchSelectDialog
from workers.srs_review_v2_worker import SrsReviewV2Worker
from workers.cb_upload_worker import CbUploadWorker


# ══════════════════════════════════════════════════════════════
#  _FetchWorker — CB 트래커 항목 목록 fetch (QThread 백그라운드)
# ══════════════════════════════════════════════════════════════
class _FetchWorker(QObject):
    """단일 트래커의 변경점 목록을 fetch — 변경점/과거차 양쪽에 동일 사용."""
    progress = pyqtSignal(str)
    done     = pyqtSignal(list)   # 결과 items 리스트
    error    = pyqtSignal(str)

    def __init__(self, fetcher: CbFetcher, tracker_id: str):
        super().__init__()
        self.fetcher    = fetcher
        self.tracker_id = str(tracker_id or "").strip()

    def run(self):
        try:
            self.progress.emit("🔐  CB 로그인 확인 중...")
            self.fetcher._get_session()
            self.progress.emit(
                f"📥  트래커 #{self.tracker_id} 항목 조회 중...")
            items = self.fetcher.fetch_tracker_items(self.tracker_id)
            self.done.emit(items or [])
        except Exception as e:
            self.error.emit(str(e))


class _MultiFetchWorker(QObject):
    """여러 트래커의 항목을 순차로 fetch 해서 한 리스트로 합쳐 반환.

    과거차 fetch 에 사용 — cb_config.json 의 section_past 에 등록된 트래커
    중 사용자가 선택한 N개를 모두 가져온다. 각 아이템 dict 에는 트래커
    구분용으로 `tracker_name` 키를 주입.
    """
    progress = pyqtSignal(str)
    done     = pyqtSignal(list)   # 합쳐진 items 리스트
    error    = pyqtSignal(str)

    def __init__(self, fetcher: CbFetcher, tracker_map: dict):
        super().__init__()
        self.fetcher     = fetcher
        # 빈/공백 ID 제외
        self.tracker_map = {
            str(n): str(tid).strip()
            for n, tid in (tracker_map or {}).items()
            if str(tid or "").strip()
        }

    def run(self):
        try:
            self.progress.emit("🔐  CB 로그인 확인 중...")
            self.fetcher._get_session()
            all_items: list = []
            total = len(self.tracker_map)
            for idx, (name, tid) in enumerate(self.tracker_map.items(), start=1):
                self.progress.emit(
                    f"📥  [{idx}/{total}] {name} (#{tid}) 항목 조회 중...")
                items = self.fetcher.fetch_tracker_items(tid) or []
                for it in items:
                    # 화면에서 어떤 트래커에서 온 항목인지 구분할 수 있도록 주입
                    if isinstance(it, dict):
                        it.setdefault("tracker_name", name)
                all_items.extend(items)
            self.done.emit(all_items)
        except Exception as e:
            self.error.emit(str(e))


# ══════════════════════════════════════════════════════════════
#  SrsReviewV2Controller — 새 SRS 검토 워크플로우 흐름 제어
# ══════════════════════════════════════════════════════════════
class SrsReviewV2Controller(QObject):
    """SrsPage 의 새 위젯 (CbHistoricalSubTab + ChecklistReviewSubTab) 와
    CB 연동 / AI 호출을 연결.

    Args:
        mw       : MainWindow 인스턴스 (status bar / 다이얼로그 부모용)
        srs_page : view.pages.page_swe.SrsPage 인스턴스
                   (cb_historical_tab / checklist_review_tab 속성 보유)
    """

    def __init__(self, mw, srs_page):
        super().__init__()
        self._mw       = mw
        self._srs_page = srs_page
        self._cb_tab   = getattr(srs_page, "cb_historical_tab", None)
        self._ck_tab   = getattr(srs_page, "checklist_review_tab", None)

        # fetch 스레드 라이프사이클 — 동시 실행 1개씩만 허용
        self._change_thread:     QThread | None     = None
        self._change_worker:     _FetchWorker | None = None
        self._historical_thread: QThread | None     = None
        self._historical_worker: _FetchWorker | None = None

        # AI 분석 — 변경점 N개 병렬 실행 (각각 QThread + SrsReviewV2Worker)
        self._ai_threads: list = []   # list of (QThread, SrsReviewV2Worker)
        self._ai_total:     int = 0
        self._ai_completed: int = 0

        # CB 업로드 — 순차 처리 (CB rate limit 고려)
        self._upload_queue: list = []   # 대기 항목 [(card_id, item, md), ...]
        self._upload_tracker_id: str = ""
        self._upload_thread:    QThread | None       = None
        self._upload_worker:    CbUploadWorker | None = None
        self._upload_success:   int = 0
        self._upload_failed:    int = 0
        self._upload_total:     int = 0

        self._wire_signals()

    # ── 시그널 와이어링 ─────────────────────────────────────
    def _wire_signals(self):
        if self._cb_tab is not None:
            self._cb_tab.change_fetch_requested.connect(
                self._on_change_fetch_requested)
            self._cb_tab.historical_fetch_requested.connect(
                self._on_historical_fetch_requested)
        if self._ck_tab is not None:
            self._ck_tab.ai_run_requested.connect(self._on_ai_run_requested)
            self._ck_tab.save_checklist_requested.connect(
                self._on_checklist_saved)
            self._ck_tab.edit_checklist_requested.connect(
                self._on_checklist_edited)
        out_panel = getattr(self._srs_page, "ai_result_panel", None)
        if out_panel is not None:
            out_panel.upload_all_requested.connect(self._on_upload_all_requested)

    # ── 유틸 — CbFetcher 인스턴스 ────────────────────────────
    def _make_fetcher(self) -> "CbFetcher | None":
        """cb_config.json 에서 자격증명 읽어 CbFetcher 생성. 미설정 시 None."""
        try:
            cfg = load_config() or {}
        except Exception:
            cfg = {}
        url  = (cfg.get("url")      or "").strip()
        user = (cfg.get("username") or "").strip()
        pw   = (cfg.get("password") or "").strip()
        if not (url and user and pw):
            self._warn(
                "Codebeamer 자격증명 미설정",
                "사이드바 헤더 🔌 버튼으로 Codebeamer URL/계정/비밀번호 를 "
                "먼저 설정해주세요.")
            return None
        return CbFetcher(url, user, pw)

    # ── 변경점 트래커 fetch ──────────────────────────────────
    def _on_change_fetch_requested(self, raw_id: str):
        tracker_id = parse_tracker_id_from_url(raw_id) or str(raw_id).strip()
        if not tracker_id:
            self._warn("트래커 ID 누락", "변경점 트래커 ID 또는 URL 을 입력해주세요.")
            return
        if self._change_thread is not None:
            return   # 진행 중 — 무시 (버튼 비활성으로 가드되긴 함)

        fetcher = self._make_fetcher()
        if fetcher is None:
            return

        self._cb_tab.set_change_fetch_running(True)
        self._sb(f"📥  변경점 트래커 #{tracker_id} fetch 시작...")

        worker = _FetchWorker(fetcher, tracker_id)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._sb)
        worker.done.connect(self._on_change_fetch_done)
        worker.error.connect(self._on_change_fetch_error)
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_change_thread)
        self._change_thread, self._change_worker = thread, worker
        thread.start()

    def _on_change_fetch_done(self, items: list):
        n = len(items)
        self._cb_tab.set_change_items(items)
        self._cb_tab.set_change_fetch_running(False)
        self._sb(f"✅  변경점 {n}개 불러옴")

    def _on_change_fetch_error(self, msg: str):
        self._cb_tab.set_change_items([])
        self._cb_tab.change_list.set_loading_text(f"❌  불러오기 실패: {msg[:80]}")
        self._cb_tab.set_change_fetch_running(False)
        self._sb(f"⚠  변경점 fetch 실패 — {msg[:120]}")

    def _cleanup_change_thread(self):
        if self._change_thread is not None:
            self._change_thread.deleteLater()
        if self._change_worker is not None:
            self._change_worker.deleteLater()
        self._change_thread = None
        self._change_worker = None

    # ── 과거차 트래커 fetch ──────────────────────────────────
    def _on_historical_fetch_requested(self):
        """과거차 [불러오기] — 코드리뷰 ⑥ 과거차 섹션과 동일 트래커 풀에서
        선택. cb_config.json 의 `section_past` 에 등록된 트래커 목록을
        _FetchSelectDialog 로 보여주고 선택된 트래커들의 항목을 합쳐 표시.
        """
        if self._historical_thread is not None:
            return

        # 1) 등록된 과거차 트래커 목록 로드 (코드리뷰 섹션과 공유)
        try:
            cfg = load_config() or {}
        except Exception:
            cfg = {}
        section_map: dict = cfg.get("section_past") or {}
        # 레거시 폴백 — section_past 가 비어있으면 cfg 상의 tracker_* 키 사용
        # (CbSectionWidget._load_trackers_from_cfg 와 동일 규칙)
        if not section_map:
            section_map = {}
            for k, v in cfg.items():
                if isinstance(k, str) and k.startswith("tracker_") \
                        and isinstance(v, str) and v.strip():
                    section_map[k[len("tracker_"):].upper()] = v.strip()
        # 빈/공백 트래커 ID 제외
        section_map = {
            n: str(tid).strip()
            for n, tid in section_map.items()
            if str(tid or "").strip()
        }
        if not section_map:
            self._warn(
                "등록된 과거차 트래커 없음",
                "코드리뷰 ⑥ > 과거차 섹션에서 트래커를 먼저 등록해주세요.\n"
                "(섹션 하단의 이름/ID 입력란에서 ＋ 버튼으로 추가)")
            return

        # 2) 사용자에게 트래커 선택 다이얼로그 표시
        dlg = _FetchSelectDialog(section_map, parent=self._mw)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dlg.get_selected()
        if not selected:
            self._sb("⚠  선택된 과거차 트래커가 없습니다.")
            return

        # 3) CB 자격증명 확인 후 multi-fetch 워커 시작
        fetcher = self._make_fetcher()
        if fetcher is None:
            return

        self._cb_tab.set_historical_fetch_running(True)
        names_str = ", ".join(selected.keys())
        self._sb(f"📥  과거차 fetch 시작 — [{names_str}] ({len(selected)}개 트래커)")

        worker = _MultiFetchWorker(fetcher, selected)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._sb)
        worker.done.connect(self._on_historical_fetch_done)
        worker.error.connect(self._on_historical_fetch_error)
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_historical_thread)
        self._historical_thread, self._historical_worker = thread, worker
        thread.start()

    def _on_historical_fetch_done(self, items: list):
        n = len(items)
        self._cb_tab.set_historical_items(items)
        self._cb_tab.set_historical_fetch_running(False)
        self._sb(f"✅  과거차 {n}개 불러옴")

    def _on_historical_fetch_error(self, msg: str):
        self._cb_tab.set_historical_items([])
        self._cb_tab.historical_list.set_loading_text(
            f"❌  불러오기 실패: {msg[:80]}")
        self._cb_tab.set_historical_fetch_running(False)
        self._sb(f"⚠  과거차 fetch 실패 — {msg[:120]}")

    def _cleanup_historical_thread(self):
        if self._historical_thread is not None:
            self._historical_thread.deleteLater()
        if self._historical_worker is not None:
            self._historical_worker.deleteLater()
        self._historical_thread = None
        self._historical_worker = None

    # ── 체크리스트 저장/수정 (Phase 2-3 와 호환 — 상태바 메시지만) ──
    def _on_checklist_saved(self):
        self._sb("🔒  체크리스트 잠금 — 다음 실행 시 자동 복원됨")

    def _on_checklist_edited(self):
        self._sb("✏  체크리스트 잠금 해제")

    # ── AI 인사이트 실행 — Phase 3-3: 변경점 N개 병렬 호출 ──────
    def _on_ai_run_requested(self):
        if self._ai_threads:
            self._warn("분석 진행 중",
                       "이미 AI 분석이 진행 중입니다. 완료될 때까지 기다려주세요.")
            return

        # 1) 입력 검증
        change_items = (self._cb_tab.get_selected_change_items()
                        if self._cb_tab else [])
        hist_items   = (self._cb_tab.get_selected_historical_items()
                        if self._cb_tab else [])
        if not change_items:
            self._warn(
                "변경점 미선택",
                "변경점 트래커에서 항목을 먼저 불러오고 분석할 변경점을 "
                "1개 이상 체크해주세요.")
            return

        common   = (self._ck_tab.get_common_inputs() if self._ck_tab else {})
        req_diff = ""
        try:
            req_diff = (self._srs_page.get_text() or "").strip()
        except Exception:
            req_diff = ""

        # 2) 확인 다이얼로그 — 변경점 N개 × API 호출이라 비용/시간 안내
        n_ch = len(change_items)
        n_hi = len(hist_items)
        diff_msg = f"\n요구사항 DIFF: 있음 ({len(req_diff):,} chars)" if req_diff else \
                   "\n요구사항 DIFF: 없음 (6번 매칭 섹션 생략)"
        confirm = QMessageBox.question(
            self._mw,
            "AI 인사이트 실행 확인",
            f"변경점 {n_ch}개를 병렬로 분석합니다.\n\n"
            f"• 변경점:     {n_ch}개 (각각 Claude API 1회 호출)\n"
            f"• 과거차:     {n_hi}개 (공통 컨텍스트로 전달){diff_msg}\n\n"
            f"분석 결과는 OUTPUT 탭에 변경점 드롭다운으로 표시됩니다.\n"
            f"계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # 3) OUTPUT 패널 초기화 + 드롭다운 채우기
        out_panel = getattr(self._srs_page, "ai_result_panel", None)
        if out_panel is not None:
            out_panel.set_change_items(change_items)
            out_panel.set_progress(0, n_ch)

        # 4) AI 버튼 비활성 + 카운터 리셋
        if self._ck_tab is not None:
            self._ck_tab.set_ai_running(True)
        self._ai_total     = n_ch
        self._ai_completed = 0
        self._ai_threads   = []

        # 5) N개 변경점에 대해 워커 + QThread 생성, 동시 시작
        for item in change_items:
            worker = SrsReviewV2Worker(
                card_id=str(item.get("id") or ""),
                cb_item=item,
                common=common,
                historical=hist_items,
                req_diff=req_diff,
            )
            thread = QThread()
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.progress.connect(self._sb)
            worker.done.connect(self._on_ai_worker_done)
            worker.error.connect(
                lambda msg, w=worker: self._on_ai_worker_error(w.card_id, msg))
            worker.done.connect(thread.quit)
            worker.error.connect(thread.quit)
            thread.finished.connect(
                lambda t=thread, w=worker: self._cleanup_ai_thread(t, w))
            self._ai_threads.append((thread, worker))

        self._sb(f"🤖  AI 분석 시작 — 변경점 {n_ch}개 병렬 호출")
        for thread, _w in self._ai_threads:
            thread.start()

    def _on_ai_worker_done(self, payload: dict):
        cid = str(payload.get("card_id") or "")
        markdown = str(payload.get("markdown") or "")
        out_panel = getattr(self._srs_page, "ai_result_panel", None)
        if out_panel is not None:
            out_panel.set_result(cid, markdown)
        self._ai_completed += 1
        if out_panel is not None:
            out_panel.set_progress(self._ai_completed, self._ai_total)
        self._sb(f"✅  변경점 #{cid} 분석 완료 "
                 f"({self._ai_completed}/{self._ai_total})")
        self._maybe_finalize_ai()

    def _on_ai_worker_error(self, card_id: str, msg: str):
        out_panel = getattr(self._srs_page, "ai_result_panel", None)
        if out_panel is not None:
            out_panel.set_error(card_id, msg)
        self._ai_completed += 1
        if out_panel is not None:
            out_panel.set_progress(self._ai_completed, self._ai_total)
        self._sb(f"⚠  변경점 #{card_id} 실패 — {msg[:80]} "
                 f"({self._ai_completed}/{self._ai_total})")
        self._maybe_finalize_ai()

    def _maybe_finalize_ai(self):
        """모든 워커가 종료되면 AI 버튼 재활성 + OUTPUT 탭으로 자동 전환."""
        if self._ai_completed < self._ai_total:
            return
        # 모든 분석 완료 (성공 + 실패 합산)
        if self._ck_tab is not None:
            self._ck_tab.set_ai_running(False)
        if hasattr(self._srs_page, "switch_to_ai_result_tab"):
            self._srs_page.switch_to_ai_result_tab()
        self._sb(f"🎯  AI 분석 종료 — 총 {self._ai_total}개 처리")

    def _cleanup_ai_thread(self, thread: QThread, worker):
        """thread.finished 시 호출 — 라이프사이클 정리."""
        try:
            self._ai_threads = [
                (t, w) for (t, w) in self._ai_threads if t is not thread
            ]
        except Exception:
            pass
        try:
            worker.deleteLater()
        except Exception:
            pass
        try:
            thread.deleteLater()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════
    #  Phase 3-5 — AI 결과 → CB 업로드 (변경점 1개 = CB 이슈 1개)
    # ══════════════════════════════════════════════════════════════
    def _on_upload_all_requested(self):
        """[📤 CB 업로드] 클릭 — 분석 완료된 결과들을 순차로 CB 이슈로 업로드.

        흐름:
          1) 결과 ≥1개 확인 → 트래커 ID 입력 다이얼로그 (cb_config 의 last-used 폴백)
          2) 확인 다이얼로그 (N개 업로드 안내)
          3) 큐에 담아 순차 처리 — 하나 완료 후 다음 spawn (CB rate limit 회피)
          4) 모두 완료 시 성공/실패 카운트 + 마지막 이슈 브라우저 열기 옵션
        """
        if self._upload_thread is not None:
            self._warn("업로드 진행 중", "이전 업로드가 끝날 때까지 기다려주세요.")
            return

        out_panel = getattr(self._srs_page, "ai_result_panel", None)
        if out_panel is None:
            return
        results_map = out_panel.get_all_results()
        if not results_map:
            self._warn(
                "업로드할 결과 없음",
                "AI 분석 결과가 없습니다. 먼저 [🤖 AI 인사이트 실행] 을 실행해주세요.")
            return

        # 트래커 ID — cb_config 의 last-used 우선 폴백
        try:
            cfg = load_config() or {}
        except Exception:
            cfg = {}
        last_id = str(cfg.get("last_upload_tracker_id") or "").strip()

        raw_id, ok = QInputDialog.getText(
            self._mw, "CB 업로드 — 대상 트래커 ID",
            "SRS 검토 결과를 등록할 Codebeamer 트래커 ID 또는 URL 을 입력하세요:",
            text=last_id,
        )
        if not ok:
            return
        tracker_id = parse_tracker_id_from_url(raw_id) or str(raw_id).strip()
        if not tracker_id:
            self._warn("트래커 ID 누락", "트래커 ID 를 입력해주세요.")
            return

        # 확인 다이얼로그
        n = len(results_map)
        confirm = QMessageBox.question(
            self._mw, "CB 업로드 확인",
            f"분석 결과 {n}개를 트래커 #{tracker_id} 에 각각 별도 이슈로 등록합니다.\n\n"
            f"• 이슈 제목: [SRS 검토] {{원 변경점 제목}}\n"
            f"• 본문: AI 분석 마크다운 (5섹션)\n"
            f"• 첨부: MD/HTML 단독 문서 자동 첨부\n"
            f"• 원 변경점 ID 는 parent 로 연결 시도\n\n"
            f"계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # last-used 트래커 ID 저장 (cb_config.json)
        try:
            cfg["last_upload_tracker_id"] = tracker_id
            save_config(cfg)
        except Exception:
            pass

        # 큐 빌드 — [(card_id, item, markdown), ...]
        self._upload_queue   = []
        for cid, md in results_map.items():
            item = out_panel.get_change_item(cid)
            self._upload_queue.append((cid, item, md))
        self._upload_tracker_id = tracker_id
        self._upload_total   = n
        self._upload_success = 0
        self._upload_failed  = 0

        # UI 잠금
        out_panel.set_upload_enabled(False)
        self._sb(f"📤  CB 업로드 시작 — {n}개 (트래커 #{tracker_id})")

        # 첫 항목 시작
        self._spawn_next_upload()

    def _spawn_next_upload(self):
        """큐에서 다음 항목 꺼내 CbUploadWorker 1개 실행. 큐 비면 마무리."""
        if not self._upload_queue:
            self._finalize_upload()
            return
        card_id, item, markdown = self._upload_queue.pop(0)

        fetcher = self._make_fetcher()
        if fetcher is None:
            self._finalize_upload()
            return

        title = str(item.get("name") or item.get("title")
                    or item.get("summary") or "(제목 없음)").strip()
        summary = f"[SRS 검토] {title}".strip()
        parent_id = str(item.get("id") or "").strip()
        idx = self._upload_success + self._upload_failed + 1

        self._sb(f"📤  업로드 중 [{idx}/{self._upload_total}] "
                 f"— 변경점 #{card_id}")

        worker = CbUploadWorker(
            fetcher        = fetcher,
            tracker_id     = self._upload_tracker_id,
            summary        = summary,
            description_md = markdown,
            project_name   = "SRS 검토",
            attach_md      = True,
            attach_html    = True,
            parent_item_id = parent_id,
        )
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._sb)
        worker.done.connect(lambda payload, cid=card_id:
                            self._on_upload_done(cid, payload))
        worker.error.connect(lambda msg, cid=card_id:
                             self._on_upload_error(cid, msg))
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_upload_thread)
        self._upload_thread, self._upload_worker = thread, worker
        thread.start()

    def _on_upload_done(self, card_id: str, payload: dict):
        self._upload_success += 1
        item_id = payload.get("item_id") or ""
        url     = payload.get("url") or ""
        self._sb(f"✅  변경점 #{card_id} → CB 이슈 #{item_id} 등록 "
                 f"({self._upload_success + self._upload_failed}/{self._upload_total})")
        # 다음 항목으로 진행은 _cleanup_upload_thread 에서 처리

    def _on_upload_error(self, card_id: str, msg: str):
        self._upload_failed += 1
        self._sb(f"⚠  변경점 #{card_id} 업로드 실패 — {msg[:80]}")

    def _cleanup_upload_thread(self):
        if self._upload_thread is not None:
            self._upload_thread.deleteLater()
        if self._upload_worker is not None:
            self._upload_worker.deleteLater()
        self._upload_thread = None
        self._upload_worker = None
        # 다음 항목 처리
        self._spawn_next_upload()

    def _finalize_upload(self):
        """큐 비었을 때 호출 — UI 복원 + 최종 요약."""
        out_panel = getattr(self._srs_page, "ai_result_panel", None)
        if out_panel is not None:
            out_panel.set_upload_enabled(True)
        n_ok   = self._upload_success
        n_fail = self._upload_failed
        n_tot  = self._upload_total
        if n_fail == 0:
            self._sb(f"🎯  CB 업로드 완료 — {n_ok}/{n_tot} 모두 성공")
            self._info("CB 업로드 완료",
                       f"분석 결과 {n_ok}개를 트래커 #{self._upload_tracker_id} 에 "
                       f"모두 정상 등록했습니다.")
        else:
            self._sb(f"⚠  CB 업로드 종료 — 성공 {n_ok}/{n_tot}, 실패 {n_fail}")
            self._warn("CB 업로드 일부 실패",
                       f"성공: {n_ok}개\n실패: {n_fail}개\n총: {n_tot}개\n\n"
                       f"실패한 항목은 상태바 로그를 확인해주세요.")
        # 리셋
        self._upload_total = 0
        self._upload_success = 0
        self._upload_failed  = 0
        self._upload_tracker_id = ""

    # ── 헬퍼: 상태바 / 다이얼로그 ────────────────────────────
    def _sb(self, msg: str):
        try:
            self._mw.statusBar().showMessage(msg)
        except Exception:
            pass

    def _warn(self, title: str, msg: str):
        try:
            QMessageBox.warning(self._mw, title, msg)
        except Exception:
            pass

    def _info(self, title: str, msg: str):
        try:
            QMessageBox.information(self._mw, title, msg)
        except Exception:
            pass
