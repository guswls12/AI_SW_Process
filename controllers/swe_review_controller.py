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
        try:
            self._page.change_match_card.upload_clicked.connect(self.on_upload)
        except Exception:
            pass

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
            # 매칭 없음 — 사용자에게 안내 (그래도 강제 실행 옵션 제공)
            ret = QMessageBox.question(
                mw, "매칭 정보 없음",
                "변경점 ↔ 요구사항 ID 매칭 정보가 없거나 인식할 수 없습니다.\n\n"
                "전체 체크리스트를 AI 분석하시겠습니까?\n"
                "(매칭 결과 탭에서 요구사항 ID 를 먼저 입력하면 비용을 절약할 수 있습니다.)",
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
            # OUTPUT 탭 → AI 결과 탭으로 자동 전환
            page.switch_to_ai_result_tab()
        except Exception as e:
            self._mw._sb.showMessage(f"⚠  AI 결과 반영 실패: {e}")
            return
        self._mw._sb.showMessage(
            f"✅  AI 분석 완료 — 체크리스트 {len(merged)}개 항목 갱신")

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
    def on_upload(self, mappings: list):
        """[📤 매칭 결과 CB 업로드] — 매칭 결과 + ASPICE 체크리스트 xlsx 첨부."""
        mw = self._mw
        page = self._page

        proj = getattr(mw, "_project_name", "") or ""
        ver  = getattr(mw, "_project_version", "") or ""
        if not proj or not ver:
            QMessageBox.information(
                mw, "프로젝트 정보 미설정",
                "프로그램 시작 시 표시되는 '프로젝트 정보' 다이얼로그에서\n"
                "프로젝트명/버전을 먼저 입력해주세요.")
            return

        from core import project_state
        tracker_id = project_state.get_tracker_id(proj, ver, self._page_key)
        if not tracker_id:
            QMessageBox.information(
                mw, f"{self._page_key.upper()} 트래커 미설정",
                f"이 페이지의 트래커 ID 가 비어있습니다.\n"
                f"프로젝트 정보 다이얼로그에서 등록해주세요.")
            return

        cfg = load_config()
        url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                         cfg.get("password",""))
        if not (url and user and pw):
            QMessageBox.warning(
                mw, "Codebeamer 미설정",
                "먼저 사이드바 헤더의 🔌 버튼에서 CB URL/계정/PW 를 설정해주세요.")
            return

        # 체크리스트 갱신본 저장 (임시 파일)
        st = page.aspice_checklist.get_state()
        if not st or not (st.get("source_path") or "").strip():
            QMessageBox.warning(
                mw, "체크리스트 미로드",
                "ASPICE 체크리스트 파일을 먼저 로드 후 [🤖 AI 분석 실행] 또는 "
                "수동 편집 후 업로드해주세요.")
            return

        from core.checklist_parser import save_checklist
        tmp_path = os.path.join(
            tempfile.gettempdir(),
            f"aspice_checklist_{self._page_key}_{proj}_{ver}.xlsx")
        try:
            saved = save_checklist(st, tmp_path)
        except Exception as e:
            QMessageBox.critical(
                mw, "체크리스트 저장 실패",
                f"체크리스트 xlsx 갱신 중 오류:\n\n{e}")
            return

        # 본문 마크다운 — 매칭 결과 표 + 체크리스트 요약
        body_md = _build_upload_body_md(page, mappings, st)
        summary = (f"[{self._page_key.upper()}] 체크리스트 검토 결과 "
                   f"({proj} v{ver})")

        # CbUploadWorker 호출
        from workers.cb_upload_worker import CbUploadWorker
        fetcher = CbFetcher(url, user, pw)

        if self._upload_thread is not None:
            return

        self._upload_thread = QThread()
        self._upload_worker = CbUploadWorker(
            fetcher, tracker_id,
            summary, body_md, summary,
            attach_md=False, attach_html=False,
            parent_item_id=cfg.get("last_upload_parent_id", ""),
            extra_attachments=[saved],   # ★ 체크리스트 xlsx 첨부
        )
        self._upload_worker.moveToThread(self._upload_thread)
        self._upload_thread.started.connect(self._upload_worker.run)
        self._upload_worker.progress.connect(
            lambda msg: mw._sb.showMessage(msg))
        self._upload_worker.done.connect(self._on_upload_done)
        self._upload_worker.error.connect(self._on_upload_error)
        self._upload_worker.done.connect(self._upload_thread.quit)
        self._upload_worker.error.connect(self._upload_thread.quit)
        mw._sb.showMessage(
            f"📤  [{self._page_key.upper()}] 체크리스트 결과 CB 업로드 시작...")
        self._upload_thread.start()

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
