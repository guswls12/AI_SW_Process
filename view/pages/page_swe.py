"""page_swe.py — ② SWE.1 SRS / ③ SWE.2 SAD / ④ SWE.3 SDD 공통 페이지.

세 페이지는 단어만 다르고 구조가 동일하므로 한 클래스로 파라미터화한다:
  - SWE.1 → 요구사항
  - SWE.2 → 아키텍처
  - SWE.3 → 상세설계

구성:
  INPUT 탭 / OUTPUT 탭
    INPUT 탭 :
      • 변경전/후 {NAME}서 입력 탭   — 기존 ReqInput 위젯 재사용 (드롭존 2개 + 추출 버튼)
      • {NAME} 체크시트 1 탭        — 추후 설계 (placeholder)
      • {NAME} 체크시트 2 탭        — 추후 설계 (placeholder)
    OUTPUT 탭 :
      • 변경점 VIEW 탭              — 기존 ReqDiffView 재사용
      • 체크시트 결과 탭            — 추후 설계 (placeholder)
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QScrollArea,
)

from config import C
from view.ui_result import ReqInput, ReqDiffView
from ._common import BasePage, TabStack, PlaceholderBody
from .page_srs_review_panel import (
    # 새 SRS 검토 워크플로우 UI (INPUT 2·3 탭 + OUTPUT AI 결과)
    CbHistoricalSubTab, ChecklistReviewSubTab,
    AiResultDropdownPanel,
)


class _SrsLikeInputCard(QWidget):
    """SWE 페이지 INPUT > 변경전/후 NAME서 입력 탭 본문.

    상단에 ReqInput 위젯 (드롭존 2개 또는 직접 입력) + DIFF 추출 버튼.
    """

    diff_requested = pyqtSignal()

    def __init__(self, name: str, parent=None):
        """변경 전/후 {name}서 입력 카드 — ReqInput + DIFF 추출 버튼 + 결과 뷰."""
        super().__init__(parent)
        self._name = name
        self._req_input: "ReqInput | None" = None
        self.inline_diff_view: "ReqDiffView | None" = None
        self._req_diff_btn: QPushButton = None
        self._build()

    def _build(self):
        # 기존 보라(#7E60C0) → 프로그램 메인 BLUE 통일.
        # 변수명은 본문 흐름 가독성 위해 ACCENT 로 유지.
        ACCENT = C.BLUE
        self.setStyleSheet(f"background:{C.BG_APP};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget(); inner.setStyleSheet(f"background:{C.BG_APP};")
        il = QVBoxLayout(inner)
        il.setContentsMargins(16, 16, 16, 16); il.setSpacing(14)

        # 변경 전/후 요구사항서 입력 카드.
        self._req_input = ReqInput()
        card = QFrame(); card.setObjectName("inp_card")
        card.setStyleSheet(
            f"#inp_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # 헤더
        hdr = QFrame(); hdr.setFixedHeight(40)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 18)
        accent.setStyleSheet(f"background:{ACCENT}; border-radius:2px;")
        hl.addWidget(accent)
        # '아키텍처서' 는 어색해서 "서" 안 붙임 — 그 외 요구사항/상세설계는 "서" 접미사
        _suffix = "" if self._name == "아키텍처" else "서"
        t = QLabel(f"📋  변경 전/후 {self._name}{_suffix} 입력")
        t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{ACCENT}; background:transparent;")
        hl.addWidget(t); hl.addStretch()
        cl.addWidget(hdr)

        # 본문 — ReqInput + DIFF 추출 버튼 + DIFF 결과 뷰 (창 크기 비례 stretch)
        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(10)
        bl.addWidget(self._req_input)

        btn = QPushButton(f"  📋  {self._name} DIFF 추출")
        btn.setFixedHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:#FFFFFF;"
            f"  border:2px solid {C.ACCENT_H}; border-radius:8px;"
            f"  font-size:12px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:pressed {{ background:{C.BLUE_DK}; }}"
            f"QPushButton:disabled {{ background:#E2E8F0; color:#94A3B8;"
            f"  border-color:#CBD5E1; }}")
        btn.clicked.connect(self._on_diff_clicked)
        self._req_diff_btn = btn
        bl.addWidget(btn)

        # DIFF 추출 결과 뷰 — stretch=1 로 창 높이에 비례해서 끝까지 채움
        # (DIFF 미추출 시에도 빈 영역이 시각적으로 확보됨 — 추출 후 본문 표시)
        self.inline_diff_view = ReqDiffView()
        self.inline_diff_view.setMinimumHeight(240)
        bl.addWidget(self.inline_diff_view, stretch=1)

        # 카드 안의 body + il 안의 card 도 stretch 로 확장 → DIFF 뷰가
        # 최종적으로 사용 가능한 모든 vertical 공간을 차지하게 됨.
        cl.addWidget(body, stretch=1)
        il.addWidget(card, stretch=1)

        scroll.setWidget(inner)
        lay.addWidget(scroll)

    def _on_diff_clicked(self):
        if self._req_input is None:
            return
        old_path = self._req_input.get_old_req_path()
        new_path = self._req_input.get_new_req_path()
        if not old_path or not new_path:
            from PyQt6.QtWidgets import QToolTip
            QToolTip.showText(
                self._req_diff_btn.mapToGlobal(
                    self._req_diff_btn.rect().bottomLeft()),
                f"수정 전/후 {self._name} 파일을 모두 선택해주세요.",
                self._req_diff_btn, self._req_diff_btn.rect(), 3000)
            return
        self.diff_requested.emit()

    # ── 외부에서 사용 — SRS 활성 페이지(with_tracker=True)는 _req_input 없음 ──
    def get_old_path(self) -> str:
        return self._req_input.get_old_req_path() if self._req_input else ""
    def get_new_path(self) -> str:
        return self._req_input.get_new_req_path() if self._req_input else ""
    def get_text(self) -> str:
        return self._req_input.get_text() if self._req_input else ""
    def set_diff_text(self, text: str):
        if self._req_input:
            self._req_input.set_req_diff_text(text)
    def render_diff(self, old_lines: list, new_lines: list):
        """추출된 DIFF 결과를 인라인 뷰(버튼 아래)에 렌더링."""
        if self.inline_diff_view:
            self.inline_diff_view.render(old_lines, new_lines)
    def set_running(self, running: bool):
        if self._req_diff_btn:
            self._req_diff_btn.setEnabled(not running)
            self._req_diff_btn.setText(
                "  ⏳  추출 중..." if running
                else f"  📋  {self._name} DIFF 추출")


# ══════════════════════════════════════════════════════════════
#  SwePage — 공통 페이지 클래스
# ══════════════════════════════════════════════════════════════
class SwePage(BasePage):
    """SWE.1/2/3 공통 페이지.

    Args:
        number : 좌측탭 번호 (②/③/④)
        title  : 헤더 제목 (예: "SWE.1 SRS")
        name   : 대상 문서명 (예: "요구사항"/"아키텍처"/"상세설계")
    """

    # 컨트롤러에 노출되는 시그널 — DIFF 추출 요청
    diff_requested = pyqtSignal()
    # ② ③ ④ 공통 — [📥 불러오기] 헤더 버튼 클릭
    # 컨트롤러가 project_state 에서 트래커 ID 얻어 fetch 후 상태 배너 갱신.
    load_requested = pyqtSignal()

    def __init__(self, number: str, title: str, name: str,
                 srs_review: bool = False, parent=None):
        """3단계 (2026-06): srs_review 인자는 더 이상 의미 없음 — 호환성
        위해 시그너처만 유지. 모든 SWE 페이지가 동일한 새 구조 사용.
        """
        super().__init__(number, title, parent)
        self._name = name
        # 레거시 호환 — 일부 코드가 _srs_review_enabled 참조할 수 있음
        self._srs_review_enabled = False
        self.status_banner = None
        self._build_content()
        self._install_swe_header_actions()

    def _build_content(self):
        # INPUT 탭 첫번째 — 변경 전/후 {name}서 입력 카드 (단순 폼).
        self.input_card = _SrsLikeInputCard(self._name)
        self.input_card.diff_requested.connect(self.diff_requested)

        # ── SRS 검토 활성 페이지 (SWE.1) 만 새 워크플로우 UI 마운트 ───
        # SrsReviewV2Controller 가 cb_historical_tab + checklist_review_tab 와 연결.
        self.cb_historical_tab: "CbHistoricalSubTab | None"     = None
        self.checklist_review_tab: "ChecklistReviewSubTab | None" = None

        # ── 3단계 (2026-06): SRS/SAD/SDD 공통 새 구조 ──────────────
        # INPUT 탭 2개:
        #   1) 변경 전/후 입력 + 변경점 불러오기 + 변경 없음 체크
        #   2) ASPICE 체크리스트 (xlsx 로드/표시/편집)
        # OUTPUT 탭 3개:
        #   1) 변경점 VIEW (ReqDiffView)
        #   2) 변경점 ↔ 요구사항 ID 매칭 결과
        #   3) 체크리스트 AI 분석 결과 (AiResultDropdownPanel)
        from .page_swe_v3_panel import (
            ChangePointLoadCard, AspiceChecklistCard, ChangePointMatchingCard,
        )

        # ── 신규 위젯 인스턴스 ────────────────────────────────
        self.change_load_card = ChangePointLoadCard(self._name)
        self.aspice_checklist = AspiceChecklistCard()
        self.change_match_card = ChangePointMatchingCard()
        self.ai_result_panel = AiResultDropdownPanel()

        # ── INPUT 탭 1: 변경 전/후 입력 + 변경점 불러오기 ───────
        # _SrsLikeInputCard + ChangePointLoadCard 를 세로로 적층한 컨테이너
        input_tab1 = QWidget()
        input_tab1.setStyleSheet(f"background:{C.BG_APP};")
        it1_lay = QVBoxLayout(input_tab1)
        it1_lay.setContentsMargins(16, 16, 16, 16); it1_lay.setSpacing(12)
        it1_lay.addWidget(self.input_card, stretch=2)
        it1_lay.addWidget(self.change_load_card, stretch=1)

        _suffix = "" if self._name == "아키텍처" else "서"
        input_tabs = TabStack(
            pages=[
                ("input_files",
                 f"📋  변경 전/후 {self._name}{_suffix} + 변경점 불러오기",
                 input_tab1),
                ("aspice_checklist",
                 "📊  ASPICE 체크리스트",
                 self.aspice_checklist),
            ],
            accent_color=C.BLUE,
            height=36,
        )
        self._input_tabs = input_tabs

        # ── OUTPUT 탭 — DIFF VIEW / 매칭 결과 / AI 결과 ─────────
        self.diff_view = ReqDiffView()
        diff_container = QWidget()
        diff_container.setStyleSheet(f"background:{C.BG_APP};")
        dcl = QVBoxLayout(diff_container)
        dcl.setContentsMargins(16, 16, 16, 16); dcl.setSpacing(0)
        dcl.addWidget(self.diff_view, stretch=1)

        match_container = QWidget()
        match_container.setStyleSheet(f"background:{C.BG_APP};")
        mcl = QVBoxLayout(match_container)
        mcl.setContentsMargins(16, 16, 16, 16); mcl.setSpacing(0)
        mcl.addWidget(self.change_match_card, stretch=1)

        output_tabs = TabStack(
            pages=[
                ("diff_view", "🔀  변경점 VIEW",        diff_container),
                ("match",     "🔗  변경점 매칭 결과",    match_container),
                ("ai_result", "🤖  체크리스트 AI 분석 결과", self.ai_result_panel),
            ],
            accent_color=C.BLUE,
            height=36,
        )
        self._output_tabs = output_tabs
        # cb_historical_tab / checklist_review_tab 은 더 이상 SwePage 에 없음
        # (① 사양변경 페이지로 이전됨). 외부 호환 위해 None 유지.
        self.cb_historical_tab    = None
        self.checklist_review_tab = None

        # 외부 INPUT/OUTPUT 탭
        outer_tabs = TabStack(
            pages=[
                ("input",  "📥  INPUT",   input_tabs),
                ("output", "📤  OUTPUT",  output_tabs),
            ],
            accent_color=C.BLUE,
            height=40,
        )
        self._outer_tabs = outer_tabs   # 컨트롤러가 OUTPUT 으로 자동 전환할 때 사용

        # ── 상단 상태 배너 — 트래커 등록 결과 표시 (초기 숨김) ──
        # 헤더와 본문 사이에 stretch=0 으로 끼워넣음. [📥 불러오기] 누르기 전엔
        # 보이지 않다가 컨트롤러가 fetch 결과로 set_items/set_empty/... 호출 시 노출.
        from ._upload_status_banner import UploadStatusBanner
        self.status_banner = UploadStatusBanner()
        # _body_lay 에 직접 add — add_body() 는 stretch=1 인 본문용이므로 별도 호출
        banner_wrap = QWidget(); banner_wrap.setStyleSheet("background:transparent;")
        bwl = QVBoxLayout(banner_wrap)
        bwl.setContentsMargins(16, 12, 16, 0); bwl.setSpacing(0)
        bwl.addWidget(self.status_banner)
        self._body_lay.addWidget(banner_wrap)   # stretch=0

        self.add_body(outer_tabs)

    # ── 헤더 액션 — [📥 불러오기] 버튼 추가 ───────────────────
    def _install_swe_header_actions(self):
        """헤더의 [💾 저장] / [📤 CB 업로드] 옆에 [📥 불러오기] 버튼 추가.

        클릭 시 load_requested 시그널 emit → 컨트롤러가 현재 페이지의 트래커
        ID 로 CB 이슈 목록을 fetch → status_banner 갱신.
        """
        self.load_btn = QPushButton("📥  불러오기")
        self.load_btn.setObjectName("btn_sub")
        self.load_btn.setFixedHeight(30)
        self.load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_btn.setToolTip(
            "이 트래커에 이미 등록된 결과가 있는지 조회합니다.\n"
            "새 결과는 [📤 CB 업로드] 버튼으로 등록할 수 있습니다.")
        self.load_btn.clicked.connect(self.load_requested.emit)

        # 헤더 레이아웃의 save_btn 앞에 삽입 (위치 인덱스 3 = stretch 뒤)
        header_lay = self.header.layout()
        # save_btn / upload_btn 자리 index 를 찾아 그 앞에 둔다
        try:
            save_idx = header_lay.indexOf(self.header.save_btn)
            if save_idx >= 0:
                header_lay.insertWidget(save_idx, self.load_btn)
            else:
                header_lay.addWidget(self.load_btn)
        except Exception:
            header_lay.addWidget(self.load_btn)

    # ── 컨트롤러가 호출 — 상태 배너 갱신 ─────────────────────
    def set_load_running(self, running: bool, tracker_id: str = ""):
        """fetch 진행 중 / 완료 — 버튼 비활성 + 배너 로딩 표시."""
        try:
            self.load_btn.setEnabled(not running)
            self.load_btn.setText("⏳  조회 중..." if running else "📥  불러오기")
        except Exception:
            pass
        if running and self.status_banner is not None:
            self.status_banner.set_loading(tracker_id)

    # ── 외부 (컨트롤러) 가 AI 분석 완료 후 OUTPUT/AI 결과 탭으로 전환 ──
    def switch_to_ai_result_tab(self):
        """OUTPUT 탭 + AI 인사이트 결과 서브탭으로 자동 전환."""
        try:
            if getattr(self, "_outer_tabs", None) is not None:
                self._outer_tabs.set_current("output")
            if getattr(self, "_output_tabs", None) is not None:
                self._output_tabs.set_current("ai_result")
        except Exception:
            pass

    # ── 컨트롤러 위임용 메서드 ──────────────────────────────
    def get_old_path(self) -> str: return self.input_card.get_old_path()
    def get_new_path(self) -> str: return self.input_card.get_new_path()
    def get_text(self) -> str: return self.input_card.get_text()
    def set_diff_text(self, text: str): self.input_card.set_diff_text(text)
    def set_running(self, running: bool): self.input_card.set_running(running)
    def render_diff(self, old_lines: list, new_lines: list):
        # 입력 탭의 인라인 뷰 + OUTPUT 탭의 변경점 VIEW 양쪽에 동일 렌더
        self.input_card.render_diff(old_lines, new_lines)
        self.diff_view.render(old_lines, new_lines)

    # ══════════════════════════════════════════════════════════════
    #  Phase 2-3 — 세션 자동 저장/복원 (srs_review=True 페이지 한정)
    # ══════════════════════════════════════════════════════════════
    @staticmethod
    def _state_file_path() -> str:
        """srs_review_state.json 절대 경로 — cb_config.json / spec_state.json
        과 동일 데이터 디렉터리 (개발 모드 = 프로젝트 루트, .exe = %APPDATA%).
        """
        import os
        from integrations.codebeamer import _BASE
        return os.path.join(_BASE, "srs_review_state.json")

    def to_state(self) -> dict:
        """3단계 새 구조 — 변경 없음 체크/코멘트 + 체크리스트 파일 경로 등.
        체크리스트 본문 자체는 xlsx 파일에 저장되므로 여기엔 경로만.
        """
        # 페이지별 파일 분리 — name 으로 구분 (요구사항/아키텍처/상세설계)
        out = {
            "name": self._name,
            "change_load": self.change_load_card.to_state()
                           if self.change_load_card else {},
        }
        # 체크리스트 source_path (있으면)
        try:
            st = self.aspice_checklist.get_state() if self.aspice_checklist else {}
            if isinstance(st, dict) and st.get("source_path"):
                out["aspice_checklist_path"] = st["source_path"]
        except Exception:
            pass
        return out

    def apply_state(self, state: dict):
        """to_state() 결과를 받아 위젯들에 복원."""
        if not isinstance(state, dict):
            return
        if self.change_load_card is not None:
            self.change_load_card.apply_state(state.get("change_load") or {})
        # 체크리스트 파일 자동 재로드 (경로가 보존되어 있으면)
        path = (state.get("aspice_checklist_path") or "").strip()
        if path and self.aspice_checklist is not None:
            try:
                import os as _os
                if _os.path.exists(path):
                    self.aspice_checklist.load_from_path(path)
            except Exception:
                pass

    def save_state(self):
        """앱 종료 시 호출 — 페이지별 state json 저장."""
        try:
            import json, os
            path = self._state_file_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # 페이지별로 한 파일에 dict 키로 보관 (요구사항/아키텍처/상세설계)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    blob = json.load(f) or {}
            except Exception:
                blob = {}
            if not isinstance(blob, dict):
                blob = {}
            blob[self._name] = self.to_state()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(blob, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_state(self):
        """앱 시작 시 호출 — 페이지별 state 가 있으면 복원."""
        try:
            import json, os
            path = self._state_file_path()
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                blob = json.load(f) or {}
            if not isinstance(blob, dict):
                return
            self.apply_state(blob.get(self._name) or {})
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
#  편의 팩토리 — 각 번호별 페이지
# ══════════════════════════════════════════════════════════════
class SrsPage(SwePage):
    """② SWE.1 SRS — 요구사항.

    3단계 (2026-06) 구조:
      INPUT 2탭 — [변경 전/후 요구사항서 + 변경점 불러오기] / [ASPICE 체크리스트]
      OUTPUT 3탭 — [변경점 VIEW] / [변경점 매칭 결과] / [체크리스트 AI 분석 결과]
    SAD/SDD 와 동일 구조 (체크리스트 매핑만 페이지별로 다름).
    """
    def __init__(self, parent=None):
        super().__init__("②", "SWE.1 SRS", "요구사항", parent=parent)


class SadPage(SwePage):
    """③ SWE.2 SAD — 아키텍처."""
    def __init__(self, parent=None):
        super().__init__("③", "SWE.2 SAD", "아키텍처", parent)


class SddPage(SwePage):
    """④ SWE.3 SDD — 상세설계."""
    def __init__(self, parent=None):
        super().__init__("④", "SWE.3 SDD", "상세설계", parent)
