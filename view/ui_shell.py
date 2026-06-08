"""ui_shell.py — 9탭 세로 사이드바 + 페이지 스택 메인 셸.

레이아웃:
  ┌─────────────┬───────────────────────────────────┐
  │ SW 배포 P/L │ PageHeader (페이지 제목 + 저장/CB)│  ← 두 헤더 모두 56px,
  ├─────────────┼───────────────────────────────────┤   같은 y 에서 구분선
  │  ①  사양변경│                                   │
  │     ↓       │     선택된 페이지 본문            │
  │  ②  SWE.1   │                                   │
  │     ↓       │                                   │
  │  ...        │                                   │
  │  ⑨  배포    │                                   │
  └─────────────┴───────────────────────────────────┘

번호 클릭 → 해당 페이지 활성화 + 번호/이름 색상 강조 (글자 크기는 동일)
화살표(↓)는 번호 사이의 단순 시각 요소 — 번호 칸 정중앙 정렬.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QStackedWidget, QScrollArea, QSizePolicy,
)

from config import C


# 사이드바 항목 — (key, 번호 글자, 한글 제목)
SIDEBAR_ITEMS = [
    ("spec",    "①", "사양 변경"),
    ("srs",     "②", "SWE.1 SRS"),
    ("sad",     "③", "SWE.2 SAD"),
    ("sdd",     "④", "SWE.3 SDD"),
    ("static",  "⑤", "정적 검증 결과"),
    ("review",  "⑥", "코드리뷰 결과"),
    ("test",    "⑦", "설계자 테스트 결과"),
    ("open",    "⑧", "OPEN 항목 및 잔여 조치"),
    ("deploy",  "⑨", "배포 리뷰"),
]

# 사이드바 헤더 높이 — PageHeader 와 동일하게 유지해 구분선이 가로로 일치.
# ⚠ 변경 시 view/pages/_common.py PageHeader.setFixedHeight(...) 도 함께 변경 필수.
SIDEBAR_HEADER_H = 68

# 번호 배지 크기.
NUM_BADGE = 26
# 카드 외부 좌우 margin — ArrowLabel 도 동일 margin 으로 정렬.
ITEM_MARGIN_L = 12
ITEM_MARGIN_R = 12
# 카드 내부 좌측 padding (배지가 시작되는 위치).
CARD_INNER_LEFT = 10
# 배지 + 텍스트 사이 spacing.
BADGE_SPACING = 12

# ── 사이드바 전용 액센트 컬러 (프로그램 메인 블루 톤과 통일) ──
# 기존 Indigo(#4F46E5) → C.BLUE 계열로 교체.
# 같은 톤만 쓰면 그라데이션이 밋밋해지므로 BLUE → 더 진한 블루(#4E9DB5)
# 로 폭을 줘서 헤더/활성 카드의 시각적 무게를 유지.
SB_ACCENT       = C.BLUE        # #8BBDD0 — 활성 카드 시작색 (전체 등록 버튼과 동일)
SB_ACCENT_DK    = "#4E9DB5"     # 더 진한 블루 — 활성 호버 / 헤더 하단 보더
SB_ACCENT_LT    = C.BLUE_LT     # #DCEEF8 — 비활성 호버 배경 (체크박스 호버 등과 통일)
SB_ACCENT_MID   = C.ACCENT_H    # #6AAABF — 비활성 번호 색 / ↓ 화살표 색
SB_GRADIENT     = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    f"stop:0 {SB_ACCENT_DK}, stop:1 {SB_ACCENT})"
)


# ══════════════════════════════════════════════════════════════
#  SidebarItem — 카드형 아이템 (좌측 액센트 + 번호 배지 + 제목)
#
#  내부 구조: [좌우 margin] [카드: accent + 번호 배지 + 제목]
#  활성/비활성 모두 동일 폰트 크기/굵기 — 색·배경만 변화.
# ══════════════════════════════════════════════════════════════
class SidebarItem(QWidget):
    clicked = pyqtSignal()

    def __init__(self, number: str, title: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self._active = False
        self._build(number, title)
        self._apply_style()

    def _build(self, number: str, title: str):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(ITEM_MARGIN_L, 3, ITEM_MARGIN_R, 3)
        outer.setSpacing(0)

        # 카드 — hover/active 배경이 카드 안에서만 발생 (모서리 둥글게)
        self._card = QFrame()
        self._card.setObjectName("sb_card")
        cl = QHBoxLayout(self._card)
        cl.setContentsMargins(CARD_INNER_LEFT, 0, 10, 0)
        cl.setSpacing(BADGE_SPACING)

        # 번호 배지 — 항상 배경이 있어 시각적 무게 유지
        self._num_lbl = QLabel(number)
        self._num_lbl.setFixedSize(NUM_BADGE, NUM_BADGE)
        self._num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._num_lbl.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        cl.addWidget(self._num_lbl)

        # 제목
        self._title_lbl = QLabel(title)
        self._title_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.DemiBold))
        cl.addWidget(self._title_lbl, stretch=1)

        outer.addWidget(self._card)

    def _apply_style(self):
        if self._active:
            # 활성 — 진한 인디고 그라데이션 카드 + 흰 글자 (강한 강조)
            card_bg     = SB_GRADIENT
            badge_fg    = "#FFFFFF"
            title_fg    = "#FFFFFF"
            hover_bg    = SB_GRADIENT       # 활성 호버는 동일 유지
        else:
            # 비활성 — 카드 자체는 투명, 호버 시만 옅은 인디고 배경
            card_bg     = "transparent"
            badge_fg    = SB_ACCENT_MID     # 번호는 인디고 톤
            title_fg    = C.T0              # 제목은 진한 글자
            hover_bg    = SB_ACCENT_LT      # 호버 시 옅은 인디고

        # 카드 — 호버/활성 시 라운드 카드 형태로 두드러짐
        self._card.setStyleSheet(
            f"#sb_card {{ background:{card_bg};"
            f"  border:none; border-radius:10px; }}"
            f"#sb_card:hover {{ background:{hover_bg}; }}")

        # 번호 — 배지 없이 텍스트만 (배경/보더 모두 제거)
        self._num_lbl.setStyleSheet(
            f"QLabel {{ background:transparent; color:{badge_fg};"
            f"  border:none; }}")

        # 제목
        self._title_lbl.setStyleSheet(
            f"color:{title_fg}; background:transparent;")

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)


# ══════════════════════════════════════════════════════════════
#  ArrowLabel — 번호 사이 ↓ 화살표 (번호 위치 정중앙 아래)
# ══════════════════════════════════════════════════════════════
class ArrowLabel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)
        lay = QHBoxLayout(self)
        # SidebarItem 의 outer margin + 카드 내부 좌측 padding 만큼 좌측 spacer.
        left = ITEM_MARGIN_L + CARD_INNER_LEFT
        lay.setContentsMargins(left, 0, 0, 0)
        lay.setSpacing(0)

        # 번호 폭과 정확히 맞춰 화살표가 번호 정중앙 아래로 정렬됨
        self._arrow = QLabel("↓")
        self._arrow.setFixedWidth(NUM_BADGE)
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        self._arrow.setStyleSheet(
            f"color:{SB_ACCENT_MID}; background:transparent;")
        lay.addWidget(self._arrow)
        lay.addStretch()


# ══════════════════════════════════════════════════════════════
#  Sidebar — 9탭 세로 네비
# ══════════════════════════════════════════════════════════════
class Sidebar(QFrame):
    """좌측 9탭 세로 사이드바.

    Signals:
      changed(str)        — 사용자가 선택한 탭 key
      cb_config_clicked() — 헤더의 🔌 버튼 클릭 (Codebeamer 연동 설정 다이얼로그)
    """

    changed           = pyqtSignal(str)
    cb_config_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar9")
        # 244 → 280 — "SW 배포 파이프라인" / "코드비머 연동 프로그램" / 긴 탭명
        # ("⑧ OPEN 항목 및 잔여 조치") 잘림 방지
        self.setFixedWidth(280)
        # 사이드바 자체 배경은 살짝 따뜻한 흰색 — 본문(BG_APP)과 미세 분리.
        self.setStyleSheet(
            f"#sidebar9 {{ background:#FBFBFD;"
            f"  border-right:1px solid {C.BDR}; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        # ── 헤더 ─────────────────────────────────────────────
        # PageHeader 와 동일한 높이 → 두 헤더의 하단 구분선이 같은 y 에 정렬.
        hdr = QFrame()
        hdr.setObjectName("sb_header")
        hdr.setFixedHeight(SIDEBAR_HEADER_H)
        # 인디고 그라데이션 헤더 — 사이드바 정체성 형성
        hdr.setStyleSheet(
            f"#sb_header {{ background:{SB_GRADIENT};"
            f"  border-bottom:1px solid {SB_ACCENT_DK}; }}")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(11)

        # 아이콘 박스 — 흰 배지 위 이모지, 그라데이션 헤더 위에서 강한 대비
        icon_box = QFrame()
        icon_box.setFixedSize(36, 36)
        icon_box.setStyleSheet(
            f"background:rgba(255, 255, 255, 0.20);"
            f"border:1px solid rgba(255, 255, 255, 0.35);"
            f"border-radius:9px;")
        ib = QHBoxLayout(icon_box); ib.setContentsMargins(0, 0, 0, 0)
        icon = QLabel("🤖")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont(C.FUI, 16))
        icon.setStyleSheet("background:transparent;")
        ib.addWidget(icon)
        hl.addWidget(icon_box)

        # 타이틀 + 부제 + 버전 — 흰 글자 3단 구성 (헤더 68px)
        title_col = QVBoxLayout(); title_col.setSpacing(1)
        tt = QLabel("SW 배포 파이프라인")
        tt.setFont(QFont(C.FUI, 12, QFont.Weight.Bold))
        tt.setStyleSheet("color:#FFFFFF; background:transparent;"
                         "letter-spacing:0.3px;")
        title_col.addWidget(tt)
        desc = QLabel("코드비머 연동 프로그램")
        desc.setFont(QFont(C.FUI, 8))
        desc.setStyleSheet("color:rgba(255, 255, 255, 0.85);"
                           "background:transparent;"
                           "letter-spacing:0.2px;")
        title_col.addWidget(desc)
        sub = QLabel("VER 1.0")
        sub.setFont(QFont(C.FUI, 7))
        sub.setStyleSheet("color:rgba(255, 255, 255, 0.65);"
                          "background:transparent;"
                          "letter-spacing:0.4px;")
        title_col.addWidget(sub)
        hl.addLayout(title_col)
        hl.addStretch()

        # ── Codebeamer 연동 설정 버튼 ─────────────────────────
        # 처음 시작 화면에서 CB 설정을 건너뛰었거나, 나중에 자격증명 / URL 을
        # 다시 입력하고 싶을 때 언제든 다이얼로그를 다시 띄울 수 있게 헤더에
        # 작은 버튼으로 노출.
        self._cb_btn = QPushButton("🔌")
        self._cb_btn.setFixedSize(30, 30)
        self._cb_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cb_btn.setToolTip("Codebeamer 연동 설정")
        self._cb_btn.setStyleSheet(
            "QPushButton {"
            "  background:rgba(255,255,255,0.18);"
            "  color:#FFFFFF;"
            "  border:1px solid rgba(255,255,255,0.30);"
            "  border-radius:7px;"
            "  font-size:13px;"
            "}"
            "QPushButton:hover {"
            "  background:rgba(255,255,255,0.32);"
            "  border-color:rgba(255,255,255,0.55);"
            "}"
            "QPushButton:pressed {"
            "  background:rgba(255,255,255,0.40);"
            "}")
        self._cb_btn.clicked.connect(self.cb_config_clicked.emit)
        hl.addWidget(self._cb_btn)

        outer.addWidget(hdr)

        # ── 항목 스크롤 ───────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        body = QWidget()
        body.setStyleSheet(f"background:transparent;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 12, 0, 12); bl.setSpacing(2)

        self._items: dict[str, SidebarItem] = {}
        for i, (key, num, title) in enumerate(SIDEBAR_ITEMS):
            item = SidebarItem(num, title)
            item.clicked.connect(lambda k=key: self._on_clicked(k))
            self._items[key] = item
            bl.addWidget(item)
            if i < len(SIDEBAR_ITEMS) - 1:
                bl.addWidget(ArrowLabel())

        bl.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)

        self._current_key: str = ""

    def _on_clicked(self, key: str):
        self.set_current(key)

    def set_current(self, key: str):
        if key == self._current_key:
            return
        if key not in self._items:
            return
        self._current_key = key
        for k, it in self._items.items():
            it.set_active(k == key)
        self.changed.emit(key)

    def current(self) -> str:
        return self._current_key


# ══════════════════════════════════════════════════════════════
#  EmptyRight — 페이지 미선택 시 우측 영역
# ══════════════════════════════════════════════════════════════
class EmptyRight(QWidget):
    """앱 시작 후, 사용자가 사이드바에서 아직 페이지를 클릭하지 않은 상태."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C.BG_APP};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(8)
        lay.addStretch()
        ic = QLabel("👈")
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("background:transparent; font-size:48px;")
        lay.addWidget(ic)
        msg = QLabel("왼쪽 탭에서 페이지를 선택하세요")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setFont(QFont(C.FUI, 13, QFont.Weight.Bold))
        msg.setStyleSheet(f"color:{C.T3}; background:transparent;")
        lay.addWidget(msg)
        lay.addStretch()


# ══════════════════════════════════════════════════════════════
#  MainShell — 사이드바 + 페이지 스택
# ══════════════════════════════════════════════════════════════
class MainShell(QWidget):
    """좌측 사이드바 + 우측 페이지 스택 메인 셸.

    각 페이지는 별도 모듈에서 import 해 외부에서 add_page() 로 등록.
    """

    page_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C.BG_APP};")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        self.sidebar = Sidebar()
        outer.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, stretch=1)

        # 빈 우측 영역(처음 표시)
        self._empty = EmptyRight()
        self.stack.addWidget(self._empty)
        self._key_to_idx: dict[str, int] = {"__empty__": 0}

        self.sidebar.changed.connect(self._on_sidebar_changed)

    def add_page(self, key: str, widget: QWidget):
        self.stack.addWidget(widget)
        self._key_to_idx[key] = self.stack.count() - 1

    def show_page(self, key: str):
        if key in self._key_to_idx:
            self.stack.setCurrentIndex(self._key_to_idx[key])

    def show_empty(self):
        self.stack.setCurrentIndex(0)

    def _on_sidebar_changed(self, key: str):
        self.show_page(key)
        self.page_changed.emit(key)
