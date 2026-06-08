"""page_review.py — ⑥ 코드리뷰 결과 페이지.

가장 큰 페이지. 기존 ResultPanel 을 통째로 본문에 임베드하고, 내부 5탭을
[INPUT/OUTPUT] 2단계 + 서브탭 구조로 재포장한다.

내부 구조 매핑 (ResultPanel 페이지 키와 1:1):
  INPUT 탭
    • 변경전/후 코드 입력  → ResultPanel "files"
    • 추가 분석 자료       → ResultPanel "extras"
  OUTPUT 탭
    • 변경점 VIEW          → ResultPanel "diff"
    • 변경점 요약          → ResultPanel "summary"
    • 취약점 분석          → ResultPanel "vuln"

AI 분석 실행 버튼은 AnalysisFilePanel의 '코드 DIFF 추출' 버튼 아래로 주입한다.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QPushButton, QProgressBar,
)

from config import C
from view.ui_result import ResultPanel
from ._common import BasePage, TabBar


class ReviewPage(BasePage):
    """⑥ 코드리뷰 결과.

    Signals (외부 controllers/main.py 가 사용):
      ai_clicked      — AI 분석 실행 버튼 클릭
      stop_requested  — 분석 중 버튼 재클릭 (중단)
    """

    ai_clicked     = pyqtSignal(dict)
    stop_requested = pyqtSignal()
    # [📥 불러오기] 헤더 버튼 — 트래커에 이미 등록된 결과 있는지 조회
    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("⑥", "코드리뷰 결과", parent)
        self._ai_running = False
        self._last_params: dict = {}

        # ResultPanel — 기존 위젯 통째로 사용
        self.result = ResultPanel()
        self.result.set_tab_bar_visible(False)
        # extras 탭 안에 있는 [요구사항/과거차] 중 요구사항 입력은 SRS 페이지로
        # 이동했지만, ExtrasPanel 인스턴스는 컨트롤러 호환을 위해 그대로 둔다.

        # 헤더 [📥 불러오기] + 상단 상태 배너 마운트 (BasePage 헬퍼)
        # — _build_content() 이전에 호출해야 배너가 외부 탭(INPUT/OUTPUT) 위에 위치.
        self.attach_status_banner()
        self.install_load_button(self.load_requested.emit)

        self._build_content()

    def _build_content(self):
        # ── 외부 INPUT / OUTPUT 탭 ────────────────────────────
        self._outer_bar = TabBar(
            items=[("input",  "📥  INPUT"),
                   ("output", "📤  OUTPUT")],
            height=40,
            accent_color=C.BLUE,
        )
        self._outer_bar.changed.connect(self._on_outer_changed)
        self.add_body_no_stretch(self._outer_bar)

        # ── 서브탭 (INPUT/OUTPUT 따라 다름) ───────────────────
        # INPUT 서브탭
        self._input_sub = TabBar(
            items=[
                ("files",  "🔀  변경전/후 코드 입력"),
                ("extras", "📋  추가 분석 자료"),
            ],
            height=34,
            accent_color="#7BA7D4",
        )
        # OUTPUT 서브탭
        self._output_sub = TabBar(
            items=[
                ("diff",    "🔀  변경점 VIEW"),
                ("summary", "📝  변경점 요약"),
                ("vuln",    "🔍  취약점 분석"),
            ],
            height=34,
            accent_color="#7BA7D4",
        )
        self._input_sub.changed.connect(self._on_sub_changed)
        self._output_sub.changed.connect(self._on_sub_changed)
        # OUTPUT 서브탭은 처음엔 숨김
        self._output_sub.setVisible(False)
        self.add_body_no_stretch(self._input_sub)
        self.add_body_no_stretch(self._output_sub)

        # ── ResultPanel 본문 ──────────────────────────────────
        self.add_body(self.result)

        # ── AI 분석 실행 버튼을 AnalysisFilePanel 카드에 주입 ──
        self._build_ai_button()
        ap = self.result.analysis_panel
        # 진행률 + AI 버튼 묶음 컨테이너
        ai_box = QWidget(); ai_box.setStyleSheet("background:transparent;")
        ablx = QVBoxLayout(ai_box); ablx.setContentsMargins(0, 4, 0, 0); ablx.setSpacing(6)
        ablx.addWidget(self._prog)
        ablx.addWidget(self._ai_btn)
        ap.attach_below_diff_button(ai_box)

        # 초기 화면 — INPUT > 변경전/후 코드 입력
        self.result.switch_page("files")

    # add_body 헬퍼: 스트레치 0 으로 추가 (탭바 같은 고정 높이 위젯용)
    def add_body_no_stretch(self, widget):
        self._body_lay.addWidget(widget)

    def _build_ai_button(self):
        """AnalysisFilePanel 카드 안에 주입할 AI 실행 버튼 + 진행률 바."""
        self._prog = QProgressBar()
        self._prog.setRange(0, 0)
        self._prog.hide()

        self._ai_btn = QPushButton("  🤖  AI 분석 실행")
        self._ai_btn.setObjectName("btn_ai_review")
        # DIFF 버튼과 동일한 36px 높이로 통일 (기존 44px)
        self._ai_btn.setFixedHeight(36)
        self._ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._restyle_ai_button(running=False)
        self._ai_btn.setEnabled(False)
        self._ai_btn.setToolTip("DIFF 추출 후 활성화됩니다")
        self._ai_btn.clicked.connect(self._on_ai_clicked)

    def _restyle_ai_button(self, running: bool):
        # 코드 DIFF 추출 버튼과 동일한 톤/크기 (height 36 / font 12 / radius 8 / padding 없음)
        if running:
            self._ai_btn.setText("  ✋🏻  분석 중단")
            self._ai_btn.setStyleSheet("""
                QPushButton#btn_ai_review {
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 #CB8A8A, stop:1 #E8AAAA);
                    color:#5C1C1C; border:2px solid #BB7777; border-radius:8px;
                    font-size:12px; font-weight:bold;
                }
                QPushButton#btn_ai_review:hover {
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 #B86666, stop:1 #CB8A8A);
                    color:#FFFFFF; border-color:#A05050;
                }
                QPushButton#btn_ai_review:pressed { background:#A05050; color:#FFFFFF; }
            """)
        else:
            # 프로그램 메인 BLUE 패밀리 그라데이션으로 통일
            # (기존 #CEEAF6 / #BBCEF0 / #A3BDED 톤은 BLUE 와 어울리지 않음)
            self._ai_btn.setText("  🤖  AI 분석 실행")
            self._ai_btn.setStyleSheet(f"""
                QPushButton#btn_ai_review {{
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 {C.BLUE_DK}, stop:1 {C.BLUE});
                    color:#FFFFFF; border:2px solid {C.BLUE_DK}; border-radius:8px;
                    font-size:12px; font-weight:bold;
                }}
                QPushButton#btn_ai_review:hover {{
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 {C.BLUE}, stop:1 {C.BLUE_LT});
                    border-color:{C.ACCENT_H};
                }}
                QPushButton#btn_ai_review:pressed {{ background:{C.BLUE_DK}; color:#FFFFFF; }}
                QPushButton#btn_ai_review:disabled {{
                    background:{C.BDR}; color:{C.T3};
                    border:2px solid {C.BDR2}; font-size:12px;
                }}""")

    # ── 외부 탭 라우팅 ──────────────────────────────────────
    def _on_outer_changed(self, key: str):
        if key == "input":
            self._input_sub.setVisible(True)
            self._output_sub.setVisible(False)
            self.result.switch_page(self._input_sub.current())
        else:
            self._input_sub.setVisible(False)
            self._output_sub.setVisible(True)
            self.result.switch_page(self._output_sub.current())

    def _on_sub_changed(self, key: str):
        self.result.switch_page(key)

    # ── AI 버튼 핸들러 (InputPanel 의 _on_ai 와 동일 로직) ──
    def _on_ai_clicked(self):
        if self._ai_running:
            self.stop_requested.emit(); return
        if not self._last_params:
            self._warn_ai_btn("먼저 DIFF 추출을 실행해주세요."); return
        # InputPanel._on_ai 와 동일 — 최신 옵션을 갱신해 emit
        params = dict(self._last_params)
        self.ai_clicked.emit(params)

    def _warn_ai_btn(self, msg: str):
        from PyQt6.QtCore import QTimer
        orig = self._ai_btn.text()
        self._ai_btn.setText(f"⚠  {msg}")
        self._ai_btn.setStyleSheet(
            f"QPushButton {{ background:{C.AMBER}; color:white; border:none; "
            f"border-radius:8px; font-size:11px; font-weight:bold; padding:10px; }}")
        QTimer.singleShot(2400, lambda: (
            self._ai_btn.setText(orig),
            self._restyle_ai_button(self._ai_running)))

    # ── 외부 (controllers/main.py) 에서 호출되는 위임 메서드 ─
    def set_last_params(self, params: dict):
        self._last_params = params

    def enable_ai(self):
        self._ai_btn.setEnabled(True)
        self._ai_btn.setToolTip(
            "클릭하면 Claude AI가 변경점을 요약하고 취약점을 분석합니다")

    def set_diff_running(self, running: bool):
        ap = self.result.analysis_panel
        if hasattr(ap, "set_diff_running"):
            ap.set_diff_running(running)

    def set_ai_running(self, running: bool):
        self._ai_running = running
        self._prog.setVisible(running)
        self._restyle_ai_button(running)

    def switch_to_output(self, sub_key: str = "diff"):
        """OUTPUT 탭으로 전환하고 지정된 서브탭으로 이동."""
        self._outer_bar.set_current("output")
        self._output_sub.set_current(sub_key)
