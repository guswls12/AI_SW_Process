"""ui_dialog.py — 모달 다이얼로그 위젯.

DiffLoadingDialog       : 폴더 DIFF 추출 진행률 표시용 모달 다이얼로그
SrsAnalysisProgressDialog : SRS 검토 AI 분석 진행 다이얼로그 (입력 토큰 + 경과 시간)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsDropShadowEffect, QDialog, QProgressBar,
    QTextEdit, QScrollArea, QLineEdit, QComboBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QElapsedTimer
from PyQt6.QtGui import QColor

from config import C


def _shadow(widget, blur: int = 18, dx: int = 0, dy: int = 4, alpha: int = 18):
    """위젯에 부드러운 드롭 그림자를 적용한다."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(dx)
    eff.setYOffset(dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)


class DiffLoadingDialog(QDialog):
    """폴더 DIFF 추출 진행률 표시용 모달 다이얼로그 (프레임리스 + 카드 스타일)."""

    cancel_requested = pyqtSignal()   # ★ 중단 버튼 클릭 시 emit

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        # 프레임리스: 시스템 타이틀 바 숨김 + 투명 배경 (라운드 카드 연출)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 250)

        # ── 외곽 레이아웃 (그림자 여백용) ────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 22)
        outer.setSpacing(0)

        # ── 카드 ──────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("diff_load_card")
        card.setStyleSheet(f"""
            QFrame#diff_load_card {{
                background:{C.BG_CARD};
                border:1px solid {C.BDR};
                border-radius:14px;
            }}
        """)
        _shadow(card, blur=30, dy=6, alpha=40)
        outer.addWidget(card)

        clay = QVBoxLayout(card)
        clay.setContentsMargins(0, 0, 0, 0); clay.setSpacing(0)

        # ── 헤더 (그라디언트 바) ─────────────────────────────
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                border-top-left-radius:14px;
                border-top-right-radius:14px;
                border:none;
            }}
            QLabel {{ background:transparent; }}
        """)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(18, 0, 18, 0); hlay.setSpacing(0)
        htitle = QLabel("🔀  DIFF 추출 중")
        htitle.setStyleSheet(
            f"color:#FFFFFF; font-family:'{C.FUI}'; font-size:12px; font-weight:700;")
        hlay.addWidget(htitle); hlay.addStretch()
        clay.addWidget(header)

        # ── 본문 ──────────────────────────────────────────────
        body = QFrame()
        body.setStyleSheet("QFrame { background:transparent; border:none; } "
                           "QLabel { background:transparent; }")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(22, 18, 22, 18); blay.setSpacing(10)

        self._phase_lbl = QLabel("📂  폴더 분석 중...")
        self._phase_lbl.setStyleSheet(
            f"color:{C.T0}; font-family:'{C.FUI}'; font-size:13px; font-weight:700;")
        blay.addWidget(self._phase_lbl)

        self._file_lbl = QLabel("준비 중...")
        self._file_lbl.setStyleSheet(
            f"color:{C.T2}; font-family:'{C.FCODE}'; font-size:10px;")
        self._file_lbl.setFixedHeight(16)
        self._file_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        blay.addWidget(self._file_lbl)

        blay.addSpacing(4)

        # ── 프로그레스 바 (두껍게 + 라운드, 로컬 재스타일) ──
        self._prog = QProgressBar()
        self._prog.setRange(0, 0)  # 초기: indeterminate
        self._prog.setTextVisible(False)
        self._prog.setFixedHeight(10)
        self._prog.setStyleSheet(f"""
            QProgressBar {{
                background:{C.BG_HOVER};
                border:1px solid {C.BDR};
                border-radius:5px;
                height:10px;
            }}
            QProgressBar::chunk {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                border-radius:4px;
            }}
        """)
        blay.addWidget(self._prog)

        # ── 통계 줄 ──────────────────────────────────────────
        stats_row = QHBoxLayout(); stats_row.setContentsMargins(0, 0, 0, 0)
        self._pct_lbl = QLabel("")
        self._pct_lbl.setStyleSheet(
            f"color:{C.BLUE}; font-family:'{C.FUI}'; font-size:11px; font-weight:700;")
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(
            f"color:{C.T3}; font-family:'{C.FUI}'; font-size:10px;")
        stats_row.addWidget(self._pct_lbl); stats_row.addStretch()
        stats_row.addWidget(self._count_lbl)
        blay.addLayout(stats_row)

        # ── 중단 버튼 줄 ──────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setContentsMargins(0, 6, 0, 0)
        btn_row.addStretch()
        self._cancel_btn = QPushButton("✕  DIFF 추출 중단")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setFixedHeight(30)
        self._cancel_btn.setMinimumWidth(140)
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C.BG_CARD};
                color:{C.T2};
                border:1px solid {C.BDR2};
                border-radius:6px;
                font-family:'{C.FUI}';
                font-size:10px;
                font-weight:600;
                padding:4px 14px;
            }}
            QPushButton:hover {{
                background:#FEF2F2;
                color:{C.RED};
                border-color:{C.RED};
            }}
            QPushButton:pressed {{
                background:#FEE2E2;
            }}
            QPushButton:disabled {{
                background:{C.BG_HOVER};
                color:{C.T3};
                border-color:{C.BDR};
            }}
        """)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.addWidget(self._cancel_btn)
        blay.addLayout(btn_row)

        clay.addWidget(body)

    # ── 중단 버튼 클릭 핸들러 ────────────────────────────────
    def _on_cancel_clicked(self):
        """즉시 UI 를 '취소 중' 상태로 전환하고 시그널 emit.
        실제 워커 정지는 main 에서 처리."""
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("⏳  중단 중...")
        self._phase_lbl.setText("⚠  DIFF 추출 중단 중...")
        self._phase_lbl.setStyleSheet(
            f"color:{C.RED}; font-family:'{C.FUI}'; font-size:13px; font-weight:700;")
        self._prog.setRange(0, 0)  # indeterminate
        self.cancel_requested.emit()

    # ── 경로 중간 생략 헬퍼 ──────────────────────────────────
    @staticmethod
    def _ellipsize(path: str, max_len: int = 64) -> str:
        """경로가 너무 길면 중간을 '…' 로 축약한다 (파일명은 보존)."""
        if len(path) <= max_len:
            return path
        head = max_len // 4
        tail = max_len - head - 1
        return path[:head] + "…" + path[-tail:]

    def update_progress(self, phase: str, cur: int, total: int, name: str):
        """phase: 'scan' (폴더 스캔 + 파일 읽기) 또는 'build' (변경점 분석)."""
        if phase == "scan":
            self._phase_lbl.setText("📂  폴더 스캔 · 파일 읽기")
        else:
            self._phase_lbl.setText("🔀  변경점 분석")

        self._file_lbl.setText(self._ellipsize(name))

        if total > 0:
            self._prog.setRange(0, total)
            self._prog.setValue(cur)
            pct = int(cur * 100 / total) if total else 0
            self._pct_lbl.setText(f"{pct}%")
            self._count_lbl.setText(f"{cur} / {total}")
        else:
            self._prog.setRange(0, 0)  # indeterminate
            self._pct_lbl.setText("")
            self._count_lbl.setText("")

    def reject(self):
        # ESC 키로 닫히지 않도록 override
        pass

    def keyPressEvent(self, ev):
        # ESC 무시
        if ev.key() == Qt.Key.Key_Escape:
            ev.ignore(); return
        super().keyPressEvent(ev)


# ══════════════════════════════════════════════════════════════
#  MissingFieldsDialog — 필수 입력 누락 경고 (앱 디자인 톤)
# ══════════════════════════════════════════════════════════════
class MissingFieldsDialog(QDialog):
    """필수 입력 항목이 빠진 경우 띄우는 경고 다이얼로그.

    QMessageBox 기본 스타일 대신 프레임리스 카드 + 앰버 그라디언트 헤더 +
    누락 항목 리스트(연한 앰버 배경 칩 영역) 형태로 표시한다.
    """

    def __init__(self, parent, fields: list,
                 title: str = "프로젝트 정보 입력 필요",
                 message: str = "Codebeamer 업로드 전에 아래 항목을 모두 입력해주세요."):
        super().__init__(parent)
        self.setModal(True)
        # 프레임리스 + 투명 배경 — DiffLoadingDialog 와 동일 패턴
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 항목 수에 따른 높이 자동 산정
        row_h = 24
        body_h = 150 + max(1, len(fields)) * row_h
        self.setFixedSize(460, body_h)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 22)
        outer.setSpacing(0)

        # ── 카드 ──────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("warn_card")
        card.setStyleSheet(f"""
            QFrame#warn_card {{
                background:{C.BG_CARD};
                border:1px solid {C.BDR};
                border-radius:14px;
            }}
        """)
        _shadow(card, blur=30, dy=6, alpha=40)
        outer.addWidget(card)

        clay = QVBoxLayout(card)
        clay.setContentsMargins(0, 0, 0, 0); clay.setSpacing(0)

        # ── 헤더 (앰버 그라디언트) ─────────────────────────────
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #B7864E, stop:1 {C.AMBER});
                border-top-left-radius:14px;
                border-top-right-radius:14px;
                border:none;
            }}
            QLabel {{ background:transparent; }}
        """)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(18, 0, 18, 0); hlay.setSpacing(0)
        htitle = QLabel(f"⚠  {title}")
        htitle.setStyleSheet(
            f"color:#FFFFFF; font-family:'{C.FUI}'; "
            f"font-size:12px; font-weight:700;")
        hlay.addWidget(htitle); hlay.addStretch()
        clay.addWidget(header)

        # ── 본문 ──────────────────────────────────────────────
        body = QFrame()
        body.setStyleSheet(
            "QFrame { background:transparent; border:none; } "
            "QLabel { background:transparent; }")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(22, 18, 22, 18); blay.setSpacing(14)

        # 안내 문구
        sub_lbl = QLabel(message)
        sub_lbl.setStyleSheet(
            f"color:{C.T1}; font-family:'{C.FUI}'; font-size:12px;")
        sub_lbl.setWordWrap(True)
        blay.addWidget(sub_lbl)

        # 누락 항목 리스트 박스
        list_frame = QFrame()
        list_frame.setStyleSheet("""
            QFrame {
                background:#FEF6EC;
                border:1px solid #F0D8A8;
                border-radius:8px;
            }
        """)
        list_lay = QVBoxLayout(list_frame)
        list_lay.setContentsMargins(16, 10, 16, 10); list_lay.setSpacing(2)
        for fname in fields:
            row = QLabel(f"  •   {fname}")
            row.setStyleSheet(
                f"color:#7C4A1A; font-family:'{C.FUI}'; "
                f"font-size:12px; font-weight:600; "
                f"background:transparent; border:none;")
            list_lay.addWidget(row)
        blay.addWidget(list_frame)

        blay.addStretch()

        # ── 확인 버튼 ────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()
        ok_btn = QPushButton("확인")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setFixedHeight(32)
        ok_btn.setMinimumWidth(96)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                color:#FFFFFF;
                border:none;
                border-radius:6px;
                font-family:'{C.FUI}';
                font-size:11px;
                font-weight:700;
                padding:6px 18px;
            }}
            QPushButton:hover {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #7AA0D5, stop:1 #7AAFC6);
            }}
            QPushButton:pressed {{
                background:{C.INDIGO};
            }}
        """)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        blay.addLayout(btn_row)

        clay.addWidget(body)

    # ── 드래그 이동 (프레임리스라 시스템 타이틀바 없음) ────────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()


# ══════════════════════════════════════════════════════════════
#  ErrorDialog — 일반 에러 다이얼로그 (앱 디자인 톤, 스크롤 디테일)
# ══════════════════════════════════════════════════════════════
class ErrorDialog(QDialog):
    """에러 상황 안내 다이얼로그.

    QMessageBox 기본 스타일 대신 프레임리스 카드 + RED 그라디언트 헤더 +
    스크롤 가능한 디테일 박스(모노스페이스, 라인랩)로 긴 메시지도 깔끔히 표시.
    """

    def __init__(self, parent,
                 title: str = "오류",
                 headline: str = "오류가 발생했습니다.",
                 detail: str = ""):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(560, 360)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 22)
        outer.setSpacing(0)

        # ── 카드 ──────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("err_card")
        card.setStyleSheet(f"""
            QFrame#err_card {{
                background:{C.BG_CARD};
                border:1px solid {C.BDR};
                border-radius:14px;
            }}
        """)
        _shadow(card, blur=30, dy=6, alpha=40)
        outer.addWidget(card)

        clay = QVBoxLayout(card)
        clay.setContentsMargins(0, 0, 0, 0); clay.setSpacing(0)

        # ── 헤더 (RED 그라디언트) ─────────────────────────────
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #B85A52, stop:1 {C.RED});
                border-top-left-radius:14px;
                border-top-right-radius:14px;
                border:none;
            }}
            QLabel {{ background:transparent; }}
        """)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(18, 0, 18, 0); hlay.setSpacing(0)
        htitle = QLabel(f"❌  {title}")
        htitle.setStyleSheet(
            f"color:#FFFFFF; font-family:'{C.FUI}'; "
            f"font-size:12px; font-weight:700;")
        hlay.addWidget(htitle); hlay.addStretch()
        clay.addWidget(header)

        # ── 본문 ──────────────────────────────────────────────
        body = QFrame()
        body.setStyleSheet(
            "QFrame { background:transparent; border:none; } "
            "QLabel { background:transparent; }")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(22, 18, 22, 18); blay.setSpacing(12)

        # 상단 제목
        hd_lbl = QLabel(headline)
        hd_lbl.setStyleSheet(
            f"color:{C.T0}; font-family:'{C.FUI}'; "
            f"font-size:13px; font-weight:700;")
        hd_lbl.setWordWrap(True)
        blay.addWidget(hd_lbl)

        # 디테일 박스 (스크롤 + 모노스페이스)
        detail_box = QTextEdit()
        detail_box.setReadOnly(True)
        detail_box.setPlainText(detail or "")
        detail_box.setStyleSheet(f"""
            QTextEdit {{
                background:#FEF2F2;
                color:#7F1D1D;
                border:1px solid #F4CDCD;
                border-radius:8px;
                padding:10px 12px;
                font-family:'{C.FCODE}','Consolas',monospace;
                font-size:11px;
                line-height:1.5;
                selection-background-color:#FCA5A5;
                selection-color:#7F1D1D;
            }}
            QScrollBar:vertical {{
                background:transparent; width:8px; border-radius:4px;
            }}
            QScrollBar::handle:vertical {{
                background:#E5B4B4; border-radius:4px; min-height:24px;
            }}
            QScrollBar::handle:vertical:hover {{ background:#D49494; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background:transparent; height:0px;
            }}
        """)
        blay.addWidget(detail_box, stretch=1)

        # ── 확인 버튼 ────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()
        ok_btn = QPushButton("확인")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setFixedHeight(32)
        ok_btn.setMinimumWidth(96)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                color:#FFFFFF;
                border:none;
                border-radius:6px;
                font-family:'{C.FUI}';
                font-size:11px;
                font-weight:700;
                padding:6px 18px;
            }}
            QPushButton:hover {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #7AA0D5, stop:1 #7AAFC6);
            }}
            QPushButton:pressed {{
                background:{C.INDIGO};
            }}
        """)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        blay.addLayout(btn_row)

        clay.addWidget(body)

    # ── 드래그 이동 ──────────────────────────────────────────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()


# ══════════════════════════════════════════════════════════════
#  TokenLimitDialog — 입력 토큰 한도 초과 위험 경고 (앱 디자인 톤)
# ══════════════════════════════════════════════════════════════
class TokenLimitDialog(QDialog):
    """Claude 컨텍스트 윈도우(200K) 초과 위험 시 띄우는 경고 다이얼로그.

    토큰 사용량 breakdown 표 + 권장 조치 리스트 + "취소 / 그래도 진행" 2버튼.

    Accepted → 그래도 진행 (사용자 책임)
    Rejected → 취소 (분석 안 함)
    """

    def __init__(self, parent,
                 input_tokens: int,
                 max_tokens: int,
                 buffer: int,
                 model_limit: int = 200_000,
                 title: str = "입력 토큰 한도 초과 위험"):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 450)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 22); outer.setSpacing(0)

        # ── 카드 ──────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("tlim_card")
        card.setStyleSheet(f"""
            QFrame#tlim_card {{
                background:{C.BG_CARD};
                border:1px solid {C.BDR};
                border-radius:14px;
            }}
        """)
        _shadow(card, blur=30, dy=6, alpha=40)
        outer.addWidget(card)

        clay = QVBoxLayout(card)
        clay.setContentsMargins(0, 0, 0, 0); clay.setSpacing(0)

        # ── 헤더 (앰버 그라디언트) ────────────────────────────
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #B7864E, stop:1 {C.AMBER});
                border-top-left-radius:14px;
                border-top-right-radius:14px;
                border:none;
            }}
            QLabel {{ background:transparent; }}
        """)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(18, 0, 18, 0); hlay.setSpacing(0)
        htitle = QLabel(f"⚠  {title}")
        htitle.setStyleSheet(
            f"color:#FFFFFF; font-family:'{C.FUI}'; "
            f"font-size:12px; font-weight:700;")
        hlay.addWidget(htitle); hlay.addStretch()
        clay.addWidget(header)

        # ── 본문 ──────────────────────────────────────────────
        body = QFrame()
        body.setStyleSheet(
            "QFrame { background:transparent; border:none; } "
            "QLabel { background:transparent; }")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(22, 18, 22, 18); blay.setSpacing(12)

        # 안내 문구
        projected = input_tokens + max_tokens + buffer
        overflow  = max(0, projected - model_limit)
        head_lbl = QLabel(
            f"Claude 모델 컨텍스트 한도(<b>{model_limit:,}</b> 토큰)를 "
            f"초과할 위험이 있습니다."
            f"<br>그대로 진행하면 API 가 분석 요청을 거부할 수 있습니다.")
        head_lbl.setTextFormat(Qt.TextFormat.RichText)
        head_lbl.setStyleSheet(
            f"color:{C.T1}; font-family:'{C.FUI}'; "
            f"font-size:12px; line-height:160%;")
        head_lbl.setWordWrap(True)
        blay.addWidget(head_lbl)

        # 토큰 breakdown 박스 (모노스페이스로 정렬)
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background:#FEF6EC;
                border:1px solid #F0D8A8;
                border-radius:8px;
            }
        """)
        info_lay = QVBoxLayout(info_frame)
        info_lay.setContentsMargins(18, 12, 18, 12); info_lay.setSpacing(4)

        def _row(label, value, value_color=None, bold=False):
            r = QHBoxLayout(); r.setContentsMargins(0, 0, 0, 0); r.setSpacing(8)
            l_lbl = QLabel(label)
            l_lbl.setStyleSheet(
                f"color:#7C4A1A; font-family:'{C.FUI}'; "
                f"font-size:11px; {'font-weight:700;' if bold else 'font-weight:600;'} "
                f"background:transparent; border:none;")
            v_lbl = QLabel(value)
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight |
                               Qt.AlignmentFlag.AlignVCenter)
            v_lbl.setStyleSheet(
                f"color:{value_color or '#7C4A1A'}; "
                f"font-family:'{C.FCODE}','Consolas',monospace; "
                f"font-size:12px; {'font-weight:700;' if bold else 'font-weight:600;'} "
                f"background:transparent; border:none;")
            r.addWidget(l_lbl); r.addStretch(); r.addWidget(v_lbl)
            return r

        info_lay.addLayout(_row("입력 토큰 (input)",   f"{input_tokens:,}"))
        info_lay.addLayout(_row("최대 응답 (output)",  f"{max_tokens:,}"))
        info_lay.addLayout(_row("시스템 프롬프트 버퍼", f"~{buffer:,}"))
        # 구분선
        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet("background:#F0D8A8; border:none;")
        info_lay.addWidget(sep)
        info_lay.addLayout(_row("예상 합계",      f"{projected:,}",
                                 value_color="#92400E", bold=True))
        info_lay.addLayout(_row("모델 한도",      f"{model_limit:,}",
                                 value_color="#7C4A1A"))
        info_lay.addLayout(_row("초과 예상량",    f"{overflow:,}",
                                 value_color="#B91C1C", bold=True))

        blay.addWidget(info_frame)

        # 권장 조치 리스트
        suggest_lbl = QLabel("💡  권장 조치 (입력이 줄어드는 순서)")
        suggest_lbl.setStyleSheet(
            f"color:{C.T1}; font-family:'{C.FUI}'; "
            f"font-size:11px; font-weight:700; padding-top:4px;")
        blay.addWidget(suggest_lbl)

        suggestions = [
            "정적 검증 옵션 OFF — CERT-C / MISRA-C 룰 파일이 가장 큼",
            "과거차 (CB) 체크 해제 또는 항목 수 줄이기",
            "max_tokens 출력 한도 슬라이더 ↓ (입력 가용량 ↑)",
            "폴더 모드 → 단일 파일 모드 또는 변경 파일만 체크",
        ]
        for s in suggestions:
            l = QLabel(f"  •   {s}")
            l.setStyleSheet(
                f"color:{C.T2}; font-family:'{C.FUI}'; "
                f"font-size:11px; padding:2px 0;")
            l.setWordWrap(True)
            blay.addWidget(l)

        blay.addStretch()

        # ── 버튼 영역 ────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0); btn_row.setSpacing(8)
        btn_row.addStretch()

        # 그래도 진행 (위험 — 회색 톤)
        risk_btn = QPushButton("그래도 진행")
        risk_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        risk_btn.setFixedHeight(32); risk_btn.setMinimumWidth(100)
        risk_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C.BG_HOVER};
                color:{C.T2};
                border:1px solid {C.BDR2};
                border-radius:6px;
                font-family:'{C.FUI}';
                font-size:11px;
                font-weight:600;
                padding:6px 14px;
            }}
            QPushButton:hover {{
                background:#FEF2F2;
                color:{C.RED};
                border-color:{C.RED};
            }}
            QPushButton:pressed {{ background:#FEE2E2; }}
        """)
        risk_btn.clicked.connect(self.accept)
        btn_row.addWidget(risk_btn)

        # 취소 (분석 안 함 — 기본 / 파란 강조)
        cancel_btn = QPushButton("취소")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedHeight(32); cancel_btn.setMinimumWidth(100)
        cancel_btn.setDefault(True)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                color:#FFFFFF;
                border:none;
                border-radius:6px;
                font-family:'{C.FUI}';
                font-size:11px;
                font-weight:700;
                padding:6px 18px;
            }}
            QPushButton:hover {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #7AA0D5, stop:1 #7AAFC6);
            }}
            QPushButton:pressed {{ background:{C.INDIGO}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        blay.addLayout(btn_row)
        clay.addWidget(body)

    # ── 드래그 이동 ──────────────────────────────────────────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()


# ══════════════════════════════════════════════════════════════
#  SuccessDialog — 성공 안내 + 선택적 보조 액션 (앱 디자인 톤)
# ══════════════════════════════════════════════════════════════
class SuccessDialog(QDialog):
    """성공 안내 다이얼로그 — 프라이머리(액션) + 세컨더리(닫기) 두 버튼.

    exec() 반환값:
      QDialog.DialogCode.Accepted → 프라이머리 액션 클릭 (예: 브라우저 열기)
      QDialog.DialogCode.Rejected → 세컨더리/ESC/X 닫기
    """

    def __init__(self, parent,
                 title: str = "완료",
                 headline: str = "작업이 완료되었습니다.",
                 link_url: str = "",
                 primary_label: str = "확인",
                 secondary_label: str = "닫기"):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 링크 유무에 따라 높이 가변
        h = 230 if link_url else 190
        self.setFixedSize(500, h)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 22)
        outer.setSpacing(0)

        # ── 카드 ──────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("ok_card")
        card.setStyleSheet(f"""
            QFrame#ok_card {{
                background:{C.BG_CARD};
                border:1px solid {C.BDR};
                border-radius:14px;
            }}
        """)
        _shadow(card, blur=30, dy=6, alpha=40)
        outer.addWidget(card)

        clay = QVBoxLayout(card)
        clay.setContentsMargins(0, 0, 0, 0); clay.setSpacing(0)

        # ── 헤더 (GREEN 그라디언트) ──────────────────────────
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #3E8B5E, stop:1 {C.GREEN});
                border-top-left-radius:14px;
                border-top-right-radius:14px;
                border:none;
            }}
            QLabel {{ background:transparent; }}
        """)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(18, 0, 18, 0); hlay.setSpacing(0)
        htitle = QLabel(f"✅  {title}")
        htitle.setStyleSheet(
            f"color:#FFFFFF; font-family:'{C.FUI}'; "
            f"font-size:12px; font-weight:700;")
        hlay.addWidget(htitle); hlay.addStretch()
        clay.addWidget(header)

        # ── 본문 ──────────────────────────────────────────────
        body = QFrame()
        body.setStyleSheet(
            "QFrame { background:transparent; border:none; } "
            "QLabel { background:transparent; }")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(22, 20, 22, 18); blay.setSpacing(12)

        # 안내 문구
        hd_lbl = QLabel(headline)
        hd_lbl.setStyleSheet(
            f"color:{C.T0}; font-family:'{C.FUI}'; "
            f"font-size:13px; font-weight:700;")
        hd_lbl.setWordWrap(True)
        blay.addWidget(hd_lbl)

        # 링크 칩 (URL 이 있을 때만)
        if link_url:
            link_lbl = QLabel(link_url)
            link_lbl.setStyleSheet(f"""
                QLabel {{
                    background:#ECFDF5;
                    color:#065F46;
                    border:1px solid #A7F3D0;
                    border-radius:6px;
                    padding:8px 12px;
                    font-family:'{C.FCODE}','Consolas',monospace;
                    font-size:11px;
                }}
            """)
            link_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            link_lbl.setCursor(Qt.CursorShape.IBeamCursor)
            link_lbl.setWordWrap(True)
            blay.addWidget(link_lbl)

        blay.addStretch()

        # ── 버튼 영역 ────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0); btn_row.setSpacing(8)
        btn_row.addStretch()

        # 세컨더리 (회색 톤)
        sec_btn = QPushButton(secondary_label)
        sec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sec_btn.setFixedHeight(32)
        sec_btn.setMinimumWidth(80)
        sec_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C.BG_HOVER};
                color:{C.T1};
                border:1px solid {C.BDR2};
                border-radius:6px;
                font-family:'{C.FUI}';
                font-size:11px;
                font-weight:600;
                padding:6px 16px;
            }}
            QPushButton:hover {{
                background:{C.BDR};
                color:{C.T0};
                border-color:{C.T3};
            }}
            QPushButton:pressed {{
                background:{C.BDR2};
            }}
        """)
        sec_btn.clicked.connect(self.reject)
        btn_row.addWidget(sec_btn)

        # 프라이머리 (파란 그라디언트)
        pri_btn = QPushButton(primary_label)
        pri_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pri_btn.setFixedHeight(32)
        pri_btn.setMinimumWidth(120)
        pri_btn.setDefault(True)
        pri_btn.setStyleSheet(f"""
            QPushButton {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                color:#FFFFFF;
                border:none;
                border-radius:6px;
                font-family:'{C.FUI}';
                font-size:11px;
                font-weight:700;
                padding:6px 18px;
            }}
            QPushButton:hover {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #7AA0D5, stop:1 #7AAFC6);
            }}
            QPushButton:pressed {{
                background:{C.INDIGO};
            }}
        """)
        pri_btn.clicked.connect(self.accept)
        btn_row.addWidget(pri_btn)

        blay.addLayout(btn_row)
        clay.addWidget(body)

    # ── 드래그 이동 ──────────────────────────────────────────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()


# ══════════════════════════════════════════════════════════════
#  ConfirmDialog — Yes/No 확인 (앱 톤 일관)
# ══════════════════════════════════════════════════════════════
class ConfirmDialog(QDialog):
    """Yes/No 확인 다이얼로그 — 프레임리스 카드 + 파란 그라디언트 헤더.

    QMessageBox.question 의 OS 기본 룩 대신 앱 다른 다이얼로그(Success/Error)
    와 동일한 스타일. headline 한 줄 + 선택적 detail 본문 + 진행/취소 버튼.

    exec() 반환값:
      QDialog.DialogCode.Accepted → 진행 (primary 클릭)
      QDialog.DialogCode.Rejected → 취소/ESC
    """

    def __init__(self, parent,
                 title: str = "확인",
                 headline: str = "계속하시겠습니까?",
                 detail: str = "",
                 primary_label: str = "진행",
                 secondary_label: str = "취소"):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        h = 250 if detail else 190
        self.setFixedSize(500, h)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 22); outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("cf_card")
        card.setStyleSheet(f"""
            QFrame#cf_card {{
                background:{C.BG_CARD};
                border:1px solid {C.BDR};
                border-radius:14px;
            }}
        """)
        _shadow(card, blur=30, dy=6, alpha=40)
        outer.addWidget(card)

        clay = QVBoxLayout(card)
        clay.setContentsMargins(0, 0, 0, 0); clay.setSpacing(0)

        # 헤더 (BLUE 그라디언트)
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                border-top-left-radius:14px;
                border-top-right-radius:14px;
                border:none;
            }}
            QLabel {{ background:transparent; }}
        """)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(18, 0, 18, 0); hlay.setSpacing(0)
        htitle = QLabel(f"❓  {title}")
        htitle.setStyleSheet(
            f"color:#FFFFFF; font-family:'{C.FUI}'; "
            f"font-size:12px; font-weight:700;")
        hlay.addWidget(htitle); hlay.addStretch()
        clay.addWidget(header)

        # 본문
        body = QFrame()
        body.setStyleSheet(
            "QFrame { background:transparent; border:none; } "
            "QLabel { background:transparent; }")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(22, 20, 22, 18); blay.setSpacing(12)

        hd_lbl = QLabel(headline)
        hd_lbl.setStyleSheet(
            f"color:{C.T0}; font-family:'{C.FUI}'; "
            f"font-size:13px; font-weight:700;")
        hd_lbl.setWordWrap(True)
        blay.addWidget(hd_lbl)

        if detail:
            dt_lbl = QLabel(detail)
            dt_lbl.setStyleSheet(
                f"color:{C.T2}; font-family:'{C.FUI}'; "
                f"font-size:11px; line-height:1.5;")
            dt_lbl.setWordWrap(True)
            blay.addWidget(dt_lbl)

        blay.addStretch()

        # 버튼
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0); btn_row.setSpacing(8)
        btn_row.addStretch()

        sec_btn = QPushButton(secondary_label)
        sec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sec_btn.setFixedHeight(32); sec_btn.setMinimumWidth(80)
        sec_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C.BG_HOVER}; color:{C.T1};
                border:1px solid {C.BDR2}; border-radius:6px;
                font-family:'{C.FUI}'; font-size:11px; font-weight:600;
                padding:6px 16px;
            }}
            QPushButton:hover {{
                background:{C.BDR}; color:{C.T0}; border-color:{C.T3};
            }}
            QPushButton:pressed {{ background:{C.BDR2}; }}
        """)
        sec_btn.clicked.connect(self.reject)
        btn_row.addWidget(sec_btn)

        pri_btn = QPushButton(primary_label)
        pri_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pri_btn.setFixedHeight(32); pri_btn.setMinimumWidth(100)
        pri_btn.setDefault(True)
        pri_btn.setStyleSheet(f"""
            QPushButton {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                color:#FFFFFF; border:none; border-radius:6px;
                font-family:'{C.FUI}'; font-size:11px; font-weight:700;
                padding:6px 18px;
            }}
            QPushButton:hover {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #7AA0D5, stop:1 #7AAFC6);
            }}
            QPushButton:pressed {{ background:{C.INDIGO}; }}
        """)
        pri_btn.clicked.connect(self.accept)
        btn_row.addWidget(pri_btn)

        blay.addLayout(btn_row)
        clay.addWidget(body)

    # 드래그 이동
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                ev.globalPosition().toPoint() - self.frameGeometry().topLeft())
            ev.accept()

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()


# ══════════════════════════════════════════════════════════════
#  SrsAnalysisProgressDialog — SRS 검토 AI 분석 진행 다이얼로그
# ══════════════════════════════════════════════════════════════
class SrsAnalysisProgressDialog(QDialog):
    """SRS 검토 AI 분석 진행 표시용 모달 다이얼로그.

    구성:
      - 헤더: 청록 그라디언트 + 변경점 #ID + 제목
      - 본문: 진행 단계 텍스트 / 인디터미네이트 프로그레스 바 /
              입력 토큰 수 / 경과 시간 / 체크리스트 항목 수
      - 푸터: 취소 버튼 (cancel_requested 시그널 emit)

    컨트롤러가 다음 슬롯을 호출:
      - set_phase(str)       : 진행 단계 텍스트 갱신
      - set_token_count(int) : 토큰 카운트 표시 갱신
      - set_finishing()      : 완료 직전 상태 (자동 닫힘 전)
    """
    cancel_requested = pyqtSignal()

    def __init__(self, parent, item_id: str = "", title: str = "",
                 checklist_count: int = 0):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 290)

        self._item_id         = str(item_id or "")
        self._item_title      = str(title or "")
        self._checklist_count = int(checklist_count or 0)
        self._cancelled       = False

        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._tick = QTimer(self)
        self._tick.setInterval(250)
        self._tick.timeout.connect(self._refresh_elapsed)

        self._build_ui()
        self._tick.start()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 22); outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("srs_ana_card")
        card.setStyleSheet(f"""
            QFrame#srs_ana_card {{
                background:{C.BG_CARD};
                border:1px solid {C.BDR};
                border-radius:14px;
            }}
        """)
        _shadow(card, blur=30, dy=6, alpha=40)
        outer.addWidget(card)

        clay = QVBoxLayout(card)
        clay.setContentsMargins(0, 0, 0, 0); clay.setSpacing(0)

        # 헤더 (블루 그라디언트)
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                border-top-left-radius:14px;
                border-top-right-radius:14px;
                border:none;
            }}
            QLabel {{ background:transparent; }}
        """)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(18, 0, 18, 0); hlay.setSpacing(0)
        htitle = QLabel("🤖  SRS 검토 — AI 분석 중")
        htitle.setStyleSheet(
            f"color:#FFFFFF; font-family:'{C.FUI}'; "
            f"font-size:12px; font-weight:700;")
        hlay.addWidget(htitle); hlay.addStretch()
        clay.addWidget(header)

        # 본문
        body = QFrame()
        body.setStyleSheet("QFrame { background:transparent; border:none; } "
                           "QLabel { background:transparent; }")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(22, 18, 22, 16); blay.setSpacing(10)

        # 변경점 정보 (#ID — 제목)
        item_text = f"#{self._item_id} — {self._item_title}" \
            if self._item_id else (self._item_title or "(변경점)")
        self._item_lbl = QLabel(item_text)
        self._item_lbl.setStyleSheet(
            f"color:{C.T0}; font-family:'{C.FUI}'; "
            f"font-size:12px; font-weight:700;")
        self._item_lbl.setWordWrap(True)
        blay.addWidget(self._item_lbl)

        # 단계 텍스트
        self._phase_lbl = QLabel("🔢  입력 토큰 수 계산 중...")
        self._phase_lbl.setStyleSheet(
            f"color:{C.T2}; font-family:'{C.FUI}'; font-size:11px;")
        blay.addWidget(self._phase_lbl)

        # 프로그레스 바 (인디터미네이트)
        self._prog = QProgressBar()
        self._prog.setRange(0, 0)
        self._prog.setTextVisible(False)
        self._prog.setFixedHeight(8)
        self._prog.setStyleSheet(f"""
            QProgressBar {{
                background:{C.BG_HOVER};
                border:1px solid {C.BDR};
                border-radius:4px;
                height:8px;
            }}
            QProgressBar::chunk {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                border-radius:4px;
            }}
        """)
        blay.addWidget(self._prog)

        # 통계 영역 (입력 토큰 / 체크리스트 / 경과 시간)
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background:#EFF6FF;
                border:1px solid #BFDBFE;
                border-radius:8px;
            }
        """)
        info_lay = QHBoxLayout(info_frame)
        info_lay.setContentsMargins(14, 10, 14, 10); info_lay.setSpacing(0)

        def _stat(label_text: str, value_initial: str):
            box = QVBoxLayout(); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(2)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"color:{C.BLUE_DK}; font-family:'{C.FUI}'; "
                f"font-size:10px; font-weight:600;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(lbl)
            val = QLabel(value_initial)
            val.setStyleSheet(
                f"color:{C.T0}; "
                f"font-family:'{C.FCODE}','Consolas',monospace; "
                f"font-size:14px; font-weight:700;")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(val)
            wrap = QWidget(); wrap.setLayout(box)
            wrap.setStyleSheet("background:transparent;")
            return wrap, val

        tok_wrap, self._token_val = _stat("입력 토큰", "계산 중…")
        info_lay.addWidget(tok_wrap, 1)

        sep1 = QFrame(); sep1.setFixedWidth(1)
        sep1.setStyleSheet("background:#BFDBFE; border:none;")
        info_lay.addWidget(sep1)

        chk_wrap, self._chk_val = _stat(
            "체크리스트", f"{self._checklist_count}")
        info_lay.addWidget(chk_wrap, 1)

        sep2 = QFrame(); sep2.setFixedWidth(1)
        sep2.setStyleSheet("background:#BFDBFE; border:none;")
        info_lay.addWidget(sep2)

        el_wrap, self._elapsed_val = _stat("경과 시간", "0.0s")
        info_lay.addWidget(el_wrap, 1)

        blay.addWidget(info_frame)

        # 취소 버튼
        btn_row = QHBoxLayout(); btn_row.setContentsMargins(0, 4, 0, 0)
        btn_row.addStretch()
        self._cancel_btn = QPushButton("✕  분석 취소")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setFixedHeight(30); self._cancel_btn.setMinimumWidth(120)
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C.BG_CARD}; color:{C.T2};
                border:1px solid {C.BDR2}; border-radius:6px;
                font-family:'{C.FUI}'; font-size:10px; font-weight:600;
                padding:4px 14px;
            }}
            QPushButton:hover {{
                background:#FEF2F2; color:{C.RED}; border-color:{C.RED};
            }}
            QPushButton:pressed {{ background:#FEE2E2; }}
            QPushButton:disabled {{
                background:{C.BG_HOVER}; color:{C.T3}; border-color:{C.BDR};
            }}
        """)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.addWidget(self._cancel_btn)
        blay.addLayout(btn_row)

        clay.addWidget(body)

    # 공개 슬롯
    def set_phase(self, text: str):
        if not self._cancelled:
            self._phase_lbl.setText(text or "")

    def set_token_count(self, n: int):
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 0
        self._token_val.setText(f"{n:,}" if n > 0 else "—")

    def set_finishing(self):
        self._phase_lbl.setText("✅  결과 수신 — 표시 준비 중...")

    def _on_cancel_clicked(self):
        if self._cancelled:
            return
        self._cancelled = True
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("⏳  취소 중...")
        self._phase_lbl.setText("⚠  분석 취소 중...")
        self._phase_lbl.setStyleSheet(
            f"color:{C.RED}; font-family:'{C.FUI}'; "
            f"font-size:11px; font-weight:700;")
        self.cancel_requested.emit()

    def _refresh_elapsed(self):
        sec = self._elapsed.elapsed() / 1000.0
        self._elapsed_val.setText(f"{sec:.1f}s")

    def closeEvent(self, ev):
        self._tick.stop()
        super().closeEvent(ev)

    def reject(self):
        if not self._cancelled:
            self._on_cancel_clicked()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            ev.ignore(); return
        super().keyPressEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                ev.globalPosition().toPoint() - self.frameGeometry().topLeft())
            ev.accept()

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()


# ══════════════════════════════════════════════════════════════
#  TextInputDialog — 앱 스타일에 맞춘 한 줄 텍스트 입력 다이얼로그
# ══════════════════════════════════════════════════════════════
class TextInputDialog(QDialog):
    """프레임리스 카드 + 파란 그라디언트 헤더의 텍스트 입력 다이얼로그.

    QInputDialog.getText 대체용 — 앱의 다른 다이얼로그(Confirm/Missing)
    와 동일 스타일.

    사용:
        text, ok = TextInputDialog.get_text(
            parent, title="...", headline="...", detail="...",
            initial="...", placeholder="...")
    """

    def __init__(self, parent,
                 title: str = "입력",
                 headline: str = "",
                 detail: str = "",
                 initial: str = "",
                 placeholder: str = "",
                 primary_label: str = "확인",
                 secondary_label: str = "취소"):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        h = 260 if detail else 220
        self.setFixedSize(500, h)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 22); outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("ti_card")
        card.setStyleSheet(f"""
            QFrame#ti_card {{
                background:{C.BG_CARD};
                border:1px solid {C.BDR};
                border-radius:14px;
            }}
        """)
        _shadow(card, blur=30, dy=6, alpha=40)
        outer.addWidget(card)

        clay = QVBoxLayout(card)
        clay.setContentsMargins(0, 0, 0, 0); clay.setSpacing(0)

        # 헤더 (BLUE 그라디언트)
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                border-top-left-radius:14px;
                border-top-right-radius:14px;
                border:none;
            }}
            QLabel {{ background:transparent; }}
        """)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(18, 0, 18, 0); hlay.setSpacing(0)
        htitle = QLabel(f"✏  {title}")
        htitle.setStyleSheet(
            f"color:#FFFFFF; font-family:'{C.FUI}'; "
            f"font-size:12px; font-weight:700;")
        hlay.addWidget(htitle); hlay.addStretch()
        clay.addWidget(header)

        # 본문
        body = QFrame()
        body.setStyleSheet(
            "QFrame { background:transparent; border:none; } "
            "QLabel { background:transparent; }")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(22, 18, 22, 18); blay.setSpacing(10)

        if headline:
            hd_lbl = QLabel(headline)
            hd_lbl.setStyleSheet(
                f"color:{C.T0}; font-family:'{C.FUI}'; "
                f"font-size:13px; font-weight:700;")
            hd_lbl.setWordWrap(True)
            blay.addWidget(hd_lbl)

        if detail:
            dt_lbl = QLabel(detail)
            dt_lbl.setStyleSheet(
                f"color:{C.T2}; font-family:'{C.FUI}'; "
                f"font-size:10px; line-height:1.5;")
            dt_lbl.setWordWrap(True)
            blay.addWidget(dt_lbl)

        # 입력란
        self._input = QLineEdit()
        self._input.setText(initial)
        if placeholder:
            self._input.setPlaceholderText(placeholder)
        self._input.setFixedHeight(36)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background:{C.BG_INPUT};
                color:{C.T0};
                border:1.5px solid {C.BDR2};
                border-radius:6px;
                padding:4px 12px;
                font-family:'{C.FUI}';
                font-size:12px;
                font-weight:500;
                selection-background-color:{C.BLUE};
                selection-color:#FFFFFF;
            }}
            QLineEdit:focus {{
                border-color:{C.BLUE};
                background:#FFFFFF;
            }}
        """)
        # Enter 키 → 확인
        self._input.returnPressed.connect(self.accept)
        blay.addWidget(self._input)

        blay.addStretch()

        # 버튼
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0); btn_row.setSpacing(8)
        btn_row.addStretch()

        sec_btn = QPushButton(secondary_label)
        sec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sec_btn.setFixedHeight(32); sec_btn.setMinimumWidth(80)
        sec_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C.BG_HOVER}; color:{C.T1};
                border:1px solid {C.BDR2}; border-radius:6px;
                font-family:'{C.FUI}'; font-size:11px; font-weight:600;
                padding:6px 16px;
            }}
            QPushButton:hover {{
                background:{C.BDR}; color:{C.T0}; border-color:{C.T3};
            }}
            QPushButton:pressed {{ background:{C.BDR2}; }}
        """)
        sec_btn.clicked.connect(self.reject)
        btn_row.addWidget(sec_btn)

        pri_btn = QPushButton(primary_label)
        pri_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pri_btn.setFixedHeight(32); pri_btn.setMinimumWidth(100)
        pri_btn.setDefault(True)
        pri_btn.setStyleSheet(f"""
            QPushButton {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {C.INDIGO}, stop:1 {C.BLUE});
                color:#FFFFFF; border:none; border-radius:6px;
                font-family:'{C.FUI}'; font-size:11px; font-weight:700;
                padding:6px 18px;
            }}
            QPushButton:hover {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #7AA0D5, stop:1 #7AAFC6);
            }}
            QPushButton:pressed {{ background:{C.INDIGO}; }}
        """)
        pri_btn.clicked.connect(self.accept)
        btn_row.addWidget(pri_btn)

        blay.addLayout(btn_row)
        clay.addWidget(body)

        # 입력란 포커스 + 전체 선택
        self._input.setFocus()
        self._input.selectAll()

    @property
    def text_value(self) -> str:
        return self._input.text()

    @staticmethod
    def get_text(parent,
                 title: str = "입력",
                 headline: str = "",
                 detail: str = "",
                 initial: str = "",
                 placeholder: str = "") -> tuple:
        """QInputDialog.getText 와 유사한 시그니처. 반환: (text, ok)."""
        dlg = TextInputDialog(
            parent, title=title, headline=headline, detail=detail,
            initial=initial, placeholder=placeholder)
        ok = (dlg.exec() == QDialog.DialogCode.Accepted)
        return (dlg.text_value if ok else "", ok)

    # 드래그 이동
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                ev.globalPosition().toPoint() - self.frameGeometry().topLeft())
            ev.accept()

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()


# ══════════════════════════════════════════════════════════════
#  SpecMappingDialog — 변경 함수 ↔ 사양변경 매핑 다이얼로그
# ══════════════════════════════════════════════════════════════
class SpecMappingDialog(QDialog):
    """AI 분석 실행 직전 사용자가 변경된 함수별로 어떤 사양변경에 매칭되는지
    드롭다운으로 확정한다.

    입력:
      changed_funcs : list of dict — [{"file": "App_BMS.c", "function": "...", ...}, ...]
      spec_changes  : list of dict — [{"id": "1071064", "name": "MCU ...", ...}, ...]

    결과 (mapping property):
      list of dict — 입력 changed_funcs 와 동일 순서, 각 dict 에 "spec_id" 키 추가.
                     spec_id 가 "" 이면 미매칭.

    효율화:
      - 상단 🔍 검색창 — 함수명/파일명 부분 일치 필터 (대소문자 무시)
      - 파일 헤더 옆 [이 파일 전체 ▼] 일괄 드롭다운 — 그 파일의 (보이는)
        모든 함수를 같은 사양변경으로 한 번에 매핑
    """

    def __init__(self, parent, changed_funcs: list, spec_changes: list):
        super().__init__(parent)
        self.setWindowTitle("변경점 ↔ 사양변경 매핑")
        self.setMinimumSize(820, 600)
        self.setStyleSheet(
            f"QDialog {{ background:{C.BG_PANEL}; border:1px solid {C.BDR2}; }}")
        self._changed_funcs = list(changed_funcs or [])
        self._spec_changes  = list(spec_changes or [])
        # _rows : list of dict
        #   {item, file_lbl_text, func_text_lower,
        #    row_widget, combo}
        self._rows: list[dict] = []
        # _files : OrderedDict {file_name: {header_widget, bulk_combo,
        #                                    row_idxs: [int, ...]}}
        self._files: dict = {}
        self._mapping: list = []
        self._build()

    @property
    def mapping(self) -> list:
        return self._mapping

    def _combo_style(self) -> str:
        return (f"QComboBox {{ background:#FFFFFF; color:{C.T1};"
                f"  border:1px solid {C.BDR}; border-radius:4px;"
                "  padding:3px 8px; font-size:10px; min-height:22px; }}"
                f"QComboBox:hover {{ border-color:{C.BLUE}; }}"
                "QComboBox QAbstractItemView { font-size:10px; }")

    def _bulk_combo_style(self) -> str:
        return (f"QComboBox {{ background:#EEF2F7; color:{C.BLUE};"
                f"  border:1px dashed {C.BLUE}; border-radius:4px;"
                "  padding:2px 8px; font-size:10px; min-height:20px;"
                "  font-weight:bold; }}"
                f"QComboBox:hover {{ background:#E0EAF7; }}"
                "QComboBox QAbstractItemView { font-size:10px; }")

    def _spec_options(self) -> list[tuple[str, str]]:
        """드롭다운에 들어갈 옵션 — (display, data) 튜플 리스트."""
        out = [("— 미매칭 —", "")]
        for sc in self._spec_changes:
            sid = sc.get("id", "")
            name = sc.get("name", "") or f"#{sid}"
            out.append((f"#{sid} — {name}", sid))
        return out

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18); outer.setSpacing(0)

        # ── 헤더 ─────────────────────────────────────────────
        icon = QLabel("🔗")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background:transparent; border:none; font-size:24px;")
        outer.addWidget(icon)
        outer.addSpacing(2)

        title = QLabel("변경점 ↔ 사양변경 매핑 확정")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{C.T0}; background:transparent; border:none;"
            "font-size:14px; font-weight:bold;")
        outer.addWidget(title)
        outer.addSpacing(4)

        n_funcs = sum(1 for f in self._changed_funcs
                      if (f.get("function") or "") != "__global__")
        n_specs = len(self._spec_changes)
        info = QLabel(
            f"변경된 함수 {n_funcs}개를 사양변경 {n_specs}개 중 하나에 매핑하거나 "
            f"<b>미매칭</b>으로 두세요. 파일 헤더의 <b>[이 파일 전체 ▼]</b> "
            f"드롭다운으로 한 번에 매핑할 수 있고, 상단 🔍 검색으로 범위를 좁힐 "
            f"수 있습니다.")
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet(
            f"color:{C.T3}; background:transparent; border:none;"
            "font-size:11px;")
        outer.addWidget(info)
        outer.addSpacing(10)

        # ── 검색창 ──────────────────────────────────────────
        search_row = QHBoxLayout(); search_row.setSpacing(8)
        s_lbl = QLabel("🔍")
        s_lbl.setStyleSheet(
            f"color:{C.T2}; background:transparent; font-size:13px;")
        search_row.addWidget(s_lbl)
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "함수명 / 파일명 일부 입력 (예: ReadDataLength, App_BMS)")
        self._search.setStyleSheet(
            f"QLineEdit {{ background:#FFFFFF; color:{C.T1};"
            f"  border:1px solid {C.BDR}; border-radius:5px;"
            "  padding:5px 10px; font-size:11px; }}"
            f"QLineEdit:focus {{ border-color:{C.BLUE}; }}")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search, 1)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(
            f"color:{C.T3}; background:transparent; font-size:10px;")
        search_row.addWidget(self._count_lbl)
        outer.addLayout(search_row)
        outer.addSpacing(8)

        # ── 스크롤 영역 ─────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.StyledPanel)
        scroll.setStyleSheet(
            f"QScrollArea {{ background:{C.BG_APP};"
            f"  border:1px solid {C.BDR}; border-radius:6px; }}")

        inner = QWidget()
        inner.setStyleSheet(f"background:{C.BG_APP};")
        self._inner_lay = QVBoxLayout(inner)
        self._inner_lay.setContentsMargins(10, 10, 10, 10)
        self._inner_lay.setSpacing(4)

        # 파일별 그룹화 — 입력 순서 보존
        cur_file = None
        for idx, item in enumerate(self._changed_funcs):
            fname = item.get("file") or "(파일 미상)"
            func  = item.get("function") or ""
            display_func = "(전역 영역)" if func == "__global__" else f"{func}()"

            # 파일 헤더 (첫 등장 시)
            if fname != cur_file:
                if cur_file is not None:
                    self._inner_lay.addSpacing(4)
                header_widget = self._make_file_header(fname)
                self._inner_lay.addWidget(header_widget)
                cur_file = fname

            # 함수 행 (라벨 + 콤보)
            row_widget = QWidget()
            row_widget.setStyleSheet("background:transparent;")
            row_lay = QHBoxLayout(row_widget)
            row_lay.setContentsMargins(18, 0, 0, 0); row_lay.setSpacing(8)

            func_lbl = QLabel(display_func)
            func_lbl.setStyleSheet(
                f"color:{C.T2}; background:transparent; font-size:11px;")
            func_lbl.setMinimumWidth(260)
            row_lay.addWidget(func_lbl)

            combo = QComboBox()
            combo.setStyleSheet(self._combo_style())
            combo.setMinimumWidth(360)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Fixed)
            for display, data in self._spec_options():
                combo.addItem(display, data)
            combo.setCurrentIndex(0)
            row_lay.addWidget(combo, 1)

            self._inner_lay.addWidget(row_widget)

            row_info = {
                "item":            item,
                "row_widget":      row_widget,
                "combo":           combo,
                "func_text_lower": display_func.lower(),
                "file_lower":      fname.lower(),
            }
            self._rows.append(row_info)
            # 파일별 row index 누적
            self._files[fname]["row_idxs"].append(len(self._rows) - 1)

        self._inner_lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)
        outer.addSpacing(10)

        # ── 하단 일괄 동작 ──────────────────────────────────
        bulk = QHBoxLayout(); bulk.setSpacing(8)
        clear_btn = QPushButton("🧹  모두 미매칭")
        clear_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.T2};"
            f"  border:1px solid {C.BDR}; border-radius:5px;"
            "  padding:4px 12px; font-size:10px; }}"
            f"QPushButton:hover {{ color:{C.T0}; border-color:{C.T2}; }}")
        clear_btn.setToolTip("(보이는 행만) 모두 미매칭으로 초기화")
        clear_btn.clicked.connect(self._clear_visible)
        bulk.addWidget(clear_btn)
        bulk.addStretch()
        outer.addLayout(bulk)
        outer.addSpacing(8)

        # ── 버튼 ────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        btn_row.addStretch()
        cancel_btn = QPushButton("취소")
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background:#FFFFFF; color:{C.T1};"
            f"  border:1px solid {C.BDR}; border-radius:6px;"
            "  padding:6px 18px; font-size:11px; font-weight:600; }}"
            f"QPushButton:hover {{ border-color:{C.T2}; }}")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("✅  분석 진행")
        ok_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:6px;"
            "  padding:6px 18px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H};"
            f"  border-color:{C.ACCENT_H}; }}")
        ok_btn.clicked.connect(self._on_ok)
        ok_btn.setDefault(True)
        btn_row.addWidget(ok_btn)
        outer.addLayout(btn_row)

        # 초기 카운트 갱신
        self._update_count()

    # ── 파일 헤더 (이름 + 일괄 매핑 드롭다운) ─────────────────
    def _make_file_header(self, fname: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 6, 0, 2); h.setSpacing(8)

        lbl = QLabel(f"📄 <b>{fname}</b>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setStyleSheet(
            f"color:{C.T1}; background:transparent; font-size:11px;")
        h.addWidget(lbl, 1)

        bulk = QComboBox()
        bulk.setStyleSheet(self._bulk_combo_style())
        bulk.setFixedWidth(280)
        bulk.addItem("📋  이 파일 전체 적용 …", "__sentinel__")
        for display, data in self._spec_options():
            bulk.addItem(display, data)
        bulk.setCurrentIndex(0)
        bulk.currentIndexChanged.connect(
            lambda _i, f=fname, c=bulk: self._on_bulk_changed(f, c))
        h.addWidget(bulk)

        self._files[fname] = {
            "header_widget": w,
            "bulk_combo":    bulk,
            "row_idxs":      [],
        }
        return w

    # ── 파일 일괄 매핑 ──────────────────────────────────────
    def _on_bulk_changed(self, fname: str, bulk_combo: QComboBox):
        # sentinel ("선택해주세요") 이면 무시
        data = bulk_combo.currentData()
        if data == "__sentinel__":
            return
        # 그 파일의 visible 한 row 들의 combo 를 같은 spec_id 로 set
        info = self._files.get(fname)
        if not info:
            return
        for idx in info["row_idxs"]:
            row = self._rows[idx]
            if not row["row_widget"].isVisible():
                continue
            # data ↔ combo 항목 매칭
            combo = row["combo"]
            for i in range(combo.count()):
                if combo.itemData(i) == data:
                    combo.setCurrentIndex(i)
                    break
        # 일괄 적용 후 sentinel 로 되돌림 (다시 선택 가능 + 실수 방지)
        bulk_combo.blockSignals(True)
        bulk_combo.setCurrentIndex(0)
        bulk_combo.blockSignals(False)

    # ── 검색 필터 ───────────────────────────────────────────
    def _apply_filter(self, text: str):
        q = (text or "").strip().lower()
        # 각 row visible 갱신
        for row in self._rows:
            if not q:
                visible = True
            else:
                visible = (q in row["func_text_lower"]
                           or q in row["file_lower"])
            row["row_widget"].setVisible(visible)
        # 파일 헤더: 그 파일에 visible row 가 있으면 헤더도 visible
        for fname, info in self._files.items():
            any_visible = any(
                self._rows[i]["row_widget"].isVisible()
                for i in info["row_idxs"])
            info["header_widget"].setVisible(any_visible)
        self._update_count()

    def _update_count(self):
        total = len(self._rows)
        shown = sum(1 for r in self._rows if r["row_widget"].isVisible())
        if shown == total:
            self._count_lbl.setText(f"{total}개 표시 중")
        else:
            self._count_lbl.setText(f"{shown} / {total}개 표시 중")

    # ── 모두 미매칭 (보이는 것만) ────────────────────────────
    def _clear_visible(self):
        for row in self._rows:
            if row["row_widget"].isVisible():
                row["combo"].setCurrentIndex(0)

    # ── OK ──────────────────────────────────────────────────
    def _on_ok(self):
        out = []
        for row in self._rows:
            d = dict(row["item"])
            d["spec_id"] = row["combo"].currentData() or ""
            out.append(d)
        self._mapping = out
        self.accept()
