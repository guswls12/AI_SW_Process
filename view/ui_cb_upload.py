"""ui_cb_upload.py — Codebeamer 트래커 업로드 다이얼로그.

사용자에게 다음을 묻는다:
  - 트래커 URL 또는 ID (마지막 사용값 자동 채움)
  - 상위 이슈 (선택) — 비우면 트래커 최상위에 생성
  - 첨부 파일: HTML  (MD 첨부는 사용 안 함 — 항상 False)

항상 새 이슈 생성 모드. 확인 시 result_data 프로퍼티에 dict 로 결과를 보관.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout,
)

from config import C
from integrations.codebeamer import (
    parse_item_id_from_url, parse_tracker_id_from_url,
)


class CbUploadDialog(QDialog):
    def __init__(self, parent, project_name: str, summary_preview: str,
                 last_tracker_id: str = "",
                 last_attach_md: bool = True,
                 last_attach_html: bool = True,
                 last_parent_id: str = "",
                 body_hint: str = "",
                 last_hzt_enabled: bool = False,
                 last_hzt_tracker_id: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Codebeamer 업로드")
        self.setFixedSize(560, 680)
        self.setStyleSheet(
            f"QDialog {{ background:{C.BG_PANEL}; border:1px solid {C.BDR2}; }}")

        self._result: dict | None = None

        vlay = QVBoxLayout(self)
        vlay.setContentsMargins(28, 22, 28, 22)
        vlay.setSpacing(0)

        # ── 헤더 ──────────────────────────────────────────────
        icon = QLabel("📤")
        icon.setFont(QFont("Segoe UI Emoji", 26))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background:transparent; border:none;")
        vlay.addWidget(icon)
        vlay.addSpacing(4)

        title = QLabel("Codebeamer 트래커에 업로드")
        title.setFont(QFont(C.FUI, 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{C.T0}; background:transparent; border:none;")
        vlay.addWidget(title)
        vlay.addSpacing(14)

        # ── 트래커 입력 ───────────────────────────────────────
        vlay.addWidget(self._mk_label("트래커 URL 또는 ID"))
        self._tracker_input = QLineEdit()
        self._tracker_input.setText(last_tracker_id)
        self._tracker_input.setPlaceholderText(
            "예: https://codebeamer.slworld.com/cb/tracker/9486521 또는 9486521")
        self._tracker_input.setStyleSheet(self._line_style())
        self._tracker_input.setMinimumHeight(32)
        vlay.addWidget(self._tracker_input)
        vlay.addSpacing(14)

        # ── 상위 이슈 (선택) ──────────────────────────────────
        vlay.addWidget(self._mk_label("상위 이슈 (선택)"))
        self._parent_input = QLineEdit()
        self._parent_input.setText(last_parent_id)
        self._parent_input.setPlaceholderText(
            "예: https://codebeamer.slworld.com/cb/issue/987588 또는 987588 "
            "(비우면 트래커 최상위에 생성)")
        self._parent_input.setStyleSheet(self._line_style())
        self._parent_input.setMinimumHeight(28)
        vlay.addWidget(self._parent_input)

        parent_hint = QLabel(
            "└ 입력 시 새 이슈가 해당 항목의 하위(child)로 등록됩니다.")
        parent_hint.setStyleSheet(
            f"color:{C.T3}; background:transparent; border:none;"
            "font-size:9px; padding:2px 0 0 4px;")
        vlay.addWidget(parent_hint)
        vlay.addSpacing(14)

        # ── 수평전개 동기 옵션 ──────────────────────────────────
        # 체크 시 별도 트래커에 수평전개 전용 이슈 생성 (차종별 적용여부 매핑).
        vlay.addWidget(self._mk_label("수평전개 트래커 동기 (선택)"))

        self._chk_hzt = QCheckBox(
            "이 변경점의 수평전개 내용을 다른 트래커에 별도 이슈로 등록")
        self._chk_hzt.setStyleSheet(self._check_style())
        self._chk_hzt.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chk_hzt.setChecked(bool(last_hzt_enabled))
        vlay.addWidget(self._chk_hzt)

        self._hzt_tracker_input = QLineEdit()
        self._hzt_tracker_input.setText(last_hzt_tracker_id)
        self._hzt_tracker_input.setPlaceholderText(
            "수평전개 트래커 URL 또는 ID (예: .../cb/tracker/9486800)")
        self._hzt_tracker_input.setStyleSheet(self._line_style())
        self._hzt_tracker_input.setMinimumHeight(28)
        self._hzt_tracker_input.setEnabled(self._chk_hzt.isChecked())
        vlay.addWidget(self._hzt_tracker_input)

        hzt_hint = QLabel(
            "└ 변경점 본문 이슈와 별도로, 차종별 적용여부(미적용/적용/NA)가 "
            "각 차종 필드에 매핑된 이슈를 자동 생성합니다.")
        hzt_hint.setWordWrap(True)
        hzt_hint.setStyleSheet(
            f"color:{C.T3}; background:transparent; border:none;"
            "font-size:9px; padding:2px 0 0 4px;")
        vlay.addWidget(hzt_hint)

        # 체크박스 ↔ 입력란 활성화 연동
        self._chk_hzt.toggled.connect(self._hzt_tracker_input.setEnabled)

        vlay.addSpacing(14)

        # ── 미리보기 ──────────────────────────────────────────
        vlay.addWidget(self._mk_label("이슈 요약(제목) 미리보기"))
        self._preview = QLabel(summary_preview or f"[{project_name}] SW 배포 파이프라인")
        self._preview.setWordWrap(True)
        self._preview.setStyleSheet(
            f"color:{C.T0}; background:{C.BG_INPUT};"
            f"  border:1px solid {C.BDR}; border-radius:4px;"
            f"  padding:8px 12px; font-family:'{C.FCODE}'; font-size:10px;")
        vlay.addWidget(self._preview)

        # 안내 문구 — 호출자가 hint 를 지정하지 않으면 기본 문구
        hint_text = body_hint or (
            "본문에는 변경점 요약과 취약점 분석이 markdown 으로 들어갑니다.")
        hint = QLabel(hint_text)
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{C.T3}; background:transparent; border:none;"
            "font-size:9px; padding-top:6px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vlay.addWidget(hint)

        vlay.addStretch(1)

        # ── 버튼 ──────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        cancel = QPushButton("취소")
        cancel.setFixedHeight(36)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(
            f"QPushButton {{ background:{C.BG_CARD}; color:{C.T2};"
            f"  border:1px solid {C.BDR}; border-radius:6px;"
            f"  font-size:11px; font-weight:600; padding:0 18px; }}"
            f"QPushButton:hover {{ background:{C.BG_HOVER}; color:{C.T0}; }}")
        cancel.clicked.connect(self.reject)

        confirm = QPushButton("📤  업로드")
        confirm.setFixedHeight(36)
        confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        # 프로그램 메인 BLUE 통일
        confirm.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:none; border-radius:6px;"
            f"  font-size:11px; font-weight:700; padding:0 22px; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:pressed {{ background:{C.BLUE_DK}; }}")
        confirm.clicked.connect(self._on_confirm)
        confirm.setDefault(True)

        btn_row.addStretch(1)
        btn_row.addWidget(cancel)
        btn_row.addWidget(confirm)
        vlay.addLayout(btn_row)

        # 부모 중앙
        if parent and parent.isVisible():
            geo = parent.geometry()
            self.move(geo.x() + (geo.width()  - self.width())  // 2,
                      geo.y() + (geo.height() - self.height()) // 2)

    # ── 결과 dict (accept 후 읽기) ──────────────────────────────
    @property
    def result_data(self) -> dict | None:
        return self._result

    # ── 내부 헬퍼 ────────────────────────────────────────────
    def _mk_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont(C.FUI, 9, QFont.Weight.DemiBold))
        lbl.setStyleSheet(
            f"color:{C.T1}; background:transparent; border:none;"
            "padding-bottom:4px;")
        return lbl

    def _line_style(self) -> str:
        return (
            f"QLineEdit {{ background:{C.BG_INPUT}; color:{C.T0};"
            f"  border:1px solid {C.BDR}; border-radius:4px;"
            f"  padding:4px 8px; font-family:'{C.FCODE}'; font-size:11px; }}"
            f"QLineEdit:focus {{ border-color:{C.BLUE}; }}"
            f"QLineEdit:disabled {{ color:{C.T3}; background:{C.BG_PANEL}; }}")

    def _check_style(self) -> str:
        return (
            f"QCheckBox {{ color:{C.T1}; background:transparent;"
            f"  font-family:'{C.FUI}'; font-size:11px; padding:2px 0; }}"
            "QCheckBox::indicator { width:14px; height:14px; }")

    def _flag_invalid(self, line: QLineEdit, msg: str = ""):
        line.setStyleSheet(
            self._line_style().replace(C.BDR, "#DC2626"))
        line.setFocus()
        if msg:
            QMessageBox.warning(self, "입력 확인 필요", msg)

    def _on_confirm(self):
        tid = parse_tracker_id_from_url(self._tracker_input.text())
        if not tid:
            self._flag_invalid(
                self._tracker_input,
                "트래커 URL 또는 ID 가 올바르지 않습니다.\n\n"
                "허용 형식:\n"
                "  • https://codebeamer.slworld.com/cb/tracker/9486521\n"
                "  • 9486521  (숫자만)")
            return

        # 상위 이슈 — 선택 입력. 비어 있으면 트래커 최상위에 생성.
        parent_id = ""
        parent_raw = self._parent_input.text().strip()
        if parent_raw:
            parent_id = parse_item_id_from_url(parent_raw)
            if not parent_id:
                self._flag_invalid(
                    self._parent_input,
                    "상위 이슈 ID 또는 URL 이 올바르지 않습니다.\n\n"
                    "허용 형식:\n"
                    "  • https://codebeamer.slworld.com/cb/issue/987588\n"
                    "  • 987588  (이슈 번호만)\n\n"
                    "필요 없으면 비워두세요.")
                return
        # 수평전개 동기 옵션 — 체크 시 트래커 ID 검증
        hzt_enabled = self._chk_hzt.isChecked()
        hzt_tid = ""
        if hzt_enabled:
            hzt_tid = parse_tracker_id_from_url(
                self._hzt_tracker_input.text())
            if not hzt_tid:
                self._flag_invalid(
                    self._hzt_tracker_input,
                    "수평전개 트래커 URL 또는 ID 가 올바르지 않습니다.\n\n"
                    "허용 형식:\n"
                    "  • https://codebeamer.slworld.com/cb/tracker/9486800\n"
                    "  • 9486800  (숫자만)\n\n"
                    "수평전개 동기가 필요 없으면 체크박스를 해제하세요.")
                return

        self._result = {
            "tracker_id":     tid,
            "parent_item_id": parent_id,
            # MD / HTML 자동 첨부 기능 비활성화 — 항상 False (사용자 요청)
            # 본문 description 에 동일 내용이 이미 들어가므로 별도 파일 불필요.
            "attach_md":      False,
            "attach_html":    False,
            "hzt_enabled":    hzt_enabled,
            "hzt_tracker_id": hzt_tid,
        }
        self.accept()
