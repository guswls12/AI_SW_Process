"""
main.py — 진입점 + MainWindow (9탭 사이드바 + 페이지 스택).

레이어 구조:
  main.py              ← MainShell (좌측 9탭 사이드바 + 우측 페이지) +
                         InputShim / ResultShim 으로 컨트롤러 인터페이스 유지
  view.ui_shell        ← MainShell + Sidebar + ArrowLabel
  view.pages           ← 페이지별 위젯 (spec / swe / review / placeholder)
  controllers/         ← 흐름 제어 (CB / DIFF / AI) — 기존 그대로 사용
  view/                ← UI 위젯 + 저장/내보내기 헬퍼
  core/                ← diff 비교 / 함수 범위 탐지
  workers/             ← QThread 백그라운드 작업자
  integrations/        ← 외부 시스템 어댑터 (Codebeamer)
  config.py            ← 색상 토큰, QSS, 공통 헬퍼
"""

import os
import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QStatusBar, QDialog,
)
from PyQt6.QtCore import Qt, QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QPalette, QColor, QIcon

from config import C, build_qss, get_dpi_scale
from view import ui_diff_export
from view.ui_shell import MainShell
from view.pages.page_spec        import SpecChangePage
from view.pages.page_swe         import SrsPage, SadPage, SddPage
from view.pages.page_review      import ReviewPage
from view.pages.page_placeholder import StaticResultPage, TestResultPage
from view.pages.page_open_items    import OpenItemsPage
from view.pages.page_deploy_review import DeployReviewPage
from controllers.cb_controller   import CbController
from controllers.diff_controller import DiffController
from controllers.ai_controller   import AiController
from controllers.srs_review_v2_controller import SrsReviewV2Controller
from controllers.swe_review_controller import SweReviewController


# ══════════════════════════════════════════════════════════════
#  _ExtrasProxy — ResultShim.extras_panel 용 프록시.
#  '요구사항' 관련 호출은 SRS 페이지로, 그 외는 진짜 ExtrasPanel 로 위임.
# ══════════════════════════════════════════════════════════════
class _ExtrasProxy:
    def __init__(self, real_extras, srs_page):
        self._real = real_extras
        self._srs  = srs_page

    # 요구사항 입력은 ② SWE.1 SRS 페이지로 이동했으므로 SRS 페이지에 위임
    def get_req_text(self):
        return self._srs.get_text() if self._srs else ""
    def get_req_old_path(self):
        return self._srs.get_old_path() if self._srs else ""
    def get_req_new_path(self):
        return self._srs.get_new_path() if self._srs else ""
    def set_req_diff_running(self, running):
        if self._srs:
            self._srs.set_running(running)
    def set_req_diff_text(self, text):
        if self._srs:
            self._srs.set_diff_text(text)
    def set_req_diff(self, old_lines, new_lines):
        if self._srs:
            self._srs.render_diff(old_lines, new_lines)

    # 나머지는 진짜 ExtrasPanel 위임
    def __getattr__(self, name):
        return getattr(self._real, name)


# ══════════════════════════════════════════════════════════════
#  InputShim — 컨트롤러가 기대하는 InputPanel 인터페이스 어댑터.
#  실제 위젯은 SpecChangePage(프로젝트 정보) + ReviewPage(AI 버튼) 에 분산.
# ══════════════════════════════════════════════════════════════
class InputShim(QObject):
    diff_clicked                  = pyqtSignal(dict)
    ai_clicked                    = pyqtSignal(dict)
    stop_requested                = pyqtSignal()
    cb_clicked                    = pyqtSignal()
    include_changed               = pyqtSignal(str, bool)
    change_register_requested     = pyqtSignal(int, dict)
    change_register_all_requested = pyqtSignal(list)
    spec_register_requested       = pyqtSignal(dict)
    hzt_register_requested        = pyqtSignal(dict)

    def __init__(self, spec_page: SpecChangePage, review_page: ReviewPage,
                 result_shim: "ResultShim"):
        super().__init__()
        self._spec    = spec_page
        self._review  = review_page
        self._result  = result_shim
        self._last_params: dict = {}

        # AnalysisFilePanel 의 '코드 DIFF 추출' 버튼 → params 구성 후 emit
        ap = review_page.result.analysis_panel
        ap.diff_requested.connect(self._on_diff_btn)

        # ReviewPage 의 AI 분석 실행 → ai_clicked 로 전파
        review_page.ai_clicked.connect(self._on_ai_emit)
        review_page.stop_requested.connect(self.stop_requested)

        # ① 사양 변경 페이지 — 이슈 묶음별 [📤 등록] → CB 업로드로 전파
        spec_page.change_register_requested.connect(self.change_register_requested)
        # ① 사양 변경 페이지 — 헤더 [📤 전체 등록] → CB 일괄 업로드로 전파
        spec_page.change_register_all_requested.connect(
            self.change_register_all_requested)
        # ① 사양 변경 페이지 — 사양변경/수평전개 탭 [📤 등록] → CB 업로드로 전파
        spec_page.spec_register_requested.connect(self.spec_register_requested)
        spec_page.hzt_register_requested.connect(self.hzt_register_requested)

    # ── 코드 DIFF 추출 버튼 클릭 시 params 구성 ──────────────
    def _on_diff_btn(self):
        from core.text_io import read_text_lines
        from core.model    import build_unified_diff
        ap = self._review.result.analysis_panel
        extras = self._review.result.extras_panel
        mode = ap.get_input_mode()
        code_info    = extras.get_code_info()
        opts         = extras.get_opts()
        include_opts = self._build_include_opts(extras)

        if mode == "folder":
            old_path = ap.get_old_folder_path()
            new_path = ap.get_new_folder_path()
            if not old_path or not new_path:
                return
            params = {
                "mode":            "folder",
                "old_folder":      old_path,
                "new_folder":      new_path,
                "file_pairs":      [],
                "old_code":        "",
                "new_code":        "",
                "diff_code":       "",
                "code_info":       code_info,
                "req_text":        "",
                "opts":            opts,
                "include_opts":    include_opts,
                "ignore_comments": ap.get_ignore_comments(),
            }
        else:
            old_path = ap.get_old_path()
            new_path = ap.get_new_path()
            if not old_path or not new_path:
                return
            old_lines = read_text_lines(old_path)
            new_lines = read_text_lines(new_path)
            params = {
                "old_lines":       old_lines,
                "new_lines":       new_lines,
                "old_code":        "\n".join(old_lines),
                "new_code":        "\n".join(new_lines),
                "diff_code":       build_unified_diff(
                    old_lines, new_lines,
                    os.path.basename(old_path), os.path.basename(new_path)),
                "code_info":       code_info,
                "req_text":        "",
                "opts":            opts,
                "include_opts":    include_opts,
                "ignore_comments": ap.get_ignore_comments(),
                "single_filename": os.path.basename(new_path),
            }
        self._last_params = params
        self._review.set_last_params(params)
        self.diff_clicked.emit(params)
        # 단일 파일 모드는 즉시 활성, 폴더 모드는 워커 완료 후 enable_ai() 호출됨
        if mode != "folder":
            self._review.enable_ai()

    def _on_ai_emit(self, params):
        # AI 실행 직전 ExtrasPanel 의 최신 옵션을 반영해 emit.
        extras = self._review.result.extras_panel
        params = dict(params)
        params["code_info"]    = extras.get_code_info()
        params["opts"]         = extras.get_opts()
        params["include_opts"] = self._build_include_opts(extras)
        self.ai_clicked.emit(params)

    @staticmethod
    def _build_include_opts(extras) -> dict:
        """ExtrasPanel 의 'AI 분석에 포함' 체크박스 상태를 ai_controller 가
        쓰는 include_opts dict 로 변환.

        ai_controller 는 include_opts.get(key, True) 로 읽으므로,
        체크 안 된 키만 False 로 넣어주면 충분하다 (다른 키는 default True).
        """
        opts = {}
        for key in ("code_info", "past", "static"):
            if hasattr(extras, "get_include"):
                opts[key] = extras.get_include(key)
        return opts

    # ── controllers 가 호출하는 메서드들 ─────────────────────
    def get_project_meta(self) -> dict:
        return self._spec.get_project_meta()

    def get_project_header_md(self) -> str:
        return self._spec.get_project_header_md()

    def get_change_items_md(self) -> str:
        return self._spec.get_change_items_md()

    def get_project_name(self) -> str:
        return self._spec.get_project_name()

    def update_cb_status(self, ok: bool):
        pass  # 좌측 사이드바엔 CB 상태 표시 없음

    def set_diff_running(self, running: bool):
        self._review.set_diff_running(running)

    def set_ai_running(self, running: bool):
        self._review.set_ai_running(running)

    def enable_ai(self):
        self._review.enable_ai()

    def set_folder_pairs(self, pairs: list):
        if self._last_params is not None:
            self._last_params["file_pairs"] = pairs
        self._review.set_last_params(self._last_params)

    def set_analysis_panel(self, panel):
        pass   # 이미 ReviewPage 내부에서 연결됨

    def set_include_opt(self, key: str, checked: bool):
        pass   # 좌측 리뷰 옵션 panel 제거됨


# ══════════════════════════════════════════════════════════════
#  ResultShim — 컨트롤러가 기대하는 ResultPanel 인터페이스 어댑터.
#  실제 데이터는 ReviewPage.result(ResultPanel) + SrsPage 가 보유.
# ══════════════════════════════════════════════════════════════
class ResultShim(QObject):
    export_full_xlsx_clicked = pyqtSignal()
    export_full_html_clicked = pyqtSignal()
    cb_upload_clicked        = pyqtSignal()
    req_diff_requested       = pyqtSignal()
    include_changed          = pyqtSignal(str, bool)

    def __init__(self, review_page: ReviewPage, srs_page: SrsPage):
        super().__init__()
        self._review = review_page
        self._srs    = srs_page

        rp = review_page.result
        # ResultPanel 의 시그널 forward
        rp.export_full_xlsx_clicked.connect(self.export_full_xlsx_clicked)
        rp.export_full_html_clicked.connect(self.export_full_html_clicked)
        rp.cb_upload_clicked.connect(self.cb_upload_clicked)
        rp.include_changed.connect(self.include_changed)

        # SRS 페이지에서 'DIFF 추출' 요청 → req_diff_requested 전파
        srs_page.diff_requested.connect(self.req_diff_requested)

        # ⑥ 헤더의 [📤 CB 업로드] 클릭 → ResultPanel 의 동일 시그널 발생
        review_page.upload_clicked.connect(self.cb_upload_clicked.emit)
        # ⑥ 헤더의 [💾 결과물 저장] 클릭 → ResultPanel 의 저장 팝업 호출
        # ★ anchor_btn=header.save_btn 전달 — 팝업이 헤더 버튼 아래에 뜨도록
        #   (전달 안 하면 ResultPanel 내부의 숨겨진 _save_btn 위치에 떠서 엉뚱한 곳에 표시됨)
        review_page.save_clicked.connect(
            lambda: review_page.result._show_save_popup(
                anchor_btn=review_page.header.save_btn))

        self._extras_proxy = _ExtrasProxy(rp.extras_panel, srs_page)

    # ── ResultPanel 메서드 위임 ───────────────────────────────
    def clear(self):                   self._review.result.clear()
    def set_summary(self, t):          self._review.result.set_summary(t)
    def set_vuln(self, t):             self._review.result.set_vuln(t)
    def update_vuln_text(self, t):     self._review.result.update_vuln_text(t)
    def set_project_name(self, n):     self._review.result.set_project_name(n)
    def auto_fetch_cb(self):           self._review.result.auto_fetch_cb()
    def set_include_opt(self, k, c):   self._review.result.set_include_opt(k, c)
    def get_single_file_checked(self):
        return self._review.result.get_single_file_checked()
    def get_checked_folder_pairs(self):
        return self._review.result.get_checked_folder_pairs()
    def get_cb_filtered_md(self, k):
        return self._review.result.get_cb_filtered_md(k)
    def get_current_file_lines(self):
        return self._review.result.get_current_file_lines()
    def render_diff(self, old_lines, new_lines, func_list,
                    old_cmp=None, new_cmp=None, filename=""):
        self._review.result.render_diff(
            old_lines, new_lines, func_list,
            old_cmp=old_cmp, new_cmp=new_cmp, filename=filename)
        # 코드 DIFF 추출이 완료되면 자동으로 OUTPUT > 변경점 VIEW 로 전환
        self._review.switch_to_output("diff")
    def render_folder(self, file_pairs, per_file_func_counts=None):
        self._review.result.render_folder(file_pairs, per_file_func_counts)
        self._review.switch_to_output("diff")

    # 요구사항 DIFF 결과 → SRS 페이지로
    def set_req_diff(self, old_lines, new_lines):
        self._srs.render_diff(old_lines, new_lines)

    # ── 속성 접근 ─────────────────────────────────────────────
    @property
    def extras_panel(self):
        return self._extras_proxy

    @property
    def analysis_panel(self):
        return self._review.result.analysis_panel

    @property
    def step_bar(self):
        return self._review.result.step_bar

    # cb_controller / ui_save 가 직접 접근하는 내부 위젯/속성
    def __getattr__(self, name):
        # __getattr__ 은 표준 속성 lookup 실패 시에만 호출됨.
        # ResultPanel 내부 위젯(_sum_view, _vuln_view, _cb_upload_btn,
        # _project_name) 을 그대로 노출.
        if name.startswith("_"):
            inner = self.__dict__.get("_review")
            if inner is not None:
                return getattr(inner.result, name)
        raise AttributeError(name)


# ══════════════════════════════════════════════════════════════
#  MainWindow — 9탭 셸을 메인 영역에 배치
# ══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ── 현재 작업 중인 프로젝트 정보 ──────────────────────────
        # 시작 다이얼로그(ProjectStartDialog)에서 입력받아 세팅된다.
        # project_state JSON 의 키 + 각 컨트롤러가 트래커 ID 조회 시 사용.
        self._project_name:    str  = ""
        self._project_version: str  = ""
        self._project_trackers: dict = {}   # {page_key: tracker_id, ...}

        self.setWindowTitle("SW 배포 파이프라인")
        # 윈도우 타이틀바 좌측 아이콘 — QApplication 디폴트가 있어도 명시.
        _icon_path = _app_icon_path()
        if os.path.exists(_icon_path):
            self.setWindowIcon(QIcon(_icon_path))

        screen = QApplication.primaryScreen()
        if screen:
            ag = screen.availableGeometry()
            init_w = min(2300, int(ag.width()  * 0.92))
            init_h = min(1400, int(ag.height() * 0.92))
            self.resize(init_w, init_h)
            self.move(
                ag.left() + (ag.width()  - init_w) // 2,
                ag.top()  + (ag.height() - init_h) // 2,
            )
        else:
            self.resize(1400, 900)
        self.setMinimumSize(1100, 700)

        # DPI 스케일에 맞춰 QSS 재생성 및 적용
        _scale = get_dpi_scale()
        QApplication.instance().setStyleSheet(build_qss(_scale))

        # ── 페이지 인스턴스 생성 ───────────────────────────────
        self._page_spec   = SpecChangePage()
        self._page_srs    = SrsPage()
        self._page_sad    = SadPage()
        self._page_sdd    = SddPage()
        self._page_static = StaticResultPage()
        self._page_review = ReviewPage()
        self._page_test   = TestResultPage()
        self._page_open   = OpenItemsPage()
        self._page_deploy = DeployReviewPage()

        # ── 컨트롤러 ──────────────────────────────────────────
        self._cb   = CbController(self)
        self._diff = DiffController(self)
        self._ai   = AiController(self)
        # ── 체크리스트 회의 컨트롤러 (구 SRS 검토 v2 — 이름만 유지) ──
        # 2-B (2026-06) 부터 호스트 페이지 = ① 사양변경 페이지의 '체크리스트
        # 회의' 탭.
        self._srs_review_v2 = None
        if (getattr(self._page_spec, "cb_historical_tab", None) is not None
                and getattr(self._page_spec, "checklist_review_tab", None) is not None):
            self._srs_review_v2 = SrsReviewV2Controller(self, self._page_spec)

        # ── ②③④ SWE 새 워크플로우 컨트롤러 (3-D, 2026-06) ──────
        # 변경점 불러오기 / AI 분석 실행 / CB 업로드 시그널 연결.
        self._swe_srs = SweReviewController(self, "srs", self._page_srs)
        self._swe_sad = SweReviewController(self, "sad", self._page_sad)
        self._swe_sdd = SweReviewController(self, "sdd", self._page_sdd)

        # ── shim (컨트롤러 호환) ──────────────────────────────
        self._result = ResultShim(self._page_review, self._page_srs)
        self._input  = InputShim(self._page_spec, self._page_review, self._result)

        self._build_shell()
        self._wire_signals()
        self._wire_placeholder_buttons()

        # 직전 세션에서 저장된 ① 사양 변경 페이지 입력값 복원
        try:
            self._page_spec.load_state()
        except Exception:
            pass
        # ② SWE.1 SRS 검토 페이지 (트래커 ID + 체크리스트/검토/회의록) 복원
        try:
            self._page_srs.load_state()
        except Exception:
            pass

    def _build_shell(self):
        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)

        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        self._shell = MainShell()
        self._shell.add_page("spec",   self._page_spec)
        self._shell.add_page("srs",    self._page_srs)
        self._shell.add_page("sad",    self._page_sad)
        self._shell.add_page("sdd",    self._page_sdd)
        self._shell.add_page("static", self._page_static)
        self._shell.add_page("review", self._page_review)
        self._shell.add_page("test",   self._page_test)
        self._shell.add_page("open",   self._page_open)
        self._shell.add_page("deploy", self._page_deploy)
        lay.addWidget(self._shell)

        # 사이드바 헤더의 🔌 Codebeamer 설정 버튼 → CB 다이얼로그
        self._shell.sidebar.cb_config_clicked.connect(self._cb.open_dialog)

        # 상태바
        self._sb = QStatusBar(); self.setStatusBar(self._sb)
        self._sb.showMessage(
            "왼쪽 사이드바에서 페이지를 선택하세요. ")

    def _wire_signals(self):
        # 컨트롤러 ↔ shim 시그널 연결 (기존 main.py 와 동일 패턴)
        self._input.diff_clicked.connect(self._diff.on_diff)
        self._input.ai_clicked.connect(self._ai.on_ai)
        self._input.stop_requested.connect(self._ai.on_stop)
        self._input.cb_clicked.connect(self._cb.open_dialog)
        self._input.change_register_requested.connect(
            self._cb.on_register_change_item)
        self._input.change_register_all_requested.connect(
            self._cb.on_register_all_change_items)
        self._input.spec_register_requested.connect(
            self._cb.on_register_spec_change)
        self._input.hzt_register_requested.connect(
            self._cb.on_register_hzt_item)
        # ① 사양 변경 페이지 — [📥 트래커에서 불러오기] 버튼
        self._page_spec.load_requested.connect(self._cb.on_spec_page_load)
        # ② SRS / ③ SAD / ④ SDD / ⑤ 정적 / ⑥ 코드리뷰 / ⑦ 설계자 테스트
        # — [📥 불러오기] 헤더 버튼 (page_key 와 함께 공통 핸들러로 전달)
        self._page_srs.load_requested.connect(
            lambda: self._cb.on_swe_page_load("srs"))
        self._page_sad.load_requested.connect(
            lambda: self._cb.on_swe_page_load("sad"))
        self._page_sdd.load_requested.connect(
            lambda: self._cb.on_swe_page_load("sdd"))
        self._page_static.load_requested.connect(
            lambda: self._cb.on_swe_page_load("static"))
        self._page_review.load_requested.connect(
            lambda: self._cb.on_swe_page_load("review"))
        self._page_test.load_requested.connect(
            lambda: self._cb.on_swe_page_load("test"))

        self._result.req_diff_requested.connect(self._diff.on_req_diff)
        self._result.export_full_xlsx_clicked.connect(self._on_export_full_xlsx)
        self._result.export_full_html_clicked.connect(self._on_export_full_html)
        self._result.cb_upload_clicked.connect(self._cb.on_cb_upload)

        # InputShim include_changed 와 ResultShim include_changed 양방향 동기화
        # — 좌측 InputPanel 의 옵션 panel 이 제거되었으므로 단방향 (Result→ no-op) 만 의미.
        self._input.include_changed.connect(self._result.set_include_opt)
        self._result.include_changed.connect(self._input.set_include_opt)

    def _wire_placeholder_buttons(self):
        """placeholder 페이지 + SWE 페이지 헤더의 저장/CB 업로드 버튼은 임시.

        클릭 시 상태바에 안내만 표시.
        ⑧/⑨ 페이지는 실제 CB 업로드 핸들러와 연결되므로 별도 처리.
        """
        for page in (self._page_spec, self._page_srs, self._page_sad,
                     self._page_sdd, self._page_static, self._page_test):
            page.save_clicked.connect(
                lambda: self._sb.showMessage(
                    "ℹ  이 페이지의 결과물 저장 기능은 추후 설계 예정입니다."))
            page.upload_clicked.connect(
                lambda: self._sb.showMessage(
                    "ℹ  CB 업로드는 ⑥ 코드리뷰 결과 페이지에서만 활성화됩니다."))

        # ── ⑧ OPEN 항목 & 잔여 조치 ─────────────────────────────
        # [💾 결과물 저장] 헤더 버튼은 일단 상태바 안내 (추후 MD/HTML 저장 시 확장)
        self._page_open.save_clicked.connect(
            lambda: self._sb.showMessage(
                "ℹ  ⑧ 페이지 결과물 저장 기능은 추후 설계 예정입니다."))
        # [📥 불러오기] 카드 버튼 — ⑤⑥⑦ 결과 자동 채움
        self._page_open.load_requested.connect(self._cb.on_open_items_load)
        # [📤 CB 업로드] 헤더 버튼 — CbUploadDialog → 워커
        self._page_open.upload_clicked.connect(self._cb.on_open_items_upload)

        # ── ⑨ 배포 리뷰 ─────────────────────────────────────────
        self._page_deploy.save_clicked.connect(
            lambda: self._sb.showMessage(
                "ℹ  ⑨ 페이지 결과물 저장 기능은 추후 설계 예정입니다."))
        # [📥 불러오기] 카드 버튼 — project_state JSON 에서 트래커 로드
        self._page_deploy.load_requested.connect(self._cb.on_deploy_review_load)
        # [📤 CB 업로드] 헤더 버튼
        self._page_deploy.upload_clicked.connect(self._cb.on_deploy_review_upload)

    def show_startup_dialogs(self):
        """앱 시작 직후 — CB 연결 다이얼로그 → 프로젝트 정보 다이얼로그 순차 표시.

        1) CbConfigDialog — 서버 URL/계정/PW 입력 (modal)
        2) ProjectStartDialog — 프로젝트명/버전/9개 트래커 ID 입력 (modal)
           결과로 MainWindow 의 _project_name/_project_version/_project_trackers
           세팅 + ① 페이지 메타에 자동 복사.
        """
        try:
            self._cb.open_dialog()           # blocking — CB 다이얼로그 닫힐 때까지 대기
        except Exception as e:
            self._sb.showMessage(f"⚠  CB 연동 다이얼로그 표시 실패: {e}")
        # CB 다이얼로그 닫힌 후 (취소했더라도) 프로젝트 다이얼로그 표시
        self._show_project_dialog()

    # 기존 명칭 호환 — 외부에서 호출하는 경우 대비 alias 유지
    def show_startup_cb_dialog(self):
        self.show_startup_dialogs()

    def _show_project_dialog(self):
        """ProjectStartDialog 표시 + 결과 적용."""
        from view.ui_project_dialog import ProjectStartDialog
        dlg = ProjectStartDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            # 취소 — 빈 상태로 시작 (사용자가 메뉴에서 나중에 열 수 있도록 한다)
            self._sb.showMessage(
                "⚠  프로젝트 정보 미입력 — 일부 기능이 제한됩니다.")
            return
        data = dlg.result_data or {}
        self._apply_project_info(data)

    def _apply_project_info(self, data: dict):
        """프로젝트 다이얼로그 결과를 MainWindow + ① 페이지에 반영."""
        self._project_name     = str(data.get("project_name") or "")
        self._project_version  = str(data.get("version")      or "")
        self._project_trackers = dict(data.get("trackers")    or {})

        # ① 사양 변경 페이지의 메타 입력 칸에 자동 복사 (사용자가 수정 가능)
        try:
            sp = self._page_spec
            if hasattr(sp, "proj_name") and self._project_name:
                sp.proj_name.setText(self._project_name)
            if hasattr(sp, "proj_ver_new") and self._project_version:
                sp.proj_ver_new.setText(self._project_version)
        except Exception:
            pass

        # 윈도우 타이틀에 프로젝트 정보 표시
        if self._project_name and self._project_version:
            self.setWindowTitle(
                f"SW 배포 파이프라인 — {self._project_name} (v{self._project_version})")
            self._sb.showMessage(
                f"📋  프로젝트: {self._project_name} (v{self._project_version}) — "
                f"트래커 ID {sum(1 for v in self._project_trackers.values() if v)}/9 등록")

    def closeEvent(self, event):
        """앱 종료 시 ① 사양변경 / ② SWE.1 SRS 페이지 입력값 자동 저장.
        실패는 무시 — 사용자 종료 흐름 방해 X.
        """
        try:
            self._page_spec.save_state()
        except Exception:
            pass
        try:
            self._page_srs.save_state()
        except Exception:
            pass
        super().closeEvent(event)

    # ── 엑셀/HTML 추출 (기존 main.py 와 동일) ─────────────────
    def _on_export_full_xlsx(self):
        ui_diff_export.export_full_xlsx(
            self, self._result, self._sb,
            self._diff.old_lines, self._diff.new_lines,
        )

    def _on_export_full_html(self):
        ui_diff_export.export_full_html(
            self, self._result, self._sb,
            self._diff.old_lines, self._diff.new_lines,
        )


def _app_icon_path() -> str:
    """앱 아이콘(SVG) 절대 경로 반환.
    개발 모드: 프로젝트 루트의 assets/app_icon.svg
    EXE(frozen) 모드: PyInstaller 임시 추출 경로(_MEIPASS)/assets/app_icon.svg
    """
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "app_icon.svg")


def _deploy_bundled_resources():
    """EXE(frozen) 실행 시 번들된 prompts MD 파일을 %APPDATA%\\CodeReviewer 에 배포."""
    if not getattr(sys, "frozen", False):
        return
    import shutil

    appdata_base = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), "CodeReviewer")
    src_review = os.path.join(sys._MEIPASS, "prompts")
    dst_review = os.path.join(appdata_base, "prompts")

    if os.path.isdir(src_review):
        shutil.copytree(src_review, dst_review, dirs_exist_ok=True)


def main():
    _deploy_bundled_resources()
    app = QApplication(sys.argv)
    app.setApplicationName("SW 배포 파이프라인")
    # 작업표시줄 / Alt-Tab 아이콘 — 모든 윈도우의 디폴트 아이콘으로 사용됨
    _icon_path = _app_icon_path()
    if os.path.exists(_icon_path):
        app.setWindowIcon(QIcon(_icon_path))
    app.setStyle("Fusion")
    app.setStyleSheet(build_qss(1.0))

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(C.BG_APP))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(C.T0))
    pal.setColor(QPalette.ColorRole.Base,            QColor(C.BG_PANEL))
    pal.setColor(QPalette.ColorRole.Text,            QColor(C.T0))
    pal.setColor(QPalette.ColorRole.Button,          QColor(C.BG_INPUT))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(C.T0))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(C.BLUE))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    # 윈도우 표시 직후 — CB 연결 다이얼로그 → 프로젝트 정보 다이얼로그 순차 표시
    QTimer.singleShot(150, win.show_startup_dialogs)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
