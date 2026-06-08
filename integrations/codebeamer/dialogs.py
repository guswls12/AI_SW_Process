"""dialogs.py — Codebeamer 연동용 다이얼로그.

  - CbConfigDialog     : URL/계정/비밀번호 입력 + 연결 테스트
  - _FetchSelectDialog : 'CB 불러오기' 시 트래커 다중선택 팝업 (CbSectionWidget 에서 사용)
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from config import C

from .api import CbFetcher
from .config import load_config, save_config
from .ui_primitives import _ca


# ══════════════════════════════════════════════════════════════
#  CbConfigDialog — 연결 설정 다이얼로그
# ══════════════════════════════════════════════════════════════
class CbConfigDialog(QDialog):
    context_updated = pyqtSignal(str)
    connected       = pyqtSignal()   # 연결 테스트 성공 시 발생

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Codebeamer 연동 설정")
        self.setFixedSize(520, 360)
        self.setModal(True)
        self._thread = self._worker = None
        self._build()
        self._load_fields()

    # ── UI 구성 ───────────────────────────────────────────────
    def _build(self):
        self.setStyleSheet(f"""
            QDialog   {{ background:{C.BG_APP}; }}
            QLabel    {{ color:{C.T1}; background:transparent; }}
            QLineEdit {{
                background:{C.BG_INPUT}; color:{C.T0};
                border:1px solid {C.BDR}; border-radius:6px;
                padding:6px 10px; font-size:12px;
                selection-background-color:{C.ACCENT_H};
                selection-color:#FFFFFF;
            }}
            QLineEdit:focus {{ border-color:{C.BDR_FOCUS}; }}
            QFrame#sec {{
                background:{C.BG_CARD};
                border:1px solid {C.BDR};
                border-radius:10px;
            }}
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 16)
        outer.setSpacing(12)

        # ── 제목 영역 (아이콘 + 제목 + 부제) ──────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(10)
        icon_box = QFrame()
        icon_box.setFixedSize(40, 40)
        icon_box.setStyleSheet(
            f"background:{C.BLUE_LT}; border:1px solid {C.BDR};"
            f"border-radius:8px;")
        ib = QHBoxLayout(icon_box); ib.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel("🔗")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont(C.FUI, 16))
        icon_lbl.setStyleSheet("background:transparent;")
        ib.addWidget(icon_lbl)
        hdr.addWidget(icon_box)

        title_box = QVBoxLayout(); title_box.setSpacing(1)
        title = QLabel("Codebeamer 연동 설정")
        title.setFont(QFont(C.FUI, 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C.T0}; background:transparent;")
        title_box.addWidget(title)
        subtitle = QLabel("서버 주소 / 계정을 입력하고 '연결 테스트'로 검증하세요.")
        subtitle.setFont(QFont(C.FUI, 9))
        subtitle.setStyleSheet(f"color:{C.T3}; background:transparent;")
        title_box.addWidget(subtitle)
        hdr.addLayout(title_box)
        hdr.addStretch()
        outer.addLayout(hdr)

        # ── 섹션 1: 서버 연결 ─────────────────────────────────
        sec1 = QFrame(); sec1.setObjectName("sec")
        f1   = QVBoxLayout(sec1)
        f1.setContentsMargins(16, 14, 16, 14); f1.setSpacing(10)
        f1.addWidget(self._sec_lbl("🌐  서버 연결"))

        self._url_edit  = self._le("예) https://codebeamer.slworld.com/cb")
        self._user_edit = self._le("사용자 ID")
        self._pw_edit   = self._le("비밀번호", pw=True)

        for lbl_txt, widget in [
            ("서버 URL",  self._url_edit),
            ("사용자 ID", self._user_edit),
            ("비밀번호",  self._pw_edit),
        ]:
            f1.addLayout(self._row(lbl_txt, widget, 70))

        # 연결 테스트 버튼 + 결과 라벨
        self._test_btn = QPushButton("🔌  연결 테스트")
        self._test_btn.setFixedHeight(30)
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.setStyleSheet(self._btn_ss(C.ACCENT, C.ACCENT_H))
        self._test_btn.clicked.connect(self._on_test)
        self._test_lbl = QLabel("")
        self._test_lbl.setFont(QFont(C.FUI, 9))
        self._test_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")
        tr = QHBoxLayout(); tr.setSpacing(10)
        tr.addWidget(self._test_btn); tr.addWidget(self._test_lbl, stretch=1)
        f1.addLayout(tr)
        outer.addWidget(sec1)

        outer.addStretch()

        # ── 하단 버튼 — 확인 한 개만 (취소는 ESC 또는 X 로 처리) ──
        br = QHBoxLayout(); br.setSpacing(8)
        br.addStretch()
        self._save_btn = QPushButton("✓  확인")
        self._save_btn.setFixedHeight(34)
        self._save_btn.setMinimumWidth(120)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setStyleSheet(self._btn_ss(C.BLUE, C.ACCENT_H))
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._on_save)
        br.addWidget(self._save_btn)
        outer.addLayout(br)
        # _close_btn 더 이상 사용 안 함 — 다른 코드가 참조하지 않도록 None 으로 표시
        self._close_btn = None

    # ── 헬퍼 ──────────────────────────────────────────────────
    def _sec_lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        l.setStyleSheet(f"color:{C.T0}; background:transparent;")
        return l

    def _le(self, placeholder: str, pw: bool = False) -> QLineEdit:
        le = QLineEdit()
        le.setPlaceholderText(placeholder)
        le.setFixedHeight(30)
        if pw:
            le.setEchoMode(QLineEdit.EchoMode.Password)
        return le

    @staticmethod
    def _row(label: str, widget, lbl_w: int = 80) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(8)
        l = QLabel(label); l.setFixedWidth(lbl_w)
        l.setFont(QFont(C.FUI, 10))
        row.addWidget(l); row.addWidget(widget)
        return row

    @staticmethod
    def _btn_ss(bg: str, hover: str) -> str:
        return (f"QPushButton {{ background:{bg}; color:#FFFFFF;"
                f"  border:none; border-radius:6px;"
                f"  font-size:11px; font-weight:600; padding:0 18px; }}"
                f"QPushButton:hover {{ background:{hover}; }}"
                f"QPushButton:disabled {{ background:{C.BDR2}; color:#FFFFFF; }}")

    # ── 필드 로드 ─────────────────────────────────────────────
    def _load_fields(self):
        cfg = load_config()
        self._url_edit.setText(cfg.get("url", ""))
        self._user_edit.setText(cfg.get("username", ""))
        self._pw_edit.setText(cfg.get("password", ""))

    def _current_cfg(self) -> dict:
        return {
            "url":      self._url_edit.text().strip(),
            "username": self._user_edit.text().strip(),
            "password": self._pw_edit.text(),
        }

    # ── 연결 테스트 ───────────────────────────────────────────
    def _on_test(self):
        cfg = self._current_cfg()
        if not cfg["url"] or not cfg["username"]:
            self._test_lbl.setText("URL / ID를 먼저 입력해주세요.")
            self._test_lbl.setStyleSheet(f"color:{C.RED}; background:transparent;")
            return
        self._test_btn.setEnabled(False)
        self._test_lbl.setText("연결 중...")
        self._test_lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")
        try:
            fetcher = CbFetcher(cfg["url"], cfg["username"], cfg["password"])
            msg = fetcher.test_connection()
            self._test_lbl.setText(msg)
            self._test_lbl.setStyleSheet(f"color:{C.GREEN}; background:transparent;")
            # 연결 성공 → 자동 저장 + 시그널
            save_config(cfg)
            self.connected.emit()
        except Exception as e:
            self._test_lbl.setText(str(e)[:70])
            self._test_lbl.setStyleSheet(f"color:{C.RED}; background:transparent;")
        finally:
            self._test_btn.setEnabled(True)

    # ── 확인 (저장 후 다이얼로그 닫기) ────────────────────────
    def _on_save(self):
        save_config(self._current_cfg())
        # 입력값을 저장하고 즉시 다이얼로그를 닫는다. (확인 = OK 의미)
        self.accept()


# ══════════════════════════════════════════════════════════════
#  _FetchSelectDialog — "CB 불러오기" 전 트래커 선택 팝업
# ══════════════════════════════════════════════════════════════
class _FetchSelectDialog(QDialog):
    """
    사용자가 어떤 트래커의 이슈를 가져올지 체크박스로 선택하는 모달.
    CbSectionWidget._on_fetch 에서 accordion_list_mode 일 때 사용.
    """

    def __init__(self, tracker_id_map: dict, section_color: str = C.BLUE,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("가져올 트래커 선택")
        self.setModal(True)
        self._tracker_id_map = tracker_id_map
        self._color = section_color
        self._checkboxes: dict = {}
        self._count_lbl: QLabel = None
        self._fetch_btn: QPushButton = None
        self._build()

    def _build(self):
        self.setFixedSize(440, 520)
        self.setStyleSheet(f"QDialog {{ background:{C.BG_PANEL}; }}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(12)

        # ── 헤더 ───────────────────────────────────────
        title = QLabel("📥  가져올 트래커 선택")
        title.setFont(QFont(C.FUI, 13, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color:{self._color}; background:transparent;")
        lay.addWidget(title)

        desc = QLabel(
            "체크한 트래커의 이슈 목록만 Codebeamer 에서 가져옵니다.\n"
            "선택이 많을수록 조회 시간이 길어집니다.")
        desc.setFont(QFont(C.FUI, 9))
        desc.setStyleSheet(f"color:{C.T3}; background:transparent;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # ── 전체 선택 / 해제 + 카운트 ──────────────────
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        for label, state in [("✓  전체 선택", True), ("✕  전체 해제", False)]:
            b = QPushButton(label)
            b.setFixedHeight(26)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background:{C.BDR2}; color:{C.T2};"
                f"  border:none; border-radius:4px;"
                f"  font-size:10px; padding:0 12px; }}"
                f"QPushButton:hover {{"
                f"  background:{_ca(self._color, '22')};"
                f"  color:{self._color}; }}")
            b.clicked.connect(lambda _, s=state: self._set_all(s))
            ctrl_row.addWidget(b)
        ctrl_row.addStretch()
        self._count_lbl = QLabel("0 / 0 선택")
        self._count_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        self._count_lbl.setStyleSheet(
            f"color:{self._color}; background:transparent;")
        ctrl_row.addWidget(self._count_lbl)
        lay.addLayout(ctrl_row)

        # ── 체크박스 리스트 (스크롤) ─────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border:1px solid {C.BDR};"
            f"  border-radius:6px; background:{C.BG_CARD}; }}"
            f"QScrollBar:vertical {{ width:6px; background:transparent; }}"
            f"QScrollBar::handle:vertical {{"
            f"  background:{C.BDR2}; border-radius:3px; }}")

        container = QWidget()
        container.setStyleSheet(f"background:{C.BG_CARD};")
        vl = QVBoxLayout(container)
        vl.setContentsMargins(6, 6, 6, 6)
        vl.setSpacing(2)

        cb_ss = (
            f"QCheckBox {{"
            f"  color:{C.T0}; background:transparent;"
            f"  spacing:10px; font-size:10pt;"
            f"  font-weight:600; padding:2px; border:none; }}"
            f"QCheckBox::indicator {{"
            f"  width:15px; height:15px;"
            f"  border-radius:3px;"
            f"  border:1.5px solid {C.BDR2};"
            f"  background:{C.BG_INPUT}; }}"
            f"QCheckBox::indicator:hover {{"
            f"  border-color:{self._color}; }}"
            f"QCheckBox::indicator:checked {{"
            f"  background:{self._color};"
            f"  border-color:{self._color};"
            f"  image:url(none); }}")

        any_row = False
        for name, tid in self._tracker_id_map.items():
            if not tid or not str(tid).strip():
                continue
            any_row = True
            row = QWidget()
            row.setStyleSheet(
                f"QWidget {{ background:transparent; }}"
                f"QWidget:hover {{"
                f"  background:{_ca(self._color, '14')};"
                f"  border-radius:4px; }}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 6, 12, 6)
            rl.setSpacing(10)
            cb = QCheckBox(name)
            cb.setStyleSheet(cb_ss)
            cb.toggled.connect(self._update_count)
            rl.addWidget(cb)
            rl.addStretch()
            id_lbl = QLabel(f"ID {tid}")
            id_lbl.setFont(QFont(C.FUI, 8))
            id_lbl.setStyleSheet(
                f"color:{C.T3}; background:{C.BG_APP};"
                f"border:1px solid {C.BDR}; border-radius:4px;"
                f"padding:1px 6px;")
            rl.addWidget(id_lbl)
            vl.addWidget(row)
            self._checkboxes[name] = cb

        if not any_row:
            empty = QLabel("등록된 트래커가 없습니다.\n"
                           "좌측 CB 설정에서 트래커를 먼저 추가하세요.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{C.T3}; background:transparent;"
                f"padding:40px; font-size:10pt;")
            vl.addWidget(empty)

        vl.addStretch()
        scroll.setWidget(container)
        lay.addWidget(scroll, stretch=1)

        # ── 하단 버튼 ───────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setFixedWidth(84)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BG_CARD}; color:{C.T2};"
            f"  border:1px solid {C.BDR}; border-radius:6px;"
            f"  font-size:11px; }}"
            f"QPushButton:hover {{"
            f"  background:{C.BG_HOVER}; color:{C.T0}; }}")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._fetch_btn = QPushButton("📥  가져오기")
        self._fetch_btn.setFixedHeight(36)
        self._fetch_btn.setFixedWidth(130)
        self._fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fetch_btn.setStyleSheet(
            f"QPushButton {{ background:{self._color};"
            f"  color:#FFFFFF; border:none; border-radius:6px;"
            f"  font-size:11px; font-weight:bold; }}"
            f"QPushButton:hover {{"
            f"  background:{_ca(self._color, 'DD')}; }}"
            f"QPushButton:disabled {{"
            f"  background:{C.BDR2}; color:{C.T3}; }}")
        self._fetch_btn.clicked.connect(self.accept)
        self._fetch_btn.setEnabled(False)
        btn_row.addWidget(self._fetch_btn)

        lay.addLayout(btn_row)
        self._update_count()

    def _set_all(self, checked: bool):
        for cb in self._checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        self._update_count()

    def _update_count(self):
        total = len(self._checkboxes)
        sel = sum(1 for cb in self._checkboxes.values() if cb.isChecked())
        if self._count_lbl:
            self._count_lbl.setText(f"{sel} / {total} 선택")
        if self._fetch_btn:
            self._fetch_btn.setEnabled(sel > 0)

    def get_selected(self) -> dict:
        """체크된 항목만 {tracker_name: tracker_id} dict 로 반환."""
        return {
            name: self._tracker_id_map[name]
            for name, cb in self._checkboxes.items()
            if cb.isChecked()
        }
