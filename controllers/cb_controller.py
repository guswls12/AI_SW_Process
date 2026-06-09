"""cb_controller.py — Codebeamer 컨텍스트 로드 / 설정 다이얼로그 제어.

main.py 의 _on_cb, _on_cb_connected, _on_cb_context_updated, _load_cb_sections
와 _CB_SECTION_TITLES 상수를 한곳에 모은다.

MainWindow 는 본 컨트롤러를 보유하고 시그널만 연결한다 — 컨트롤러는
result_panel / input_panel / status_bar 를 MainWindow 로부터 받아 사용한다.

★ AI 리뷰 결과 → Codebeamer 업로드 흐름도 본 컨트롤러가 담당 (on_cb_upload).
"""

import os
import datetime
import webbrowser

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QDialog, QMessageBox

from integrations.codebeamer import (
    CbConfigDialog, load_cb_context, _BASE as CB_BASE,
    CbFetcher, load_config, save_config,
)
from core import project_state


class CbController:
    # 섹션 key(영문) → 실제 디스크에 저장된 CbSectionWidget safe_title
    # codebeamer.py의 _md_path()가 self.title을 re.sub(r"[^\w가-힣]", "_", ...)로
    # 정규화하여 파일명을 만들기 때문에, 폴백도 동일한 네이밍으로 맞춰야 한다.
    _SECTION_TITLES = {
        "past": "과거차",
        # "ll":   "L_L",    # [LL/SWE DISABLED]
        # "swe1": "SWE1",   # [LL/SWE DISABLED]
        # "swe3": "SWE3",   # [LL/SWE DISABLED]
    }

    def __init__(self, main_window):
        self._mw = main_window
        # 앱 시작 시 디스크의 CB 마크다운을 로드해 컨텍스트로 보유
        self.cb_context: str = load_cb_context()
        # ★ 업로드 워커 핸들 (가비지 컬렉션 방지를 위해 인스턴스로 보관)
        self._upload_thread = None
        self._upload_worker = None
        # ★ ① 사양 변경 페이지 트래커 fetch 워커 핸들
        self._spec_load_thread = None
        self._spec_load_worker = None
        # ★ ② ③ ④ SWE 페이지 트래커 fetch 워커 핸들 (page_key 별 분리)
        # {page_key: (QThread, QObject)} — 동시 한 페이지만 실행 가정
        self._swe_load_jobs: dict = {}

    # ── 다이얼로그 열기 ─────────────────────────────────────
    def open_dialog(self):
        dlg = CbConfigDialog(self._mw)
        dlg.context_updated.connect(self.on_context_updated)
        dlg.connected.connect(self.on_connected)
        dlg.exec()

    # ── 다이얼로그 시그널 슬롯 ──────────────────────────────
    def on_connected(self):
        """연결 테스트 성공 시 좌측 패널 상태 업데이트."""
        self._mw._input.update_cb_status(True)
        self._mw._sb.showMessage(
            "✅  Codebeamer 연결 성공 — 각 섹션에서 '가져오기'를 눌러주세요.")

    def on_context_updated(self, md_text: str):
        """CB 데이터 갱신 후 컨텍스트를 메모리에 반영한다."""
        self.cb_context = md_text
        self._mw._input.update_cb_status(bool(md_text))
        self._mw._sb.showMessage(
            "✅  Codebeamer 데이터 갱신 완료 — 다음 AI 분석부터 적용됩니다.")

    # ── AI 분석 시 호출되는 컨텍스트 빌더 ───────────────────
    def load_sections(self, keys: list) -> str:
        """지정된 CB 섹션을 합쳐 컨텍스트 문자열로 반환.
        우선순위:
          1) ResultPanel.get_cb_filtered_md(key) → 사용자가 체크한 항목만 (있으면)
          2) cb_sec_{safe_title}.md 파일 전체 (필터 미지원 모드 폴백)
        체크된 항목이 0건이면(빈 문자열) 해당 섹션은 컨텍스트에서 제외.
        """
        # ★ EXE(frozen) 실행 시 %APPDATA%\CodeReviewer, 개발 시 스크립트 폴더 사용
        base = CB_BASE
        parts = []
        for key in keys:
            filtered = None
            try:
                filtered = self._mw._result.get_cb_filtered_md(key)
            except Exception:
                filtered = None

            if filtered is not None:
                # 필터링 지원 모드 — 빈 문자열이면 사용자가 0개 선택 → 스킵
                if filtered.strip():
                    parts.append(filtered)
                continue

            # 폴백: 파일 전체 (영문 key → safe_title 매핑)
            safe_title = self._SECTION_TITLES.get(key, key)
            fpath = os.path.join(base, f"cb_sec_{safe_title}.md")
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    parts.append(f.read())
        return "\n\n".join(parts) if parts else ""

    # ──────────────────────────────────────────────────────────
    #  AI 리뷰 결과 → Codebeamer 업로드
    # ──────────────────────────────────────────────────────────
    def on_cb_upload(self):
        """결과 패널의 '📤 CB 업로드' 버튼 핸들러.
        분석 결과(요약+취약점) 가 있으면 다이얼로그를 띄우고 워커로 업로드.
        """
        mw = self._mw
        sum_md  = mw._result._sum_view.text()  if hasattr(mw._result, "_sum_view")  else ""
        vuln_md = mw._result._vuln_view.text() if hasattr(mw._result, "_vuln_view") else ""
        project_name = getattr(mw._result, "_project_name", "") or ""

        # ── 1) 분석 결과 존재 확인 ─────────────────────────────
        if not (sum_md.strip() or vuln_md.strip()):
            from view.ui_save import _show_no_result_dialog
            _show_no_result_dialog(mw)
            return

        # ── 2) CB 자격증명 확인 ────────────────────────────────
        cfg = load_config()
        url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                         cfg.get("password",""))
        if not (url and user and pw):
            QMessageBox.warning(
                mw, "Codebeamer 미설정",
                "먼저 좌측의 Codebeamer 설정에서 URL/계정/비밀번호를 입력해주세요.")
            return

        # ── 3) 프로젝트 메타데이터 필수 입력 검증 ──────────────
        try:
            meta = mw._input.get_project_meta()
        except Exception:
            meta = {"name": project_name}

        required = [
            ("name",    "변경내용요약"),
            ("ver_old", "변경 전 (.ver)"),
            ("ver_new", "변경 후 (.ver)"),
            ("author",  "설계자"),
        ]
        missing = [label for key, label in required
                   if not (meta.get(key) or "").strip()]
        if missing:
            from view.ui_dialog import MissingFieldsDialog
            MissingFieldsDialog(mw, missing).exec()
            return

        # ── 4) 다이얼로그 ─────────────────────────────────────
        summary = self._build_summary(meta)
        from view.ui_cb_upload import CbUploadDialog
        dlg = CbUploadDialog(
            mw, project_name, summary,
            last_tracker_id=cfg.get("last_upload_tracker_id", ""),
            last_attach_md=cfg.get("last_upload_attach_md", True),
            last_attach_html=cfg.get("last_upload_attach_html", True),
            last_parent_id=cfg.get("last_upload_parent_id", ""),
            last_hzt_enabled=cfg.get("last_hzt_enabled", False),
            last_hzt_tracker_id=cfg.get("last_hzt_tracker_id", ""),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.result_data
        if not data:
            return

        # ── 4) 마지막 사용값 저장 ──────────────────────────────
        cfg["last_upload_tracker_id"]  = data["tracker_id"]
        cfg["last_upload_attach_md"]   = data["attach_md"]
        cfg["last_upload_attach_html"] = data["attach_html"]
        cfg["last_upload_parent_id"]   = data.get("parent_item_id", "")
        cfg["last_hzt_enabled"]        = data.get("hzt_enabled", False)
        cfg["last_hzt_tracker_id"]     = data.get("hzt_tracker_id", "")
        save_config(cfg)

        # ── 5) 워커 스핀 ───────────────────────────────────────
        from workers.cb_upload_worker import CbUploadWorker
        fetcher = CbFetcher(url, user, pw)
        description = (sum_md + "\n\n---\n\n" + vuln_md).strip()

        # 프로젝트 메타데이터(좌측 입력 패널) 를 본문 최상단에 prepend.
        # AI 리뷰 프롬프트엔 들어가지 않고, CB 업로드/첨부 파일에만 노출된다.
        try:
            header_md = mw._input.get_project_header_md()
        except Exception:
            header_md = ""
        try:
            changes_md = mw._input.get_change_items_md()
        except Exception:
            changes_md = ""

        prepend_parts = [p for p in (header_md, changes_md) if p]
        if prepend_parts:
            description = "\n\n---\n\n".join(prepend_parts + [description])

        # 업로드 버튼 비활성화 (중복 클릭 방지)
        if hasattr(mw._result, "_cb_upload_btn"):
            mw._result._cb_upload_btn.setEnabled(False)

        self._upload_thread = QThread()
        self._upload_worker = CbUploadWorker(
            fetcher, data["tracker_id"],
            summary, description, project_name,
            attach_md=data["attach_md"],
            attach_html=data["attach_html"],
            parent_item_id=data.get("parent_item_id", ""),
        )
        self._upload_worker.moveToThread(self._upload_thread)
        self._upload_thread.started.connect(self._upload_worker.run)
        self._upload_worker.progress.connect(
            lambda msg: mw._sb.showMessage(msg))
        self._upload_worker.done.connect(self._on_upload_done)
        self._upload_worker.error.connect(self._on_upload_error)
        self._upload_worker.done.connect(self._upload_thread.quit)
        self._upload_worker.error.connect(self._upload_thread.quit)
        mw._sb.showMessage("📤  Codebeamer 업로드 시작...")
        self._upload_thread.start()

    # ──────────────────────────────────────────────────────────
    #  사양 변경 페이지 — 변경점 묶음 한 개만 CB 등록
    # ──────────────────────────────────────────────────────────
    def on_register_change_item(self, idx: int, data: dict):
        """사양 변경 페이지의 변경점 카드 [📤 등록] 버튼 핸들러.
        AI 분석 결과 없이도 단독 업로드 가능.
        제어기/버전/설계자 메타데이터 + 해당 변경점 본문만 등록한다.
        """
        from view.pages.page_spec import SpecChangePage

        mw = self._mw

        # ── 1) 변경점 제목 검증 ──────────────────────────────
        if not (data.get("title") or "").strip():
            QMessageBox.warning(
                mw, "제목 필요",
                f"변경점 #{idx} 의 제목을 먼저 입력해주세요.")
            return

        # ── 2) CB 자격증명 확인 ──────────────────────────────
        cfg = load_config()
        url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                         cfg.get("password",""))
        if not (url and user and pw):
            QMessageBox.warning(
                mw, "Codebeamer 미설정",
                "먼저 좌측의 Codebeamer 설정에서 URL/계정/비밀번호를 입력해주세요.")
            return

        # ── 3) 프로젝트 메타데이터 검증 (이슈 제목/헤더용) ───
        try:
            meta = mw._input.get_project_meta()
        except Exception:
            meta = {}
        required = [
            ("ver_old", "변경 전 (.ver)"),
            ("ver_new", "변경 후 (.ver)"),
            ("author",  "설계자"),
        ]
        missing = [label for key, label in required
                   if not (meta.get(key) or "").strip()]
        if missing:
            from view.ui_dialog import MissingFieldsDialog
            MissingFieldsDialog(mw, missing).exec()
            return

        # ── 4) 본문(description) 먼저 구성 — 다이얼로그 미리보기에도 사용
        try:
            header_md = mw._input.get_project_header_md()
        except Exception:
            header_md = ""
        item_md = SpecChangePage.render_change_item_md(idx, data)

        parts = [p for p in (header_md, item_md) if p]
        description = "\n\n---\n\n".join(parts) if parts else item_md

        # ── 5) 다이얼로그 — 이슈 제목은 변경점 제목 그대로 사용 ──
        # 프로젝트 정보(제어기/버전/설계자)는 본문 헤더에만 들어가고
        # 이슈 제목에는 포함하지 않는다.
        item_title = data["title"].strip()
        summary = item_title
        body_hint = (
            f"본문: 프로젝트 정보 + 변경점 #{idx} "
            f"(제목 / JIRA 링크 / 현상 / 분석 내용 / 대책 / 수평전개)")
        from view.ui_cb_upload import CbUploadDialog
        dlg = CbUploadDialog(
            mw, item_title, summary,
            last_tracker_id=cfg.get("last_upload_tracker_id", ""),
            last_attach_md=cfg.get("last_upload_attach_md", True),
            last_attach_html=cfg.get("last_upload_attach_html", True),
            last_parent_id=cfg.get("last_upload_parent_id", ""),
            body_hint=body_hint,
            last_hzt_enabled=cfg.get("last_hzt_enabled", False),
            last_hzt_tracker_id=cfg.get("last_hzt_tracker_id", ""),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        upload = dlg.result_data
        if not upload:
            return

        # ── 6) 마지막 사용값 저장 ────────────────────────────
        cfg["last_upload_tracker_id"]  = upload["tracker_id"]
        cfg["last_upload_attach_md"]   = upload["attach_md"]
        cfg["last_upload_attach_html"] = upload["attach_html"]
        cfg["last_upload_parent_id"]   = upload.get("parent_item_id", "")
        cfg["last_hzt_enabled"]        = upload.get("hzt_enabled", False)
        cfg["last_hzt_tracker_id"]     = upload.get("hzt_tracker_id", "")
        save_config(cfg)

        # ── 7) 워커 스핀 ─────────────────────────────────────
        from workers.cb_upload_worker import CbUploadWorker
        fetcher = CbFetcher(url, user, pw)

        hzt_tracker = (
            upload.get("hzt_tracker_id", "")
            if upload.get("hzt_enabled") else "")

        from workers.cb_upload_worker import build_hzt_description
        # HZT 추가 텍스트 필드 — UI 의 발생시점/고객OPEN → CB 필드명으로 매핑
        hzt_extra = {
            "발생시점":  data.get("occurrence")    or "",
            "고객OPEN": data.get("customer_open") or "",
        }
        self._upload_thread = QThread()
        self._upload_worker = CbUploadWorker(
            fetcher, upload["tracker_id"],
            summary, description, item_title,
            attach_md=upload["attach_md"],
            attach_html=upload["attach_html"],
            parent_item_id=upload.get("parent_item_id", ""),
            extra_attachments=data.get("attachments") or [],
            hzt_tracker_id=hzt_tracker,
            hzt_state=data.get("hzt") or {},
            hzt_title=item_title,
            hzt_jira_link=data.get("jira") or "",
            hzt_body=build_hzt_description(data),
            hzt_extra_fields=hzt_extra,
            # 메인 트래커에 차종/JIRA_LINK/JIRA_URL 필드가 있으면 자동 매핑.
            # 차종 필드가 없는 일반 트래커이면 create_hzt_item 의 minimal 폴백으로
            # 본문만 들어가므로 손해 없음 — 항상 켜둔다.
            main_is_hzt=True,
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
            f"📤  변경점 #{idx} 「{item_title}」 Codebeamer 업로드 시작...")
        self._upload_thread.start()

    # ──────────────────────────────────────────────────────────
    #  사양 변경 페이지 — 사양변경 탭 본문 단독 등록
    # ──────────────────────────────────────────────────────────
    def on_register_spec_change(self, data: dict):
        """사양변경 탭 본문 [📤 등록] 버튼 핸들러.
        제목/변경 내용/변경 사유/수평전개/첨부 → 새 CB 이슈 1개로 등록.
        """
        from view.pages.page_spec import SpecChangePage
        self._register_single_card(
            data,
            item_md_func=SpecChangePage.render_spec_change_md,
            kind_label="사양변경",
            body_hint=("본문: 프로젝트 정보 + 사양변경 "
                       "(제목 / 변경 내용 / 변경 사유 / 수평전개)"),
            # 사양변경에는 발생시점/JIRA 필드 없음 — HZT 추가 필드도 비움
            hzt_extra_fields=None,
        )

    # ──────────────────────────────────────────────────────────
    #  사양 변경 페이지 — 수평전개 탭 본문 단독 등록
    # ──────────────────────────────────────────────────────────
    def on_register_hzt_item(self, data: dict):
        """수평전개 탭 본문 [📤 등록] 버튼 핸들러.
        제목/JIRA/수평전개 내용/발생시점/수평전개 → 새 CB 이슈 1개로 등록.
        """
        from view.pages.page_spec import SpecChangePage
        self._register_single_card(
            data,
            item_md_func=SpecChangePage.render_hzt_item_md,
            kind_label="수평전개",
            body_hint=("본문: 프로젝트 정보 + 수평전개 "
                       "(제목 / JIRA 링크 / 수평전개 내용 / 발생시점 / 수평전개)"),
            hzt_extra_fields={"발생시점": data.get("occurrence") or ""},
        )

    # ──────────────────────────────────────────────────────────
    #  단일 카드 등록 공용 헬퍼 (사양변경 / 수평전개 공용)
    # ──────────────────────────────────────────────────────────
    def _register_single_card(self, data: dict, *,
                              item_md_func, kind_label: str,
                              body_hint: str,
                              hzt_extra_fields: dict | None):
        """사양변경 / 수평전개 탭의 단일 카드를 CB 새 이슈로 등록.

        item_md_func : data → 본문 마크다운 (render_spec_change_md 등)
        kind_label   : 상태 메시지/제목 검증 다이얼로그에 쓰는 라벨
        body_hint    : CbUploadDialog 본문 미리보기 안내문
        hzt_extra_fields : 수평전개 동기 트래커로 보낼 추가 텍스트 필드
                           (사양변경/수평전개는 발생시점/고객OPEN 없음 → None/빈값)
        """
        mw = self._mw

        # 1) 제목 검증
        if not (data.get("title") or "").strip():
            QMessageBox.warning(
                mw, "제목 필요",
                f"{kind_label}의 제목을 먼저 입력해주세요.")
            return

        # 2) CB 자격증명 확인
        cfg = load_config()
        url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                         cfg.get("password",""))
        if not (url and user and pw):
            QMessageBox.warning(
                mw, "Codebeamer 미설정",
                "먼저 좌측의 Codebeamer 설정에서 URL/계정/비밀번호를 입력해주세요.")
            return

        # 3) 프로젝트 메타데이터 검증
        try:
            meta = mw._input.get_project_meta()
        except Exception:
            meta = {}
        required = [
            ("ver_old", "변경 전 (.ver)"),
            ("ver_new", "변경 후 (.ver)"),
            ("author",  "설계자"),
        ]
        missing = [label for key, label in required
                   if not (meta.get(key) or "").strip()]
        if missing:
            from view.ui_dialog import MissingFieldsDialog
            MissingFieldsDialog(mw, missing).exec()
            return

        # 4) 본문 구성
        try:
            header_md = mw._input.get_project_header_md()
        except Exception:
            header_md = ""
        item_md = item_md_func(data) or ""
        parts = [p for p in (header_md, item_md) if p]
        description = "\n\n---\n\n".join(parts) if parts else item_md

        # 5) 다이얼로그 — 이슈 탭과 동일한 UI (수평전개 동기 옵션 그대로)
        item_title = data["title"].strip()
        summary = item_title
        from view.ui_cb_upload import CbUploadDialog
        dlg = CbUploadDialog(
            mw, item_title, summary,
            last_tracker_id=cfg.get("last_upload_tracker_id", ""),
            last_attach_md=cfg.get("last_upload_attach_md", True),
            last_attach_html=cfg.get("last_upload_attach_html", True),
            last_parent_id=cfg.get("last_upload_parent_id", ""),
            body_hint=body_hint,
            last_hzt_enabled=cfg.get("last_hzt_enabled", False),
            last_hzt_tracker_id=cfg.get("last_hzt_tracker_id", ""),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        upload = dlg.result_data
        if not upload:
            return

        # 6) 마지막 사용값 저장
        cfg["last_upload_tracker_id"]  = upload["tracker_id"]
        cfg["last_upload_attach_md"]   = upload["attach_md"]
        cfg["last_upload_attach_html"] = upload["attach_html"]
        cfg["last_upload_parent_id"]   = upload.get("parent_item_id", "")
        cfg["last_hzt_enabled"]        = upload.get("hzt_enabled", False)
        cfg["last_hzt_tracker_id"]     = upload.get("hzt_tracker_id", "")
        save_config(cfg)

        # 7) 수평전개 본문 — content 필드만 있는 단순 형식 (build_hzt_description
        #    은 phenom/analysis/action 기반이라 여기선 직접 구성)
        hzt_body_sections = []
        content = (data.get("content") or "").strip()
        if content:
            label = "[변경 내용]" if kind_label == "사양변경" else "[수평전개 내용]"
            hzt_body_sections.append(f"{label}\n{content}")
        # 사양변경 — 변경 사유도 hzt 본문에 함께 (있을 때만)
        if kind_label == "사양변경":
            reason = (data.get("reason") or "").strip()
            if reason:
                hzt_body_sections.append(f"[변경 사유]\n{reason}")
        jira = (data.get("jira") or "").strip()
        if jira:
            hzt_body_sections.append(f"[JIRA]\n{jira}")
        hzt_body = "\n\n".join(hzt_body_sections)

        # 8) 워커 스핀
        from workers.cb_upload_worker import CbUploadWorker
        fetcher = CbFetcher(url, user, pw)

        hzt_tracker = (
            upload.get("hzt_tracker_id", "")
            if upload.get("hzt_enabled") else "")

        # 메인 모드 결정 — 다이얼로그의 hzt sync 옵션 상태에 따라 동적 분기.
        #   · hzt sync 옵션 OFF (단일 트래커 모드):
        #       사용자가 메인 트래커에 곧장 수평전개 트래커 ID 를 넣은 경우.
        #       → main_is_hzt=True 로 메인 등록에서 차종 필드까지 한 번에 매핑.
        #       (연관 사양변경 필드는 박지 않음 — 메인이 자체이므로 자기 참조 무의미)
        #   · hzt sync 옵션 ON (이슈 탭 흐름):
        #       메인=사양변경 트래커, HZT 동기=수평전개 트래커 분리 등록.
        #       → main_is_hzt=False (메인은 일반 create_item) + HZT 동기 이슈에
        #         '연관 사양변경'=메인 ID 자동 연결.
        main_is_hzt_flag = not bool(upload.get("hzt_enabled", False))

        self._upload_thread = QThread()
        self._upload_worker = CbUploadWorker(
            fetcher, upload["tracker_id"],
            summary, description, item_title,
            attach_md=upload["attach_md"],
            attach_html=upload["attach_html"],
            parent_item_id=upload.get("parent_item_id", ""),
            extra_attachments=data.get("attachments") or [],
            hzt_tracker_id=hzt_tracker,
            hzt_state=data.get("hzt") or {},
            hzt_title=item_title,
            hzt_jira_link=jira,
            hzt_body=hzt_body,
            hzt_extra_fields=hzt_extra_fields or {},
            main_is_hzt=main_is_hzt_flag,
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
            f"📤  {kind_label} 「{item_title}」 Codebeamer 업로드 시작...")
        self._upload_thread.start()

    # ──────────────────────────────────────────────────────────
    #  사양 변경 페이지 — 이슈 묶음 전체 일괄 등록
    # ──────────────────────────────────────────────────────────
    def on_register_all_change_items(self, payload: list):
        """변경점 내용 헤더 [📤 전체 등록] 버튼 핸들러.
        payload: list of (1-based idx, data dict).
        하나의 다이얼로그로 트래커/상위/첨부 받고 워커가 N개 순차 등록.
        """
        from view.pages.page_spec import SpecChangePage

        mw = self._mw

        # ── 1) 등록 대상 필터링 — 제목 있는 변경점만 ───────────
        candidates: list[tuple[int, dict]] = []
        skipped_no_title: list[int] = []
        for idx, data in payload:
            if (data.get("title") or "").strip():
                candidates.append((idx, data))
            else:
                # 제목 없는 항목 — 본문도 비어있으면 조용히 스킵, 본문 있으면 카운트
                has_content = any((data.get(k) or "").strip()
                                  for k in ("jira", "phenom", "analysis", "action"))
                if has_content:
                    skipped_no_title.append(idx)

        if not candidates:
            QMessageBox.warning(
                mw, "등록할 변경점 없음",
                "제목이 입력된 변경점이 하나도 없습니다.\n"
                "각 변경점에 제목을 먼저 입력해주세요.")
            return

        # ── 2) CB 자격증명 / 프로젝트 메타 검증 ────────────────
        cfg = load_config()
        url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                         cfg.get("password",""))
        if not (url and user and pw):
            QMessageBox.warning(
                mw, "Codebeamer 미설정",
                "먼저 좌측의 Codebeamer 설정에서 URL/계정/비밀번호를 입력해주세요.")
            return

        try:
            meta = mw._input.get_project_meta()
        except Exception:
            meta = {}
        required = [
            ("ver_old", "변경 전 (.ver)"),
            ("ver_new", "변경 후 (.ver)"),
            ("author",  "설계자"),
        ]
        missing = [label for key, label in required
                   if not (meta.get(key) or "").strip()]
        if missing:
            from view.ui_dialog import MissingFieldsDialog
            MissingFieldsDialog(mw, missing).exec()
            return

        # ── 3) 사용자 사전 확인 ───────────────────────────────
        skip_msg = ""
        if skipped_no_title:
            skip_msg = (
                f"\n\n⚠ 제목 없이 본문만 작성된 변경점 "
                f"{len(skipped_no_title)}개 (#{', #'.join(map(str, skipped_no_title))}) "
                f"는 등록에서 제외됩니다.")
        from view.ui_dialog import ConfirmDialog
        detail = (skip_msg.strip() if skip_msg else
                  "각 변경점이 새 이슈로 트래커에 개별 등록됩니다.")
        confirm = ConfirmDialog(
            mw,
            title="전체 등록 확인",
            headline=f"변경점 {len(candidates)}개를 트래커에 한 번에 등록합니다.",
            detail=detail,
            primary_label="📤  등록 진행",
            secondary_label="취소",
        )
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        # ── 4) 다이얼로그 — 트래커/상위/첨부 한 번만 입력 ──────
        try:
            header_md = mw._input.get_project_header_md()
        except Exception:
            header_md = ""

        # 미리보기용 제목 — 첫 번째 변경점 + N개
        first_title = candidates[0][1]["title"].strip()
        preview_summary = (
            f"{first_title}  외 {len(candidates)-1}개"
            if len(candidates) > 1 else first_title)
        body_hint = (
            f"본문: 프로젝트 정보 + 변경점 {len(candidates)}개 각각 별도 이슈로 생성")

        from view.ui_cb_upload import CbUploadDialog
        dlg = CbUploadDialog(
            mw, first_title, preview_summary,
            last_tracker_id=cfg.get("last_upload_tracker_id", ""),
            last_attach_md=cfg.get("last_upload_attach_md", True),
            last_attach_html=cfg.get("last_upload_attach_html", True),
            last_parent_id=cfg.get("last_upload_parent_id", ""),
            body_hint=body_hint,
            last_hzt_enabled=cfg.get("last_hzt_enabled", False),
            last_hzt_tracker_id=cfg.get("last_hzt_tracker_id", ""),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        upload = dlg.result_data
        if not upload:
            return

        # ── 5) 마지막 사용값 저장 ────────────────────────────
        cfg["last_upload_tracker_id"]  = upload["tracker_id"]
        cfg["last_upload_attach_md"]   = upload["attach_md"]
        cfg["last_upload_attach_html"] = upload["attach_html"]
        cfg["last_upload_parent_id"]   = upload.get("parent_item_id", "")
        cfg["last_hzt_enabled"]        = upload.get("hzt_enabled", False)
        cfg["last_hzt_tracker_id"]     = upload.get("hzt_tracker_id", "")
        save_config(cfg)

        # ── 6) 항목별 본문 빌드 (헤더 + 변경점 마크다운) ──────
        from workers.cb_upload_worker import build_hzt_description
        items = []
        for idx, data in candidates:
            item_md = SpecChangePage.render_change_item_md(idx, data)
            parts = [p for p in (header_md, item_md) if p]
            body_md = "\n\n---\n\n".join(parts) if parts else item_md
            items.append({
                "idx":         idx,
                "title":       data["title"].strip(),
                "summary":     data["title"].strip(),
                "body_md":     body_md,
                "attachments": data.get("attachments") or [],
                # 수평전개 동기용 — 차종별 상태값 + JIRA 링크 + 본문
                "hzt_state":   data.get("hzt") or {},
                "jira_link":   data.get("jira") or "",
                "hzt_body":    build_hzt_description(data),
                # HZT 추가 텍스트 필드 (발생시점/고객OPEN 등)
                "hzt_extra_fields": {
                    "발생시점":  data.get("occurrence")    or "",
                    "고객OPEN": data.get("customer_open") or "",
                },
            })

        # ── 7) 워커 스핀 ─────────────────────────────────────
        from workers.cb_bulk_upload_worker import CbBulkUploadWorker
        fetcher = CbFetcher(url, user, pw)

        hzt_tracker = (
            upload.get("hzt_tracker_id", "")
            if upload.get("hzt_enabled") else "")

        self._upload_thread = QThread()
        self._upload_worker = CbBulkUploadWorker(
            fetcher, upload["tracker_id"], items,
            project_name=mw._input.get_project_name() or "AIreview",
            attach_md=upload["attach_md"],
            attach_html=upload["attach_html"],
            parent_item_id=upload.get("parent_item_id", ""),
            hzt_tracker_id=hzt_tracker,
            # 메인 트래커에 차종 필드가 있으면 자동 매핑 (없으면 minimal 폴백)
            main_is_hzt=True,
        )
        self._upload_worker.moveToThread(self._upload_thread)
        self._upload_thread.started.connect(self._upload_worker.run)
        self._upload_worker.progress.connect(
            lambda msg: mw._sb.showMessage(msg))
        self._upload_worker.done.connect(self._on_bulk_upload_done)
        self._upload_worker.error.connect(self._on_upload_error)
        self._upload_worker.done.connect(self._upload_thread.quit)
        self._upload_worker.error.connect(self._upload_thread.quit)
        mw._sb.showMessage(
            f"📤  변경점 {len(candidates)}개 일괄 업로드 시작...")
        self._upload_thread.start()

    # ── 일괄 업로드 완료 슬롯 ────────────────────────────────
    def _on_bulk_upload_done(self, info: dict):
        mw = self._mw
        results  = info.get("results", []) or []
        failures = info.get("failures", []) or []
        n_ok = len(results)
        n_fail = len(failures)

        # 상태바
        if n_fail == 0:
            mw._sb.showMessage(
                f"✅  Codebeamer 일괄 등록 완료 — {n_ok}개 성공")
        else:
            mw._sb.showMessage(
                f"⚠  Codebeamer 일괄 등록 — {n_ok}개 성공 / {n_fail}개 실패")

        # 결과 다이얼로그
        lines = []
        if results:
            lines.append(f"✓ 성공 {n_ok}개:")
            for r in results:
                lines.append(
                    f"  • #{r['idx']} 「{r['title']}」 → {r['url']}")
        if failures:
            lines.append("")
            lines.append(f"✗ 실패 {n_fail}개:")
            for f in failures:
                lines.append(
                    f"  • #{f['idx']} 「{f['title']}」 — {f['error'][:120]}")

        from view.ui_dialog import SuccessDialog, ErrorDialog
        if n_fail == 0 and results:
            # 모두 성공 — 첫 번째 항목 URL 을 primary 링크로
            primary_url = results[0]["url"] if results else ""
            dlg = SuccessDialog(
                mw,
                title="Codebeamer 일괄 등록 완료",
                headline=f"변경점 {n_ok}개가 성공적으로 등록되었습니다.",
                link_url=primary_url,
                primary_label="열기" if primary_url else "확인",
                secondary_label="닫기",
            )
            if dlg.exec() == QDialog.DialogCode.Accepted and primary_url:
                try:
                    webbrowser.open(primary_url)
                except Exception:
                    pass
        else:
            # 일부 또는 전체 실패 — 에러 다이얼로그로 상세 결과 표시
            ErrorDialog(
                mw,
                title="Codebeamer 일괄 등록 결과",
                headline=f"{n_ok}개 성공 / {n_fail}개 실패",
                detail="\n".join(lines),
            ).exec()

    # ── 업로드 완료 슬롯 ──────────────────────────────────────
    def _on_upload_done(self, info: dict):
        mw = self._mw
        if hasattr(mw._result, "_cb_upload_btn"):
            mw._result._cb_upload_btn.setEnabled(True)

        item_id = info.get("item_id", "")
        url     = info.get("url", "")
        body = f"새 이슈 #{item_id} 가 생성되었습니다."
        mw._sb.showMessage(f"✅  Codebeamer 새 이슈 생성 완료 — #{item_id}")
        from view.ui_dialog import SuccessDialog
        dlg = SuccessDialog(
            mw,
            title="Codebeamer 업로드 완료",
            headline=body,
            link_url=url,
            primary_label="브라우저에서 열기",
            secondary_label="닫기",
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and url:
            try:
                webbrowser.open(url)
            except Exception:
                pass

    def _on_upload_error(self, msg: str):
        mw = self._mw
        if hasattr(mw._result, "_cb_upload_btn"):
            mw._result._cb_upload_btn.setEnabled(True)
        mw._sb.showMessage(f"❌  업로드 실패: {msg[:200]}")
        from view.ui_dialog import ErrorDialog
        ErrorDialog(
            mw,
            title="Codebeamer 업로드 실패",
            headline="업로드 중 오류가 발생했습니다.",
            detail=str(msg),
        ).exec()

    # ── 헬퍼 ──────────────────────────────────────────────────
    @staticmethod
    def _build_summary(meta) -> str:
        """프로젝트 메타데이터를 조합해 CB 이슈 제목 생성.
        meta: get_project_meta() dict 또는 (구버전 호환) 단일 문자열.

        포맷: [제어기] {변경내용요약} - v{old}→v{new} ({설계자}, {날짜})
        예시 (모든 필드):
          [STM32H743] NX5 PLBM 30Ah, BSP 변경 사항 - v1.2.0→v1.2.1 (홍길동, 2026-05-11)
        비어있는 필드는 자연스럽게 생략된다.
        """
        # 구버전 호환 — 문자열이 넘어오면 dict 로 래핑
        if isinstance(meta, str):
            meta = {"name": meta}
        meta   = meta or {}
        name   = (meta.get("name")    or "").strip()  # 변경내용요약
        mcu    = (meta.get("mcu")     or "").strip()
        v_old  = (meta.get("ver_old") or "").strip()
        v_new  = (meta.get("ver_new") or "").strip()
        author = (meta.get("author")  or "").strip()
        date   = (meta.get("date")    or "").strip() \
                 or datetime.date.today().isoformat()

        # ① 제어기 브래킷 (없으면 생략)
        bracket = f"[{mcu}] " if mcu else ""

        # ② 메인 타이틀 — 변경내용요약 우선, 없으면 '코드 리뷰' 폴백
        main = name or "코드 리뷰"

        # ③ 버전 블록 — 둘 다 있을 때만 'old → new', 한쪽만 있으면 단일
        if v_old and v_new:
            ver_block = f" - v{v_old} → v{v_new}"
        elif v_new:
            ver_block = f" - v{v_new}"
        elif v_old:
            ver_block = f" - v{v_old}"
        else:
            ver_block = ""

        # ④ 꼬리 (설계자, 날짜)
        tail_parts = [p for p in (author, date) if p]
        tail = f" ({', '.join(tail_parts)})" if tail_parts else ""

        title = f"{bracket}{main}{ver_block}{tail}".strip()
        # 메타가 거의 비어있어 빈 폴백 제목인 경우 안전 디폴트
        if title.strip() in ("코드 리뷰", f"코드 리뷰 ({date})"):
            return f"[SW 배포 파이프라인] {date}"
        return title

    # ══════════════════════════════════════════════════════════════
    #  ① 사양 변경 — 트래커에서 이슈 불러오기
    # ══════════════════════════════════════════════════════════════
    def on_spec_page_load(self):
        """① 사양 변경 페이지 헤더 [📥 트래커에서 불러오기] 핸들러.

        흐름:
          1) project_state 의 trackers["spec"] 트래커 ID 가져옴
          2) CbFetcher + SpecFetchWorker → 트래커의 모든 이슈 + description fetch
          3) spec_md_parser 가 이슈 / 사양변경 / 수평전개 카테고리로 분류
          4) SpecChangePage.apply_loaded_items() 로 각 탭에 묶음 복원
          5) 'other' 카테고리는 사용자에게 안내 메시지로 알림
        """
        mw = self._mw
        page = getattr(mw, "_page_spec", None)
        if page is None:
            return

        # 진행 중인 워커가 있으면 무시 (중복 클릭 방지)
        if getattr(self, "_spec_load_thread", None) is not None:
            return

        # 1) 트래커 ID
        proj, ver = self._current_project_meta()
        if not proj or not ver:
            QMessageBox.information(
                mw, "프로젝트 정보 미설정",
                "프로그램 시작 시 표시되는 '프로젝트 정보' 다이얼로그에서\n"
                "프로젝트명/버전을 먼저 입력해주세요.")
            return
        from core import project_state
        tracker_id = project_state.get_tracker_id(proj, ver, "spec")
        if not tracker_id:
            QMessageBox.information(
                mw, "① 트래커 ID 없음",
                "현재 프로젝트의 ① 사양 변경 트래커 ID 가 비어있습니다.\n\n"
                "프로젝트 정보 다이얼로그를 다시 열어 ① 트래커 ID 를 입력하거나,\n"
                "이번 세션에서 ① 페이지로 새 이슈를 등록하면 자동 저장됩니다.")
            return

        # 2) CB 자격증명 + 워커 준비
        cfg = load_config()
        url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                         cfg.get("password",""))
        if not (url and user and pw):
            QMessageBox.warning(
                mw, "Codebeamer 미설정",
                "먼저 사이드바 헤더의 🔌 버튼에서 CB URL/계정/PW 를 설정해주세요.")
            return

        # 사용자 확인 — 기존 입력값이 새 내용으로 대체된다는 경고
        confirm = QMessageBox.question(
            mw, "트래커에서 불러오기",
            f"트래커 #{tracker_id} 의 모든 이슈를 가져와 ① 페이지에 복원합니다.\n\n"
            f"⚠ 현재 입력된 이슈/사양변경/수평전개 내용은 모두 새 내용으로 \n"
            f"  대체됩니다. 계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # 버튼 비활성 (중복 클릭 방지)
        try:
            page.load_btn.setEnabled(False)
            page.load_btn.setText("⏳  불러오는 중...")
        except Exception:
            pass

        from workers.spec_fetch_worker import SpecFetchWorker
        fetcher = CbFetcher(url, user, pw)
        worker = SpecFetchWorker(fetcher, tracker_id)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda msg: mw._sb.showMessage(msg))
        worker.done.connect(self._on_spec_load_done)
        worker.error.connect(self._on_spec_load_error)
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._cleanup_spec_load_thread)
        self._spec_load_thread = thread
        self._spec_load_worker = worker
        thread.start()

    def _on_spec_load_done(self, classified: dict):
        mw = self._mw
        page = getattr(mw, "_page_spec", None)
        if page is None:
            return
        try:
            counts = page.apply_loaded_items(classified)
        except Exception as e:
            counts = {"issue": 0, "spec": 0, "hzt": 0, "other": 0}
            mw._sb.showMessage(f"⚠  ① 페이지 적용 실패: {e}")

        # 결과 안내 다이얼로그
        n_i = counts.get("issue", 0)
        n_s = counts.get("spec",  0)
        n_h = counts.get("hzt",   0)
        n_o = counts.get("other", 0)
        msg = (f"트래커에서 다음 항목들을 복원했습니다:\n\n"
               f"  📝 이슈      : {n_i}건\n"
               f"  📐 사양변경  : {n_s}건\n"
               f"  🚗 수평전개  : {n_h}건\n")
        if n_o > 0:
            msg += (f"\n⚠ 본문이 비어있어 분류 불가 : {n_o}건\n"
                    f"  (CB 이슈에 description 이 비어있는 항목 — 복원할 내용 없음)")
        QMessageBox.information(mw, "트래커 불러오기 완료", msg)
        mw._sb.showMessage(
            f"✅  ① 트래커 불러오기 — 이슈 {n_i} / 사양변경 {n_s} / "
            f"수평전개 {n_h} 건 복원")

    def _on_spec_load_error(self, msg: str):
        mw = self._mw
        mw._sb.showMessage(f"❌  ① 트래커 불러오기 실패: {msg[:200]}")
        QMessageBox.warning(
            mw, "트래커 불러오기 실패",
            f"트래커 조회 중 오류가 발생했습니다:\n\n{msg[:400]}")

    def _cleanup_spec_load_thread(self):
        """워커 종료 시 thread 정리 + 버튼 복구."""
        mw = self._mw
        page = getattr(mw, "_page_spec", None)
        if page is not None:
            try:
                page.load_btn.setEnabled(True)
                page.load_btn.setText("📥  트래커에서 불러오기")
            except Exception:
                pass
        thread = getattr(self, "_spec_load_thread", None)
        worker = getattr(self, "_spec_load_worker", None)
        if thread is not None:
            try:
                thread.deleteLater()
            except Exception:
                pass
        if worker is not None:
            try:
                worker.deleteLater()
            except Exception:
                pass
        self._spec_load_thread = None
        self._spec_load_worker = None

    # ══════════════════════════════════════════════════════════════
    #  ② SRS / ③ SAD / ④ SDD — 트래커 등록 결과 조회 (공통 흐름)
    # ══════════════════════════════════════════════════════════════
    # page_key → MainWindow attr 매핑 (② ~ ⑦ 공통 흐름)
    _SWE_PAGE_ATTRS = {
        "srs":    "_page_srs",      # ② SWE.1 SRS
        "sad":    "_page_sad",      # ③ SWE.2 SAD
        "sdd":    "_page_sdd",      # ④ SWE.3/4 SDD
        "static": "_page_static",   # ⑤ 정적 검증 결과
        "review": "_page_review",   # ⑥ 코드리뷰 결과
        "test":   "_page_test",     # ⑦ 설계자 테스트 결과
    }
    _SWE_PAGE_LABELS = {
        "srs":    "② SWE.1 SRS",
        "sad":    "③ SWE.2 SAD",
        "sdd":    "④ SWE.3/4 SDD",
        "static": "⑤ 정적 검증 결과",
        "review": "⑥ 코드리뷰 결과",
        "test":   "⑦ 설계자 테스트 결과",
    }

    def _get_swe_page(self, page_key: str):
        """page_key (srs/sad/sdd) → 페이지 인스턴스. 잘못된 key 면 None."""
        attr = self._SWE_PAGE_ATTRS.get(page_key)
        if attr is None:
            return None
        return getattr(self._mw, attr, None)

    def on_swe_page_load(self, page_key: str):
        """②③④ 페이지 [📥 불러오기] 핸들러 — page_key 별 공통 흐름.

        흐름:
          1) project_state 의 trackers[page_key] 확인
          2) 트래커 ID 없으면 배너에 'no_tracker' 표시
          3) CB 자격증명 + CbItemsWorker 스핀
          4) done → status_banner.set_items / set_empty
          5) error → status_banner.set_error
        """
        mw = self._mw
        page = self._get_swe_page(page_key)
        if page is None or page.status_banner is None:
            return

        # 진행 중 워커 있으면 무시
        if page_key in self._swe_load_jobs:
            return

        proj, ver = self._current_project_meta()
        if not proj or not ver:
            QMessageBox.information(
                mw, "프로젝트 정보 미설정",
                "프로그램 시작 시 표시되는 '프로젝트 정보' 다이얼로그에서\n"
                "프로젝트명/버전을 먼저 입력해주세요.")
            return

        from core import project_state
        tracker_id = project_state.get_tracker_id(proj, ver, page_key)
        if not tracker_id:
            page.status_banner.set_no_tracker()
            label = self._SWE_PAGE_LABELS.get(page_key, page_key)
            mw._sb.showMessage(f"⚠  {label} 트래커 ID 가 비어있습니다.")
            return

        cfg = load_config()
        url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                         cfg.get("password",""))
        if not (url and user and pw):
            QMessageBox.warning(
                mw, "Codebeamer 미설정",
                "먼저 사이드바 헤더의 🔌 버튼에서 CB URL/계정/PW 를 설정해주세요.")
            return

        # 배너 + 버튼 로딩 상태
        page.set_load_running(True, tracker_id)

        fetcher = CbFetcher(url, user, pw)

        # ⑤ 정적 / ⑦ 테스트 — 첨부/댓글까지 가져오는 CbReviewFetchWorker
        # 그 외 (②③④) — 기존 CbItemsWorker (이슈 목록만)
        if page_key in ("static", "test"):
            from workers.cb_review_fetch_worker import CbReviewFetchWorker
            worker = CbReviewFetchWorker(fetcher, tracker_id)
            done_handler = (
                lambda data, k=page_key, tid=tracker_id:
                    self._on_review_load_done(k, tid, data))
        else:
            from workers.cb_items_worker import CbItemsWorker
            worker = CbItemsWorker(fetcher, tracker_id)
            done_handler = (
                lambda items, k=page_key, tid=tracker_id:
                    self._on_swe_load_done(k, tid, items))

        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda msg: mw._sb.showMessage(msg))
        worker.done.connect(done_handler)
        worker.error.connect(
            lambda msg, k=page_key: self._on_swe_load_error(k, msg))
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(
            lambda k=page_key: self._cleanup_swe_load_thread(k))
        self._swe_load_jobs[page_key] = (thread, worker)
        thread.start()

    def _on_swe_load_done(self, page_key: str, tracker_id: str, items: list):
        page = self._get_swe_page(page_key)
        if page is None:
            return
        n = len(items or [])
        if n == 0:
            page.status_banner.set_empty(tracker_id)
        else:
            page.status_banner.set_items(tracker_id, items)
        label = self._SWE_PAGE_LABELS.get(page_key, page_key)
        self._mw._sb.showMessage(
            f"✅  {label} — 트래커 #{tracker_id} 등록 {n}건 확인")

    def _on_review_load_done(self, page_key: str, tracker_id: str, data: dict):
        """⑤ 정적 / ⑦ 테스트 페이지 done — 첨부 OK/NG + 댓글 리스트 반영."""
        page = self._get_swe_page(page_key)
        if page is None:
            return
        items = data.get("items") or []
        n = len(items)
        # 배너 — 빈 트래커면 empty, 아니면 단순 카운트 표시
        if n == 0:
            page.status_banner.set_empty(tracker_id)
        else:
            page.status_banner.set_items(tracker_id, items)
        # 본문 — 첨부/댓글 결과 위젯에 그대로 전달
        try:
            page.apply_result(data)
        except Exception as e:
            self._mw._sb.showMessage(f"⚠  결과 표시 실패: {e}")
        label = self._SWE_PAGE_LABELS.get(page_key, page_key)
        ok_ng = "OK" if data.get("has_attachment") else "NG"
        self._mw._sb.showMessage(
            f"✅  {label} — 트래커 #{tracker_id}  첨부 {ok_ng}  /  이슈 {n}건")

    def _on_swe_load_error(self, page_key: str, msg: str):
        page = self._get_swe_page(page_key)
        if page is not None and page.status_banner is not None:
            page.status_banner.set_error(msg)
        label = self._SWE_PAGE_LABELS.get(page_key, page_key)
        self._mw._sb.showMessage(f"❌  {label} 조회 실패 — {msg[:160]}")

    def _cleanup_swe_load_thread(self, page_key: str):
        """워커 종료 시 thread 정리 + 버튼 복구."""
        page = self._get_swe_page(page_key)
        if page is not None:
            page.set_load_running(False)
        job = self._swe_load_jobs.pop(page_key, None)
        if job is not None:
            thread, worker = job
            try:
                worker.deleteLater()
            except Exception:
                pass
            try:
                thread.deleteLater()
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════
    #  ⑧ OPEN 항목 / ⑨ 배포 리뷰 — 공용 흐름
    # ══════════════════════════════════════════════════════════════
    def _current_project_meta(self) -> tuple:
        """현재 작업 중인 (프로젝트명, 버전).

        프로그램 시작 시 ProjectStartDialog 에서 입력받아 MainWindow 에 저장된
        값을 사용. 비어있으면 ('', '') 반환 (사용자에게 안내).
        """
        mw = self._mw
        return (
            getattr(mw, "_project_name", "") or "",
            getattr(mw, "_project_version", "") or "",
        )

    # ── ⑧ 불러오기 (4단계 새 양식) ──────────────────────────
    def on_open_items_load(self):
        """⑧ 페이지 [📥 불러오기] — 4단계 새 양식.

        흐름:
          1) ① 사양변경 페이지 변경점 (이슈/사양변경/수평전개) 수집 → 행 생성
          2) ②③④ 페이지의 change_load_card 변경 없음 / change_match_card 매핑으로
             변경점별 SRS/SAD/SDD 결과 (O / N/A / X) 산출
          3) ⑤⑦ 페이지 has_result() — 같은 트래커 첨부 여부 (협의 완료)
          4) ⑥ 코드리뷰는 보류 ('-') — 사용자 협의 대기
        """
        mw = self._mw
        page = getattr(mw, "_page_open", None)
        if page is None:
            return

        # 1) 변경점 수집
        change_items = self._collect_change_items()
        page.set_change_items(change_items)
        if not change_items:
            mw._sb.showMessage(
                "⚠  ① 사양변경 페이지에 입력된 변경점이 없습니다.")
            return

        # 2) ②③④ 결과 산출
        results_by_id = self._compute_swe_results(change_items)

        # 3) ⑤⑦ — 같은 정적/테스트 트래커
        try:
            static_has = bool(mw._page_static.has_result())
        except Exception:
            try:
                static_has = bool(mw._page_static.get_attachments())
            except Exception:
                static_has = False
        try:
            test_has = bool(mw._page_test.has_result())
        except Exception:
            try:
                test_has = bool(mw._page_test.get_attachments())
            except Exception:
                test_has = False

        page.apply_results(
            results_by_id,
            static=("O" if static_has else "X"),
            review="-",   # 4단계 보류
            test  =("O" if test_has else "X"),
        )
        mw._sb.showMessage(
            f"📥  ⑧ 자동 채움 — 변경점 {len(change_items)}건 / "
            f"정적:{'O' if static_has else 'X'} / "
            f"테스트:{'O' if test_has else 'X'} / 코드리뷰:보류")

    # ── ⑧⑨ 공통: ① 사양변경 페이지에서 변경점 수집 ──────────
    def _collect_change_items(self) -> list:
        """① 의 [이슈/사양변경/수평전개] 묶음을 단일 리스트로.
        반환: [{"cat":"issue/spec/hzt", "title": str, "id": str}, ...]
        제목 없는 빈 묶음은 스킵.
        """
        mw = self._mw
        page_spec = getattr(mw, "_page_spec", None)
        if page_spec is None:
            return []
        out: list = []
        try:
            for i, b in enumerate(getattr(page_spec, "_items", []), start=1):
                d = b.get_data() or {}
                if (d.get("title") or "").strip():
                    out.append({"cat": "issue", "title": d["title"].strip(),
                                "id": f"issue#{i}"})
        except Exception:
            pass
        try:
            for i, b in enumerate(getattr(page_spec, "_spec_blocks", []), start=1):
                d = b.get_data() or {}
                if (d.get("title") or "").strip():
                    out.append({"cat": "spec", "title": d["title"].strip(),
                                "id": f"spec#{i}"})
        except Exception:
            pass
        try:
            for i, b in enumerate(getattr(page_spec, "_hzt_blocks", []), start=1):
                d = b.get_data() or {}
                if (d.get("title") or "").strip():
                    out.append({"cat": "hzt", "title": d["title"].strip(),
                                "id": f"hzt#{i}"})
        except Exception:
            pass
        return out

    def _compute_swe_results(self, change_items: list) -> dict:
        """변경점별 SRS/SAD/SDD 결과 산출.

        규칙:
          · ② 변경 없음 체크 → 모든 변경점에 SRS = N/A
          · ② 매핑에 이 변경점이 있고 req_ids 1개 이상 → O
          · 그 외 → X
          · ③ SAD, ④ SDD 동일
        매칭은 change_id 우선, 폴백으로 제목 substring.
        """
        mw = self._mw
        out: dict = {ci["id"]: {} for ci in change_items}
        for col_key, page_attr in (("srs", "_page_srs"),
                                   ("sad", "_page_sad"),
                                   ("sdd", "_page_sdd")):
            page = getattr(mw, page_attr, None)
            if page is None:
                for ci in change_items:
                    out[ci["id"]][col_key] = "X"
                continue
            try:
                no_change = bool(page.change_load_card.is_no_change())
            except Exception:
                no_change = False
            try:
                mappings = page.change_match_card.get_mappings() or []
            except Exception:
                mappings = []
            for ci in change_items:
                if no_change:
                    out[ci["id"]][col_key] = "N/A"
                    continue
                matched = False
                for m in mappings:
                    mid   = str(m.get("change_id") or "")
                    mname = str(m.get("change_name") or "")
                    reqs  = m.get("req_ids") or []
                    if not reqs:
                        continue
                    if mid and mid == ci["id"]:
                        matched = True; break
                    title = ci.get("title") or ""
                    if mname and title and (title in mname or mname in title):
                        matched = True; break
                out[ci["id"]][col_key] = "O" if matched else "X"
        return out

    def _compute_deploy_swe_results(self, change_items: list,
                                    trackers: dict) -> dict:
        """⑨ 배포리뷰 변경점별 SRS/SAD/SDD 셀 값 산출.

        반환 dict 값:
          · 트래커 ID 문자열  → 매칭 + 트래커 등록됨 (초록)
          · 'N/A'             → 변경 없음 체크
          · ''                → 매칭 없음 (빨강)
        """
        mw = self._mw
        out: dict = {ci["id"]: {} for ci in change_items}
        for col_key, page_attr in (("srs", "_page_srs"),
                                   ("sad", "_page_sad"),
                                   ("sdd", "_page_sdd")):
            page = getattr(mw, page_attr, None)
            tid = str((trackers or {}).get(col_key) or "").strip()
            if page is None:
                for ci in change_items:
                    out[ci["id"]][col_key] = ""
                continue
            try:
                no_change = bool(page.change_load_card.is_no_change())
            except Exception:
                no_change = False
            try:
                mappings = page.change_match_card.get_mappings() or []
            except Exception:
                mappings = []
            for ci in change_items:
                if no_change:
                    out[ci["id"]][col_key] = "N/A"
                    continue
                matched = False
                for m in mappings:
                    mid   = str(m.get("change_id") or "")
                    mname = str(m.get("change_name") or "")
                    reqs  = m.get("req_ids") or []
                    if not reqs:
                        continue
                    if mid and mid == ci["id"]:
                        matched = True; break
                    title = ci.get("title") or ""
                    if mname and title and (title in mname or mname in title):
                        matched = True; break
                # 매칭 + 트래커 ID 있으면 → 트래커 ID 셀
                out[ci["id"]][col_key] = tid if (matched and tid) else (
                    "" if not matched else "")
        return out

    # ── ⑨ 불러오기 (4단계 새 양식) ─────────────────────────
    def on_deploy_review_load(self):
        """⑨ 페이지 [📥 불러오기] — 4단계 새 양식.

        흐름:
          1) ① 사양변경 페이지 변경점 수집 → 행 생성
          2) ②③④ 트래커 ID + 매핑 / 변경 없음 → 셀 값 산출 (트래커ID / N/A / 없음)
          3) ⑤⑦ 트래커 ID 동일 적용 (정적/테스트)
          4) ②③④ 체크리스트 결과 트래커 ID → Result 행 첨부 안내문
        """
        mw = self._mw
        page = getattr(mw, "_page_deploy", None)
        if page is None:
            return

        proj, ver = self._current_project_meta()
        if not proj or not ver:
            QMessageBox.information(
                mw, "프로젝트 정보 미설정",
                "프로그램 시작 시 표시되는 '프로젝트 정보' 다이얼로그에서\n"
                "프로젝트명/버전을 먼저 입력해주세요.")
            return

        # 1) 변경점 수집
        change_items = self._collect_change_items()
        page.set_change_items(change_items)
        if not change_items:
            mw._sb.showMessage(
                "⚠  ① 사양변경 페이지에 입력된 변경점이 없습니다.")
            # 결재란 등 복원만
            st = project_state.load_state(proj, ver)
            try:
                page.apply_state(st.get("deploy_review") or {})
            except Exception:
                pass
            return

        # 2) ②③④ 결과 — 트래커 ID / N/A / X
        trackers = project_state.get_all_trackers(proj, ver)
        results_by_id = self._compute_deploy_swe_results(change_items, trackers)

        # 3) ⑤⑦ 트래커 ID (같은 정적/테스트 트래커)
        static_tid = str(trackers.get("static") or "").strip()
        test_tid   = str(trackers.get("test")   or "").strip()

        # SAS 첨부 안내문 — 각 페이지의 체크리스트 결과 트래커 ID
        sas = {
            "srs": trackers.get("srs") or "",
            "sad": trackers.get("sad") or "",
            "sdd": trackers.get("sdd") or "",
        }

        page.apply_results(
            results_by_id,
            static_link=static_tid,
            review_text="-",
            test_link=test_tid,
            sas=sas,
        )

        n_chg = len(change_items)
        mw._sb.showMessage(
            f"📥  ⑨ 자동 채움 — 변경점 {n_chg}건 / 트래커 매핑 완료")

        # ⑧ 페이지의 입력값 + ⑨ 결재란도 같은 JSON 에 보관되므로 복원 시도
        st = project_state.load_state(proj, ver)
        try:
            mw._page_open.apply_state(st.get("open_items") or {})
        except Exception:
            pass
        try:
            page.apply_state(st.get("deploy_review") or {})
        except Exception:
            pass

        n = sum(1 for v in trackers.values() if v)
        mw._sb.showMessage(
            f"📥  ⑨ 배포 리뷰 — '{proj} v{ver}' 트래커 {n}/{len(trackers)} 개 로드")

    # ── ⑧ CB 업로드 ────────────────────────────────────────
    def on_open_items_upload(self):
        """⑧ OPEN 항목 페이지의 [📤 CB 업로드] 헤더 버튼 핸들러."""
        self._upload_simple_page(
            page_attr="_page_open",
            page_key="open",
            title_prefix="OPEN 항목 잔여 조치",
            body_hint=(
                "본문: OPEN 항목 점검표 (정적 검증 / 코드 리뷰 H·M·L / 설계자 테스트)"),
        )

    # ── ⑨ CB 업로드 ────────────────────────────────────────
    def on_deploy_review_upload(self):
        """⑨ 배포 리뷰 페이지의 [📤 CB 업로드] 헤더 버튼 핸들러."""
        # ⑨ 업로드 시점에는 자동으로 최신 트래커 ID 를 우선 한번 더 불러옴.
        # (사용자가 [불러오기] 누르지 않고 바로 업로드한 경우 대응)
        try:
            self.on_deploy_review_load()
        except Exception:
            pass
        self._upload_simple_page(
            page_attr="_page_deploy",
            page_key="",   # ⑨ 자체는 트래커 ID 저장 안 함 (배포 산출물 자체)
            title_prefix="배포 리뷰",
            body_hint="본문: 진행 점검표 (①~⑧ PASS/FAIL + 트래커 링크) + 결재란",
        )

    # ── 공용 헬퍼 ──────────────────────────────────────────
    def _upload_simple_page(self, *, page_attr: str, page_key: str,
                            title_prefix: str, body_hint: str):
        """⑧/⑨ 같은 단순 페이지의 CB 업로드 공용 흐름.

        - page.render_markdown() 으로 본문 마크다운 생성
        - CbUploadDialog → CbUploadWorker
        - 업로드 성공 시 page_key 가 있으면 deploy_state 에 트래커 ID 저장
        """
        mw = self._mw
        page = getattr(mw, page_attr, None)
        if page is None:
            return

        # 1) CB 자격증명 확인
        cfg = load_config()
        url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                         cfg.get("password",""))
        if not (url and user and pw):
            QMessageBox.warning(
                mw, "Codebeamer 미설정",
                "먼저 사이드바 헤더의 🔌 버튼으로 Codebeamer URL/계정/비밀번호를 "
                "설정해주세요.")
            return

        # 2) 본문 마크다운 생성
        try:
            description = page.render_markdown() or ""
        except Exception as e:
            QMessageBox.warning(mw, "본문 생성 실패", str(e))
            return
        if not description.strip():
            QMessageBox.information(mw, "본문 비어 있음",
                "표 / 입력 값을 먼저 채워주세요.")
            return

        # 3) 프로젝트 메타 기반 제목
        try:
            meta = mw._input.get_project_meta()
        except Exception:
            meta = {}
        base = self._build_summary(meta)
        summary = f"[{title_prefix}] {base}"

        # 4) 다이얼로그 — 트래커 ID / 상위 이슈 입력
        from view.ui_cb_upload import CbUploadDialog
        # ⑧/⑨ 전용 last_upload key — 페이지별로 따로 보관
        last_key = f"last_{page_attr.lstrip('_')}_tracker_id"
        dlg = CbUploadDialog(
            mw, title_prefix, summary,
            last_tracker_id=cfg.get(last_key, "")
                            or cfg.get("last_upload_tracker_id", ""),
            last_attach_md=False, last_attach_html=False,
            last_parent_id=cfg.get("last_upload_parent_id", ""),
            body_hint=body_hint,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.result_data
        if not data:
            return

        # 5) 마지막 사용값 저장
        cfg[last_key] = data["tracker_id"]
        cfg["last_upload_parent_id"] = data.get("parent_item_id", "")
        save_config(cfg)

        # 6) 워커 스핀
        from workers.cb_upload_worker import CbUploadWorker
        fetcher = CbFetcher(url, user, pw)
        self._upload_thread = QThread()
        self._upload_worker = CbUploadWorker(
            fetcher, data["tracker_id"],
            summary, description, title_prefix,
            attach_md=False, attach_html=False,
            parent_item_id=data.get("parent_item_id", ""),
        )
        self._upload_worker.moveToThread(self._upload_thread)
        self._upload_thread.started.connect(self._upload_worker.run)
        self._upload_worker.progress.connect(
            lambda msg: mw._sb.showMessage(msg))

        # 업로드 성공 시 project_state 에 page_key 트래커 ID 저장
        proj, ver = self._current_project_meta()

        def _on_done_save(info: dict):
            try:
                # 페이지의 트래커 ID 자체를 저장 (CB 업로드한 대상 트래커)
                if page_key and proj and ver:
                    project_state.set_tracker_id(
                        proj, ver, page_key, data["tracker_id"])
                    # ⑧ 페이지 입력값도 같이 보관
                    if page_attr == "_page_open":
                        st = project_state.load_state(proj, ver)
                        try:
                            st["open_items"] = page.to_state()
                        except Exception:
                            pass
                        project_state.save_state(proj, ver, st)
                    elif page_attr == "_page_deploy":
                        st = project_state.load_state(proj, ver)
                        try:
                            st["deploy_review"] = page.to_state()
                        except Exception:
                            pass
                        project_state.save_state(proj, ver, st)
            finally:
                self._on_upload_done(info)

        self._upload_worker.done.connect(_on_done_save)
        self._upload_worker.error.connect(self._on_upload_error)
        self._upload_worker.done.connect(self._upload_thread.quit)
        self._upload_worker.error.connect(self._upload_thread.quit)
        mw._sb.showMessage(f"📤  [{title_prefix}] Codebeamer 업로드 시작...")
        self._upload_thread.start()
