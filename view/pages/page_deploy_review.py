"""page_deploy_review.py — ⑨ 배포 리뷰 페이지.

표 1 — ①~⑧ 진행 점검표 (결과 출력 전용 — 사용자 편집 불가)
       trackers[page_key] 가 채워져 있으면 PASS, 비어있으면 FAIL.
       링크는 https://codebeamer.slworld.com/cb/tracker/{ID} 로 자동 생성.

표 2 — 결재란 (작성자 / 검토자)
       배포 승인은 Codebeamer 측에서 진행 — 이 페이지에서는 결재 X.

페이지의 [📥 불러오기] 는 project_state JSON 에서 trackers 를 로드해
①~⑨ 점검표 결과/링크를 갱신한다.
"""

from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QGridLayout, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QDateEdit, QScrollArea,
)

from config import C
from ._common import BasePage
from core.project_state import build_tracker_url, build_issue_url


# ── 달력 팝업 라이트 모드 QSS ─────────────────────────────────
# QDateEdit 의 calendarPopup 은 OS 테마(다크) 를 그대로 받으므로
# 본문 카드와 맞도록 화이트 배경 + 슬레이트/블루 톤으로 명시 지정.
_LIGHT_CAL_QSS = (
    "QCalendarWidget QWidget { background:#FFFFFF; color:#1E293B; }"
    "QCalendarWidget QWidget#qt_calendar_navigationbar {"
    "  background:#EFF6FF; border-bottom:1px solid #BFDBFE; }"
    "QCalendarWidget QToolButton {"
    "  background:transparent; color:#1D4ED8;"
    "  border:none; border-radius:4px;"
    "  padding:4px 10px; font-weight:600; font-size:11px; }"
    "QCalendarWidget QToolButton:hover {"
    "  background:#DBEAFE; color:#1E40AF; }"
    "QCalendarWidget QToolButton::menu-indicator { image:none; }"
    "QCalendarWidget QSpinBox {"
    "  background:#FFFFFF; color:#1E293B;"
    "  border:1px solid #CBD5E1; border-radius:3px;"
    "  padding:2px 4px; selection-background-color:#3B82F6;"
    "  selection-color:#FFFFFF; }"
    "QCalendarWidget QMenu {"
    "  background:#FFFFFF; color:#1E293B;"
    "  border:1px solid #CBD5E1; }"
    "QCalendarWidget QMenu::item {"
    "  background:transparent; padding:4px 16px; }"
    "QCalendarWidget QMenu::item:selected {"
    "  background:#DBEAFE; color:#1D4ED8; }"
    "QCalendarWidget QAbstractItemView {"
    "  background:#FFFFFF; color:#1E293B;"
    "  selection-background-color:#3B82F6;"
    "  selection-color:#FFFFFF;"
    "  alternate-background-color:#F8FAFC;"
    "  outline:none; }"
    "QCalendarWidget QAbstractItemView:disabled { color:#94A3B8; }"
    "QCalendarWidget QAbstractItemView:enabled {"
    "  font-size:11px; }"
)


# ── 4단계 (2026-06) 새 양식 — 변경점 N 행 + 컬럼별 PASS/NG ────────
# 컬럼: [분류] | 사양변경 리스트 | SRS | SAD | SDD | 정적 | 코드리뷰 | 테스트 | OPEN/CLOSE

_DR_W_CAT    = 100   # '사양변경' 글자 짤리지 않게 확대
_DR_W_TITLE  = 260
_DR_W_RESULT = 100   # SRS/SAD/SDD/정적/코드리뷰/테스트 각각
_DR_W_STATE  = 110

_DR_HEADER_H = 36
_DR_ROW_H    = 36
_DR_RESULT_ROW_H = 36   # ⑧ 과 동일 — 데이터 행 높이와 일치

# 셀 공통 border (셀 사이 흰색 구분선)
_DR_CELL_BORDER = "border:1px solid #E2E8F0; border-right:2px solid #FFFFFF;"


# ══════════════════════════════════════════════════════════════
#  점검표 셀 헬퍼 (사용자 편집 불가 — 전부 QLabel)
# ══════════════════════════════════════════════════════════════
_TBL_HDR_BG = C.BLUE   # 하늘색 (#8BBDD0) — ⑧⑨ 표 헤더 공통


def _dr_hdr(text: str, width: int = 0) -> QLabel:
    lb = QLabel(text)
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
    lb.setStyleSheet(
        f"color:#FFFFFF; background:{_TBL_HDR_BG};"
        f" border:1px solid {_TBL_HDR_BG};"
        f" border-right:2px solid #FFFFFF;"
        f" padding:0;")
    lb.setMinimumHeight(_DR_HEADER_H)
    lb.setMaximumHeight(_DR_HEADER_H)
    if width > 0:
        lb.setMinimumWidth(width)
    return lb


def _dr_item(text: str, width: int = 0) -> QLabel:
    lb = QLabel(text)
    lb.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    lb.setFont(QFont(C.FUI, 10, QFont.Weight.DemiBold))
    lb.setStyleSheet(
        f"color:{C.T0}; background:{C.BG_CARD};"
        f" border:1px solid {C.BDR}; padding:4px 14px;")
    lb.setMinimumHeight(_DR_ROW_H)
    if width > 0:
        lb.setMinimumWidth(width)
    return lb


def _dr_result(width: int = 0) -> QLabel:
    """결과 셀 (PASS/FAIL 자동 표시 — 클릭 / 편집 불가)."""
    lb = QLabel("-")
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
    lb.setStyleSheet(
        f"color:{C.T3}; background:{C.BG_CARD};"
        f" border:1px solid {C.BDR}; padding:4px 8px;")
    lb.setMinimumHeight(_DR_ROW_H)
    if width > 0:
        lb.setMinimumWidth(width)
    return lb


def _dr_link() -> QLabel:
    """링크 셀 — 트래커 URL 표시 (클릭 가능 a 태그)."""
    lb = QLabel("-")
    lb.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    lb.setFont(QFont(C.FUI, 10))
    lb.setStyleSheet(
        f"color:{C.T1}; background:{C.BG_CARD};"
        f" border:1px solid {C.BDR}; padding:4px 12px;")
    lb.setMinimumHeight(_DR_ROW_H)
    lb.setOpenExternalLinks(True)
    lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    return lb


def _dr_color_cell(width: int = 0) -> QLabel:
    """변경점 행의 SWE/정적/코드리뷰/테스트 셀 — 색상 + 트래커 링크.
    apply_results 에서 _apply_cell 로 색상 갱신.
    """
    lb = QLabel("-")
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
    lb.setStyleSheet(
        f"color:{C.T3}; background:{C.BG_CARD};"
        f" {_DR_CELL_BORDER} padding:4px 6px;")
    lb.setMinimumHeight(_DR_ROW_H)
    if width > 0:
        lb.setMinimumWidth(width)
    lb.setOpenExternalLinks(True)
    lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    return lb


def _dr_state_combo(width: int = 0):
    """OPEN/CLOSE 토글 — ⑧ OPEN 항목 페이지의 _StateToggle 재사용."""
    from .page_open_items import _StateToggle
    tg = _StateToggle()
    if width > 0:
        tg.setMinimumWidth(width)
    return tg


def _dr_result_summary(width: int = 0) -> QLabel:
    """Result 행 셀 — PASS/NG 표시 (편집 불가)."""
    lb = QLabel("-")
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
    lb.setStyleSheet(
        f"color:{C.T3}; background:{C.BG_CARD};"
        f" {_DR_CELL_BORDER} padding:4px 6px;")
    lb.setMinimumHeight(_DR_RESULT_ROW_H)
    lb.setMaximumHeight(_DR_RESULT_ROW_H)
    if width > 0:
        lb.setMinimumWidth(width)
    return lb


def _apply_pass_fail(lbl: QLabel, value: str):
    """PASS / FAIL 색상 + 텍스트 적용."""
    v = (value or "").upper()
    if v == "PASS":
        fg, bg = "#15803D", "#DCFCE7"
    elif v == "FAIL":
        fg, bg = "#B91C1C", "#FEE2E2"
    else:
        fg, bg = C.T3, C.BG_CARD
        v = "-"
    lbl.setText(v)
    lbl.setStyleSheet(
        f"color:{fg}; background:{bg};"
        f" border:1px solid {C.BDR}; padding:4px 8px;"
        f" font-weight:700;")


# ══════════════════════════════════════════════════════════════
#  결재란 — 작성자 / 검토자 / 배포 승인자
# ══════════════════════════════════════════════════════════════
class _ApprovalBox(QFrame):
    """결재란 한 칸. editable=False 면 모든 입력 비활성 + 안내문 노출."""

    def __init__(self, title: str, *,
                 editable: bool = True,
                 hint: str = "",
                 parent=None):
        super().__init__(parent)
        self._editable = bool(editable)
        self.setObjectName("ap_box")
        # 비활성 칸은 살짝 음영 배경으로 시각적으로 구분
        bg = C.BG_CARD if self._editable else C.BG_PANEL
        self.setStyleSheet(
            f"#ap_box {{ background:{bg};"
            f"  border:1px solid {C.BDR}; border-radius:6px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10); lay.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(
            f"color:{C.BLUE_DK}; background:{C.BLUE_LT};"
            f" border-radius:4px; padding:4px 0;")
        lay.addWidget(title_lbl)

        # 소속 / 이름 / 날짜
        self.dept = self._mk_le("소속")
        lay.addLayout(self._row("소속", self.dept))
        self.name = self._mk_le("이름")
        lay.addLayout(self._row("이름", self.name))
        self.date = self._mk_date()
        lay.addLayout(self._row("날짜", self.date))

        # 비활성 안내 — editable=False 일 때만
        if hint:
            hint_lbl = QLabel(hint)
            hint_lbl.setWordWrap(True)
            hint_lbl.setFont(QFont(C.FUI, 8))
            hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint_lbl.setStyleSheet(
                f"color:{C.T2}; background:#FEF3C7;"
                f" border:1px solid #FCD34D; border-radius:4px;"
                f" padding:6px 8px; margin-top:2px;")
            lay.addWidget(hint_lbl)

        # editable=False → 모든 입력 위젯 비활성
        if not self._editable:
            self.dept.setReadOnly(True)
            self.name.setReadOnly(True)
            self.dept.setEnabled(False)
            self.name.setEnabled(False)
            self.date.setEnabled(False)
            # 시각적으로도 흐릿하게
            for w in (self.dept, self.name, self.date):
                w.setStyleSheet(
                    w.styleSheet() +
                    f"\nQLineEdit:disabled, QDateEdit:disabled {{"
                    f"  background:#F1F5F9; color:{C.T3};"
                    f"  border-color:{C.BDR}; }}")

    def _mk_le(self, ph: str) -> QLineEdit:
        le = QLineEdit()
        le.setPlaceholderText(ph)
        le.setFixedHeight(28)
        le.setStyleSheet(
            f"QLineEdit {{ background:{C.BG_INPUT}; color:{C.T0};"
            f"  border:1px solid {C.BDR}; border-radius:4px;"
            f"  padding:2px 8px; font-size:10px; }}"
            f"QLineEdit:focus {{ border-color:{C.BLUE}; }}")
        return le

    def _mk_date(self) -> QDateEdit:
        de = QDateEdit()
        de.setCalendarPopup(True)
        de.setDisplayFormat("yyyy-MM-dd")
        de.setDate(QDate.currentDate())
        de.setFixedHeight(28)
        de.setStyleSheet(
            f"QDateEdit {{ background:{C.BG_INPUT}; color:{C.T0};"
            f"  border:1px solid {C.BDR}; border-radius:4px;"
            f"  padding:2px 8px; font-size:10px; }}"
            f"QDateEdit:focus {{ border-color:{C.BLUE}; }}")
        # 달력 팝업을 라이트 모드로 — OS 다크 테마 무시
        cal = de.calendarWidget()
        if cal is not None:
            cal.setStyleSheet(_LIGHT_CAL_QSS)
        return de

    def _row(self, lbl_text: str, widget) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(6)
        lb = QLabel(lbl_text)
        lb.setFixedWidth(40)
        lb.setFont(QFont(C.FUI, 9))
        lb.setStyleSheet(f"color:{C.T2}; background:transparent;")
        row.addWidget(lb); row.addWidget(widget, 1)
        return row

    # ── 직렬화 ──────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "dept": self.dept.text().strip(),
            "name": self.name.text().strip(),
            "date": self.date.date().toString("yyyy-MM-dd")
                    if self.date.date().isValid() else "",
        }

    def apply_dict(self, d: dict):
        if not isinstance(d, dict):
            return
        self.dept.setText(str(d.get("dept") or ""))
        self.name.setText(str(d.get("name") or ""))
        ds = str(d.get("date") or "").strip()
        if ds:
            qd = QDate.fromString(ds, "yyyy-MM-dd")
            if qd.isValid():
                self.date.setDate(qd)


# ══════════════════════════════════════════════════════════════
#  DeployReviewPage
# ══════════════════════════════════════════════════════════════
class DeployReviewPage(BasePage):
    """⑨ 배포 리뷰."""

    load_requested = pyqtSignal()   # [📥 불러오기] 클릭
    saved_now      = pyqtSignal()   # [💾 페이지 저장] — main.py 가 project_state 저장

    def __init__(self, parent=None):
        super().__init__("⑨", "배포 리뷰", parent)
        # 레거시 호환 — 일부 외부 호출이 _rows / _tracker_ids 를 참조할 수 있음
        self._rows: dict = {}
        self._tracker_ids: dict = {}
        # 4단계 새 양식 — 동적 데이터 행
        self._data_rows: list = []
        self._result_widgets: dict = {}
        self._build_content()

    def _build_content(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget(); inner.setStyleSheet(f"background:{C.BG_APP};")
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(20, 18, 20, 18); outer.setSpacing(14)

        outer.addWidget(self._build_checklist_card())
        outer.addWidget(self._build_approval_card())
        outer.addStretch()

        scroll.setWidget(inner)
        self.add_body(scroll)

    # ── 카드 1 : 진행 점검표 (결과 출력 전용) ────────────────
    def _build_checklist_card(self) -> QFrame:
        card = QFrame(); card.setObjectName("dr_card")
        card.setStyleSheet(
            f"#dr_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # 헤더 (제목 + 불러오기)
        hdr = QFrame(); hdr.setFixedHeight(44)
        hdr.setStyleSheet(
            f"background:{C.BG_PANEL}; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 22)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        hl.addWidget(accent)
        t = QLabel("✅  배포 전 진행 점검표")
        t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()

        self.load_btn = QPushButton("📥  불러오기")
        self.load_btn.setFixedHeight(28)
        self.load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_btn.setToolTip(
            "현재 프로젝트 + 버전의 project_state JSON 에서 각 페이지 트래커 ID 를\n"
            "불러와 결과 / 링크를 자동 갱신합니다.")
        self.load_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}")
        self.load_btn.clicked.connect(self.load_requested.emit)
        hl.addWidget(self.load_btn)

        # 페이지 저장 — 다른 페이지의 [💾 페이지 저장] 과 동일 동작
        self.save_now_btn = QPushButton("💾  페이지 저장")
        self.save_now_btn.setFixedHeight(28)
        self.save_now_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_now_btn.setToolTip(
            "현재 변경점 행 상태 + 결재란 내용을 즉시 저장합니다.")
        self.save_now_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.BLUE};"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
        self.save_now_btn.clicked.connect(self.saved_now.emit)
        hl.addWidget(self.save_now_btn)
        cl.addWidget(hdr)

        # 본문 — 그리드 표
        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 14, 14, 14); bl.setSpacing(0)
        bl.addWidget(self._build_grid_table())

        # 안내 문구 — 점검표는 결과 출력 전용
        hint = QLabel(
            "ℹ  점검표는 [📥 불러오기] 클릭 시 결과가 자동으로 출력됩니다.")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{C.T3}; background:transparent;"
            f" font-size:10px; padding:10px 2px 0 2px;")
        bl.addWidget(hint)

        cl.addWidget(body)
        return card

    def _build_grid_table(self) -> QFrame:
        """변경점 N 행 + Result 1행 표.

        헤더: [분류] | 사양변경 리스트 | SRS | SAD | SDD | 정적 | 코드리뷰 | 테스트 | OPEN/CLOSE
        데이터 행은 set_change_items() / apply_results() 가 동적 생성.
        """
        wrap = QFrame()
        wrap.setStyleSheet("background:transparent;")
        self._grid = QGridLayout(wrap)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(0)

        # 헤더 행
        cols = [
            ("[분류]",         _DR_W_CAT),
            ("사양변경 리스트", _DR_W_TITLE),
            ("SRS",            _DR_W_RESULT),
            ("SAD",            _DR_W_RESULT),
            ("SDD",            _DR_W_RESULT),
            ("정적",            _DR_W_RESULT),
            ("코드리뷰",        _DR_W_RESULT),
            ("테스트",          _DR_W_RESULT),
            ("OPEN/CLOSE",     _DR_W_STATE),
        ]
        for c, (lbl, w) in enumerate(cols):
            self._grid.addWidget(_dr_hdr(lbl, width=w), 0, c)
        # 컬럼별 stretch 비율 — 결과 컬럼이 가로 폭 흡수해서 페이지 가득 채움
        col_stretch = (1, 4, 2, 2, 2, 2, 2, 2, 2)   # cat, title, SRS, SAD, SDD, 정적, 코드리뷰, 테스트, 상태
        for c, s in enumerate(col_stretch):
            self._grid.setColumnStretch(c, s)

        # 빈 상태 메시지
        self._empty_msg = QLabel(
            "📭  [📥 불러오기] 를 누르면 변경점이 자동으로 표시됩니다.")
        self._empty_msg.setFont(QFont(C.FUI, 10))
        self._empty_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_msg.setStyleSheet(
            f"color:{C.T3}; background:{C.BG_CARD};"
            f" border:1px solid {C.BDR}; padding:20px;")
        self._grid.addWidget(self._empty_msg, 1, 0, 1, 9)

        # 동적 행 보관
        # rows: [{cat, title, change_id, widgets:{srs, sad, sdd, static, review, test, state}}]
        self._data_rows: list[dict] = []
        # Result 행 보관 — set_change_items 이후 마지막 행에 생성
        self._result_widgets: dict = {}
        return wrap

    # ── 카드 2 : 결재란 ─────────────────────────────────────
    def _build_approval_card(self) -> QFrame:
        card = QFrame(); card.setObjectName("ap_card")
        card.setStyleSheet(
            f"#ap_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        hdr = QFrame(); hdr.setFixedHeight(44)
        hdr.setStyleSheet(
            f"background:{C.BG_PANEL}; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 22)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        hl.addWidget(accent)
        t = QLabel("✍  결재란")
        t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()
        cl.addWidget(hdr)

        body = QWidget(); body.setStyleSheet("background:transparent;")
        # 작성자/검토자 좌우 배치
        bl = QHBoxLayout(body); bl.setContentsMargins(14, 14, 14, 14); bl.setSpacing(10)

        # 작성자 / 검토자 — 입력 가능 (배포 승인자는 CB 에서 직접 결재)
        self.box_writer   = _ApprovalBox("작성자",   editable=True)
        self.box_reviewer = _ApprovalBox("검토자",   editable=True)

        bl.addWidget(self.box_writer, 1)
        bl.addWidget(self.box_reviewer, 1)
        cl.addWidget(body)
        return card

    # ── 공개 API (4단계 새 양식) ────────────────────────────
    def set_change_items(self, items: list):
        """변경점 dict 리스트 → 행 동적 생성.
        items: [{"cat": "issue/spec/hzt", "title": str, "id": str}, ...]
        """
        # 기존 데이터 행 + Result 행 정리
        self._clear_data_rows()
        if not items:
            self._empty_msg.setVisible(True)
            self._empty_msg.setText(
                "📭  변경점이 없습니다. ① 사양변경 페이지에서 먼저 입력하세요.")
            return
        self._empty_msg.setVisible(False)

        # 데이터 행
        for i, it in enumerate(items, start=1):
            self._add_data_row(i, it)
        # Result 행
        self._add_result_row(len(self._data_rows) + 1)

    def apply_results(self, results_by_id: dict, *,
                      static_link: str = "", review_text: str = "-",
                      test_link: str = "",
                      sas: dict = None) -> None:
        """변경점별 컬럼 결과 적용.

        results_by_id : {change_id: {"srs": "track_id"|"N/A"|"", "sad":..., "sdd":...}}
                        값이 트래커 ID (숫자 문자열) 면 초록 + 링크 표시
                        "N/A"  → 노란색 N/A
                        "" / X → 빨강 "없음"
        static_link   : 정적 트래커 ID (모든 행 동일)
        test_link     : 테스트 트래커 ID (모든 행 동일)
        review_text   : 코드리뷰 표시 텍스트 (4단계 보류 → "-")
        sas           : {"srs": "체크리스트 결과 트래커 ID", "sad":..., "sdd":...}
                        Result 행 아래 첨부 안내문에 사용
        """
        for r in self._data_rows:
            cid = r["change_id"]
            res = (results_by_id or {}).get(cid, {}) if isinstance(results_by_id, dict) else {}
            for col_key in ("srs", "sad", "sdd"):
                self._apply_cell(r["widgets"][col_key], res.get(col_key, ""))
            self._apply_cell(r["widgets"]["static"], static_link or "")
            self._apply_cell(r["widgets"]["review"], review_text or "-")
            self._apply_cell(r["widgets"]["test"],   test_link or "")

        # Result 행 — 컬럼별 PASS/NG 계산
        self._refresh_result_row(sas or {})

    # ── 데이터 행 헬퍼 ──────────────────────────────────────
    def _add_data_row(self, idx: int, item: dict):
        cat   = str(item.get("cat") or "")
        title = str(item.get("title") or "")
        cid   = str(item.get("id") or "")
        # 카테고리 한글 라벨
        cat_text = {"spec": "사양변경", "issue": "이슈",
                    "hzt": "수평전개"}.get(cat, cat or "-")

        cat_lbl   = _dr_item(cat_text, width=_DR_W_CAT)
        cat_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl = _dr_item(f"{idx}. {title or '(제목 없음)'}", width=_DR_W_TITLE)
        widgets = {
            "srs":    _dr_color_cell(_DR_W_RESULT),
            "sad":    _dr_color_cell(_DR_W_RESULT),
            "sdd":    _dr_color_cell(_DR_W_RESULT),
            "static": _dr_color_cell(_DR_W_RESULT),
            "review": _dr_color_cell(_DR_W_RESULT),
            "test":   _dr_color_cell(_DR_W_RESULT),
            "state":  _dr_state_combo(_DR_W_STATE),
        }
        row_idx = len(self._data_rows) + 1   # 헤더 다음
        self._grid.addWidget(cat_lbl,   row_idx, 0)
        self._grid.addWidget(title_lbl, row_idx, 1)
        for c, key in enumerate(("srs", "sad", "sdd", "static",
                                 "review", "test", "state"), start=2):
            self._grid.addWidget(widgets[key], row_idx, c)

        self._data_rows.append({
            "cat":       cat,
            "title":     title,
            "change_id": cid,
            "widgets":   {**widgets, "cat_lbl": cat_lbl, "title_lbl": title_lbl},
        })

    def _add_result_row(self, row_idx: int):
        """Result 행 생성. 각 컬럼별 PASS/NG/-."""
        result_lbl = QLabel("Result")
        result_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        result_lbl.setStyleSheet(
            f"color:#FFFFFF; background:{_TBL_HDR_BG};"
            f" border:1px solid {_TBL_HDR_BG}; padding:4px 8px;")
        result_lbl.setMinimumHeight(_DR_RESULT_ROW_H)
        result_lbl.setMaximumHeight(_DR_RESULT_ROW_H)
        self._grid.addWidget(result_lbl, row_idx, 0, 1, 2)

        self._result_widgets = {}
        for c, key in enumerate(("srs", "sad", "sdd", "static",
                                 "review", "test", "state"), start=2):
            cell = _dr_result_summary(_DR_W_RESULT if key != "state" else _DR_W_STATE)
            self._grid.addWidget(cell, row_idx, c)
            self._result_widgets[key] = cell

    def _refresh_result_row(self, sas_trackers: dict):
        """각 컬럼별 상태 → Result 셀 PASS/NG.

        규칙:
          · N/A 포함 시 PASS 로 처리 (사용자 협의 완료)
          · 모두 트래커 ID(초록) 또는 N/A 면 PASS
          · X(없음) 하나라도 있으면 NG
        """
        for col_key in ("srs", "sad", "sdd", "static", "review", "test"):
            values = [r["widgets"][col_key].property("status") or ""
                      for r in self._data_rows]
            if not values:
                self._set_result(col_key, "-")
                continue
            has_red = any(v == "red" for v in values)
            if has_red:
                self._set_result(col_key, "NG")
            else:
                # 모두 green / yellow / 빈값 — PASS
                self._set_result(col_key, "PASS")
        # 상태(OPEN/CLOSE) 컬럼의 Result — 전체 CLOSE 면 PASS, 아니면 NG
        if self._data_rows:
            states = [r["widgets"]["state"].currentText() for r in self._data_rows]
            self._set_result(
                "state", "PASS" if all(s == "CLOSE" for s in states) else "NG")
        else:
            self._set_result("state", "-")

        # SRS/SAD/SDD 체크리스트 결과 트래커 첨부 안내문 (Result 셀 아래 작은 텍스트)
        sas = sas_trackers or {}
        attach_hints = {
            "srs": f"+ SRS 체크리스트 결과 #{sas.get('srs', '')}" if sas.get("srs") else "",
            "sad": f"+ SAD 체크리스트 결과 #{sas.get('sad', '')}" if sas.get("sad") else "",
            "sdd": f"+ SDD 체크리스트 결과 #{sas.get('sdd', '')}" if sas.get("sdd") else "",
        }
        for k, hint in attach_hints.items():
            cell = self._result_widgets.get(k)
            if cell is not None and hint:
                cell.setToolTip(hint)

    def _set_result(self, col_key: str, value: str):
        cell = self._result_widgets.get(col_key)
        if cell is None:
            return
        v = (value or "-").upper()
        if v == "PASS":
            fg, bg = "#15803D", "#DCFCE7"
        elif v == "NG":
            fg, bg = "#B91C1C", "#FEE2E2"
        else:
            fg, bg = C.T3, C.BG_CARD
        cell.setText(v)
        cell.setStyleSheet(
            f"color:{fg}; background:{bg};"
            f" {_DR_CELL_BORDER} padding:4px 6px;"
            f" font-weight:700; font-size:11px;")

    def _apply_cell(self, cell: QLabel, value: str):
        """변경점 셀 한 칸의 색상 + 텍스트 적용.

        value:
          · 숫자/문자열 (트래커 ID) → 초록 + 링크
          · 'N/A'                  → 노란색
          · ''/'X'                 → 빨강 (없음)
          · '-' / 그 외             → 회색
        """
        v = (value or "").strip()
        if v.upper() == "N/A":
            cell.setText("N/A")
            cell.setStyleSheet(
                f"color:#92400E; background:#FEF3C7;"
                f" {_DR_CELL_BORDER} padding:4px 6px;"
                f" font-weight:700;")
            cell.setProperty("status", "yellow")
            cell.setToolTip("이 페이지의 변경 없음 — 단계 N/A")
            return
        if v in ("", "X", "x", "-"):
            cell.setText("없음")
            cell.setStyleSheet(
                f"color:#B91C1C; background:#FEE2E2;"
                f" {_DR_CELL_BORDER} padding:4px 6px;"
                f" font-weight:700;")
            cell.setProperty("status", "red")
            cell.setToolTip("이 변경점이 매칭된 트래커가 없음")
            return
        # 이슈 ID (콤마로 여러개 가능) — 초록 + 각 ID 별 링크
        ids = [s.strip() for s in v.split(",") if s.strip()]
        if not ids:
            cell.setText("-")
            return
        # 각 ID 별로 /cb/issue/{ID} 링크
        links = []
        for iid in ids:
            url = build_issue_url(iid)
            links.append(
                f'<a href="{url}" style="color:#15803D; text-decoration:underline;">#{iid}</a>')
        cell.setText(", ".join(links))
        cell.setStyleSheet(
            f"color:#15803D; background:#DCFCE7;"
            f" {_DR_CELL_BORDER} padding:4px 6px;"
            f" font-weight:700;")
        cell.setProperty("status", "green")
        cell.setToolTip("CB 에서 이슈 열기")

    def _clear_data_rows(self):
        """헤더(row 0) 외 모든 데이터 행 + Result 행 제거."""
        for r in self._data_rows:
            for w in r["widgets"].values():
                try:
                    w.setParent(None); w.deleteLater()
                except Exception:
                    pass
        self._data_rows.clear()
        for w in self._result_widgets.values():
            try:
                w.setParent(None); w.deleteLater()
            except Exception:
                pass
        self._result_widgets.clear()
        # Result 행 라벨 (col 0~1 spanned) 도 제거 — grid 의 last 행 위젯들 정리
        # 단순화: Result 행은 항상 마지막에 생성되므로 _result_widgets 만 비워두면 OK

    # ── 레거시 호환 — main.py 가 set_trackers 호출 ───────────
    def set_trackers(self, trackers: dict):
        """레거시 호환 — page_key 트래커 ID dict 를 받음.
        새 양식에서는 변경점 행이 필요하므로, 변경점 없을 땐 빈 상태 표시.
        실제 동작은 cb_controller.on_deploy_review_load 가 set_change_items +
        apply_results 직접 호출하는 흐름으로 변경됨.
        """
        # 무시 — 새 컨트롤러가 set_change_items / apply_results 를 호출함.
        pass

    # ── CB 업로드용 마크다운 ──────────────────────────────────
    def render_markdown(self) -> str:
        lines = [
            "## ⑨ 배포 리뷰",
            "",
            "### 변경점별 단계 점검표",
            "",
            "| 분류 | 사양변경 리스트 | SRS | SAD | SDD | 정적 | 코드리뷰 | 테스트 | OPEN/CLOSE |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        cat_text_map = {"spec": "사양변경", "issue": "이슈", "hzt": "수평전개"}
        for r in self._data_rows:
            w = r["widgets"]
            def _txt(cell):
                # HTML 태그 제거하고 원시 텍스트 (트래커 ID 또는 N/A/없음)
                t = cell.text() or ""
                import re as _re
                return _re.sub(r"<[^>]+>", "", t).strip() or "-"
            lines.append(
                f"| {cat_text_map.get(r['cat'], r['cat'] or '-')} | "
                f"{r['title'] or '(제목 없음)'} | "
                f"{_txt(w['srs'])} | {_txt(w['sad'])} | {_txt(w['sdd'])} | "
                f"{_txt(w['static'])} | {_txt(w['review'])} | {_txt(w['test'])} | "
                f"{w['state'].currentText()} |"
            )
        # Result 행
        if self._result_widgets:
            rw = self._result_widgets
            lines.append(
                f"| **Result** | — | "
                f"**{rw['srs'].text()}** | **{rw['sad'].text()}** | **{rw['sdd'].text()}** | "
                f"**{rw['static'].text()}** | **{rw['review'].text()}** | **{rw['test'].text()}** | "
                f"**{rw['state'].text()}** |"
            )
        # 안내
        lines += [
            "",
            "> ℹ️ N/A 포함 시 Result 는 PASS 로 판정됩니다 (사용자 협의 완료).",
            "> ℹ️ 정적/테스트는 동일 트래커 첨부 시 모든 변경점에 동일 적용됩니다.",
        ]

        # 결재란
        lines += [
            "",
            "### 결재란",
            "",
            "| 역할 | 소속 | 이름 | 날짜 |",
            "|---|---|---|---|",
        ]
        for title, box in [
            ("작성자", self.box_writer),
            ("검토자", self.box_reviewer),
        ]:
            d = box.to_dict()
            lines.append(
                f"| {title} | {d['dept'] or '-'} | {d['name'] or '-'} "
                f"| {d['date'] or '-'} |")

        # 배포 승인은 CB 이슈 워크플로우에서 직접 처리
        lines += [
            "",
            "> ⓘ 배포 승인은 본 Codebeamer 이슈의 워크플로우에서 직접 진행해 주세요.",
        ]
        return "\n".join(lines)

    # ── 세션 직렬화 ─────────────────────────────────────────
    def to_state(self) -> dict:
        """project_state.json 의 deploy_review 섹션."""
        return {
            "approvals": {
                "writer":   self.box_writer.to_dict(),
                "reviewer": self.box_reviewer.to_dict(),
                # 배포 승인은 CB 측 워크플로우에서 처리 — 이 페이지에서는 저장 X
            },
        }

    def apply_state(self, d: dict):
        if not isinstance(d, dict):
            return
        approvals = d.get("approvals") or {}
        self.box_writer.apply_dict(approvals.get("writer") or {})
        self.box_reviewer.apply_dict(approvals.get("reviewer") or {})
        # 'approver' 키가 옛 저장본에 있어도 무시 (배포 승인자 칸 제거됨)
