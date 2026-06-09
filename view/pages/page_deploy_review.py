"""page_deploy_review.py — ⑨ 배포 리뷰 페이지.

표 1 — ①~⑧ 진행 점검표 (결과 출력 전용 — 사용자 편집 불가)
       trackers[page_key] 가 채워져 있으면 PASS, 비어있으면 FAIL.
       링크는 https://codebeamer.slworld.com/cb/tracker/{ID} 로 자동 생성.

표 2 — 결재란 (작성자 / 검토자 / 배포 승인자)
       사용자 입력 가능 위젯은 **작성자 / 검토자만**.
       배포 승인자는 비활성 (read-only) — Codebeamer 에서 입력 가능 안내.

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
from core.project_state import build_tracker_url


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


# ── ①~⑧ 점검표 항목 ─────────────────────────────────────────
_REVIEW_ITEMS = [
    ("spec",   "①  사양 변경"),
    ("srs",    "②  SWE.1 SRS"),
    ("sad",    "③  SWE.2 SAD"),
    ("sdd",    "④  SWE.3/4 SDD"),
    ("static", "⑤  정적 검증 결과"),
    ("review", "⑥  코드리뷰 결과"),
    ("test",   "⑦  설계자 테스트 결과"),
    ("open",   "⑧  OPEN 항목 및 잔여 조치"),
]

# 점검표 컬럼 폭
_DR_W_ITEM   = 240
_DR_W_RESULT = 120
# 링크 컬럼은 stretch

_DR_HEADER_H = 36
_DR_ROW_H    = 38


# ══════════════════════════════════════════════════════════════
#  점검표 셀 헬퍼 (사용자 편집 불가 — 전부 QLabel)
# ══════════════════════════════════════════════════════════════
def _dr_hdr(text: str, width: int = 0) -> QLabel:
    lb = QLabel(text)
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
    lb.setStyleSheet(
        f"color:#FFFFFF; background:{C.BLUE_DK};"
        f" border:1px solid {C.BLUE_DK}; padding:0;")
    lb.setMinimumHeight(_DR_HEADER_H)
    lb.setMaximumHeight(_DR_HEADER_H)
    if width > 0:
        lb.setFixedWidth(width)
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
        lb.setFixedWidth(width)
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
        lb.setFixedWidth(width)
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

    def __init__(self, parent=None):
        super().__init__("⑨", "배포 리뷰", parent)
        # {page_key: {"result": QLabel, "link": QLabel}}
        self._rows: dict = {}
        # 트래커 ID 보관 (CB 업로드 마크다운에서 사용)
        self._tracker_ids: dict = {k: "" for k, _ in _REVIEW_ITEMS}
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
        wrap = QFrame()
        wrap.setStyleSheet("background:transparent;")
        g = QGridLayout(wrap)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(0)

        # 헤더
        g.addWidget(_dr_hdr("항목",                  width=_DR_W_ITEM),   0, 0)
        g.addWidget(_dr_hdr("결과",                  width=_DR_W_RESULT), 0, 1)
        g.addWidget(_dr_hdr("링크 (Codebeamer 트래커)"),                  0, 2)

        # 데이터 행
        for idx, (key, label) in enumerate(_REVIEW_ITEMS, start=1):
            g.addWidget(_dr_item(label, width=_DR_W_ITEM),   idx, 0)
            res = _dr_result(width=_DR_W_RESULT)
            g.addWidget(res, idx, 1)
            lnk = _dr_link()
            g.addWidget(lnk, idx, 2)
            self._rows[key] = {"result": res, "link": lnk}

        g.setColumnStretch(2, 1)
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
        bl = QHBoxLayout(body); bl.setContentsMargins(14, 14, 14, 14); bl.setSpacing(10)

        # 작성자 / 검토자 — 입력 가능
        self.box_writer   = _ApprovalBox("작성자",   editable=True)
        self.box_reviewer = _ApprovalBox("검토자",   editable=True)
        # 배포 승인자 — 비활성 + Codebeamer 안내
        self.box_approver = _ApprovalBox(
            "배포 승인자 (팀장)",
            editable=False,
            hint=("ⓘ 이 칸은 프로그램에서 입력할 수 없습니다.\n"
                  "Codebeamer 에 업로드된 이슈에서 직접 결재해 주세요."),
        )

        bl.addWidget(self.box_writer)
        bl.addWidget(self.box_reviewer)
        bl.addWidget(self.box_approver)
        cl.addWidget(body)
        return card

    # ── 공개 API : 컨트롤러가 trackers 로 행 갱신 ─────────────
    def set_trackers(self, trackers: dict):
        """{page_key: tracker_id} dict 로 결과/링크 자동 채움 (사용자 편집 불가)."""
        if not isinstance(trackers, dict):
            return
        for key, row in self._rows.items():
            tid = str(trackers.get(key) or "").strip()
            self._tracker_ids[key] = tid

            # 결과 — 트래커 ID 있으면 PASS, 없으면 FAIL
            _apply_pass_fail(row["result"], "PASS" if tid else "FAIL")

            # 링크
            if tid:
                url = build_tracker_url(tid)
                row["link"].setText(
                    f'<a href="{url}" style="color:{C.BLUE};">#{tid}</a>')
            else:
                row["link"].setText("-")

    # ── CB 업로드용 마크다운 ──────────────────────────────────
    def render_markdown(self) -> str:
        lines = [
            "## ⑨ 배포 리뷰",
            "",
            "### 진행 점검표",
            "",
            "| 항목 | 결과 | 링크 |",
            "|---|---|---|",
        ]
        for key, label in _REVIEW_ITEMS:
            tid = self._tracker_ids.get(key) or ""
            result = "PASS" if tid else "FAIL"
            link = (f"[#{tid}]({build_tracker_url(tid)})" if tid else "-")
            lines.append(f"| {label} | **{result}** | {link} |")

        # 결재란
        lines += [
            "",
            "### 결재란",
            "",
            "| 역할 | 소속 | 이름 | 날짜 |",
            "|---|---|---|---|",
        ]
        for title, box in [
            ("작성자",            self.box_writer),
            ("검토자",            self.box_reviewer),
            ("배포 승인자 (팀장)", self.box_approver),
        ]:
            d = box.to_dict()
            lines.append(
                f"| {title} | {d['dept'] or '-'} | {d['name'] or '-'} "
                f"| {d['date'] or '-'} |")

        # 배포 승인자 안내
        lines += [
            "",
            "> ⓘ 배포 승인자 (팀장) 칸은 본 Codebeamer 이슈에서 직접 결재해 주세요.",
        ]
        return "\n".join(lines)

    # ── 세션 직렬화 ─────────────────────────────────────────
    def to_state(self) -> dict:
        """project_state.json 의 deploy_review 섹션."""
        return {
            "approvals": {
                "writer":   self.box_writer.to_dict(),
                "reviewer": self.box_reviewer.to_dict(),
                # 배포 승인자는 프로그램에서 입력하지 않으므로 빈 값 저장
                "approver": self.box_approver.to_dict(),
            },
        }

    def apply_state(self, d: dict):
        if not isinstance(d, dict):
            return
        approvals = d.get("approvals") or {}
        self.box_writer.apply_dict(approvals.get("writer") or {})
        self.box_reviewer.apply_dict(approvals.get("reviewer") or {})
        # 배포 승인자 — 비활성이므로 복원 안 함 (혹시 이전 저장본에 값이 있어도 무시)
        # — 향후 정책이 바뀌면 여기에 복원 로직 추가
