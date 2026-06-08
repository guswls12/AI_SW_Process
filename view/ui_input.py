"""ui_input.py — 좌측 InputPanel 및 헤더 위젯.

view.py 에서 분리된 컴포넌트:
  _AppHeader  : 좌측 패널 상단 브랜딩 (InputPanel 전용)
  InputPanel  : 프로젝트명 / 코드정보 / 리뷰옵션 / AI 포함 옵션 / CB 연동 + AI 실행 버튼
"""

import os
import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QCheckBox, QProgressBar,
    QLineEdit, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from config import C
from core.model import build_unified_diff
from core.text_io import read_text_lines


# ──────────────────────────────────────────────────────────────
#  공용 그림자 헬퍼 (view.py 와 동일)
# ──────────────────────────────────────────────────────────────
def _shadow(widget, blur: int = 18, dx: int = 0, dy: int = 4, alpha: int = 18):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(dx)
    eff.setYOffset(dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)


# ══════════════════════════════════════════════════════════════
#  _AppHeader — 좌측 패널 브랜딩 헤더 (내부용)
# ══════════════════════════════════════════════════════════════
class _AppHeader(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("app_header")
        self.setFixedHeight(76)
        self.setStyleSheet(
            f"#app_header {{ background:{C.BG_PANEL}; "
            f"border-bottom:1px solid {C.BDR}; }}"
        )

        # self._egg_count = 0   # 이스터에그 클릭 카운터  [DISABLED]

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 18, 0)
        lay.setSpacing(12)

        # 아이콘 박스
        icon_box = QFrame()
        icon_box.setObjectName("icon_box")
        icon_box.setFixedSize(38, 38)
        icon_box.setStyleSheet(
            f"#icon_box {{ background:{C.BLUE_LT}; border:1px solid {C.BDR}; border-radius:8px; }}"
        )
        # icon_box.setCursor(Qt.CursorShape.PointingHandCursor)  # [DISABLED] 이스터에그용
        ib = QHBoxLayout(icon_box)
        ib.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setText("📑")
        icon_lbl.setFont(QFont(C.FUI, 16, QFont.Weight.Bold))
        icon_lbl.setStyleSheet("background:transparent;")
        ib.addWidget(icon_lbl)
        lay.addWidget(icon_box)

        # [DISABLED] 이스터에그 핸들러 — view.py 원본 참고

        # 텍스트 정보
        info = QVBoxLayout()
        info.setSpacing(2)
        title = QLabel("AI - 코드 리뷰")
        title.setFont(QFont(C.FUI, 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C.T0}; background:transparent;")
        info.addWidget(title)
        sub = QLabel("ver 1.0 - 변경점 코드 리뷰")
        sub.setFont(QFont(C.FUI, 9))
        sub.setStyleSheet(f"color:{C.T3}; background:transparent;")
        info.addWidget(sub)
        lay.addLayout(info)
        lay.addStretch()


# ══════════════════════════════════════════════════════════════
#  InputPanel — 좌측 입력 패널
# ══════════════════════════════════════════════════════════════
class InputPanel(QWidget):
    diff_clicked    = pyqtSignal(dict)
    ai_clicked      = pyqtSignal(dict)
    stop_requested  = pyqtSignal()         # ★ AI 분석 중단 요청
    cb_clicked      = pyqtSignal()         # ★ Codebeamer 설정 버튼
    include_changed = pyqtSignal(str, bool)  # (key, checked) — ExtrasPanel 동기화
    # 백그라운드 스레드에서 CB 연결 테스트 결과를 UI 스레드로 전달하기 위한 내부 시그널
    # (QTimer.singleShot은 Qt 이벤트 루프가 없는 Python threading.Thread 에서는 동작하지 않음)
    _cb_test_finished = pyqtSignal(bool, str)

    OPT_ITEMS = [
        ("cert_c",    "① CERT-C"),
        ("misra_c",   "② MISRA-C (2012)"),
        ("misra_c23", "③ MISRA-C (2023)"),
        # ("extra1",    "④ 추가 예정"),   # [EXTRA1 DISABLED]
    ]

    # AI 포함 옵션 항목 (key, 레이블)
    INCLUDE_ITEMS = [
        ("req",  "요구사항"),
        ("past", "과거차 (CB)"),
        # ("ll",   "L&L (CB)"),   # [LL/SWE DISABLED]
        # ("swe1", "SWE1 (CB)"),  # [LL/SWE DISABLED]
        # ("swe3", "SWE3 (CB)"),  # [LL/SWE DISABLED]
        # ↓ "파일 전체 컨텍스트" 옵션은 AI 분석 확인 다이얼로그로 이동 —
        #   거기서 토글하면 입력 토큰 카운트가 실시간으로 갱신되어 비용 영향을
        #   바로 볼 수 있음 (ai_controller._show_confirm_dialog 참고)
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_params: dict = {}
        self._ai_running  = False   # ★ 분석 진행 중 플래그
        self._analysis_panel = None
        self._include_chks: dict[str, QCheckBox] = {}
        # CB 인라인 연결 필드
        self._cb_url_edit: QLineEdit = None
        self._cb_id_edit:  QLineEdit = None
        self._cb_pw_edit:  QLineEdit = None
        self._cb_test_btn: QPushButton = None
        self._cb_status_lbl: QLabel = None
        self._build()

    def set_analysis_panel(self, panel):
        """ResultPanel의 분석파일 선택 패널 참조를 저장하고 신호 연결."""
        self._analysis_panel = panel
        panel.diff_requested.connect(self._on_diff)
        # req_include_changed → ExtrasPanel 로 이동됨 (연결 불필요)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        # ── 앱 헤더 ──────────────────────────────────────────
        outer.addWidget(_AppHeader())

        # ── 스크롤 영역 ───────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(18, 18, 18, 10); lay.setSpacing(20)

        # ── ① 프로젝트명 ──────────────────────────────────────
        lay.addWidget(self._sec_hdr("🗂", "프로젝트명"))
        proj_card = QFrame(); proj_card.setObjectName("card")
        pl = QVBoxLayout(proj_card); pl.setContentsMargins(14, 12, 14, 12); pl.setSpacing(8)
        r0, self._proj_name    = self._info_row("변경내용요약",     "예) NX5 PLBM 30Ah, BSP 변경 사항")
        r1, self._proj_mcu     = self._info_row("제어기",          "예) STM32H743")
        r2, self._proj_ver_old = self._info_row("변경 전 (.ver)",  "예) 1.2.0")
        r3, self._proj_ver_new = self._info_row("변경 후 (.ver)",  "예) 1.2.1")
        r4, self._proj_author  = self._info_row("설계자",          "예) 홍길동")
        for r in (r0, r1, r2, r3, r4): pl.addLayout(r)
        _shadow(proj_card)
        lay.addWidget(proj_card)

        # ── ② 날짜 ────────────────────────────────────────────
        lay.addWidget(self._sec_hdr("📅", "날짜"))
        date_card = QFrame(); date_card.setObjectName("card")
        dl = QVBoxLayout(date_card); dl.setContentsMargins(14, 12, 14, 12); dl.setSpacing(8)
        dr, self._date_edit = self._info_row("날짜", "예) 2026-04-10")
        self._date_edit.setText(datetime.date.today().isoformat())
        dl.addLayout(dr)
        _shadow(date_card)
        lay.addWidget(date_card)

        # ── ③ 코드 정보 ───────────────────────────────────────
        lay.addWidget(self._sec_hdr("💡", "코드 정보  (선택)"))
        info_card = QFrame(); info_card.setObjectName("card")
        il = QVBoxLayout(info_card); il.setContentsMargins(14, 12, 14, 12); il.setSpacing(8)
        r5, self._info_mcu    = self._info_row("MCU",     "예) Traveo CYT2B93CA 64Pin")
        r6, self._info_comm   = self._info_row("통신",    "예) CAN/LIN, RS485")
        r7, self._info_env    = self._info_row("실행환경", "예) ECU 상태와 통신상태를 제어하는 코드")
        r8, self._info_ctx    = self._info_row("환경",    "예) 멀티 코어 운영")
        r9, self._info_intent = self._info_row("의도",    "예) 변경 의도 작성")
        for r in (r5, r6, r7, r8, r9): il.addLayout(r)
        _shadow(info_card)
        lay.addWidget(info_card)

        # ── ④ 리뷰 옵션 ───────────────────────────────────────
        lay.addWidget(self._sec_hdr("☑", "정적 검증"))
        opt = QFrame(); opt.setObjectName("card")
        ol = QVBoxLayout(opt); ol.setContentsMargins(14, 12, 14, 12); ol.setSpacing(4)

        ar = QHBoxLayout()
        self._chk_all = QCheckBox("전체 선택")
        self._chk_all.setChecked(False)
        self._chk_all.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        self._chk_all.setStyleSheet(f"color:{C.T0};")
        self._chk_all.stateChanged.connect(self._toggle_all)
        ar.addWidget(self._chk_all); ar.addStretch(); ol.addLayout(ar)
        _sep1 = QFrame(); _sep1.setFixedHeight(1); _sep1.setStyleSheet(f"background:{C.BDR};")
        ol.addWidget(_sep1)

        self._opts: dict[str, QCheckBox] = {}
        for key, label in self.OPT_ITEMS:
            chk = QCheckBox(f"  {label}"); chk.setChecked(False)
            self._opts[key] = chk; ol.addWidget(chk)

        # MISRA 상호 배타: misra_c ↔ misra_c23 동시 선택 불가
        def _make_opt_handler(excl_k=None):
            def _h(state):
                if excl_k and state == Qt.CheckState.Checked.value and excl_k in self._opts:
                    self._opts[excl_k].blockSignals(True)
                    self._opts[excl_k].setChecked(False)
                    self._opts[excl_k].blockSignals(False)
                self._sync_all_chk()
            return _h
        for k in self._opts:
            if k == "misra_c":
                self._opts[k].stateChanged.connect(_make_opt_handler("misra_c23"))
            elif k == "misra_c23":
                self._opts[k].stateChanged.connect(_make_opt_handler("misra_c"))
            else:
                self._opts[k].stateChanged.connect(_make_opt_handler())
        _shadow(opt)
        lay.addWidget(opt)

        # ── ⑤ AI 분석 포함 ────────────────────────────────────
        lay.addWidget(self._sec_hdr("🤖", "리뷰 옵션"))
        inc_card = QFrame(); inc_card.setObjectName("card")
        incl = QVBoxLayout(inc_card); incl.setContentsMargins(14, 10, 14, 12); incl.setSpacing(6)

        _chk_ss = (
            f"QCheckBox {{ color:{C.T1}; background:transparent; spacing:8px; }}"
            f"QCheckBox::indicator {{ width:14px; height:14px; border-radius:3px;"
            f"  border:1px solid {C.BDR2}; background:{C.BG_INPUT}; }}"
            f"QCheckBox::indicator:checked {{ background:{C.BLUE}; border-color:{C.BLUE}; }}"
            f"QCheckBox::indicator:indeterminate {{ background:{C.BLUE}; border-color:{C.BLUE}; }}"
            f"QCheckBox::indicator:hover {{ border-color:{C.BLUE}; }}")

        # 전체선택 체크박스
        self._include_all_chk = QCheckBox("  전체 선택")
        self._include_all_chk.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        self._include_all_chk.setStyleSheet(_chk_ss)
        incl.addWidget(self._include_all_chk)
        _sep2 = QFrame(); _sep2.setFixedHeight(1); _sep2.setStyleSheet(f"background:{C.BDR};")
        incl.addWidget(_sep2)

        for key, label in self.INCLUDE_ITEMS:
            chk = QCheckBox(f"  {label}")
            chk.setChecked(False)
            chk.setFont(QFont(C.FUI, 10))
            chk.setStyleSheet(_chk_ss)
            chk.stateChanged.connect(
                lambda state, k=key: self._on_include_changed(k, state))
            self._include_chks[key] = chk
            incl.addWidget(chk)

        def _on_all_clicked():
            target = self._include_all_chk.isChecked()
            for chk in self._include_chks.values():
                chk.blockSignals(True)
                chk.setChecked(target)
                chk.blockSignals(False)
            for k in self._include_chks:
                self.include_changed.emit(k, target)

        self._include_all_chk.clicked.connect(_on_all_clicked)

        _shadow(inc_card)
        lay.addWidget(inc_card)

        # ── ⑥ CB 연동 ─────────────────────────────────────────
        lay.addWidget(self._sec_hdr("🔗", "Codebeamer 연동"))
        cb_card = QFrame(); cb_card.setObjectName("card")
        cbl = QVBoxLayout(cb_card); cbl.setContentsMargins(14, 12, 14, 12); cbl.setSpacing(8)

        # URL 행
        url_row, self._cb_url_edit = self._info_row("URL", "예) https://cb.example.com")
        cbl.addLayout(url_row)
        # ID 행
        id_row, self._cb_id_edit = self._info_row("ID", "Codebeamer 아이디")
        cbl.addLayout(id_row)
        # PW 행
        pw_row, self._cb_pw_edit = self._info_row("PW", "비밀번호")
        self._cb_pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        cbl.addLayout(pw_row)

        # 연결테스트 버튼 + 상태 표시
        conn_row = QHBoxLayout(); conn_row.setSpacing(8)
        self._cb_test_btn = QPushButton("🔌  연결 테스트")
        self._cb_test_btn.setObjectName("btn_sub"); self._cb_test_btn.setFixedHeight(28)
        self._cb_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cb_test_btn.clicked.connect(self._on_cb_test)
        self._cb_status_lbl = QLabel("")
        self._cb_status_lbl.setFont(QFont(C.FUI, 9))
        self._cb_status_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")
        conn_row.addWidget(self._cb_test_btn)
        conn_row.addWidget(self._cb_status_lbl, stretch=1)
        cbl.addLayout(conn_row)

        # 저장된 CB 설정 불러오기
        self._load_cb_inline_config()
        _shadow(cb_card)
        lay.addWidget(cb_card)

        lay.addStretch()
        scroll.setWidget(body); outer.addWidget(scroll, stretch=1)

        # ── 하단 액션 버튼 ────────────────────────────────────
        bot = QFrame()
        bot.setObjectName("input_bot")
        bot.setStyleSheet(
            f"#input_bot {{ background:{C.BG_PANEL}; border-top:1px solid {C.BDR}; }}")
        bl = QVBoxLayout(bot); bl.setContentsMargins(16, 10, 16, 14); bl.setSpacing(8)

        self._prog = QProgressBar(); self._prog.setRange(0, 0); self._prog.hide()
        bl.addWidget(self._prog)

        self._ai_btn = QPushButton("  🤖  AI 분석 실행")
        self._ai_btn.setObjectName("btn_ai"); self._ai_btn.setFixedHeight(44)
        self._ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # 프로그램 메인 BLUE 패밀리로 통일 (기존 #CEEAF6/#BBCEF0/#A3BDED 톤)
        self._ai_btn.setStyleSheet(f"""
            QPushButton#btn_ai {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {C.BLUE_DK}, stop:1 {C.BLUE});
                color:#FFFFFF; border:2px solid {C.BLUE_DK}; border-radius:10px;
                font-size:13px; font-weight:bold; padding:13px 18px;
            }}
            QPushButton#btn_ai:hover {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {C.BLUE}, stop:1 {C.BLUE_LT});
                border-color:{C.ACCENT_H};
            }}
            QPushButton#btn_ai:pressed {{ background:{C.BLUE_DK}; color:#FFFFFF; }}
            QPushButton#btn_ai:disabled {{
                background:{C.BDR}; color:{C.T3};
                border:2px solid {C.BDR2}; font-size:13px;
            }}""")
        self._ai_btn.setEnabled(False)
        self._ai_btn.setToolTip("DIFF 추출 후 활성화됩니다")
        self._ai_btn.clicked.connect(self._on_ai)
        bl.addWidget(self._ai_btn)
        outer.addWidget(bot)

    # ── 섹션 헤더 헬퍼 (왼쪽 파란 액센트 바) ────────────────
    @staticmethod
    def _sec_hdr(icon: str, text: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(w); lay.setContentsMargins(0, 4, 0, 4); lay.setSpacing(10)

        # 파란 세로 액센트 바
        accent = QFrame()
        accent.setFixedSize(3, 16)
        accent.setStyleSheet(
            f"background:{C.BLUE}; border-radius:2px;")
        lay.addWidget(accent)

        t = QLabel(f"{icon}  {text}")
        t.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.T1}; background:transparent;")
        lay.addWidget(t); lay.addStretch()
        return w

    # ── 코드 정보 입력 행 헬퍼 ───────────────────────────────
    @staticmethod
    def _info_row(label_text: str, placeholder: str):
        row = QHBoxLayout(); row.setSpacing(8)
        lbl_w = QLabel(label_text)
        lbl_w.setFixedWidth(90)
        lbl_w.setFont(QFont(C.FUI, 9))
        lbl_w.setStyleSheet(f"color:{C.T2}; background:transparent;")
        row.addWidget(lbl_w)
        le = QLineEdit(); le.setObjectName("le_info")
        le.setStyleSheet(
            f"QLineEdit#le_info {{ background:#FFFFFF; color:{C.T0}; "
            f"border:1px solid {C.BDR}; border-radius:5px; padding:5px 8px; "
            f"selection-background-color:{C.ACCENT_H}; selection-color:#FFFFFF; }}")
        le.setPlaceholderText(placeholder)
        row.addWidget(le)
        return row, le

    # ── 체크박스 로직 ─────────────────────────────────────────
    def _toggle_all(self, state):
        checked = (state == Qt.CheckState.Checked.value)
        for k, chk in self._opts.items():
            # 전체선택 시 misra_c23은 제외 (misra_c와 동시 선택 불가)
            val = False if (checked and k == "misra_c23") else checked
            chk.blockSignals(True); chk.setChecked(val); chk.blockSignals(False)

    def _sync_all_chk(self):
        all_on = all(c.isChecked() for c in self._opts.values())
        self._chk_all.blockSignals(True)
        self._chk_all.setChecked(all_on)
        self._chk_all.blockSignals(False)

    # ── 폴더 → 파일 쌍 목록 변환 ────────────────────────────
    @staticmethod
    def _scan_folder_pairs(old_folder: str, new_folder: str) -> list:
        """폴더 쌍에서 소스 파일을 스캔해 [(rel_path, old_lines, new_lines), ...] 반환.
        파일 연결 없음 — 각 파일은 독립적으로 처리된다."""
        exts = ('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')

        def scan(folder):
            found = {}
            for root, dirs, files in os.walk(folder):
                dirs.sort()
                for fname in sorted(files):
                    if fname.lower().endswith(exts):
                        full = os.path.join(root, fname)
                        rel  = os.path.relpath(full, folder)
                        found[rel] = full
            return found

        def read_lines(path):
            return read_text_lines(path)

        old_map = scan(old_folder)
        new_map = scan(new_folder)
        all_rel = sorted(set(old_map) | set(new_map))
        return [
            (rel,
             read_lines(old_map[rel]) if rel in old_map else [],
             read_lines(new_map[rel]) if rel in new_map else [])
            for rel in all_rel
        ]

    # ── DIFF 추출 ─────────────────────────────────────────────
    def _on_diff(self):
        ap = self._analysis_panel
        _btn = (ap._diff_btn_card if ap and ap._diff_btn_card
                else self._ai_btn)   # fallback

        if ap is None:
            self._warn(_btn, "분석 패널이 초기화되지 않았습니다."); return

        mode = ap.get_input_mode()
        if mode == "folder":
            old_path = ap.get_old_folder_path()
            new_path = ap.get_new_folder_path()
            if not old_path or not new_path:
                self._warn(_btn, "수정 전/후 폴더를 모두 선택해주세요."); return
            # ★ 스캔은 워커에서 수행 — 여기선 경로만 넘긴다
            self._last_params = {
                "mode":             "folder",
                "old_folder":       old_path,
                "new_folder":       new_path,
                "file_pairs":       [],  # 워커 완료 후 set_folder_pairs() 로 주입
                "old_code":         "",
                "new_code":         "",
                "diff_code":        "",
                "code_info":        self._build_code_info(),
                "req_text":         "",   # main.py._on_ai()에서 ExtrasPanel에서 주입
                "opts":             {k: c.isChecked() for k, c in self._opts.items()},
                "include_opts":     self.get_include_opts(),
                "ignore_comments":  ap.get_ignore_comments(),
            }
        else:
            old_path = ap.get_old_path(); new_path = ap.get_new_path()
            if not old_path or not new_path:
                self._warn(_btn, "수정 전/후 파일을 모두 선택해주세요."); return
            old_lines = read_text_lines(old_path)
            new_lines = read_text_lines(new_path)
            self._last_params = {
                "old_lines":        old_lines,
                "new_lines":        new_lines,
                "old_code":         "\n".join(old_lines),
                "new_code":         "\n".join(new_lines),
                "diff_code":        build_unified_diff(old_lines, new_lines,
                                        os.path.basename(old_path), os.path.basename(new_path)),
                "code_info":        self._build_code_info(),
                "req_text":         "",   # main.py._on_ai()에서 ExtrasPanel에서 주입
                "opts":             {k: c.isChecked() for k, c in self._opts.items()},
                "include_opts":     self.get_include_opts(),
                "ignore_comments":  ap.get_ignore_comments(),
                "single_filename":  os.path.basename(new_path),
            }
        self.diff_clicked.emit(self._last_params)
        # 폴더 모드는 워커 완료 후 main.py 에서 enable_ai() 로 활성화
        if mode != "folder":
            self.enable_ai()

    # ── 워커 완료 콜백용 헬퍼 ─────────────────────────────────
    def set_folder_pairs(self, file_pairs: list):
        """폴더 DIFF 워커가 완료된 후 _last_params 에 파일 쌍을 주입한다."""
        if self._last_params is not None:
            self._last_params["file_pairs"] = file_pairs

    def get_project_name(self) -> str:
        """왼쪽 입력 패널의 프로젝트명 반환 (저장 파일명 생성 용)."""
        return self._proj_name.text().strip()

    def enable_ai(self):
        """DIFF 추출 완료 후 AI 분석 버튼 활성화."""
        self._ai_btn.setEnabled(True)
        self._ai_btn.setToolTip("클릭하면 Claude AI가 변경점을 요약하고 취약점을 분석합니다")

    # ── AI 분석 ───────────────────────────────────────────────
    def _on_ai(self):
        # ★ 분석 중일 때 재클릭 → 중단 요청
        if self._ai_running:
            self.stop_requested.emit(); return
        if not self._last_params:
            self._warn(self._ai_btn, "먼저 DIFF 추출을 실행해주세요."); return
        params = dict(self._last_params)
        params["code_info"]    = self._build_code_info()
        params["req_text"]     = ""   # main.py._on_ai()에서 ExtrasPanel에서 주입
        params["opts"]         = {k: c.isChecked() for k, c in self._opts.items()}
        params["include_opts"] = self.get_include_opts()
        self.ai_clicked.emit(params)

    def _build_code_info(self) -> str:
        """AI 프롬프트로 전달되는 코드 정보.
        프로젝트 메타데이터(프로젝트명/제어기/변경전·후/설계자)는 CB 업로드 헤더로만
        쓰이고 AI 분석에는 포함하지 않는다 (get_project_header_md 참고)."""
        parts = []
        # 날짜만 프로젝트 섹션에서 살림 — 변경 시점 컨텍스트로 AI 가 활용
        v = self._date_edit.text().strip()
        if v: parts.append(f"날짜: {v}")
        # 코드 정보
        for label, field in [
            ("MCU",     self._info_mcu),
            ("통신",    self._info_comm),
            ("실행환경",self._info_env),
            ("환경",    self._info_ctx),
            ("의도",    self._info_intent),
        ]:
            v = field.text().strip()
            if v: parts.append(f"{label}: {v}")
        return "\n".join(parts)

    def get_project_meta(self) -> dict:
        """CB 업로드 제목/헤더 생성에 쓰일 프로젝트 메타데이터.
        값이 비어있는 키는 빈 문자열로 채워 반환한다."""
        return {
            "name":    self._proj_name.text().strip(),
            "mcu":     self._proj_mcu.text().strip(),
            "ver_old": self._proj_ver_old.text().strip(),
            "ver_new": self._proj_ver_new.text().strip(),
            "author":  self._proj_author.text().strip(),
            "date":    self._date_edit.text().strip(),
        }

    def get_project_header_md(self) -> str:
        """CB 업로드 본문 최상단에 붙일 프로젝트 정보 마크다운.
        모든 필드가 비어있으면 빈 문자열 반환 (헤더 자체 생략)."""
        rows = []
        for label, field in [
            ("변경내용요약",   self._proj_name),
            ("제어기",         self._proj_mcu),
            ("변경 전 (.ver)", self._proj_ver_old),
            ("변경 후 (.ver)", self._proj_ver_new),
            ("설계자",         self._proj_author),
        ]:
            v = field.text().strip()
            if v:
                rows.append(f"| {label} | {v} |")
        if not rows:
            return ""
        return ("## 📋 코드 리뷰 정보\n\n"
                "| 항목 | 내용 |\n"
                "|------|------|\n"
                + "\n".join(rows))

    # ── AI 포함 체크박스 변경 ──────────────────────────────────
    def _on_include_changed(self, key: str, state):
        checked = (state == Qt.CheckState.Checked.value)
        self.include_changed.emit(key, checked)
        # 전체선택 체크박스 상태 업데이트
        if hasattr(self, "_include_all_chk") and self._include_all_chk:
            all_checked = all(c.isChecked() for c in self._include_chks.values())
            self._include_all_chk.blockSignals(True)
            self._include_all_chk.setChecked(all_checked)
            self._include_all_chk.blockSignals(False)

    def set_include_opt(self, key: str, checked: bool):
        """ExtrasPanel 체크박스 변경을 InputPanel에 반영 (신호 루프 방지)."""
        chk = self._include_chks.get(key)
        if chk:
            chk.blockSignals(True)
            chk.setChecked(checked)
            chk.blockSignals(False)

    def get_include_opts(self) -> dict[str, bool]:
        """현재 포함 옵션 dict 반환."""
        opts = {k: c.isChecked() for k, c in self._include_chks.items()}
        return opts

    # ── CB 인라인 연결 테스트 ─────────────────────────────────
    def _on_cb_test(self):
        from integrations.codebeamer import CbFetcher, save_config, load_config
        url  = self._cb_url_edit.text().strip().rstrip("/")
        uid  = self._cb_id_edit.text().strip()
        pwd  = self._cb_pw_edit.text()
        if not url or not uid or not pwd:
            self._cb_status_lbl.setText("⚠ URL/ID/PW를 모두 입력하세요")
            self._cb_status_lbl.setStyleSheet(f"color:{C.AMBER}; background:transparent;")
            return
        self._cb_test_btn.setEnabled(False)
        self._cb_status_lbl.setText("연결 중...")
        self._cb_status_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")
        # 저장
        cfg = load_config()
        cfg["url"] = url; cfg["username"] = uid; cfg["password"] = pwd
        save_config(cfg)

        # 시그널 → 슬롯 연결 (중복 연결 방지)
        try:
            self._cb_test_finished.disconnect(self._cb_test_result)
        except TypeError:
            pass  # 아직 연결된 적 없음
        self._cb_test_finished.connect(self._cb_test_result)

        # 비동기 테스트 — 결과는 pyqtSignal 을 통해 UI 스레드로 안전하게 전달
        # (QTimer.singleShot 은 이벤트 루프 없는 Python 스레드에서 호출되지 않음)
        import threading
        def _test():
            fetcher = CbFetcher(url, uid, pwd)
            try:
                msg = fetcher.test_connection()
                self._cb_test_finished.emit(True, msg)
            except Exception as e:
                self._cb_test_finished.emit(False, str(e))
        threading.Thread(target=_test, daemon=True).start()

    def _cb_test_result(self, ok: bool, msg: str):
        self._cb_test_btn.setEnabled(True)
        if ok:
            self._cb_status_lbl.setText(f"✅ {msg}")
            self._cb_status_lbl.setStyleSheet(f"color:{C.GREEN}; background:transparent;")
        else:
            self._cb_status_lbl.setText(f"❌ {msg}")
            self._cb_status_lbl.setStyleSheet(f"color:{C.RED}; background:transparent;")
        QTimer.singleShot(5000, lambda: (
            self._cb_status_lbl.setText(""),
            self._cb_status_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")))

    def _load_cb_inline_config(self):
        """저장된 CB 설정을 인라인 필드에 불러온다."""
        try:
            from integrations.codebeamer import load_config
            cfg = load_config()
            if self._cb_url_edit: self._cb_url_edit.setText(cfg.get("url", ""))
            if self._cb_id_edit:  self._cb_id_edit.setText(cfg.get("username", ""))
            if self._cb_pw_edit:  self._cb_pw_edit.setText(cfg.get("password", ""))
        except Exception:
            pass

    def _warn(self, btn: QPushButton, msg: str):
        orig = btn.text()
        btn.setText(f"⚠  {msg}")
        btn.setStyleSheet(
            f"QPushButton {{ background:{C.AMBER}; color:white; border:none; "
            f"border-radius:8px; font-size:11px; font-weight:bold; padding:10px; }}")
        QTimer.singleShot(2400, lambda: (btn.setText(orig), btn.setStyleSheet("")))

    def set_diff_running(self, running: bool):
        """카드 내부 DIFF 버튼 상태 위임."""
        if self._analysis_panel:
            self._analysis_panel.set_diff_running(running)

    def set_ai_running(self, running: bool):
        self._ai_running = running
        self._prog.setVisible(running)
        if running:
            # 빨간 "중단" 스타일로 교체 — 버튼은 활성 상태 유지 (클릭 가능)
            self._ai_btn.setText("  ✋🏻  분석 중단")
            self._ai_btn.setStyleSheet(f"""
                QPushButton#btn_ai {{
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 #CB8A8A, stop:1 #E8AAAA);
                    color:#5C1C1C; border:2px solid #BB7777; border-radius:10px;
                    font-size:13px; font-weight:bold; padding:13px 18px;
                }}
                QPushButton#btn_ai:hover {{
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 #B86666, stop:1 #CB8A8A);
                    color:#FFFFFF; border-color:#A05050;
                }}
                QPushButton#btn_ai:pressed {{ background:#A05050; color:#FFFFFF; }}
            """)
        else:
            # 원래 파란 스타일 복원 (프로그램 메인 BLUE 패밀리)
            self._ai_btn.setText("  🤖  AI 분석 실행")
            self._ai_btn.setStyleSheet(f"""
                QPushButton#btn_ai {{
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 {C.BLUE_DK}, stop:1 {C.BLUE});
                    color:#FFFFFF; border:2px solid {C.BLUE_DK}; border-radius:10px;
                    font-size:13px; font-weight:bold; padding:13px 18px;
                }}
                QPushButton#btn_ai:hover {{
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 {C.BLUE}, stop:1 {C.BLUE_LT});
                    border-color:{C.ACCENT_H};
                }}
                QPushButton#btn_ai:pressed {{ background:{C.BLUE_DK}; color:#FFFFFF; }}
                QPushButton#btn_ai:disabled {{
                    background:{C.BDR}; color:{C.T3};
                    border:2px solid {C.BDR2}; font-size:13px;
                }}
            """)

    def update_cb_status(self, connected: bool):
        """Codebeamer 연결 상태 — InputPanel에서는 별도 표시 없이 패스."""
        pass  # CB 상태는 StatusBar와 분석파일 탭 카드에서 표시
