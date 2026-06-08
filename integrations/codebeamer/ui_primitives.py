"""ui_primitives.py — Codebeamer UI 패키지 내부에서 공유하는 작은 Qt 위젯/유틸.

  - _ca               : hex+alpha → rgba() 헬퍼
  - _ClickableWidget  : 클릭 시그널 보내는 QWidget (아코디언 헤더)
  - _ElidedLabel      : 너비에 맞춰 텍스트 끝 '…' 처리하는 QLabel
  - _FetchWorker      : 트래커 일괄 조회 백그라운드 워커 (CbSectionWidget 에서 사용)
"""

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget


def _ca(color: str, alpha_hex: str) -> str:
    """hex color + hex alpha → rgba() (Qt 스타일시트용)."""
    h = color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = round(int(alpha_hex, 16) / 255, 3)
    return f"rgba({r},{g},{b},{a})"


# ══════════════════════════════════════════════════════════════
#  _ClickableWidget — 클릭 가능한 QWidget (아코디언 헤더용)
# ══════════════════════════════════════════════════════════════
class _ClickableWidget(QWidget):
    """
    pyqtSignal 로 클릭 이벤트를 내보내는 QWidget 서브클래스.
    순수 QWidget 인스턴스에 mousePressEvent 를 속성으로 할당하면
    Qt 가상 디스패치가 Python 인스턴스 속성을 보지 않아 콜백이 호출되지 않음.
    따라서 클래스 레벨 오버라이드 + 시그널 방식으로 우회한다.
    """
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _ElidedLabel(QLabel):
    """너비에 맞게 텍스트 끝을 '…'으로 자르는 반응형 레이블."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setToolTip(text)

    def setText(self, text):
        self._full_text = text
        self.setToolTip(text)
        self.update()

    def text(self):
        return self._full_text

    def paintEvent(self, e):
        painter = QPainter(self)
        fm = self.fontMetrics()
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, self.width())
        painter.setFont(self.font())
        painter.setPen(self.palette().windowText().color())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)


# ══════════════════════════════════════════════════════════════
#  _FetchWorker — 트래커 일괄 조회 백그라운드 워커 (QThread)
# ══════════════════════════════════════════════════════════════
class _FetchWorker(QObject):
    progress = pyqtSignal(str, int)
    success  = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, fetcher, tracker_map: dict, output_path: str = None):
        super().__init__()
        self.fetcher      = fetcher
        self.tracker_map  = tracker_map
        self.output_path  = output_path  # None → 기본 CB_MD_FILE 사용

    def run(self):
        try:
            md = self.fetcher.generate_md(
                self.tracker_map,
                output_path=self.output_path,
                progress_cb=lambda msg, pct: self.progress.emit(msg, pct),
            )
            self.success.emit(md)
        except Exception as e:
            self.error.emit(str(e))
