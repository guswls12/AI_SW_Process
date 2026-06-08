"""
config.py — 디자인 토큰(C), QSS, 공통 헬퍼 (라이트 테마)
"""

from PyQt6.QtWidgets import QLabel, QFrame, QApplication
from PyQt6.QtGui import QFont


def get_dpi_scale() -> float:
    """현재 화면 DPI 기반 스케일 팩터 반환 (96dpi = 1.0 기준)."""
    app = QApplication.instance()
    if app:
        screen = app.primaryScreen()
        if screen:
            dpi = screen.logicalDotsPerInch()
            return max(0.85, min(2.0, dpi / 96.0))
    return 1.0


class C:
    # ── 배경 ──────────────────────────────────────────────────
    BG_APP   = "#F8FAFC"   # 오른쪽 메인 영역
    BG_PANEL = "#EEF2F7"   # 왼쪽 사이드바 (살짝 어둡게)
    BG_CARD  = "#FFFFFF"   # 카드
    BG_INPUT = "#FFFFFF"   # 입력칸
    BG_HOVER = "#F1F5F9"   # 호버
    BG_CODE  = "#F8FAFC"   # diff / 코드 뷰

    # ── 강조색 ────────────────────────────────────────────────
    # 프로그램 전체가 BLUE 한 톤으로 통일됨 (2026-06-04).
    # INDIGO 토큰은 BLUE 계열의 더 진한 톤으로 재포인팅 — 18곳의 BLUE→INDIGO
    # 그라데이션이 자동으로 BLUE 계열 그라데이션으로 변환됨.
    ACCENT   = "#8BBDD0"
    ACCENT_H = "#6AAABF"
    BLUE     = "#8BBDD0"   # 메인 블루 (전체 등록 버튼 등)
    BLUE_LT  = "#DCEEF8"   # 옅은 블루 (호버 배경)
    BLUE_DK  = "#4E9DB5"   # 진한 블루 (그라데이션 끝, pressed)
    INDIGO   = "#4E9DB5"   # ⚠ 호환 alias — 신규 코드는 BLUE_DK 사용 권장
    GREEN    = "#52B788"
    RED      = "#E8837C"
    AMBER    = "#D4A96A"

    # ── diff 색상 (라이트 테마) ───────────────────────────────
    ADD_BG = "#DCFCE7";  ADD_FG = "#166534";  ADD_LN = "#BBF7D0"
    DEL_BG = "#FEE2E2";  DEL_FG = "#991B1B";  DEL_LN = "#FECACA"
    MOD_BG = "#FEF3C7";  MOD_FG = "#92400E"
    EQ_FG  = "#475569";  EMPTY  = "#F1F5F9";  LN_EQ  = "#F8FAFC"

    # ── 텍스트 ────────────────────────────────────────────────
    T0 = "#0F172A"   # 주요 텍스트
    T1 = "#1E293B"   # 진한 텍스트
    T2 = "#475569"   # 보조 텍스트
    T3 = "#94A3B8"   # 힌트 / 비활성
    TC = "#1E293B"   # diff 뷰 텍스트

    # ── 테두리 ────────────────────────────────────────────────
    BDR       = "#C8D3E0"
    BDR2      = "#A0AFBE"
    BDR_FOCUS = "#8BBDD0"

    # ── 폰트 ──────────────────────────────────────────────────
    FUI   = "Segoe UI"
    FCODE = "Consolas"

    # ── 스텝바 ────────────────────────────────────────────────
    STEP_DONE   = "#52B788"
    STEP_ACTIVE = "#8BBDD0"
    STEP_IDLE   = "#CBD5E1"


def build_qss(scale: float = 1.0) -> str:
    """DPI 스케일을 적용한 QSS 문자열을 반환한다.
    scale=1.0 이 96dpi(표준) 기준이며, HiDPI 환경에서는 1.25~2.0 이 된다."""

    def sp(px: int) -> str:
        """픽셀 크기를 스케일 적용한 문자열로 반환."""
        return f"{max(1, round(px * scale))}px"

    return f"""
/* ── 전역 ── */
* {{ font-family:"{C.FUI}"; margin:0; padding:0; }}
QMainWindow, QWidget#root {{ background:{C.BG_APP}; }}

/* ── 버튼 포커스 사각형 제거 ── */
QPushButton {{ outline: none; }}
QPushButton:focus {{ outline: none; }}

/* ── 카드 ── */
QFrame#card {{
    background:{C.BG_CARD};
    border:1px solid {C.BDR};
    border-radius:{sp(12)};
}}

/* ── 텍스트 에디터 (요구사항 등) ── */
QTextEdit#te_info {{
    background:{C.BG_INPUT}; color:{C.T0};
    border:1px solid {C.BDR}; border-radius:{sp(6)};
    font-size:{sp(11)}; padding:{sp(8)} {sp(10)};
    selection-background-color:{C.ACCENT_H};
    selection-color:#FFFFFF;
}}
QTextEdit#te_info:focus {{ border-color:{C.BDR_FOCUS}; }}

/* ── diff 코드 뷰 ── */
QTextEdit#te_diff {{
    background:{C.BG_CODE}; color:{C.TC}; border:none;
    font-family:"{C.FCODE}"; font-size:{sp(12)}; padding:{sp(10)};
    selection-background-color:{C.ACCENT_H};
    selection-color:#FFFFFF;
}}

/* ── 라인에딧 ── */
QLineEdit#le_info {{
    background:{C.BG_INPUT}; color:{C.T0};
    border:1px solid {C.BDR}; border-radius:{sp(5)};
    font-size:{sp(11)}; padding:{sp(5)} {sp(8)};
    selection-background-color:{C.ACCENT_H};
    selection-color:#FFFFFF;
}}
QLineEdit#le_info:focus {{ border-color:{C.BDR_FOCUS}; }}

/* ── 체크박스 ── */
QCheckBox {{ color:{C.T1}; font-size:{sp(11)}; spacing:{sp(8)}; padding:{sp(2)} 0; background:transparent; }}
QCheckBox::indicator {{
    width:{sp(14)}; height:{sp(14)}; border-radius:{sp(3)};
    border:1px solid {C.BDR2}; background:{C.BG_INPUT};
}}
QCheckBox::indicator:checked {{ background:{C.BLUE}; border-color:{C.BLUE}; }}
QCheckBox::indicator:hover   {{ border-color:{C.BLUE}; }}

/* ── 서브 버튼 (찾아보기, 저장 등) ── */
QPushButton#btn_sub {{
    background:{C.BG_CARD}; color:{C.T2};
    border:1px solid {C.BDR2}; border-radius:{sp(5)};
    font-size:{sp(10)}; padding:{sp(4)} {sp(12)};
}}
QPushButton#btn_sub:hover {{
    color:{C.BLUE}; border-color:{C.BLUE}; background:{C.BLUE_LT};
}}

/* ── 다크 버튼 (복사 등) ── */
QPushButton#btn_dark {{
    background:{C.BG_HOVER}; color:{C.T2};
    border:1px solid {C.BDR}; border-radius:{sp(5)};
    font-size:{sp(10)}; padding:{sp(4)} {sp(12)};
}}
QPushButton#btn_dark:hover {{ background:{C.BDR2}; color:{C.T0}; }}

/* ── 탭 버튼 ── */
QPushButton#tab_on {{
    background:transparent; color:{C.T0};
    border:none; border-bottom:2px solid {C.BLUE};
    border-radius:0; font-size:{sp(12)}; font-weight:bold; padding:{sp(12)} {sp(20)};
}}
QPushButton#tab_off {{
    background:transparent; color:{C.T3};
    border:none; border-bottom:2px solid transparent;
    border-radius:0; font-size:{sp(12)}; padding:{sp(12)} {sp(20)};
}}
QPushButton#tab_off:hover {{ color:{C.T1}; }}

/* ── 직접입력 / 파일 토글 ── */
QPushButton#mini_on {{
    background:#D1D9E6; color:{C.T1};
    border:1px solid {C.BDR2}; border-radius:{sp(5)};
    font-size:{sp(10)}; padding:{sp(4)} {sp(14)}; font-weight:bold;
}}
QPushButton#mini_off {{
    background:#E8ECF2; color:{C.T2};
    border:1px solid {C.BDR}; border-radius:{sp(5)};
    font-size:{sp(10)}; padding:{sp(4)} {sp(14)};
}}
QPushButton#mini_off:hover {{ color:{C.BLUE}; border-color:{C.BLUE}; }}

/* ── 스크롤바 ── */
QScrollBar:vertical   {{ background:{C.BG_HOVER}; width:{sp(8)}; border-radius:{sp(4)}; margin:0; }}
QScrollBar:horizontal {{ background:{C.BG_HOVER}; height:{sp(8)}; border-radius:{sp(4)}; margin:0; }}
QScrollBar::handle:vertical   {{ background:#B0BEC5; border-radius:{sp(4)}; min-height:{sp(24)}; }}
QScrollBar::handle:horizontal {{ background:#B0BEC5; border-radius:{sp(4)}; min-width:{sp(24)}; }}
QScrollBar::handle:vertical:hover,
QScrollBar::handle:horizontal:hover {{ background:#78909C; }}
QScrollBar::handle:vertical:pressed,
QScrollBar::handle:horizontal:pressed {{ background:#546E7A; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical   {{ height:0; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
QScrollBar::corner {{ background:transparent; }}

/* ── 프로그레스바 ── */
QProgressBar {{
    background:{C.BDR}; border:none; border-radius:{sp(2)}; height:{sp(3)}; font-size:0px;
}}
QProgressBar::chunk {{
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C.INDIGO}, stop:1 {C.BLUE});
    border-radius:{sp(2)};
}}

/* ── 상태바 ── */
QStatusBar {{
    background:{C.BG_PANEL}; color:{C.T2};
    font-size:{sp(10)}; border-top:1px solid {C.BDR}; padding:0 {sp(12)};
}}

/* ── 구분선 ── */
QFrame#hsep {{ background:{C.BDR}; max-height:1px; }}

/* ── DIFF 버튼 ── */
QPushButton#btn_diff {{
    background:{C.BLUE};
    color:#FFFFFF; border:2px solid {C.ACCENT_H}; border-radius:{sp(10)};
    font-size:{sp(13)}; font-weight:bold; padding:{sp(10)} {sp(18)};
}}
QPushButton#btn_diff:hover {{
    background:{C.ACCENT_H};
    border-color:#4E9DB5;
}}
QPushButton#btn_diff:pressed  {{ background:#4E9DB5; }}
QPushButton#btn_diff:disabled {{ background:#E2E8F0; color:{C.T2}; border:2px solid {C.BDR2}; }}

/* ── AI 분석 버튼 ── */
/* 기존 sky-blue / indigo 그라데이션 → 프로그램 메인 BLUE 패밀리로 통일
 * 위→아래: BLUE_LT(밝게) → BLUE → BLUE_DK 의 깊이감 있는 단일 톤 그라데이션 */
QPushButton#btn_ai {{
    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {C.BLUE_DK}, stop:1 {C.BLUE});
    color:#FFFFFF; border:2px solid {C.BLUE_DK}; border-radius:{sp(10)};
    font-size:{sp(14)}; font-weight:bold; padding:{sp(14)} {sp(18)};
}}
QPushButton#btn_ai:hover {{
    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {C.BLUE}, stop:1 {C.BLUE_LT});
    border-color:{C.ACCENT_H};
}}
QPushButton#btn_ai:pressed  {{ background:{C.BLUE_DK}; }}
QPushButton#btn_ai:disabled {{ background:{C.BDR}; color:{C.T3}; border:2px solid {C.BDR2}; font-size:{sp(13)}; }}
"""


# 하위 호환: 모듈 임포트 시 기본값으로 생성 (scale=1.0)
QSS = build_qss(1.0)


def lbl(text, size=11, bold=False, color=None):
    w = QLabel(text)
    w.setFont(QFont(C.FUI, size,
                    QFont.Weight.Bold if bold else QFont.Weight.Normal))
    w.setStyleSheet(f"color:{color or C.T0}; background:transparent;")
    return w


def hsep():
    f = QFrame()
    f.setObjectName("hsep")
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    return f


def sec_label(text):
    l = lbl(text, 10, True, C.T2)
    l.setStyleSheet(f"color:{C.T2}; background:transparent; letter-spacing:0.3px;")
    return l