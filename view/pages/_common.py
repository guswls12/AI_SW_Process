"""_common.py — 페이지에서 공통으로 쓰이는 헬퍼.

PageHeader  : 우측 상단 [페이지 제목] ··· [💾 결과물 저장] [📤 CB 업로드] 바
InOutTabs   : INPUT / OUTPUT 가로 탭 컨테이너
SubTabs     : 다중 가로 서브탭 컨테이너
PlaceholderBody : "추후 설계 예정" 안내 위젯
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QStackedWidget,
)

from config import C


# ══════════════════════════════════════════════════════════════
#  PageHeader — 우측 상단 공통 헤더
# ══════════════════════════════════════════════════════════════
class PageHeader(QFrame):
    """모든 페이지 상단에 표시되는 공통 헤더.

    [페이지 번호 + 제목] ······························ [💾 결과물 저장] [📤 CB 업로드]
    """

    save_clicked   = pyqtSignal()
    upload_clicked = pyqtSignal()

    def __init__(self, number: str, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("page_header")
        # 68 — 사이드바 헤더(view/ui_shell.py SIDEBAR_HEADER_H) 와 같은 값.
        # 두 헤더 하단 구분선이 같은 y 에 정렬되어야 함.
        self.setFixedHeight(68)
        self.setStyleSheet(
            f"#page_header {{ background:{C.BG_PANEL};"
            f"  border-bottom:1px solid {C.BDR}; }}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 18, 0)
        lay.setSpacing(12)

        # 왼쪽 색상 바
        accent = QFrame()
        accent.setFixedSize(4, 28)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        lay.addWidget(accent)

        # 번호 + 제목
        title_lbl = QLabel(f"{number}  {title}")
        title_lbl.setFont(QFont(C.FUI, 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color:{C.T0}; background:transparent;")
        lay.addWidget(title_lbl)
        lay.addStretch()

        # 결과물 저장
        self.save_btn = QPushButton("💾  결과물 저장")
        self.save_btn.setObjectName("btn_sub")
        self.save_btn.setFixedHeight(30)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self.save_clicked.emit)
        lay.addWidget(self.save_btn)

        # CB 업로드
        self.upload_btn = QPushButton("📤  CB 업로드")
        self.upload_btn.setObjectName("btn_sub")
        self.upload_btn.setFixedHeight(30)
        self.upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.upload_btn.clicked.connect(self.upload_clicked.emit)
        lay.addWidget(self.upload_btn)


# ══════════════════════════════════════════════════════════════
#  TabBar — 가로 탭 버튼 그룹 (INPUT/OUTPUT 같은 외부 탭, 서브탭 모두 사용)
# ══════════════════════════════════════════════════════════════
class TabBar(QFrame):
    """가로 탭 버튼들을 표시하는 바.

    items: [(key, label), ...]
    클릭 시 changed(key) 시그널 발생.
    """

    changed = pyqtSignal(str)

    def __init__(self, items, height: int = 40,
                 accent_color: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("tabbar")
        self.setFixedHeight(height)
        self._accent = accent_color or C.BLUE
        self._items  = items
        self._btns: dict[str, QPushButton] = {}
        self._current_key = items[0][0] if items else ""

        self.setStyleSheet(
            f"#tabbar {{ background:{C.BG_PANEL};"
            f"  border-bottom:1px solid {C.BDR}; }}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0); lay.setSpacing(2)

        for key, label in items:
            btn = QPushButton(label)
            btn.setFixedHeight(height - 4)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self.set_current(k))
            self._btns[key] = btn
            lay.addWidget(btn)
        lay.addStretch()

        if self._current_key:
            self._restyle()

    def set_current(self, key: str):
        if key not in self._btns:
            return
        if self._current_key == key:
            return
        self._current_key = key
        self._restyle()
        self.changed.emit(key)

    def current(self) -> str:
        return self._current_key

    def _restyle(self):
        for k, btn in self._btns.items():
            is_on = (k == self._current_key)
            if is_on:
                btn.setStyleSheet(
                    f"QPushButton {{ background:transparent; color:{self._accent};"
                    f"  border:none; border-bottom:2px solid {self._accent};"
                    f"  border-radius:0; font-size:12px; font-weight:bold;"
                    f"  padding:6px 18px; }}")
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background:transparent; color:{C.T3};"
                    f"  border:none; border-bottom:2px solid transparent;"
                    f"  border-radius:0; font-size:12px;"
                    f"  padding:6px 18px; }}"
                    f"QPushButton:hover {{ color:{C.T1}; }}")
            btn.style().unpolish(btn); btn.style().polish(btn)


# ══════════════════════════════════════════════════════════════
#  TabStack — TabBar + QStackedWidget 묶음
# ══════════════════════════════════════════════════════════════
class TabStack(QWidget):
    """가로 탭과 페이지 스택을 묶은 위젯.

    pages: [(key, label, widget), ...]
    """

    changed = pyqtSignal(str)

    def __init__(self, pages, accent_color: str = None, height: int = 40,
                 parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        items = [(k, lbl) for k, lbl, _ in pages]
        self.bar = TabBar(items, height=height, accent_color=accent_color)
        lay.addWidget(self.bar)

        self.stack = QStackedWidget()
        self._key_to_idx: dict[str, int] = {}
        for i, (key, _, widget) in enumerate(pages):
            self.stack.addWidget(widget)
            self._key_to_idx[key] = i
        lay.addWidget(self.stack, stretch=1)

        self.bar.changed.connect(self._on_bar_changed)
        # 초기 인덱스
        if pages:
            self.stack.setCurrentIndex(0)

    def _on_bar_changed(self, key: str):
        idx = self._key_to_idx.get(key, 0)
        self.stack.setCurrentIndex(idx)
        self.changed.emit(key)

    def set_current(self, key: str):
        self.bar.set_current(key)


# ══════════════════════════════════════════════════════════════
#  PlaceholderBody — 추후 설계 예정 안내
# ══════════════════════════════════════════════════════════════
class PlaceholderBody(QWidget):
    """⑤ ⑦ ⑧ ⑨ 등 추후 설계 예정 페이지의 본문."""

    def __init__(self, message: str = "추후 설계 예정", icon: str = "🛠",
                 parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C.BG_APP};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(8)
        lay.addStretch()
        ic = QLabel(icon)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("background:transparent; font-size:48px;")
        lay.addWidget(ic)
        msg = QLabel(message)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setFont(QFont(C.FUI, 13, QFont.Weight.Bold))
        msg.setStyleSheet(f"color:{C.T3}; background:transparent;")
        lay.addWidget(msg)
        lay.addStretch()


# ══════════════════════════════════════════════════════════════
#  BasePage — 페이지 공통 베이스 (헤더 + 본문)
# ══════════════════════════════════════════════════════════════
class BasePage(QWidget):
    """모든 페이지의 베이스 클래스.

    상단 PageHeader + 본문 영역으로 구성된다.
    서브클래스는 self.body 컨테이너에 위젯을 추가하면 된다.
    """

    save_clicked   = pyqtSignal()
    upload_clicked = pyqtSignal()

    def __init__(self, number: str, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{C.BG_APP};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        self.header = PageHeader(number, title)
        self.header.save_clicked.connect(self.save_clicked)
        self.header.upload_clicked.connect(self.upload_clicked)
        outer.addWidget(self.header)

        self.body = QWidget()
        self.body.setStyleSheet(f"background:{C.BG_APP};")
        self._body_lay = QVBoxLayout(self.body)
        self._body_lay.setContentsMargins(0, 0, 0, 0); self._body_lay.setSpacing(0)
        outer.addWidget(self.body, stretch=1)

    def add_body(self, widget):
        """본문 영역에 위젯을 추가한다."""
        self._body_lay.addWidget(widget, stretch=1)

    # ══════════════════════════════════════════════════════════════
    #  [📥 불러오기] / 상태 배너 헬퍼 — ②~⑦ 페이지 공용
    # ══════════════════════════════════════════════════════════════
    def attach_status_banner(self):
        """헤더와 본문 사이에 UploadStatusBanner 마운트.

        - 항상 stretch=0 으로 본문 위에 위치 (배너가 노출되지 않는 한 공간 거의 차지 안 함)
        - 페이지 인스턴스에 self.status_banner 속성으로 노출.

        Returns: 마운트된 UploadStatusBanner 인스턴스.
        """
        from ._upload_status_banner import UploadStatusBanner
        self.status_banner = UploadStatusBanner()
        wrap = QWidget(); wrap.setStyleSheet("background:transparent;")
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(16, 12, 16, 0); wl.setSpacing(0)
        wl.addWidget(self.status_banner)
        # 본문 영역 가장 위에 끼워넣음 — add_body() 가 그 다음에 호출되어도 OK
        self._body_lay.insertWidget(0, wrap)
        return self.status_banner

    def install_load_button(self, on_click):
        """헤더의 [💾 저장] 앞에 [📥 불러오기] 버튼 추가.

        Args:
          on_click : 클릭 시 호출할 콜러블 (보통 self.load_requested.emit).

        Returns: 마운트된 QPushButton (self.load_btn).
        """
        btn = QPushButton("📥  불러오기")
        btn.setObjectName("btn_sub")
        btn.setFixedHeight(30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(
            "이 페이지의 트래커에 이미 등록된 결과가 있는지 조회합니다.\n"
            "새 결과는 [📤 CB 업로드] 버튼으로 등록할 수 있습니다.")
        btn.clicked.connect(on_click)

        lay = self.header.layout()
        # save_btn 앞에 삽입 (없으면 맨 끝)
        save_btn = getattr(self.header, "save_btn", None)
        if save_btn is not None:
            idx = lay.indexOf(save_btn)
            if idx >= 0:
                lay.insertWidget(idx, btn)
            else:
                lay.addWidget(btn)
        else:
            lay.addWidget(btn)
        self.load_btn = btn
        return btn

    def set_load_running(self, running: bool, tracker_id: str = ""):
        """컨트롤러가 워커 시작/종료 시 호출 — 버튼 비활성 + 배너 로딩 표시."""
        btn = getattr(self, "load_btn", None)
        if btn is not None:
            btn.setEnabled(not running)
            btn.setText("⏳  조회 중..." if running else "📥  불러오기")
        banner = getattr(self, "status_banner", None)
        if running and banner is not None:
            banner.set_loading(tracker_id)
