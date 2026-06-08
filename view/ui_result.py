"""ui_result.py — 우측 ResultPanel 및 보조 위젯 전체.

view.py 에서 분리된 컴포넌트:
  StepBar, DropZone, ReqInput, AnalysisFilePanel, _ReqTabContent,
  ExtrasPanel, _SyncEdit, DiffView, ReqDiffView, ResultView, ResultPanel.

ResultPanel 은 좌측 InputPanel 과 시그널/슬롯으로만 통신한다.
"""

import os
import math
import re
import difflib
import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QScrollArea, QSizePolicy,
    QCheckBox, QSplitter, QProgressBar, QStackedWidget,
    QTextEdit, QLineEdit, QTreeWidget, QTreeWidgetItem, QApplication,
    QGraphicsDropShadowEffect, QDialog, QGridLayout, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush,
    QTextCharFormat, QTextCursor, QPixmap,
)

from config import C, lbl, hsep, sec_label
from core.model import diff_func_analysis, build_unified_diff, diff_stats
from integrations.codebeamer import CbSectionWidget

# ── 분리된 헬퍼/유틸 ──
from .ui_md   import _md_to_html
from .ui_save import show_save_popup as _show_save_popup_fn


def _get_check_icon_path() -> str:
    """체크마크 SVG 파일을 생성 후 경로 반환 (QSS image: 용).
    .exe(PyInstaller) 패키징 시 sys._MEIPASS 임시 폴더를 사용한다."""
    import sys
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
        # 프로그램 메인 BLUE (C.BLUE = #8BBDD0) — 기존 #3B82F6 였음
        '<rect width="16" height="16" fill="#8BBDD0" rx="3"/>'
        '<polyline points="3,8.5 6.5,12 13,4" stroke="white"'
        ' stroke-width="2.5" fill="none"'
        ' stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    )
    if getattr(sys, "frozen", False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "_check_icon.svg")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
    except OSError:
        return ""
    return path.replace("\\", "/")


def _shadow(widget, blur: int = 18, dx: int = 0, dy: int = 4, alpha: int = 18):
    """위젯에 부드러운 드롭 그림자를 적용한다."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(dx)
    eff.setYOffset(dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)


TAB_COLORS = {
    "files":   "#7BA7D4",   # 분석파일 선택 — 파스텔 블루
    "extras":  C.BLUE_DK,   # 추가분석자료 — 진한 블루 (BLUE 통일, files 와 구분)
    "diff":    C.ADD_FG,
    "summary": C.AMBER,
    "vuln":    C.RED,
}


# ══════════════════════════════════════════════════════════════
#  StepBar — ①②③ 진행 상태 표시
# ══════════════════════════════════════════════════════════════
class StepBar(QWidget):
    _NAMES  = ["코드 비교", "변경점 요약", "취약점 분석"]
    _COLORS = [C.ADD_FG, C.AMBER, C.RED]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(0)

        self._dots:   list[QLabel] = []
        self._labels: list[QLabel] = []
        self._lines:  list[QFrame] = []

        _nums = ["①", "②", "③"]
        for i, name in enumerate(self._NAMES):
            dot = QLabel(_nums[i])
            dot.setFixedSize(24, 24)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
            self._dots.append(dot)
            lay.addWidget(dot)

            txt = QLabel(f"  {name}  ")
            txt.setFont(QFont(C.FUI, 9))
            self._labels.append(txt)
            lay.addWidget(txt)

            if i < 2:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setFixedHeight(1)
                line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                self._lines.append(line)
                lay.addWidget(line)

        self.reset()

    # ── 내부 스타일링 ─────────────────────────────────────────
    def _style_dot(self, i: int, state: str):
        dot  = self._dots[i]
        txt  = self._labels[i]
        col  = self._COLORS[i]
        nums = ["①", "②", "③"]
        if state == "done":
            dot.setText("✓")
            dot.setStyleSheet(
                f"color:#0D1117; background:{col}; border-radius:12px; font-size:9px;")
            txt.setStyleSheet(f"color:{col}; background:transparent; font-size:9px;")
        elif state == "active":
            dot.setText(nums[i])
            dot.setStyleSheet(
                f"color:white; background:{col}; border-radius:12px; "
                f"font-size:9px; font-weight:bold;")
            txt.setStyleSheet(
                f"color:{col}; background:transparent; font-weight:bold; font-size:9px;")
        else:
            dot.setText(nums[i])
            dot.setStyleSheet(
                f"color:{C.T3}; background:{C.BDR}; border-radius:12px; font-size:9px;")
            txt.setStyleSheet(f"color:{C.T3}; background:transparent; font-size:9px;")

    def _style_line(self, i: int, active: bool):
        if i < len(self._lines):
            self._lines[i].setStyleSheet(
                f"background:{'#3FB950' if active else C.BDR};")

    # ── 공개 메서드 ───────────────────────────────────────────
    def reset(self):
        for i in range(3):
            self._style_dot(i, "idle")
        for i in range(len(self._lines)):
            self._style_line(i, False)

    def advance(self, step: int):
        for i in range(3):
            if i + 1 < step:    self._style_dot(i, "done")
            elif i + 1 == step: self._style_dot(i, "active")
            else:               self._style_dot(i, "idle")
        for i in range(len(self._lines)):
            self._style_line(i, i < step - 1)

    def spotlight(self, step: int):
        """탭 클릭 시 해당 스텝만 하이라이트 (done 처리 없음)."""
        for i in range(3):
            self._style_dot(i, "active" if i + 1 == step else "idle")
        for i in range(len(self._lines)):
            self._style_line(i, False)


# ══════════════════════════════════════════════════════════════
#  DropZone — 드래그앤드롭 파일 선택
# ══════════════════════════════════════════════════════════════
class DropZone(QWidget):
    file_loaded = pyqtSignal(str)

    def __init__(self, role: str, accent_hex: str, mode: str = "file", parent=None):
        super().__init__(parent)
        self._accent = QColor(accent_hex)
        self._path   = ""
        self._state  = "idle"   # idle | hover | done
        self._tick   = 0
        self._mode   = mode     # "file" | "folder"
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        QTimer(self, timeout=self._on_tick, interval=40).start()
        self._build(role)

    def _build(self, role: str):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)

        top = QHBoxLayout(); top.setSpacing(8)

        self._icon = QLabel("↓")
        self._icon.setFixedSize(28, 28)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setFont(QFont(C.FUI, 13, QFont.Weight.Bold))
        self._icon.setStyleSheet(
            f"color:{self._accent.name()}; background:{C.BG_HOVER}; "
            f"border-radius:6px;")
        top.addWidget(self._icon)

        rl = QLabel(role)
        rl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        rl.setStyleSheet(f"color:{self._accent.name()}; background:transparent;")
        top.addWidget(rl)
        top.addStretch()

        browse = QPushButton("찾아보기")
        browse.setObjectName("btn_sub")
        browse.setFixedSize(72, 24)
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.clicked.connect(self._browse)
        top.addWidget(browse)
        lay.addLayout(top)

        _hint_text = "폴더를 드래그하거나 클릭하세요" if self._mode == "folder" else "파일을 드래그하거나 클릭하세요"
        self._hint = QLabel(_hint_text)
        self._hint.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(f"color:{C.T2}; background:transparent;")
        lay.addWidget(self._hint)

        self._file_lbl = QLabel("")
        self._file_lbl.setFont(QFont(C.FCODE, 10, QFont.Weight.Bold))
        self._file_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._file_lbl.setStyleSheet(f"color:{C.T0}; background:transparent;")
        self._file_lbl.setWordWrap(True)
        self._file_lbl.hide()
        lay.addWidget(self._file_lbl)

        self._clear_btn = QPushButton("✕  제거")
        self._clear_btn.setFixedHeight(22)
        self._clear_btn.setMinimumWidth(68)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.RED};"
            f"  border:1px solid {C.RED}; border-radius:4px;"
            f"  padding:1px 10px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.RED}; color:#FFFFFF; }}")
        self._clear_btn.clicked.connect(self.clear)
        self._clear_btn.hide()
        lay.addWidget(self._clear_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _on_tick(self):
        self._tick = (self._tick + 3) % 360
        if self._state == "idle":
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)

        if self._state == "done":
            bg = QColor(self._accent); bg.setAlpha(15)
            p.setBrush(QBrush(bg))
            p.setPen(QPen(self._accent, 1.5))
        elif self._state == "hover":
            bg = QColor(self._accent); bg.setAlpha(25)
            p.setBrush(QBrush(bg))
            p.setPen(QPen(self._accent, 2, Qt.PenStyle.DashLine))
        elif self._state == "reject":
            bg = QColor(C.RED); bg.setAlpha(18)
            p.setBrush(QBrush(bg))
            p.setPen(QPen(QColor(C.RED), 2, Qt.PenStyle.DashLine))
        else:
            pulse = (1 + math.sin(math.radians(self._tick))) / 2
            c = QColor(self._accent); c.setAlpha(int(30 + 50 * pulse))
            p.setBrush(QBrush(QColor(C.BG_CARD)))
            pen = QPen(c, 1.5, Qt.PenStyle.DashLine)
            pen.setDashPattern([6, 4]); p.setPen(pen)

        p.drawRoundedRect(r, 8, 8)
        p.end()

    def set_file(self, path: str):
        path = path.strip().strip("{}")
        if self._mode == "folder":
            if not os.path.isdir(path): return
            self._path = path; self._state = "done"
            _src_exts = ('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')
            count = sum(
                1 for _, _, files in os.walk(path)
                for f in files if f.lower().endswith(_src_exts)
            )
            self._icon.setText("✓")
            self._icon.setStyleSheet(
                f"color:white; background:{C.GREEN}; border-radius:6px; font-size:12px;")
            self._hint.setText("폴더 로드 완료")
            self._hint.setStyleSheet(f"color:{C.GREEN}; background:transparent;")
            self._file_lbl.setText(f"{os.path.basename(path)}/  (소스 {count}개)")
            self._file_lbl.show(); self._clear_btn.show()
            self.update(); self.file_loaded.emit(path)
            return
        if not os.path.isfile(path): return
        self._path = path; self._state = "done"
        kb = os.path.getsize(path) / 1024
        sz = f"{kb:.1f} KB" if kb < 1024 else f"{kb/1024:.2f} MB"
        self._icon.setText("✓")
        self._icon.setStyleSheet(
            f"color:white; background:{C.GREEN}; border-radius:6px; font-size:12px;")
        self._hint.setText("파일 로드 완료")
        self._hint.setStyleSheet(f"color:{C.GREEN}; background:transparent;")
        self._file_lbl.setText(f"{os.path.basename(path)}  ({sz})")
        self._file_lbl.show(); self._clear_btn.show()
        self.update(); self.file_loaded.emit(path)

    def clear(self):
        self._path = ""; self._state = "idle"
        self._icon.setText("↓")
        self._icon.setStyleSheet(
            f"color:{self._accent.name()}; background:{C.BG_HOVER}; border-radius:6px;")
        _reset_hint = "폴더를 드래그하거나 클릭하세요" if self._mode == "folder" else "파일을 드래그하거나 클릭하세요"
        self._hint.setText(_reset_hint)
        self._hint.setStyleSheet(f"color:{C.T3}; background:transparent;")
        self._file_lbl.hide(); self._clear_btn.hide()
        self.update(); self.file_loaded.emit("")

    def text(self) -> str: return self._path

    def _browse(self):
        if self._mode == "folder":
            path = QFileDialog.getExistingDirectory(self, "폴더 선택", "")
            if path: self.set_file(path)
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "파일 선택", "",
                "모든 파일 (*.*);;C/C++ (*.c *.cpp *.h);;Patch (*.patch *.diff);;텍스트 (*.txt)")
            if path: self.set_file(path)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            urls = e.mimeData().urls()
            path = urls[0].toLocalFile() if urls else ""
            is_dir = os.path.isdir(path)
            type_ok = (self._mode == "folder" and is_dir) or \
                      (self._mode == "file"   and not is_dir)
            if type_ok:
                e.acceptProposedAction()
                self._state = "hover"
                self._icon.setText("⬇")
                self._hint.setText(
                    "폴더를 드래그하거나 클릭하세요" if self._mode == "folder"
                    else "파일을 드래그하거나 클릭하세요")
                self._hint.setStyleSheet(f"color:{C.T3}; background:transparent;")
            else:
                e.ignore()
                self._state = "reject"
                self._icon.setText("✕")
                self._icon.setStyleSheet(
                    f"color:white; background:{C.RED}; border-radius:6px; font-size:12px;")
                wrong = "파일" if self._mode == "folder" else "폴더"
                self._hint.setText(f"{wrong}은 넣을 수 없습니다")
                self._hint.setStyleSheet(f"color:{C.RED}; background:transparent;")
            self.update()

    def dragLeaveEvent(self, _):
        self._state = "done" if self._path else "idle"
        if self._path:
            self._icon.setText("✓")
            self._icon.setStyleSheet(
                f"color:white; background:{C.GREEN}; border-radius:6px; font-size:12px;")
        else:
            self._icon.setText("↓")
            self._icon.setStyleSheet(
                f"color:{self._accent.name()}; background:{C.BG_HOVER}; border-radius:6px;")
        _reset_hint = "폴더를 드래그하거나 클릭하세요" if self._mode == "folder" \
                      else "파일을 드래그하거나 클릭하세요"
        self._hint.setText(_reset_hint)
        self._hint.setStyleSheet(f"color:{C.T3}; background:transparent;")
        self.update()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls: self.set_file(urls[0].toLocalFile())

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._browse()


# ══════════════════════════════════════════════════════════════
#  ReqInput — 요구사항 입력 (직접입력 / 파일첨부)
# ══════════════════════════════════════════════════════════════
class ReqInput(QWidget):
    """변경 전/후 요구사항서 입력 — 2단(Before/After) 레이아웃.

    각 컬럼: DropZone (파일 드롭) + QTextEdit (자동 채움 / 직접 편집).
    파일 drop 시 .txt/.md/.docx 본문이 같은 컬럼 QTextEdit 으로 자동 추출된다.

    외부 API (호환):
      - get_old_req_path() / get_new_req_path() — DropZone 의 파일 경로
        (DIFF 추출 워커에 그대로 전달)
      - set_req_diff_text(text)               — 워커 완료 후 합쳐진 diff 주입
      - get_text()                            — AI 분석 입력으로 쓰일 텍스트:
            1) 워커 결과 (`_req_diff_text`) 가 있으면 그걸 반환 (현재 흐름 유지)
            2) 없으면 Before/After QTextEdit 내용을 "수정 전 / 수정 후" 형식
               으로 묶어서 반환 (파일 없이 직접 텍스트 입력한 경우의 폴백)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._req_diff_text = ""
        self._req_err_lbls: dict = {}   # attr -> 에러 표시 라벨
        self._mode = "file"             # "file" | "text" — 기본 파일삽입
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(8)

        # 모드 토글 — [📄 파일 삽입] / [✏ 직접 입력] (Before/After 동시 전환)
        tab_row = QHBoxLayout(); tab_row.setSpacing(8)
        self._btn_file = QPushButton("📄  파일 삽입")
        self._btn_file.setObjectName("mini_on")
        self._btn_file.setFixedHeight(26)
        self._btn_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_file.clicked.connect(lambda: self._switch("file"))
        tab_row.addWidget(self._btn_file)

        self._btn_text = QPushButton("✏  직접 입력")
        self._btn_text.setObjectName("mini_off")
        self._btn_text.setFixedHeight(26)
        self._btn_text.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_text.clicked.connect(lambda: self._switch("text"))
        tab_row.addWidget(self._btn_text)
        tab_row.addStretch()
        lay.addLayout(tab_row)

        # 2단 컬럼 — 각 컬럼: 라벨 + DropZone + (에러 라벨) + QTextEdit
        in_row = QHBoxLayout(); in_row.setSpacing(10)
        for label, attr, accent in (
            ("수정 전 요구사항", "te_before", C.DEL_FG),
            ("수정 후 요구사항", "te_after",  C.ADD_FG),
        ):
            col = QVBoxLayout(); col.setSpacing(4)
            l = QLabel(label)
            l.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
            l.setStyleSheet(f"color:{C.T2}; background:transparent;")
            col.addWidget(l)

            # 파일 드롭존 — 컴팩트 (DropZone 기본 minimumHeight=150 을 override)
            dz_role = label.replace("요구사항", "파일")  # "수정 전 파일" / "수정 후 파일"
            dz = DropZone(dz_role, accent)
            dz.setMinimumHeight(0)
            dz.setFixedHeight(95)
            dz.file_loaded.connect(
                lambda path, a=attr: self._on_req_file_loaded(a, path))
            setattr(self, f"dz_{attr}", dz)
            col.addWidget(dz)

            # 파일 추출 실패 메시지 (기본 숨김)
            err = QLabel("")
            err.setFont(QFont(C.FUI, 9))
            err.setStyleSheet(f"color:{C.RED}; background:transparent;")
            err.setWordWrap(True)
            err.hide()
            self._req_err_lbls[attr] = err
            col.addWidget(err)

            te = QTextEdit()
            te.setObjectName("te_info")
            te.setStyleSheet(
                f"QTextEdit#te_info {{ background:#FFFFFF; color:{C.T0}; "
                f"border:1px solid {C.BDR}; border-radius:6px; padding:8px 10px; "
                f"selection-background-color:{C.ACCENT_H}; selection-color:#FFFFFF; }}")
            te.setPlaceholderText(
                f"{label} 텍스트를 직접 붙여넣으세요.")
            te.setFixedHeight(140)
            te.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            setattr(self, attr, te)
            col.addWidget(te)
            in_row.addLayout(col, 1)
        lay.addLayout(in_row)

        # 하단 안내 — 파일 모드에서만 표시
        self._file_hint = lbl(
            "지원 형식: .txt  .md  .docx  — 파일을 드롭하면 본문 텍스트가 자동 추출됩니다.",
            9, False, C.T3)
        lay.addWidget(self._file_hint)

        # 초기 모드 적용 (파일 삽입)
        self._switch("file")

    def _switch(self, mode: str):
        """파일 삽입 / 직접 입력 모드 전환 — Before/After 동시 적용."""
        self._mode = mode
        is_file = (mode == "file")
        for attr in ("te_before", "te_after"):
            dz = getattr(self, f"dz_{attr}", None)
            te = getattr(self, attr, None)
            err = self._req_err_lbls.get(attr)
            if dz is not None:
                dz.setVisible(is_file)
            if te is not None:
                te.setVisible(not is_file)
            # 에러 라벨은 파일 모드에서만 의미가 있음
            if err is not None and not is_file:
                err.hide(); err.setText("")
        if self._file_hint is not None:
            self._file_hint.setVisible(is_file)
        # 버튼 객체명 토글 — 글로벌 QSS mini_on/mini_off 스타일 반영
        self._btn_file.setObjectName("mini_on"  if is_file else "mini_off")
        self._btn_text.setObjectName("mini_off" if is_file else "mini_on")
        for btn in (self._btn_file, self._btn_text):
            btn.style().unpolish(btn); btn.style().polish(btn)

    def _on_req_file_loaded(self, attr: str, path: str):
        """DropZone.file_loaded 슬롯 — 파일 본문을 해당 QTextEdit 으로 주입.

        빈 path 는 ✕ 제거 이벤트: QTextEdit 내용은 보존, 에러 라벨만 숨김.
        .docx 추출 실패(python-docx 미설치) / 인코딩 오류는 카드 내 라벨에 표시.
        """
        err_lbl = self._req_err_lbls.get(attr)
        if err_lbl is not None:
            err_lbl.hide(); err_lbl.setText("")
        if not path:
            return
        try:
            from core.text_io import read_doc_lines
            lines = read_doc_lines(path)
        except ImportError:
            if err_lbl is not None:
                err_lbl.setText("⚠ .docx 처리를 위한 python-docx 패키지가 설치되어 있지 않습니다.")
                err_lbl.show()
            return
        except Exception as e:
            if err_lbl is not None:
                err_lbl.setText(f"⚠ 파일 읽기 실패: {type(e).__name__}: {e}")
                err_lbl.show()
            return
        te: QTextEdit = getattr(self, attr)
        te.setPlainText("\n".join(lines))

    # ── 외부 API (호환 유지) ─────────────────────────────────
    def get_old_req_path(self) -> str:
        return self.dz_te_before.text() if hasattr(self, "dz_te_before") else ""

    def get_new_req_path(self) -> str:
        return self.dz_te_after.text() if hasattr(self, "dz_te_after") else ""

    def get_before_text(self) -> str:
        """수정 전 요구사항 텍스트 (파일/직접 모드 무관 — QTextEdit 내용 그대로)."""
        return self.te_before.toPlainText().strip() if hasattr(self, "te_before") else ""

    def get_after_text(self) -> str:
        """수정 후 요구사항 텍스트 (파일/직접 모드 무관 — QTextEdit 내용 그대로)."""
        return self.te_after.toPlainText().strip() if hasattr(self, "te_after") else ""

    def set_req_diff_text(self, text: str):
        """워커 완료 후 추출된 diff 텍스트를 주입한다."""
        self._req_diff_text = text

    def get_text(self) -> str:
        """AI 분석 입력으로 쓰일 텍스트.

        파일 기반 diff 결과(_req_diff_text) 가 있으면 우선 사용.
        없으면 Before/After QTextEdit 내용을 "수정 전 / 수정 후" 포맷으로 묶어 반환.
        """
        diff_text = self._req_diff_text.strip()
        if diff_text:
            return diff_text
        before = self.te_before.toPlainText().strip() if hasattr(self, "te_before") else ""
        after  = self.te_after.toPlainText().strip()  if hasattr(self, "te_after")  else ""
        parts = []
        if before:
            parts.append("=== 수정 전 요구사항 ===\n" + before)
        if after:
            parts.append("=== 수정 후 요구사항 ===\n" + after)
        return "\n\n".join(parts)


# ══════════════════════════════════════════════════════════════
#  AnalysisFilePanel — 분석파일 선택 탭 (파일변경점 + 요구사항 2섹션)
# ══════════════════════════════════════════════════════════════
class AnalysisFilePanel(QWidget):
    """파일변경점 섹션 + 요구사항 섹션 수직 배치"""

    diff_requested      = pyqtSignal()        # 코드 DIFF 추출 버튼
    # req_diff_requested / req_include_changed → ExtrasPanel 로 이동

    def __init__(self, parent=None):
        super().__init__(parent)
        self._input_mode = "file"   # "file" | "folder"

        # ── 코드 diff 드롭존 ────────────────────────────────────
        self._dz_old        = DropZone("수정 전 파일  (Before)", C.DEL_FG)
        self._dz_new        = DropZone("수정 후 파일  (After)",  C.ADD_FG)
        self._dz_old_folder = DropZone("수정 전 폴더  (Before)", C.DEL_FG, mode="folder")
        self._dz_new_folder = DropZone("수정 후 폴더  (After)",  C.ADD_FG, mode="folder")

        # ── 버튼 참조 ────────────────────────────────────────────
        self._diff_btn_card: QPushButton = None

        self._build()

    # ── UI 구성 ──────────────────────────────────────────────
    def _build(self):
        self.setStyleSheet(f"background:{C.BG_APP};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        body = QWidget(); body.setStyleSheet(f"background:{C.BG_APP};")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(20)

        # ── Section 1: 파일 변경점 ─────────────────────────────
        lay.addWidget(self._build_file_section())
        # Section 2(요구사항)는 추가분석자료 탭으로 이동
        lay.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)

    # ── 섹션 1: 파일변경점 ────────────────────────────────────
    def _build_file_section(self) -> QFrame:
        # 프로그램 메인 BLUE 통일 — 기존 진한 블루(#3B82F6) 였음
        BLUE = C.BLUE
        card = QFrame(); card.setObjectName("analysis_file_card")
        card.setStyleSheet(
            f"#analysis_file_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        vl = QVBoxLayout(card); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)

        # 헤더: 왼쪽 색상 바 + 제목 + 부제목
        hdr = QFrame(); hdr.setFixedHeight(44)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            "border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(0, 0, 12, 0); hl.setSpacing(10)
        # 왼쪽 색상 바
        accent = QFrame(); accent.setFixedSize(4, 44)
        accent.setStyleSheet(
            f"background:{BLUE}; border-top-left-radius:10px;")
        hl.addWidget(accent)
        t = QLabel("🔀  파일 변경점"); t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{BLUE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()
        vl.addWidget(hdr)

        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 10, 14, 14); bl.setSpacing(8)
        vl.addWidget(body)

        # 파일/폴더 토글
        mode_row = QHBoxLayout(); mode_row.setSpacing(6)
        self._btn_file_mode   = QPushButton("📄  파일")
        self._btn_folder_mode = QPushButton("📁  폴더")
        self._btn_file_mode.setObjectName("mini_on")
        self._btn_folder_mode.setObjectName("mini_off")
        for b in (self._btn_file_mode, self._btn_folder_mode):
            b.setFixedHeight(24); b.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_file_mode.clicked.connect(lambda: self._switch_mode("file"))
        self._btn_folder_mode.clicked.connect(lambda: self._switch_mode("folder"))
        mode_row.addWidget(self._btn_file_mode)
        mode_row.addWidget(self._btn_folder_mode)
        mode_row.addStretch()
        bl.addLayout(mode_row)

        # 드롭존 스택
        self._drop_stack = QStackedWidget()
        self._drop_stack.setStyleSheet("background:transparent;")

        file_pg = QWidget(); file_pg.setStyleSheet("background:transparent;")
        fl = QHBoxLayout(file_pg); fl.setContentsMargins(0, 0, 0, 0); fl.setSpacing(6)
        fl.addWidget(self._dz_old, stretch=1)
        arr = QLabel("↔"); arr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arr.setFixedWidth(18); arr.setStyleSheet(f"color:{C.T3}; background:transparent;")
        fl.addWidget(arr); fl.addWidget(self._dz_new, stretch=1)
        self._drop_stack.addWidget(file_pg)

        folder_pg = QWidget(); folder_pg.setStyleSheet("background:transparent;")
        fol = QHBoxLayout(folder_pg); fol.setContentsMargins(0, 0, 0, 0); fol.setSpacing(6)
        fol.addWidget(self._dz_old_folder, stretch=1)
        arr2 = QLabel("↔"); arr2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arr2.setFixedWidth(18); arr2.setStyleSheet(f"color:{C.T3}; background:transparent;")
        fol.addWidget(arr2); fol.addWidget(self._dz_new_folder, stretch=1)
        self._drop_stack.addWidget(folder_pg)

        bl.addWidget(self._drop_stack)
        bl.addWidget(lbl("두 파일/폴더를 넣으면 diff를 자동 추출합니다.", 9, False, C.T2))
        bl.addSpacing(10)

        # 주석 무시 옵션
        self._chk_ignore_comments = QCheckBox("주석 변경 무시  (주석만 바뀐 줄은 변경점에서 제외)")
        self._chk_ignore_comments.setFont(QFont(C.FUI, 10))
        self._chk_ignore_comments.setStyleSheet(
            f"QCheckBox {{ color:{C.T1}; background:transparent;"
            f"  font-weight:600; spacing:6px; }}"
            f"QCheckBox::indicator {{ width:15px; height:15px; border-radius:3px;"
            f"  border:1px solid {C.BDR}; background:{C.BG_CARD}; }}"
            f"QCheckBox::indicator:checked {{ background:{C.BLUE}; border-color:{C.BLUE}; }}")
        bl.addWidget(self._chk_ignore_comments)
        bl.addSpacing(4)

        # 코드 DIFF 추출 버튼 — 프로그램 메인 BLUE 통일
        # (기존 진한 파랑 #1D4ED8/#1E40AF/#1E3A8A 그라데이션이었음)
        diff_btn = QPushButton("  🔀  코드 DIFF 추출")
        diff_btn.setFixedHeight(36)
        diff_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        diff_btn.setToolTip("수정 전/후 파일을 비교해서 코드 변경 VIEW를 표시합니다")
        diff_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:2px solid {C.ACCENT_H}; border-radius:8px;"
            f"  font-size:12px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:pressed {{ background:{C.BLUE_DK}; }}"
            f"QPushButton:disabled {{ background:#E2E8F0; color:#94A3B8;"
            f"  border-color:#CBD5E1; }}")
        diff_btn.clicked.connect(self.diff_requested.emit)
        self._diff_btn_card = diff_btn
        bl.addWidget(diff_btn)

        # AI 분석 실행 버튼이 외부에서 주입될 자리 (코드 DIFF 추출 버튼 바로 아래)
        self._below_diff_lay = bl

        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        _shadow(card)
        return card

    def attach_below_diff_button(self, widget):
        """코드 DIFF 추출 버튼 바로 아래에 위젯(보통 AI 분석 실행 버튼)을 추가한다."""
        if getattr(self, "_below_diff_lay", None) is not None:
            self._below_diff_lay.addWidget(widget)

    # ── 파일/폴더 모드 전환 ───────────────────────────────────
    def _switch_mode(self, mode: str):
        self._input_mode = mode
        self._drop_stack.setCurrentIndex(0 if mode == "file" else 1)
        self._btn_file_mode.setObjectName("mini_on"   if mode == "file" else "mini_off")
        self._btn_folder_mode.setObjectName("mini_off" if mode == "file" else "mini_on")
        for b in (self._btn_file_mode, self._btn_folder_mode):
            b.style().unpolish(b); b.style().polish(b)

    # ── DIFF 버튼 상태 제어 ───────────────────────────────────
    def set_diff_running(self, running: bool):
        if self._diff_btn_card:
            self._diff_btn_card.setEnabled(not running)
            self._diff_btn_card.setText(
                "  ⏳  추출 중..." if running else "  🔀  코드 DIFF 추출")

    # ── 외부 접근 메서드 ─────────────────────────────────────
    def get_input_mode(self)     -> str: return self._input_mode
    def get_old_path(self)       -> str: return self._dz_old.text()
    def get_new_path(self)       -> str: return self._dz_new.text()
    def get_old_folder_path(self)-> str: return self._dz_old_folder.text()
    def get_new_folder_path(self)-> str: return self._dz_new_folder.text()
    def get_ignore_comments(self) -> bool:
        return self._chk_ignore_comments.isChecked()

    # ── 요구사항 관련 메서드 → ExtrasPanel(_ReqTabContent)으로 이동됨 ──


# ══════════════════════════════════════════════════════════════
#  _ReqTabContent — 추가분석자료 > 요구사항 탭 내부 위젯
# ══════════════════════════════════════════════════════════════
class _ReqTabContent(QWidget):
    """ExtrasPanel 내 요구사항 탭: ReqInput + DIFF추출버튼 + ReqDiffView"""

    req_diff_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._req_input     = ReqInput()
        self._req_diff_btn: QPushButton = None
        self._req_diff_view = ReqDiffView()
        self._build()

    def _build(self):
        # 기존 보라(#7E60C0) → 프로그램 메인 BLUE 통일
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # ── 스크롤: 요구사항 입력 + 추출 버튼 ─────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget(); inner.setStyleSheet(f"background:{C.BG_CARD};")
        il = QVBoxLayout(inner)
        il.setContentsMargins(14, 12, 14, 10); il.setSpacing(14)
        il.addWidget(self._req_input)

        btn = QPushButton("  📋  요구사항 DIFF 추출")
        btn.setFixedHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:2px solid {C.ACCENT_H}; border-radius:8px;"
            f"  font-size:12px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:pressed {{ background:{C.BLUE_DK}; }}"
            f"QPushButton:disabled {{ background:#E2E8F0; color:#94A3B8;"
            f"  border-color:#CBD5E1; }}")
        btn.clicked.connect(self._on_req_diff_btn)
        self._req_diff_btn = btn
        il.addWidget(btn)
        scroll.setWidget(inner)
        lay.addWidget(scroll)

        # ── 구분선 ─────────────────────────────────────────────
        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C.BDR};")
        lay.addWidget(sep)

        # ── 요구사항 변경점 뷰 ─────────────────────────────────
        lay.addWidget(self._req_diff_view, stretch=1)

    def _on_req_diff_btn(self):
        old_path = self._req_input.get_old_req_path()
        new_path = self._req_input.get_new_req_path()
        if not old_path or not new_path:
            from PyQt6.QtWidgets import QToolTip
            QToolTip.showText(
                self._req_diff_btn.mapToGlobal(
                    self._req_diff_btn.rect().bottomLeft()),
                "수정 전/후 요구사항 파일을 모두 선택해주세요.",
                self._req_diff_btn, self._req_diff_btn.rect(), 3000)
            return
        self.req_diff_requested.emit()

    def get_req_text(self)       -> str:  return self._req_input.get_text()
    def get_old_req_path(self)   -> str:  return self._req_input.get_old_req_path()
    def get_new_req_path(self)   -> str:  return self._req_input.get_new_req_path()
    def set_req_diff_text(self, text: str): self._req_input.set_req_diff_text(text)
    def set_req_diff_running(self, running: bool):
        if self._req_diff_btn:
            self._req_diff_btn.setEnabled(not running)
            self._req_diff_btn.setText(
                "  ⏳  추출 중..." if running else "  📋  요구사항 DIFF 추출")
    def set_req_diff(self, old_lines: list, new_lines: list):
        self._req_diff_view.render(old_lines, new_lines)


# ══════════════════════════════════════════════════════════════
#  ExtrasPanel — 추가분석자료 탭 (요구사항 / 과거차)
# ══════════════════════════════════════════════════════════════
class ExtrasPanel(QWidget):
    """추가분석자료 탭: 요구사항/과거차 내부 탭 + 탭별 AI 포함 체크박스"""

    include_changed    = pyqtSignal(str, bool)   # (key, checked)
    req_diff_requested = pyqtSignal()            # 요구사항 DIFF 추출 요청

    # 9탭 사이드바 구조로 개편: 'req' 는 ② SWE.1 SRS 페이지로 이동.
    # 'code_info' / 'static' 은 기존 좌측 InputPanel 의 [코드 정보(선택)] /
    # [정적 검증] 카드가 여기로 이동한 결과.
    _SECTIONS = [
        # 모두 메인 BLUE 로 통일 (기존 #7E60C0 보라 → C.BLUE)
        ("code_info", "사양변경 트래커", "💡", C.BLUE),
        ("past",      "과거차",         "📁", C.BLUE),
        ("static",    "정적 검증",      "☑",  C.BLUE),
        # ("ll",   "L&L",    "📋", "#0EA5E9"),   # [LL/SWE DISABLED]
        # ("swe1", "SWE1",   "✅", "#16A34A"),   # [LL/SWE DISABLED]
        # ("swe3", "SWE3",   "🔍", "#2563EB"),   # [LL/SWE DISABLED]
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widgets: dict[str, "CbSectionWidget"] = {}
        self._tab_btns: dict[str, QPushButton] = {}
        self._include_chks: dict[str, QCheckBox] = {}
        self._stack: QStackedWidget = None
        self._req_tab: "_ReqTabContent | None" = None
        self._build()

    def _build(self):
        self.setStyleSheet(f"background:{C.BG_APP};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(0)

        # ── 카드 프레임 ────────────────────────────────────────
        # AnalysisFilePanel(analysis_file_card) 와 동일한 패턴:
        # rounded border + transparent body 로 둥근 모서리 자연스럽게 노출.
        card = QFrame(); card.setObjectName("extras_card")
        card.setStyleSheet(
            f"#extras_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # ── 탭 바 (좌: 탭 버튼  +  우: 'AI 분석에 포함' 체크박스) ───
        # 이전엔 탭 바 + 별도 체크박스 바 (chk_bar) 가 2층으로 쌓여 다른 탭
        # (AnalysisFilePanel) 의 단일 헤더와 묘하게 달라 보였음.
        # 단일 헤더 + 우측 체크박스 구조로 통일.
        tab_bar = QFrame()
        tab_bar.setObjectName("extras_tab_bar")
        tab_bar.setFixedHeight(44)
        tab_bar.setStyleSheet(
            f"#extras_tab_bar {{ background:{C.BG_PANEL};"
            f"  border-bottom:1px solid {C.BDR};"
            f"  border-top-left-radius:10px; border-top-right-radius:10px; }}")
        tl = QHBoxLayout(tab_bar)
        tl.setContentsMargins(12, 0, 14, 0); tl.setSpacing(2)

        first_key = self._SECTIONS[0][0]
        for key, title, icon, color in self._SECTIONS:
            btn = QPushButton(f"{icon}  {title}")
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._switch(k))
            self._tab_btns[key] = btn
            tl.addWidget(btn)
        tl.addStretch()

        # 'AI 분석에 포함' 체크박스 — 탭별로 미리 생성 후 한 번에 하나만 표시.
        # tab_bar 우측에 배치 (BG_PANEL 배경 위) → 단일 헤더 라인 유지.
        self._chk_widgets: dict[str, QCheckBox] = {}
        for key, title, icon, color in self._SECTIONS:
            chk = QCheckBox("AI 분석에 포함")
            chk.setChecked(False)
            chk.setCursor(Qt.CursorShape.PointingHandCursor)
            chk.setStyleSheet(
                f"QCheckBox {{ color:{C.T2}; font-size:11px; font-weight:600;"
                f"  background:transparent; spacing:6px; }}"
                f"QCheckBox::indicator {{ width:14px; height:14px; border-radius:3px;"
                f"  border:1px solid {C.BDR2}; background:{C.BG_CARD}; }}"
                f"QCheckBox::indicator:hover {{ border-color:{C.BLUE}; }}"
                f"QCheckBox::indicator:checked {{ background:{C.BLUE};"
                f"  border-color:{C.BLUE}; }}")
            chk.stateChanged.connect(lambda state, k=key: self._on_chk(k, state))
            self._include_chks[key] = chk
            self._chk_widgets[key] = chk
            chk.setVisible(False)
            tl.addWidget(chk)
        cl.addWidget(tab_bar)

        # 외부 호환 — chk_bar 변수 참조하는 코드 방지용 사용 안 함 표시
        self._chk_bar = None

        # ── 콘텐츠 스택 ───────────────────────────────────────
        # transparent: 카드의 rounded BG_CARD 가 코너에 자연스럽게 노출되도록
        # (다른 카드들이 body 를 transparent 로 두는 패턴과 동일)
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")

        section_cfg = {
            "past": dict(default_select_all=False, accordion_list_mode=True),
            # [LL/SWE DISABLED]
            # "ll":   dict(default_select_all=False, accordion_list_mode=True),
            # "swe1": dict(default_select_all=False, accordion_list_mode=True),
            # "swe3": dict(default_select_all=False, accordion_list_mode=True),
        }

        # view.extras_sections 는 ExtrasPanel 전용 — 순환 import 회피 위해 함수 내 import
        from view.extras_sections import CbSpecSection, StaticOptSection

        for key, title, icon, color in self._SECTIONS:
            if key == "code_info":
                w = CbSpecSection()
            elif key == "static":
                w = StaticOptSection()
            elif key == "past":
                cfg = section_cfg.get(key, {})
                w = CbSectionWidget(
                    title, icon, color,
                    section_key=key,
                    compact_header=True,
                    **cfg)
            else:
                continue   # 알 수 없는 키는 무시
            self._widgets[key] = w
            self._stack.addWidget(w)

        cl.addWidget(self._stack, stretch=1)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _shadow(card)
        lay.addWidget(card)
        self._switch(first_key)

    def _on_chk(self, key: str, state):
        checked = (state == Qt.CheckState.Checked.value)
        self.include_changed.emit(key, checked)

    def _switch(self, key: str):
        idx_map = {k: i for i, (k, _, _, _) in enumerate(self._SECTIONS)}
        self._stack.setCurrentIndex(idx_map.get(key, 0))

        # 현재 탭 info
        cur = next((s for s in self._SECTIONS if s[0] == key), self._SECTIONS[0])
        _, cur_title, cur_icon, cur_color = cur

        # 체크박스 바 갱신
        for k, chk in self._chk_widgets.items():
            chk.setVisible(k == key)

        # 탭 버튼 스타일
        for k, btn in self._tab_btns.items():
            _, _, _, color = next(s for s in self._SECTIONS if s[0] == k)
            is_on = (k == key)
            if is_on:
                h = color.lstrip("#")
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                bg = f"rgba({r},{g},{b},0.13)"
                btn.setStyleSheet(
                    f"QPushButton {{ background:{bg}; color:{color};"
                    f"  border-bottom:2px solid {color}; border-radius:0px;"
                    f"  font-size:12px; font-weight:bold; padding:0 14px; }}")
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background:transparent; color:{C.T2};"
                    f"  border-bottom:2px solid transparent; border-radius:0px;"
                    f"  font-size:12px; padding:0 14px; }}"
                    f"QPushButton:hover {{ color:{C.T0}; background:{C.BG_HOVER}; }}")
            btn.style().unpolish(btn); btn.style().polish(btn)

    def set_include(self, key: str, checked: bool):
        """외부에서 체크 상태를 설정 (신호 발생 없음)."""
        chk = self._include_chks.get(key)
        if chk:
            chk.blockSignals(True)
            chk.setChecked(checked)
            chk.blockSignals(False)

    def get_include(self, key: str) -> bool:
        chk = self._include_chks.get(key)
        return chk.isChecked() if chk else True

    def auto_fetch_all(self):
        for w in self._widgets.values():
            if hasattr(w, "auto_fetch"):
                w.auto_fetch()

    def get_cb_widget(self, key: str) -> "CbSectionWidget | None":
        return self._widgets.get(key)

    def get_filtered_md(self, key: str) -> "str | None":
        """ExtrasPanel → CbSectionWidget.get_filtered_md() 위임."""
        w = self._widgets.get(key)
        if w is None or not hasattr(w, "get_filtered_md"):
            return None
        return w.get_filtered_md()

    # ── 코드 정보 / 정적 검증 위임 메서드 ─────────────────────
    def get_code_info(self) -> str:
        """code_info 섹션의 코드 정보 텍스트 ('AI 분석에 포함' 미체크면 빈 문자열)."""
        w = self._widgets.get("code_info")
        if w is None or not hasattr(w, "get_code_info"):
            return ""
        chk = self._include_chks.get("code_info")
        if chk and not chk.isChecked():
            return ""
        return w.get_code_info()

    def get_spec_changes_list(self) -> list[dict]:
        """code_info 섹션에서 체크된 사양변경 dict 리스트 반환.
        ('AI 분석에 포함' 미체크면 빈 리스트)
        매핑 다이얼로그가 드롭다운 옵션 소스로 사용.
        """
        w = self._widgets.get("code_info")
        if w is None or not hasattr(w, "get_spec_changes_list"):
            return []
        chk = self._include_chks.get("code_info")
        if chk and not chk.isChecked():
            return []
        return w.get_spec_changes_list()

    def get_opts(self) -> dict:
        """static 섹션의 정적 검증 옵션 dict ('AI 분석에 포함' 미체크면 빈 dict)."""
        w = self._widgets.get("static")
        if w is None or not hasattr(w, "get_opts"):
            return {}
        chk = self._include_chks.get("static")
        if chk and not chk.isChecked():
            return {}
        return w.get_opts()

    # ── 요구사항 탭 위임 메서드 ───────────────────────────────
    def get_req_text(self) -> str:
        """AI 포함 체크박스가 체크된 경우만 요구사항 텍스트를 반환."""
        chk = self._include_chks.get("req")
        if chk and not chk.isChecked():
            return ""
        return self._req_tab.get_req_text() if self._req_tab else ""

    def get_req_old_path(self) -> str:
        return self._req_tab.get_old_req_path() if self._req_tab else ""

    def get_req_new_path(self) -> str:
        return self._req_tab.get_new_req_path() if self._req_tab else ""

    def set_req_diff_text(self, text: str):
        if self._req_tab:
            self._req_tab.set_req_diff_text(text)

    def set_req_diff_running(self, running: bool):
        if self._req_tab:
            self._req_tab.set_req_diff_running(running)

    def set_req_diff(self, old_lines: list, new_lines: list):
        if self._req_tab:
            self._req_tab.set_req_diff(old_lines, new_lines)


# ══════════════════════════════════════════════════════════════
#  DiffView — 좌우 코드 비교 뷰어
# ══════════════════════════════════════════════════════════════
class _SyncEdit(QTextEdit):
    scrolled = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.setObjectName("te_diff")
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.verticalScrollBar().valueChanged.connect(self.scrolled)
    def sync(self, v: int):
        self.verticalScrollBar().setValue(v)


class DiffView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = False
        self._row_pos: dict[int, int] = {}
        self._file_header_rows: dict[str, int] = {}  # fname → ri
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # 헤더
        hdr = QFrame()
        hdr.setObjectName("diff_hdr")
        hdr.setFixedHeight(34)
        hdr.setStyleSheet(
            f"#diff_hdr {{ background:{C.BG_CARD}; border-bottom:1px solid {C.BDR}; }}")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(0)
        for txt, col in [("  ◀  수정 전  (Before)", C.DEL_FG),
                          ("  ▶  수정 후  (After)",  C.ADD_FG)]:
            l = QLabel(txt)
            l.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
            l.setStyleSheet(f"color:{col}; background:transparent; padding:6px;")
            l.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            hl.addWidget(l)
        lay.addWidget(hdr)

        # ── 파일 단독 뷰 네비게이션 바 (폴더 모드에서만 표시) ──
        self._nav_bar = QFrame()
        self._nav_bar.setObjectName("diff_nav")
        self._nav_bar.setFixedHeight(32)
        self._nav_bar.setStyleSheet(
            "#diff_nav { background:#0D1E35; border-bottom:1px solid #1E3A5F; }")
        nav_lay = QHBoxLayout(self._nav_bar)
        nav_lay.setContentsMargins(10, 0, 10, 0); nav_lay.setSpacing(10)
        self._nav_back_btn = QPushButton("← 전체 보기")
        self._nav_back_btn.setObjectName("btn_sub")
        self._nav_back_btn.setFixedHeight(22)
        self._nav_back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        nav_lay.addWidget(self._nav_back_btn)
        self._nav_sep = QLabel("|")
        self._nav_sep.setStyleSheet("color:#1E3A5F; background:transparent;")
        nav_lay.addWidget(self._nav_sep)
        self._nav_file_lbl = QLabel("")
        self._nav_file_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        self._nav_file_lbl.setStyleSheet("color:#A0C8F0; background:transparent;")
        nav_lay.addWidget(self._nav_file_lbl)
        nav_lay.addStretch()
        self._nav_bar.hide()
        lay.addWidget(self._nav_bar)

        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.setHandleWidth(3)
        sp.setStyleSheet(
            f"QSplitter::handle {{ background:{C.BDR}; }}"
            f"QSplitter::handle:hover {{ background:{C.BDR2}; }}")
        self._left  = _SyncEdit()
        self._right = _SyncEdit()
        self._left.scrolled.connect(lambda v: self._sync(v, self._right))
        self._right.scrolled.connect(lambda v: self._sync(v, self._left))
        sp.addWidget(self._left); sp.addWidget(self._right)
        lay.addWidget(sp, stretch=1)

        # 빈 상태 플레이스홀더
        self._empty = QLabel("수정 전 / 후 파일을 선택하면\n변경점이 좌우로 표시됩니다.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(
            f"color:{C.T3}; background:{C.BG_CODE}; "
            f"font-size:14px; padding:60px;")
        lay.addWidget(self._empty)

    def _sync(self, v: int, target: _SyncEdit):
        if self._lock: return
        self._lock = True; target.sync(v); self._lock = False

    @staticmethod
    def _fmt(fg=None, bg=None) -> QTextCharFormat:
        f = QTextCharFormat()
        if fg: f.setForeground(QColor(fg))
        if bg: f.setBackground(QColor(bg))
        return f

    def render(self, old_lines: list[str], new_lines: list[str],
               old_cmp: list[str] = None, new_cmp: list[str] = None):
        """old_cmp / new_cmp : 주석 무시 시 diff 비교에만 사용할 줄 목록.
        지정하면 비교는 cmp 줄로, 화면 표시는 원본(old/new_lines)으로 렌더링한다."""
        self._empty.hide()
        self._left.clear(); self._right.clear()
        self._row_pos.clear(); self._file_header_rows.clear()

        # 비교에 사용할 줄 목록 (주석 무시 시 stripped, 아니면 원본)
        cmp_old = old_cmp if old_cmp is not None else old_lines
        cmp_new = new_cmp if new_cmp is not None else new_lines

        # 파일 구분선 패턴 감지 헬퍼
        _sep_re = re.compile(r'^// [═]+ (.+?) [═]+\s*$')
        def _sep_name(line: str):
            m = _sep_re.match(line or "")
            return m.group(1).strip() if m else None

        f = self._fmt
        f_eq    = f(fg=C.EQ_FG)
        f_add   = f(fg=C.ADD_FG, bg=C.ADD_BG)
        f_del   = f(fg=C.DEL_FG, bg=C.DEL_BG)
        f_mod_l = f(fg=C.MOD_FG, bg=C.MOD_BG)
        f_mod_r = f(fg=C.MOD_FG, bg=C.MOD_BG)
        f_emp   = f(bg=C.EMPTY)
        f_ln_eq = f(fg="#2A4A6A", bg=C.LN_EQ)
        f_ln_a  = f(fg=C.ADD_FG,  bg=C.ADD_LN)
        f_ln_d  = f(fg=C.DEL_FG,  bg=C.DEL_LN)
        f_ln_m  = f(fg=C.MOD_FG,  bg=C.MOD_BG)
        f_fhdr  = f(fg="#A0C8F0", bg="#0D1E35")   # 파일 헤더 행

        lc = QTextCursor(self._left.document())
        rc = QTextCursor(self._right.document())
        matcher = difflib.SequenceMatcher(None, cmp_old, cmp_new, autojunk=False)
        on = nn = ri = 0

        for op, a0, a1, b0, b1 in matcher.get_opcodes():
            if op == "equal":
                for i in range(a1 - a0):
                    on += 1; nn += 1
                    fname = _sep_name(old_lines[a0+i])
                    if fname:
                        hdr = f"  📄  {fname}\n"
                        lc.insertText(hdr, f_fhdr); rc.insertText(hdr, f_fhdr)
                        self._file_header_rows.setdefault(fname, ri)
                    else:
                        lc.insertText(f"{on:>5} │ ", f_ln_eq); lc.insertText(old_lines[a0+i]+"\n", f_eq)
                        rc.insertText(f"{nn:>5} │ ", f_ln_eq); rc.insertText(new_lines[b0+i]+"\n", f_eq)
                    self._row_pos[ri] = lc.blockNumber() - 1; ri += 1
            elif op == "replace":
                oc = old_lines[a0:a1]; nc = new_lines[b0:b1]
                for i in range(max(len(oc), len(nc))):
                    ol = oc[i] if i < len(oc) else None
                    nl = nc[i] if i < len(nc) else None
                    if ol is not None: on += 1
                    if nl is not None: nn += 1
                    fname = _sep_name(ol or "") or _sep_name(nl or "")
                    if fname:
                        hdr = f"  📄  {fname}\n"
                        lc.insertText(hdr, f_fhdr); rc.insertText(hdr, f_fhdr)
                        self._file_header_rows.setdefault(fname, ri)
                    else:
                        if ol is not None and nl is not None and ol.strip() == "":
                            # 왼쪽이 빈 줄 → 실질적 추가이므로 초록색으로 표시
                            lc.insertText("      │ ", f_ln_eq);    lc.insertText("\n", f_emp)
                            rc.insertText(f"{nn:>5} │ ", f_ln_a); rc.insertText(nl+"\n", f_add)
                        elif ol is not None and nl is not None:
                            lc.insertText(f"{on:>5} │ ", f_ln_m); lc.insertText(ol+"\n", f_mod_l)
                            rc.insertText(f"{nn:>5} │ ", f_ln_m); rc.insertText(nl+"\n", f_mod_r)
                        elif ol is not None:
                            lc.insertText(f"{on:>5} │ ", f_ln_d); lc.insertText(ol+"\n", f_del)
                            rc.insertText("      │ ", f_ln_eq);    rc.insertText("\n", f_emp)
                        else:
                            lc.insertText("      │ ", f_ln_eq);    lc.insertText("\n", f_emp)
                            rc.insertText(f"{nn:>5} │ ", f_ln_a); rc.insertText(nl+"\n", f_add)
                    self._row_pos[ri] = lc.blockNumber() - 1; ri += 1
            elif op == "delete":
                for i in range(a1 - a0):
                    on += 1
                    fname = _sep_name(old_lines[a0+i])
                    if fname:
                        hdr = f"  📄  {fname}  ✕ 삭제됨\n"
                        lc.insertText(hdr, f_fhdr); rc.insertText(hdr, f_fhdr)
                        self._file_header_rows.setdefault(fname, ri)
                    else:
                        lc.insertText(f"{on:>5} │ ", f_ln_d); lc.insertText(old_lines[a0+i]+"\n", f_del)
                        rc.insertText("      │ ", f_ln_eq);  rc.insertText("\n", f_emp)
                    self._row_pos[ri] = lc.blockNumber() - 1; ri += 1
            elif op == "insert":
                for i in range(b1 - b0):
                    nn += 1
                    fname = _sep_name(new_lines[b0+i])
                    if fname:
                        hdr = f"  📄  {fname}  ✚ 신규\n"
                        lc.insertText(hdr, f_fhdr); rc.insertText(hdr, f_fhdr)
                        self._file_header_rows.setdefault(fname, ri)
                    else:
                        lc.insertText("      │ ", f_ln_eq); lc.insertText("\n", f_emp)
                        rc.insertText(f"{nn:>5} │ ", f_ln_a); rc.insertText(new_lines[b0+i]+"\n", f_add)
                    self._row_pos[ri] = lc.blockNumber() - 1; ri += 1

    # ── 파일 네비게이션 바 제어 ───────────────────────────────
    def show_file_nav(self, fname: str, back_fn):
        """단독 파일 뷰 모드: 상단 네비 바를 표시한다."""
        self._nav_file_lbl.setText(f"📄  {fname}")
        try:
            self._nav_back_btn.clicked.disconnect()
        except Exception:
            pass
        self._nav_back_btn.clicked.connect(back_fn)
        self._nav_bar.show()

    def hide_file_nav(self):
        """전체 보기 모드: 네비 바를 숨긴다."""
        self._nav_bar.hide()

    def scroll_to_row(self, row_idx: int):
        block_no = self._row_pos.get(row_idx, 0)
        for ed in (self._left, self._right):
            block = ed.document().findBlockByNumber(block_no)
            if not block.isValid(): continue
            cur = QTextCursor(block)
            ed.setTextCursor(cur)
            # 블록의 절대 y좌표를 스크롤바에 직접 세팅해
            # 해당 줄이 뷰포트 상단에 오도록 배치
            block_rect = ed.document().documentLayout().blockBoundingRect(block)
            vbar = ed.verticalScrollBar()
            # 상단에서 살짝(한 줄 정도) 여백을 둬 가독성 확보
            margin = int(block_rect.height())
            target = max(0, int(block_rect.top()) - margin)
            vbar.setValue(min(target, vbar.maximum()))
        QTimer.singleShot(1800, self._clear_hl)

    def _clear_hl(self):
        for ed in (self._left, self._right):
            c = ed.textCursor(); c.clearSelection(); ed.setTextCursor(c)

    def clear_view(self):
        self._left.clear(); self._right.clear()
        self._row_pos.clear(); self._file_header_rows.clear(); self._empty.show()


# ── MD→HTML 헬퍼는 ui_md.py 로 분리됨 (위에서 import) ──



# ══════════════════════════════════════════════════════════════
#  ReqDiffView — 요구사항 좌우 비교 뷰어 (워드 스타일)
# ══════════════════════════════════════════════════════════════
class ReqDiffView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock_scroll = False
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # 헤더
        hdr = QFrame()
        hdr.setObjectName("req_diff_hdr")
        hdr.setFixedHeight(34)
        hdr.setStyleSheet(
            f"#req_diff_hdr {{ background:{C.BG_CARD}; border-bottom:1px solid {C.BDR}; }}")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(0)
        for txt, col in [("  ◀  수정 전 요구사항  (Before)", C.DEL_FG),
                          ("  ▶  수정 후 요구사항  (After)",  C.ADD_FG)]:
            lb = QLabel(txt)
            lb.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
            lb.setStyleSheet(f"color:{col}; background:transparent; padding:6px;")
            lb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            hl.addWidget(lb)
        lay.addWidget(hdr)

        # 좌우 QTextEdit (비교 뷰)
        self._sp = QSplitter(Qt.Orientation.Horizontal)
        self._sp.setHandleWidth(3)
        self._sp.setStyleSheet(
            f"QSplitter::handle {{ background:{C.BDR}; }}"
            f"QSplitter::handle:hover {{ background:{C.BDR2}; }}")

        self._left_te  = QTextEdit()
        self._right_te = QTextEdit()
        for te in (self._left_te, self._right_te):
            te.setReadOnly(True)
            te.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            te.setStyleSheet(f"QTextEdit {{ background:{C.BG_CODE}; border:none; }}")

        self._left_te.verticalScrollBar().valueChanged.connect(
            lambda v: self._sync(v, self._right_te))
        self._right_te.verticalScrollBar().valueChanged.connect(
            lambda v: self._sync(v, self._left_te))

        self._sp.addWidget(self._left_te)
        self._sp.addWidget(self._right_te)
        lay.addWidget(self._sp, stretch=1)   # 항상 표시

        # 빈 상태 플레이스홀더 — 스플리터 아래 고정 (DiffView 와 동일 레이아웃)
        self._empty = QLabel("수정 전 / 후 파일을 선택하면\n변경점이 좌우로 표시됩니다.")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(
            f"color:{C.T3}; background:{C.BG_CODE}; font-size:14px; padding:60px;")
        lay.addWidget(self._empty)   # stretch 없음 → 아래쪽 고정

    def _sync(self, v: int, target: QTextEdit):
        if self._lock_scroll: return
        self._lock_scroll = True
        target.verticalScrollBar().setValue(v)
        self._lock_scroll = False

    def render(self, old_lines: list, new_lines: list, context: int = 3):
        import difflib

        def esc(s: str) -> str:
            return (s.replace("&", "&amp;")
                      .replace("<", "&lt;")
                      .replace(">", "&gt;"))

        EQ_BG  = "#FFFFFF"; EQ_FG  = "#1E293B"
        DEL_BG = "#FEE2E2"; DEL_FG = "#B91C1C"
        ADD_BG = "#DCFCE7"; ADD_FG = "#15803D"
        EMP_BG = "#F8FAFC"
        SEP_BG = "#F1F5F9"; SEP_FG = "#94A3B8"
        DIV_EQ  = "#E2E8F0"   # equal 행 구분선
        DIV_DEL = "#FECACA"   # 삭제 행 구분선
        DIV_ADD = "#BBF7D0"   # 추가 행 구분선
        DIV_EMP = "#E9EEF4"   # 빈 행 구분선
        DIV_SEP = "#CBD5E1"   # 생략 행 구분선

        FONT = ("font-family:'맑은 고딕','Malgun Gothic',sans-serif;"
                "font-size:10.5pt; line-height:1.4;")

        def row(bg, fg, text, div=DIV_EQ):
            content = esc(text) if text.strip() else "&nbsp;"
            return (f'<p style="background:{bg}; color:{fg}; margin:0; '
                    f'padding:10px 14px 3px 14px; '
                    f'border-bottom:1px solid {div}; {FONT}">{content}</p>')

        def sep_row(skipped: int):
            txt = f"···  {skipped}줄 생략  ···"
            return (f'<p style="background:{SEP_BG}; color:{SEP_FG}; margin:0; '
                    f'padding:5px 14px; text-align:center; '
                    f'border-bottom:1px solid {DIV_SEP}; {FONT}'
                    f'font-style:italic;">{txt}</p>')

        opcodes = difflib.SequenceMatcher(
            None, old_lines, new_lines, autojunk=False).get_opcodes()

        # equal 블록에서 context 범위 밖의 줄 수를 계산해 표시할 범위를 결정
        left_rows, right_rows = [], []
        prev_end_a = prev_end_b = 0   # 마지막으로 출력한 old/new 위치

        for idx, (op, a0, a1, b0, b1) in enumerate(opcodes):
            if op == "equal":
                total = a1 - a0
                if total <= context * 2:
                    # 짧은 equal: 전부 표시
                    for ln in old_lines[a0:a1]:
                        left_rows.append(row(EQ_BG, EQ_FG, ln))
                    for ln in new_lines[b0:b1]:
                        right_rows.append(row(EQ_BG, EQ_FG, ln))
                else:
                    # 앞 context 줄
                    for ln in old_lines[a0:a0 + context]:
                        left_rows.append(row(EQ_BG, EQ_FG, ln))
                    for ln in new_lines[b0:b0 + context]:
                        right_rows.append(row(EQ_BG, EQ_FG, ln))
                    # 생략 구분선
                    skipped = total - context * 2
                    left_rows.append(sep_row(skipped))
                    right_rows.append(sep_row(skipped))
                    # 뒤 context 줄
                    for ln in old_lines[a1 - context:a1]:
                        left_rows.append(row(EQ_BG, EQ_FG, ln))
                    for ln in new_lines[b1 - context:b1]:
                        right_rows.append(row(EQ_BG, EQ_FG, ln))
            elif op == "replace":
                old_c = old_lines[a0:a1]; new_c = new_lines[b0:b1]
                for i in range(max(len(old_c), len(new_c))):
                    left_rows.append(row(DEL_BG, DEL_FG, old_c[i] if i < len(old_c) else "", DIV_DEL))
                    right_rows.append(row(ADD_BG, ADD_FG, new_c[i] if i < len(new_c) else "", DIV_ADD))
            elif op == "delete":
                for ln in old_lines[a0:a1]:
                    left_rows.append(row(DEL_BG, DEL_FG, ln, DIV_DEL))
                    right_rows.append(row(EMP_BG, EQ_FG, "", DIV_EMP))
            elif op == "insert":
                for ln in new_lines[b0:b1]:
                    left_rows.append(row(EMP_BG, EQ_FG, "", DIV_EMP))
                    right_rows.append(row(ADD_BG, ADD_FG, ln, DIV_ADD))

        wrap = lambda rows: (
            f'<html><body style="margin:0;padding:0;background:#FFFFFF;">'
            f'{"".join(rows)}</body></html>')

        self._left_te.setHtml(wrap(left_rows))
        self._right_te.setHtml(wrap(right_rows))

        self._empty.hide()
        # _sp 는 이미 항상 표시 중 — show() 불필요
        self._left_te.verticalScrollBar().setValue(0)
        self._right_te.verticalScrollBar().setValue(0)


# ══════════════════════════════════════════════════════════════
#  ResultView — AI 결과 텍스트 뷰
# ══════════════════════════════════════════════════════════════
class ResultView(QWidget):
    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # 툴바
        bar = QFrame()
        bar.setObjectName("result_bar")
        bar.setFixedHeight(34)
        bar.setStyleSheet(
            f"#result_bar {{ background:{C.BG_CARD}; border-bottom:1px solid {C.BDR}; }}")
        bl = QHBoxLayout(bar); bl.setContentsMargins(14, 0, 10, 0)

        dots = QLabel("● ● ●")
        dots.setStyleSheet(f"color:{C.BDR2}; background:transparent; font-size:10px;")
        bl.addWidget(dots); bl.addStretch()
        lay.addWidget(bar)

        self._raw_text = ""
        self._te = QTextEdit()
        self._te.setObjectName("te_result")
        self._te.setReadOnly(True)
        self._te.setStyleSheet(
            "QTextEdit#te_result { background:#FFFFFF; border:none; padding:4px; }")
        self._te.setPlaceholderText(placeholder)
        lay.addWidget(self._te, stretch=1)

    def set_text(self, t: str):
        self._raw_text = t
        self._te.setHtml(_md_to_html(t))
        self._te.verticalScrollBar().setValue(0)

    def scroll_to(self, text: str):
        """헤딩 블록을 정확히 찾아 스크롤한다.
        document().find()는 테이블 셀 내 동일 단어를 먼저 잡는 버그가 있어
        블록 순회로 headingLevel > 0 인 블록만 비교한다."""
        # 마크다운 기호 제거 후 검색 문자열 생성
        search = re.sub(r'^#+\s*', '', text).strip()
        search = re.sub(r'`([^`]+)`', r'\1', search)
        search = re.sub(r'\*\*(.+?)\*\*', r'\1', search)
        search = re.sub(r'\*(.+?)\*', r'\1', search)
        search = re.sub(r'\s+', ' ', search).strip()

        doc = self._te.document()
        block = doc.begin()
        while block.isValid():
            if block.blockFormat().headingLevel() > 0:
                block_text = re.sub(r'\s+', ' ', block.text()).strip()
                if block_text == search:
                    cursor = QTextCursor(block)
                    self._te.setTextCursor(cursor)
                    self._te.ensureCursorVisible()
                    return
            block = block.next()

        # 폴백: 첫 번째 일치 (헤딩이 없는 경우)
        cursor = doc.find(search)
        if not cursor.isNull():
            self._te.setTextCursor(cursor)
            self._te.ensureCursorVisible()

    def clear(self):
        self._te.clear(); self._raw_text = ""

    def text(self) -> str:
        return self._raw_text


# ══════════════════════════════════════════════════════════════
class ResultPanel(QWidget):
    export_full_xlsx_clicked = pyqtSignal()
    export_full_html_clicked = pyqtSignal()
    cb_upload_clicked        = pyqtSignal()           # ★ Codebeamer 업로드 요청
    req_diff_requested       = pyqtSignal()           # 요구사항 DIFF 추출 요청 (ExtrasPanel 전달)
    # [대화형AI DISABLED] 아래 2줄 주석 해제하면 복구
    # qa_submitted             = pyqtSignal(str)   # 취약점 탭 채팅 제출
    # summary_qa_submitted     = pyqtSignal(str)   # 요약 탭 채팅 제출
    include_changed          = pyqtSignal(str, bool)  # (key, checked) — InputPanel 동기화

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_name: str = ""   # ★ 저장 파일명에 사용
        self._tree_entries: dict[int, tuple] = {}
        self._vuln_entries: dict[int, str]   = {}
        self._sum_entries:  dict[int, str]   = {}
        self._file_ranges_old: list = []   # [(rel_path, start_line_0based), ...]
        self._file_ranges_new: list = []
        self._per_file_old: dict  = {}    # fname → old_lines (파일 단독 뷰용)
        self._per_file_new: dict  = {}    # fname → new_lines
        self._full_old_lines: list = []   # 전체 combined 원본 보관
        self._full_new_lines: list = []
        self._full_func_list: list = []
        self._full_old_cmp:   list = None   # 주석 무시 비교용
        self._full_new_cmp:   list = None
        self._folder_pairs: list  = []    # 폴더 모드: [(rel_path, old_lines, new_lines), ...]
        self._folder_mode: bool   = False
        self._folder_loaded_files: set = set()  # 아코디언: 이미 함수가 로드된 파일 집합
        self._current_diff_file: str   = ""     # 현재 diff 뷰에 표시된 파일 경로
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # ── 탭 바 ─────────────────────────────────────────────
        tab_bar = QFrame()
        tab_bar.setObjectName("tab_bar")
        tab_bar.setFixedHeight(48)
        tab_bar.setStyleSheet(
            f"#tab_bar {{ background:{C.BG_PANEL}; border-bottom:1px solid {C.BDR}; }}")
        self._tab_bar_widget = tab_bar
        tl = QHBoxLayout(tab_bar); tl.setContentsMargins(10, 0, 10, 0); tl.setSpacing(0)

        self._tab_btns: dict[str, QPushButton] = {}
        # ── 입력 탭 2개 ────────────────────────────────────────
        for key, label in [("files",  "📂  분석파일"),
                            ("extras", "📋  추가분석자료")]:
            btn = QPushButton(label)
            btn.setObjectName("tab_on" if key == "files" else "tab_off")
            btn.setFixedHeight(48)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._switch(k))
            self._tab_btns[key] = btn
            tl.addWidget(btn)

        # ── 구분선 ─────────────────────────────────────────────
        _sep = QFrame()
        _sep.setFixedSize(1, 26)
        _sep.setStyleSheet(f"background:{C.BDR2};")
        tl.addSpacing(6); tl.addWidget(_sep); tl.addSpacing(6)

        # ── 출력 탭 3개 ────────────────────────────────────────
        for key, label in [("diff",    "🔀  변경점VIEW"),
                            ("summary", "📝  변경점요약"),
                            ("vuln",    "🔍  취약점분석")]:
            btn = QPushButton(label)
            btn.setObjectName("tab_off")
            btn.setFixedHeight(48)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._switch(k))
            self._tab_btns[key] = btn
            tl.addWidget(btn)

        tl.addStretch()
        lbl_save = QLabel("변경점 요약/취약점 분석 결과물 저장")
        lbl_save.setStyleSheet(f"color:{C.T3}; font-size:10px; background:transparent;")
        tl.addWidget(lbl_save)
        tl.addSpacing(8)
        self._save_btn = QPushButton("💾  결과물 저장")
        self._save_btn.setObjectName("btn_sub")
        self._save_btn.setFixedHeight(28)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._show_save_popup)
        tl.addWidget(self._save_btn)
        tl.addSpacing(4)

        # ★ Codebeamer 업로드 버튼
        self._cb_upload_btn = QPushButton("📤  CB 업로드")
        self._cb_upload_btn.setObjectName("btn_sub")
        self._cb_upload_btn.setFixedHeight(28)
        self._cb_upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cb_upload_btn.setToolTip(
            "AI 분석 결과(변경점 요약 + 취약점 분석)를 "
            "Codebeamer 트래커에 새 이슈로 등록하거나 기존 이슈에 코멘트로 추가합니다.")
        self._cb_upload_btn.clicked.connect(self.cb_upload_clicked.emit)
        tl.addWidget(self._cb_upload_btn)
        tl.addSpacing(6)
        lay.addWidget(tab_bar)

        # ── 스텝바 제거됨 (step_bar 참조는 no-op 더미로 유지) ──
        self.step_bar = StepBar()
        self.step_bar.hide()

        # ── 본문 (사이드바 + 스택) ────────────────────────────
        body = QSplitter(Qt.Orientation.Horizontal)
        body.setHandleWidth(1)
        body.setStyleSheet(
            f"QSplitter::handle {{ background:{C.BDR}; }}"
            f"QSplitter::handle:hover {{ background:{C.BLUE}; }}")

        self._sidebar   = self._build_sidebar()
        self._sum_side  = self._build_summary_sidebar()
        self._vuln_side = self._build_vuln_sidebar()
        body.addWidget(self._sidebar)
        body.addWidget(self._sum_side)
        body.addWidget(self._vuln_side)

        self._stack = QStackedWidget()
        self._diff_view     = DiffView()
        # _req_diff_view → ExtrasPanel(_ReqTabContent)으로 이동됨
        self._extras_panel  = ExtrasPanel()          # ← 추가분석자료 (index 1)
        self._sum_view  = ResultView(
            "리뷰 실행 후 AI가 변경점을 요약합니다.\n\n"
            "• 변경 통계  • 주요 변경 내용  • 위험 평가 (🔴/🟡/🟢)")
        self._vuln_view = ResultView(
            "리뷰 실행 후 AI가 취약점을 분석합니다.\n\n"
            "• MISRA-C 규칙 위반  • 로직 구현 오류\n"
            "• 메모리/공유자원 문제  • Fail-safe / 예외처리 누락 등")

        # ExtrasPanel 체크박스 변경 → ResultPanel 신호로 전달
        self._extras_panel.include_changed.connect(self.include_changed.emit)
        # ExtrasPanel 요구사항 DIFF 요청 → ResultPanel 신호로 전달
        self._extras_panel.req_diff_requested.connect(self.req_diff_requested)

        # ── 변경점VIEW 컨테이너 — 코드 변경 VIEW만 표시 ──────────
        diff_container = QWidget()
        diff_container.setObjectName("diff_container")
        dcl = QVBoxLayout(diff_container)
        dcl.setContentsMargins(0, 0, 0, 0); dcl.setSpacing(0)
        dcl.addWidget(self._diff_view, stretch=1)
        # 서브탭(요구사항 변경점 VIEW) 제거 — ExtrasPanel > 요구사항 탭으로 이동

        # 변경점 요약 탭 컨테이너: ResultView
        sum_container = QWidget()
        sum_container.setObjectName("sum_container")
        scl = QVBoxLayout(sum_container)
        scl.setContentsMargins(0, 0, 0, 0); scl.setSpacing(0)
        scl.addWidget(self._sum_view, stretch=1)
        # [대화형AI DISABLED] 아래 2줄 주석 해제하면 채팅 바 복구
        # self._sum_chat_bar = self._build_chat_ui(is_summary=True)
        # scl.addWidget(self._sum_chat_bar)

        # 취약점 탭 컨테이너: ResultView
        vuln_container = QWidget()
        vuln_container.setObjectName("vuln_container")
        vcl = QVBoxLayout(vuln_container)
        vcl.setContentsMargins(0, 0, 0, 0); vcl.setSpacing(0)
        vcl.addWidget(self._vuln_view, stretch=1)
        # [대화형AI DISABLED] 아래 2줄 주석 해제하면 채팅 바 복구
        # self._chat_bar = self._build_chat_ui(is_summary=False)
        # vcl.addWidget(self._chat_bar)

        self._analysis_panel = AnalysisFilePanel()   # index 0 — files
        self._stack.addWidget(self._analysis_panel)
        self._stack.addWidget(self._extras_panel)    # index 1 — extras
        self._stack.addWidget(diff_container)        # index 2 — diff
        self._stack.addWidget(sum_container)         # index 3 — summary
        self._stack.addWidget(vuln_container)        # index 4 — vuln
        body.addWidget(self._stack)

        body.setSizes([300, 0, 0, 9999]); body.setStretchFactor(3, 1)
        self._body = body
        lay.addWidget(body, stretch=1)

        self._switch("files")

    def _build_sidebar(self) -> QFrame:
        side = QFrame(); side.setMinimumWidth(300)
        side.setObjectName("sidebar_frame")
        side.setStyleSheet(
            f"#sidebar_frame {{ background:{C.BG_APP}; border-right:1px solid {C.BDR}; }}")
        sl = QVBoxLayout(side); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(0)

        hdr = QLabel("  📃 변경 함수 목록"); hdr.setFixedHeight(34)
        hdr.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
        hdr.setStyleSheet(
            f"color:{C.BLUE}; background:{C.BG_CARD}; "
            f"border-bottom:1px solid {C.BDR}; padding-left:6px;")
        sl.addWidget(hdr)

        # ── 전체 선택/해제 체크박스 바 ───────────────────────
        chk_all_bar = QFrame()
        chk_all_bar.setObjectName("chk_all_bar")
        chk_all_bar.setFixedHeight(30)
        chk_all_bar.setStyleSheet(
            f"#chk_all_bar {{ background:{C.BG_PANEL};"
            f"  border-bottom:1px solid {C.BDR}; }}")
        cab_lay = QHBoxLayout(chk_all_bar)
        cab_lay.setContentsMargins(12, 0, 12, 0); cab_lay.setSpacing(0)
        self._chk_all_files = QCheckBox("전체 선택 / 해제")
        self._chk_all_files.setFont(QFont(C.FUI, 9))
        self._chk_all_files.setTristate(False)
        self._chk_all_files.setStyleSheet(
            f"QCheckBox {{ color:{C.T2}; background:transparent; spacing:6px; }}"
            f"QCheckBox::indicator {{ width:13px; height:13px; border-radius:3px;"
            f"  border:1px solid {C.BDR2}; background:#FFFFFF; }}"
            f"QCheckBox::indicator:checked   {{ background:{C.BLUE}; border-color:{C.BLUE}; }}"
            f"QCheckBox::indicator:unchecked {{ background:#FFFFFF; }}")
        self._chk_all_files.stateChanged.connect(self._on_chk_all_files)
        cab_lay.addWidget(self._chk_all_files)
        sl.addWidget(chk_all_bar)

        self._func_tree = QTreeWidget()
        self._func_tree.setHeaderHidden(True); self._func_tree.setIndentation(12)
        self._func_tree.setAnimated(True)
        self._func_tree.setFont(QFont(C.FUI, 10))
        _chk_icon = _get_check_icon_path()
        _chk_img  = f"image:url({_chk_icon});" if _chk_icon else ""
        self._func_tree.setStyleSheet(f"""
            QTreeWidget {{
                background:{C.BG_APP}; border:none; outline:none;
                color:{C.T1};
            }}
            QTreeWidget::item {{
                padding:6px 10px; border-radius:4px;
            }}
            QTreeWidget::item:selected {{
                background:{C.BLUE_DK}; color:#FFFFFF;
            }}
            QTreeWidget::item:hover:!selected {{
                background:{C.BG_HOVER}; color:{C.T0};
            }}
            QTreeWidget::branch {{ background:transparent; }}
            QTreeWidget::indicator {{
                width:16px; height:16px;
                border:none; background:transparent;
            }}
            QTreeWidget::indicator:checked {{
                background:{C.BLUE};
                border:2px solid {C.BLUE};
                border-radius:3px;
                {_chk_img}
            }}
            QTreeWidget::indicator:unchecked {{
                background:#FFFFFF;
                border:2px solid {C.T1};
                border-radius:3px;
                image:none;
            }}
        """)
        self._func_tree.itemClicked.connect(self._on_func_click)
        self._func_tree.itemChanged.connect(self._on_file_item_changed)
        sl.addWidget(self._func_tree, stretch=1)

        foot = QLabel("클릭 시 해당 위치로 이동"); foot.setFixedHeight(24)
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.setFont(QFont(C.FUI, 8))
        foot.setStyleSheet(
            f"color:{C.T3}; background:{C.BG_CARD}; border-top:1px solid {C.BDR};")
        sl.addWidget(foot)

        btn_area = QFrame()
        btn_area.setObjectName("btn_area")
        btn_area.setStyleSheet(
            f"#btn_area {{ background:{C.BG_CARD}; border-top:1px solid {C.BDR}; }}")
        ba = QVBoxLayout(btn_area)
        ba.setContentsMargins(10, 8, 10, 10); ba.setSpacing(5)

        grp2_lbl = QLabel("  변경점 비교 파일 추출")
        grp2_lbl.setFont(QFont(C.FUI, 8, QFont.Weight.Bold))
        grp2_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")
        ba.addWidget(grp2_lbl)

        self._export_full_xlsx_btn = QPushButton("📊 엑셀로 저장")
        self._export_full_xlsx_btn.setObjectName("btn_sub"); self._export_full_xlsx_btn.setFixedHeight(26)
        self._export_full_xlsx_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_full_xlsx_btn.clicked.connect(self.export_full_xlsx_clicked.emit)
        ba.addWidget(self._export_full_xlsx_btn)

        self._export_full_html_btn = QPushButton("🌐 HTML로 저장")
        self._export_full_html_btn.setObjectName("btn_sub"); self._export_full_html_btn.setFixedHeight(26)
        self._export_full_html_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_full_html_btn.clicked.connect(self.export_full_html_clicked.emit)
        ba.addWidget(self._export_full_html_btn)

        sl.addWidget(btn_area)
        return side

    def _build_summary_sidebar(self) -> QFrame:
        side = QFrame(); side.setMinimumWidth(300)
        side.setObjectName("sum_sidebar_frame")
        side.setStyleSheet(
            f"#sum_sidebar_frame {{ background:{C.BG_APP}; border-right:1px solid {C.BDR}; }}")
        sl = QVBoxLayout(side); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(0)

        hdr = QLabel("  📝 변경점 목록"); hdr.setFixedHeight(34)
        hdr.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
        hdr.setStyleSheet(
            f"color:{C.AMBER}; background:{C.BG_CARD}; "
            f"border-bottom:1px solid {C.BDR}; padding-left:6px;")
        sl.addWidget(hdr)

        self._sum_tree = QTreeWidget()
        self._sum_tree.setHeaderHidden(True); self._sum_tree.setIndentation(12)
        self._sum_tree.setAnimated(True)
        self._sum_tree.setFont(QFont(C.FUI, 10))
        self._sum_tree.setStyleSheet(f"""
            QTreeWidget {{
                background:{C.BG_APP}; border:none; outline:none;
                color:{C.T1};
            }}
            QTreeWidget::item {{
                padding:6px 10px; border-radius:4px;
            }}
            QTreeWidget::item:selected {{
                background:{C.BLUE_DK}; color:#FFFFFF;
            }}
            QTreeWidget::item:hover:!selected {{
                background:{C.BG_HOVER}; color:{C.T0};
            }}
            QTreeWidget::branch {{ background:transparent; }}
        """)
        self._sum_tree.itemClicked.connect(self._on_sum_click)
        sl.addWidget(self._sum_tree, stretch=1)

        foot = QLabel("클릭 시 해당 위치로 이동"); foot.setFixedHeight(24)
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.setFont(QFont(C.FUI, 8))
        foot.setStyleSheet(
            f"color:{C.T3}; background:{C.BG_CARD}; border-top:1px solid {C.BDR};")
        sl.addWidget(foot)

        return side

    def _build_vuln_sidebar(self) -> QFrame:
        side = QFrame(); side.setMinimumWidth(300)
        side.setObjectName("vuln_sidebar_frame")
        side.setStyleSheet(
            f"#vuln_sidebar_frame {{ background:{C.BG_APP}; border-right:1px solid {C.BDR}; }}")
        sl = QVBoxLayout(side); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(0)

        hdr = QLabel("  🔍 취약점 목록"); hdr.setFixedHeight(34)
        hdr.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
        hdr.setStyleSheet(
            f"color:{C.RED}; background:{C.BG_CARD}; "
            f"border-bottom:1px solid {C.BDR}; padding-left:6px;")
        sl.addWidget(hdr)

        self._vuln_tree = QTreeWidget()
        self._vuln_tree.setHeaderHidden(True); self._vuln_tree.setIndentation(12)
        self._vuln_tree.setAnimated(True)
        self._vuln_tree.setFont(QFont(C.FUI, 10))
        self._vuln_tree.setStyleSheet(f"""
            QTreeWidget {{
                background:{C.BG_APP}; border:none; outline:none;
                color:{C.T1};
            }}
            QTreeWidget::item {{
                padding:6px 10px; border-radius:4px;
            }}
            QTreeWidget::item:selected {{
                background:{C.BLUE_DK}; color:#FFFFFF;
            }}
            QTreeWidget::item:hover:!selected {{
                background:{C.BG_HOVER}; color:{C.T0};
            }}
            QTreeWidget::branch {{ background:transparent; }}
        """)
        self._vuln_tree.itemClicked.connect(self._on_vuln_click)
        sl.addWidget(self._vuln_tree, stretch=1)

        foot = QLabel("클릭 시 해당 위치로 이동"); foot.setFixedHeight(24)
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.setFont(QFont(C.FUI, 8))
        foot.setStyleSheet(
            f"color:{C.T3}; background:{C.BG_CARD}; border-top:1px solid {C.BDR};")
        sl.addWidget(foot)

        return side

    # ── 탭 전환 ───────────────────────────────────────────────
    # _switch_diff_sub 제거됨 — 서브탭 없음

    # ── 외부 임베드용 hook ────────────────────────────────────
    def set_tab_bar_visible(self, visible: bool):
        """외부에서 ResultPanel을 다른 컨테이너에 임베드할 때 내부 5탭 탭바를 숨긴다."""
        if hasattr(self, "_tab_bar_widget") and self._tab_bar_widget is not None:
            self._tab_bar_widget.setVisible(visible)

    def switch_page(self, key: str):
        """외부에서 ResultPanel의 페이지를 전환할 때 호출.

        key ∈ {"files", "extras", "diff", "summary", "vuln"}.
        """
        self._switch(key)

    def set_req_diff(self, old_lines: list, new_lines: list):
        """요구사항 DIFF 완료 후 ExtrasPanel > 요구사항 탭에 결과를 렌더링한다."""
        self._extras_panel.set_req_diff(old_lines, new_lines)

    def _switch(self, key: str):
        idx = {"files": 0, "extras": 1, "diff": 2, "summary": 3, "vuln": 4}.get(key, 0)
        self._stack.setCurrentIndex(idx)
        self._sidebar.setVisible(key == "diff")
        self._sum_side.setVisible(key == "summary")
        self._vuln_side.setVisible(key == "vuln")
        if key == "diff":
            self._body.setSizes([300, 0, 0, 9999])
        elif key == "summary":
            self._body.setSizes([0, 300, 0, 9999])
        elif key == "vuln":
            self._body.setSizes([0, 0, 300, 9999])
        else:  # "files", "extras" — 사이드바 없음
            self._body.setSizes([0, 0, 0, 9999])
        # StepBar 스포트라이트
        step_map = {"files": 0, "extras": 0, "diff": 1, "summary": 2, "vuln": 3}
        self._spotlight_step(step_map.get(key, 0))

        for k, btn in self._tab_btns.items():
            is_on = (k == key)
            btn.setObjectName("tab_on" if is_on else "tab_off")
            if is_on:
                color = TAB_COLORS.get(k, C.BLUE)
                btn.setStyleSheet(
                    f"color:{color}; font-weight:bold; "
                    f"border-bottom:2px solid {color};")
            else:
                btn.setStyleSheet(f"color:{C.T3}; font-weight:normal; border-bottom:none;")
            btn.style().unpolish(btn); btn.style().polish(btn)

    def _spotlight_step(self, step: int):
        self.step_bar.spotlight(step)

    @property
    def analysis_panel(self) -> "AnalysisFilePanel":
        """분석파일 선택 탭의 패널 참조 반환."""
        return self._analysis_panel

    @property
    def extras_panel(self) -> "ExtrasPanel":
        """추가분석자료 탭의 패널 참조 반환."""
        return self._extras_panel

    # ── 함수 트리 렌더링 ──────────────────────────────────────
    def _render_func_tree(self, func_list: list, single_filename: str = ""):
        self._func_tree.clear(); self._tree_entries.clear()
        TAG_ICON  = {"delete": "－", "insert": "＋", "replace": "～"}
        TAG_COLOR = {"delete": C.RED, "insert": C.GREEN, "replace": C.AMBER}

        def group(changes):
            if not changes: return []
            out = []
            ri, tag, ln = changes[0]; s = e = ln or 0
            for nri, ntag, nln in changes[1:]:
                nl = nln or 0
                if ntag == tag and nl <= e + 2: e = nl
                else: out.append((ri, tag, s, e)); ri, tag, s, e = nri, ntag, nl, nl
            out.append((ri, tag, s, e)); return out

        def _add_func_items(parent_widget, fn, first_ri, decl, changes, flag):
            """함수 항목과 줄 번호 자식 항목을 parent_widget 에 추가한다."""
            ic, col = ("＋", C.GREEN) if flag == "new"    else \
                      ("－", C.RED)   if flag == "deleted" else \
                      ("～", C.AMBER) if flag == "global"  else \
                      ("～", C.AMBER)
            disp = decl[:50] + "…" if len(decl) > 50 else decl
            pi = QTreeWidgetItem([f"{ic}  {disp}"])
            pi.setForeground(0, QColor(col))
            # 전역 영역은 한글이라 Bold 로도 얇게 보여서 Black 가중치로 보강
            _weight = QFont.Weight.Black if flag == "global" else QFont.Weight.Bold
            pi.setFont(0, QFont(C.FUI, 10, _weight))
            pi.setToolTip(0, decl)
            if parent_widget is self._func_tree:
                self._func_tree.addTopLevelItem(pi)
            else:
                parent_widget.addChild(pi)
            self._tree_entries[id(pi)] = ("parent", first_ri)

            for ch_ri, ch_tag, s, e in group(changes):
                lno = f"줄 {s}" if s == e else f"줄 {s} ~ {e}"
                ci = QTreeWidgetItem([f"  {TAG_ICON.get(ch_tag, '～')}  {lno}"])
                ci.setForeground(0, QColor(TAG_COLOR.get(ch_tag, C.AMBER)))
                ci.setFont(0, QFont(C.FUI, 9))
                pi.addChild(ci)
                self._tree_entries[id(ci)] = ("child", ch_ri)
            pi.setExpanded(False)

        # ── 폴더 모드: 파일 헤더 노드 아래 함수 그룹화 ──────
        is_folder_mode = bool(self._file_ranges_new or self._file_ranges_old)
        if is_folder_mode:
            # 각 함수를 소속 파일로 매핑
            file_groups: dict = {}
            order: list = []
            for entry in func_list:
                fn, first_ri, decl, changes, flag = entry
                line_no = changes[0][2] if changes else 1
                if flag == "deleted":
                    fname = self._find_file_for_line(line_no, self._file_ranges_old)
                else:
                    fname = self._find_file_for_line(line_no, self._file_ranges_new)
                if fname is None:
                    fname = "__other__"
                if fname not in file_groups:
                    file_groups[fname] = []
                    order.append(fname)
                file_groups[fname].append(entry)

            # 파일별 트리 노드 생성
            for fname in order:
                entries = file_groups[fname]
                display = os.path.basename(fname) if fname != "__other__" else "기타"
                n_new = sum(1 for e in entries if e[4] == "new")
                n_del = sum(1 for e in entries if e[4] == "deleted")
                n_mod = sum(1 for e in entries if e[4] not in ("new", "deleted", "global"))
                badges = []
                if n_new: badges.append(f"+{n_new}")
                if n_del: badges.append(f"-{n_del}")
                if n_mod: badges.append(f"~{n_mod}")
                badge_str = f"  ({', '.join(badges)})" if badges else ""
                file_item = QTreeWidgetItem([f"📄  {display}{badge_str}"])
                file_item.setForeground(0, QColor(C.BLUE))
                file_item.setFont(0, QFont(C.FUI, 10, QFont.Weight.Bold))
                file_item.setToolTip(0, fname)
                file_item.setFlags(file_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                file_item.setCheckState(0, Qt.CheckState.Checked)
                self._func_tree.addTopLevelItem(file_item)
                # 파일 헤더 행 인덱스: DiffView 에서 파싱한 값 우선, 없으면 첫 함수 위치
                file_ri = self._diff_view._file_header_rows.get(
                    fname, entries[0][1] if entries else 0)
                self._tree_entries[id(file_item)] = ("file", file_ri)

                for fn, first_ri, decl, changes, flag in entries:
                    _add_func_items(file_item, fn, first_ri, decl, changes, flag)
                file_item.setExpanded(True)

        # ── 단일 파일 모드: 파일 노드 아래 함수 그룹화 ──────
        else:
            fname = single_filename or getattr(self, "_single_filename", "")
            if fname and func_list:
                n_new = sum(1 for e in func_list if e[4] == "new")
                n_del = sum(1 for e in func_list if e[4] == "deleted")
                n_mod = sum(1 for e in func_list if e[4] not in ("new", "deleted", "global"))
                badges = []
                if n_new: badges.append(f"+{n_new}")
                if n_del: badges.append(f"-{n_del}")
                if n_mod: badges.append(f"~{n_mod}")
                badge_str = f"  ({', '.join(badges)})" if badges else ""
                file_item = QTreeWidgetItem([f"📄  {fname}{badge_str}"])
                file_item.setForeground(0, QColor(C.BLUE))
                file_item.setFont(0, QFont(C.FUI, 10, QFont.Weight.Bold))
                file_item.setToolTip(0, fname)
                file_item.setFlags(file_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                file_item.setCheckState(0, Qt.CheckState.Checked)
                self._func_tree.addTopLevelItem(file_item)
                self._tree_entries[id(file_item)] = ("file", func_list[0][1] if func_list else 0)
                for fn, first_ri, decl, changes, flag in func_list:
                    _add_func_items(file_item, fn, first_ri, decl, changes, flag)
                file_item.setExpanded(True)
            else:
                for fn, first_ri, decl, changes, flag in func_list:
                    _add_func_items(self._func_tree, fn, first_ri, decl, changes, flag)

    def _on_func_click(self, item):
        entry = self._tree_entries.get(id(item))
        # _tree_entries 에 미등록 = 폴더 노드 → 단일 클릭으로 펼침/접힘 토글
        if not entry:
            if item.childCount() > 0:
                item.setExpanded(not item.isExpanded())
            return
        kind, ri = entry
        if kind == "folder_file":
            # 폴더 모드 아코디언: 클릭 시 함수 목록 인라인 드롭다운
            rel_path = ri
            pair = next((p for p in self._folder_pairs if p[0] == rel_path), None)
            is_deleted = pair and bool(pair[1]) and not pair[2]  # old 있고 new 없음
            if is_deleted:
                # 삭제된 파일: 확장 없이 diff 뷰만 표시
                if pair:
                    _, old_lines, new_lines = pair
                    self._ensure_folder_file_in_diff(rel_path, old_lines, new_lines)
                return
            if rel_path not in self._folder_loaded_files:
                self._expand_folder_file(item, rel_path)
            else:
                # 이미 로드됨 → diff 뷰만 갱신
                if pair:
                    _, old_lines, new_lines = pair
                    self._ensure_folder_file_in_diff(rel_path, old_lines, new_lines)
            item.setExpanded(not item.isExpanded())
        elif kind == "folder_parent":
            # 폴더 아코디언 내 함수 항목
            rel_path, first_ri = ri
            pair = next((p for p in self._folder_pairs if p[0] == rel_path), None)
            if pair:
                _, old_lines, new_lines = pair
                self._ensure_folder_file_in_diff(rel_path, old_lines, new_lines)
            item.setExpanded(not item.isExpanded())
            self._diff_view.scroll_to_row(first_ri)
        elif kind == "folder_child":
            # 폴더 아코디언 내 줄 번호 항목
            rel_path, ch_ri = ri
            pair = next((p for p in self._folder_pairs if p[0] == rel_path), None)
            if pair:
                _, old_lines, new_lines = pair
                self._ensure_folder_file_in_diff(rel_path, old_lines, new_lines)
            self._diff_view.scroll_to_row(ch_ri)
        elif kind == "file":
            # 단일 파일 combined 모드: 파일 단독 뷰로 전환
            fname = item.toolTip(0)
            if fname and (fname in self._per_file_old or fname in self._per_file_new):
                self._show_file_diff(fname)
            item.setExpanded(not item.isExpanded())
        elif kind == "parent":
            item.setExpanded(not item.isExpanded())
            self._diff_view.scroll_to_row(ri)
        else:
            self._diff_view.scroll_to_row(ri)

    # ── 파일 구분선 파싱 헬퍼 ────────────────────────────────
    @staticmethod
    def _parse_file_ranges(lines: list) -> list:
        """combined lines에서 '// ══════ 파일명 ══════' 구분선을 파싱한다.
        반환: [(rel_path, start_line_0based), ...] (줄 번호 오름차순)
        """
        result = []
        for i, line in enumerate(lines):
            m = re.match(r'^// [═]+ (.+?) [═]+\s*$', line)
            if m:
                result.append((m.group(1).strip(), i))
        return result

    @staticmethod
    def _split_by_file(combined_lines: list, file_ranges: list) -> dict:
        """combined_lines를 파일별로 분리한다.
        반환: {rel_path: [lines...]}  (구분선과 빈 줄은 제외)
        """
        result = {}
        for i, (fname, start) in enumerate(file_ranges):
            end = file_ranges[i + 1][1] if i + 1 < len(file_ranges) else len(combined_lines)
            # start: 구분선 행, end: 다음 구분선 행 (또는 끝)
            # 마지막 빈 줄(combined.append(""))도 제거
            chunk = combined_lines[start + 1:end]
            while chunk and chunk[-1].strip() == "":
                chunk = chunk[:-1]
            result[fname] = chunk
        return result

    @staticmethod
    def _find_file_for_line(line_no_1based: int, file_ranges: list):
        """1-based 줄 번호가 속한 파일명을 반환한다 (없으면 None)."""
        if not file_ranges:
            return None
        ln = line_no_1based - 1  # 0-based
        result = file_ranges[0][0]
        for fname, start in file_ranges:
            if start <= ln:
                result = fname
            else:
                break
        return result

    # ── 공개 API ──────────────────────────────────────────────
    def render_diff(self, old_lines: list[str], new_lines: list[str], func_list: list,
                    old_cmp: list[str] = None, new_cmp: list[str] = None,
                    filename: str = ""):
        self._single_filename = filename
        self._file_ranges_old = self._parse_file_ranges(old_lines)
        self._file_ranges_new = self._parse_file_ranges(new_lines)

        # 파일별 라인 분리 저장 (파일 단독 뷰 전환용)
        self._full_old_lines = old_lines
        self._full_new_lines = new_lines
        self._full_func_list = func_list
        self._full_old_cmp   = old_cmp   # 주석 무시 비교용 (None이면 원본 사용)
        self._full_new_cmp   = new_cmp
        self._per_file_old   = self._split_by_file(old_lines, self._file_ranges_old)
        self._per_file_new   = self._split_by_file(new_lines, self._file_ranges_new)
        # 한쪽에만 있는 파일도 빈 리스트로 보완
        for fname in set(self._per_file_old) | set(self._per_file_new):
            self._per_file_old.setdefault(fname, [])
            self._per_file_new.setdefault(fname, [])

        self._diff_view.hide_file_nav()
        self._diff_view.render(old_lines, new_lines, old_cmp=old_cmp, new_cmp=new_cmp)
        self._render_func_tree(func_list, single_filename=filename)
        self._switch("diff"); self.step_bar.advance(1)

    def _show_file_diff(self, fname: str):
        """선택한 파일 하나만 diff 뷰에 표시한다."""
        old_f = self._per_file_old.get(fname, [])
        new_f = self._per_file_new.get(fname, [])
        self._diff_view.render(old_f, new_f)
        self._diff_view.show_file_nav(fname, self._show_all_diff)

    def _show_all_diff(self):
        """전체 combined diff 로 복원한다."""
        self._diff_view.hide_file_nav()
        self._diff_view.render(self._full_old_lines, self._full_new_lines,
                               old_cmp=self._full_old_cmp, new_cmp=self._full_new_cmp)
        # 파일 헤더 row 인덱스 재매핑 후 트리 재빌드
        self._file_ranges_old = self._parse_file_ranges(self._full_old_lines)
        self._file_ranges_new = self._parse_file_ranges(self._full_new_lines)
        self._render_func_tree(self._full_func_list)

    # ── 폴더 모드 공개 API ────────────────────────────────────
    def render_folder(self, file_pairs: list, per_file_func_counts: dict = None):
        """폴더 모드: 파일 목록 뷰로 초기화 후 표시."""
        self._folder_mode           = True
        self._folder_pairs          = file_pairs
        self._per_file_func_counts  = per_file_func_counts or {}
        # 단일 파일 모드용 상태 초기화
        self._file_ranges_old = []
        self._file_ranges_new = []
        self._per_file_old = {}
        self._per_file_new = {}
        self._full_old_lines = []
        self._full_new_lines = []
        self._full_func_list = []
        self._diff_view.hide_file_nav()
        self._show_file_list()
        self._switch("diff"); self.step_bar.advance(1)

    # ── 폴더 모드 내부 메서드 ─────────────────────────────────
    def _render_file_list_tree(self, file_pairs: list, per_file_func_counts: dict = None):
        """파일 목록을 변경 통계와 함께 함수 트리에 표시한다.
        rel_path 에 포함된 디렉토리 계층을 그대로 트리로 반영한다."""
        _func_counts = per_file_func_counts or {}

        # 트리 재빌드 중 itemChanged 신호 억제 + 전체 선택 초기화
        self._func_tree.blockSignals(True)
        self._chk_all_files.blockSignals(True)
        self._chk_all_files.setChecked(False)
        self._chk_all_files.blockSignals(False)
        self._func_tree.clear(); self._tree_entries.clear()
        self._checkable_rel_paths: set = set()   # 변경 있는 파일 경로 집합
        self._folder_loaded_files = set()   # 아코디언 로드 상태 리셋
        self._current_diff_file   = ""      # diff 뷰 상태 리셋

        # 폴더별 변경 파일 수 사전 계산 (조상 경로 포함)
        from core.model import diff_stats as _ds
        dir_changed_counts: dict = {}
        for rel_path, old_lines, new_lines in file_pairs:
            is_added   = not old_lines and bool(new_lines)
            is_deleted = bool(old_lines) and not new_lines
            n_add, n_del, n_mod = _ds(old_lines, new_lines)
            if is_added or is_deleted or n_add or n_del or n_mod:
                norm = rel_path.replace("\\", "/")
                dir_part, _, _ = norm.rpartition("/")
                parts = dir_part.split("/") if dir_part else []
                for i in range(len(parts)):
                    anc = "/".join(parts[:i + 1])
                    dir_changed_counts[anc] = dir_changed_counts.get(anc, 0) + 1

        # 디렉토리 경로 → QTreeWidgetItem 매핑 (중간 폴더 노드 재사용)
        dir_items: dict = {}

        def _get_or_create_dir(dir_path: str):
            """경로('/' 구분)에 해당하는 폴더 노드를 반환 혹은 생성."""
            if not dir_path:
                return None  # 루트 레벨
            if dir_path in dir_items:
                return dir_items[dir_path]
            parent_path, _, name = dir_path.rpartition("/")
            parent_item = _get_or_create_dir(parent_path) if parent_path else None

            cnt = dir_changed_counts.get(dir_path, 0)
            cnt_str = f"  ({cnt})" if cnt > 0 else ""
            di = QTreeWidgetItem([f"📁  {name}{cnt_str}"])
            di.setForeground(0, QColor(C.BLUE))
            di.setFont(0, QFont(C.FUI, 10, QFont.Weight.Bold))
            di.setToolTip(0, dir_path)
            # 선택 불가 — 클릭 시 어떤 동작도 하지 않도록 _tree_entries 에 등록 X
            di.setFlags(di.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            if parent_item is None:
                self._func_tree.addTopLevelItem(di)
            else:
                parent_item.addChild(di)
            # 기본 접힘 — 사용자가 화살표/더블클릭으로 펼치는 드롭다운 동작
            di.setExpanded(False)
            dir_items[dir_path] = di
            return di

        for rel_path, old_lines, new_lines in file_pairs:
            is_added   = (not old_lines and bool(new_lines))   # 신규 추가 파일
            is_deleted = (bool(old_lines) and not new_lines)   # 삭제된 파일
            n_add, n_del, n_mod = _ds(old_lines, new_lines)
            has_change = is_added or is_deleted or (n_add > 0 or n_del > 0 or n_mod > 0)

            if is_added:
                icon, color, weight = "✚ ", C.GREEN, QFont.Weight.Bold
            elif is_deleted:
                icon, color, weight = "✖ ", C.RED,   QFont.Weight.Bold
            elif has_change:
                icon, color, weight = "📄", C.BLUE,  QFont.Weight.Bold
            else:
                icon, color, weight = "≡ ", C.T0,   QFont.Weight.Normal

            # rel_path 를 '/' 로 정규화한 뒤 디렉토리/파일명 분리
            norm_path = rel_path.replace("\\", "/")
            dir_part, _, base_name = norm_path.rpartition("/")
            display = base_name or rel_path

            # 변경된 파일에는 함수 변경 수 표시
            fn_cnt = _func_counts.get(rel_path, 0)
            fn_str = f"  ({fn_cnt})" if has_change and fn_cnt > 0 else ""

            fi = QTreeWidgetItem([f"{icon}  {display}{fn_str}"])
            fi.setForeground(0, QColor(color))
            fi.setFont(0, QFont(C.FUI, 10, weight))
            fi.setToolTip(0, rel_path)

            parent_item = _get_or_create_dir(dir_part) if dir_part else None
            if parent_item is None:
                self._func_tree.addTopLevelItem(fi)
            else:
                parent_item.addChild(fi)

            self._tree_entries[id(fi)] = ("folder_file", rel_path)
            if has_change:
                # 체크박스 추가 (기본값: 미선택 — 사용자가 직접 선택)
                self._checkable_rel_paths.add(rel_path)
                fi.setFlags(fi.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                fi.setCheckState(0, Qt.CheckState.Unchecked)
                if not is_deleted:
                    # 삭제된 파일은 함수 목록 확장 불필요 — placeholder 생략
                    ph = QTreeWidgetItem([""])
                    ph.setFlags(ph.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                    fi.addChild(ph)

        # 트리 빌드 완료 — itemChanged 신호 복원
        self._func_tree.blockSignals(False)

    def _show_file_list(self):
        """폴더 모드: 파일 목록 뷰로 돌아간다."""
        self._diff_view.hide_file_nav()
        # diff 뷰 초기화
        self._diff_view.clear_view()
        # 파일 목록 트리 재빌드
        self._render_file_list_tree(
            self._folder_pairs,
            getattr(self, "_per_file_func_counts", {}))

    def _expand_folder_file(self, item: QTreeWidgetItem, rel_path: str):
        """폴더 모드 아코디언: 파일 항목에 함수 자식을 lazy-load하고 diff 뷰를 갱신한다."""
        pair = next((p for p in self._folder_pairs if p[0] == rel_path), None)
        if not pair:
            return
        _, old_lines, new_lines = pair
        func_list = diff_func_analysis(old_lines, new_lines)

        # placeholder 제거
        item.takeChildren()

        TAG_ICON  = {"delete": "－", "insert": "＋", "replace": "～"}
        TAG_COLOR = {"delete": C.RED, "insert": C.GREEN, "replace": C.AMBER}

        def _group(changes):
            if not changes: return []
            out = []
            ri0, tag, ln = changes[0]; s = e = ln or 0
            for nri, ntag, nln in changes[1:]:
                nl = nln or 0
                if ntag == tag and nl <= e + 2: e = nl
                else: out.append((ri0, tag, s, e)); ri0, tag, s, e = nri, ntag, nl, nl
            out.append((ri0, tag, s, e)); return out

        if not func_list:
            empty = QTreeWidgetItem(["  분석된 함수 없음"])
            empty.setForeground(0, QColor(C.T3))
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.addChild(empty)
        else:
            for fn, first_ri, decl, changes, flag in func_list:
                ic, col = ("＋", C.GREEN) if flag == "new"    else \
                          ("－", C.RED)   if flag == "deleted" else \
                          ("～", C.AMBER) if flag == "global"  else \
                          ("～", C.AMBER)
                disp = decl[:50] + "…" if len(decl) > 50 else decl
                pi = QTreeWidgetItem([f"{ic}  {disp}"])
                pi.setForeground(0, QColor(col))
                # 전역 영역은 한글이라 Bold 로도 얇게 보여서 Black 가중치로 보강
                _weight = QFont.Weight.Black if flag == "global" else QFont.Weight.Bold
                pi.setFont(0, QFont(C.FUI, 10, _weight))
                pi.setToolTip(0, decl)
                item.addChild(pi)
                self._tree_entries[id(pi)] = ("folder_parent", (rel_path, first_ri))

                for ch_ri, ch_tag, s, e in _group(changes):
                    lno = f"줄 {s}" if s == e else f"줄 {s} ~ {e}"
                    ci = QTreeWidgetItem([f"  {TAG_ICON.get(ch_tag, '～')}  {lno}"])
                    ci.setForeground(0, QColor(TAG_COLOR.get(ch_tag, C.AMBER)))
                    ci.setFont(0, QFont(C.FUI, 9))
                    pi.addChild(ci)
                    self._tree_entries[id(ci)] = ("folder_child", (rel_path, ch_ri))
                pi.setExpanded(False)

        self._folder_loaded_files.add(rel_path)

        # diff 뷰 갱신 (처음 로드 시에만 렌더)
        self._ensure_folder_file_in_diff(rel_path, old_lines, new_lines)

    def _ensure_folder_file_in_diff(self, rel_path: str, old_lines: list, new_lines: list):
        """해당 파일이 diff 뷰에 표시되지 않은 경우에만 렌더링한다."""
        if self._current_diff_file == rel_path:
            return
        self._diff_view.hide_file_nav()
        self._diff_view.render(old_lines, new_lines)
        self._current_diff_file = rel_path

    # ── 전체 선택/해제 ────────────────────────────────────────
    def _iter_all_folder_files(self):
        """트리 전체(중첩 폴더 포함)를 재귀 순회하며 변경 있는 folder_file 항목을 yield."""
        chk_paths = getattr(self, "_checkable_rel_paths", set())

        def walk(parent):
            for i in range(parent.childCount()):
                it = parent.child(i)
                entry = self._tree_entries.get(id(it))
                if entry and entry[0] == "folder_file" and entry[1] in chk_paths:
                    yield it
                # 폴더 노드/파일 노드 관계없이 하위도 계속 순회
                if it.childCount() > 0:
                    yield from walk(it)

        yield from walk(self._func_tree.invisibleRootItem())

    def _on_chk_all_files(self, state):
        """전체 선택/해제 체크박스 클릭 → 변경 있는 folder_file 항목만 일괄 변경."""
        target = (Qt.CheckState.Checked
                  if state == Qt.CheckState.Checked.value
                  else Qt.CheckState.Unchecked)
        self._func_tree.blockSignals(True)
        for item in self._iter_all_folder_files():
            item.setCheckState(0, target)
        self._func_tree.blockSignals(False)

    def _on_file_item_changed(self, item, col):
        """개별 파일 체크 변경 시 자식 함수 cascade + '전체 선택/해제' 체크박스 동기화."""
        if col != 0:
            return
        entry = self._tree_entries.get(id(item))
        if not entry:
            return
        # 파일 노드 체크 → 자식 함수 항목 cascade
        if entry[0] == "file" and item.childCount() > 0:
            state = item.checkState(0)
            self._func_tree.blockSignals(True)
            for i in range(item.childCount()):
                child = item.child(i)
                child_entry = self._tree_entries.get(id(child))
                if child_entry and child_entry[0] == "parent":
                    child.setCheckState(0, state)
            self._func_tree.blockSignals(False)
        if entry[0] != "folder_file":
            return
        checkable = list(self._iter_all_folder_files())
        if not checkable:
            return
        n_checked = sum(
            1 for it in checkable
            if it.checkState(0) == Qt.CheckState.Checked)
        self._chk_all_files.blockSignals(True)
        if n_checked == len(checkable):
            self._chk_all_files.setChecked(True)
        elif n_checked == 0:
            self._chk_all_files.setChecked(False)
        else:
            # 일부만 체크 → 체크 해제 상태로 표시 (tristate 미사용)
            self._chk_all_files.setChecked(False)
        self._chk_all_files.blockSignals(False)

    def get_checked_folder_pairs(self) -> list:
        """폴더 모드에서 체크된 파일들의 (rel_path, old_lines, new_lines) 목록을 반환한다.
        폴더 계층 구조로 중첩된 파일도 재귀적으로 순회한다."""
        if not self._folder_mode:
            return []
        result = []
        for item in self._iter_all_folder_files():
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            entry = self._tree_entries.get(id(item))
            if not entry:
                continue
            _, rel_path = entry
            pair = next((p for p in self._folder_pairs if p[0] == rel_path), None)
            if pair:
                result.append(pair)
        return result

    def get_single_file_checked(self) -> bool:
        """단일 파일 모드에서 파일 노드가 체크돼 있는지 반환. 파일 노드 없으면 True."""
        if self._folder_mode:
            return True
        root = self._func_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            entry = self._tree_entries.get(id(item))
            if entry and entry[0] == "file":
                return item.checkState(0) == Qt.CheckState.Checked
        return True  # 파일 노드 없으면 제한 없이 허용

    def get_current_file_lines(self):
        """폴더 모드에서 현재 diff 뷰에 표시 중인 파일의 (rel_path, old_lines, new_lines)를 반환.
        선택된 파일이 없거나 단일 파일 모드면 None 반환."""
        if not self._folder_mode or not self._current_diff_file:
            return None
        pair = next((p for p in self._folder_pairs if p[0] == self._current_diff_file), None)
        return pair  # (rel_path, old_lines, new_lines) or None

    def set_summary(self, text: str):
        self._sum_view.set_text(text)
        self._populate_sum_tree(text)
        self.step_bar.advance(2)
        # [대화형AI DISABLED] self.enable_summary_chat()

    def _populate_sum_tree(self, text: str):
        self._sum_tree.clear(); self._sum_entries.clear()

        sec_pat  = re.compile(r'^### (.+)$',  re.MULTILINE)
        func_pat = re.compile(r'^#### (.+)$', re.MULTILINE)
        file_re  = re.compile(r'\[([^\]]+)\]\s*(.+)')

        sections = [(m.start(), m.group(1).strip(), f"### {m.group(1).strip()}") for m in sec_pat.finditer(text)]
        funcs    = [(m.start(), m.group(1).strip(), f"#### {m.group(1).strip()}") for m in func_pat.finditer(text)]

        if not sections and not funcs:
            ei = QTreeWidgetItem(["  내용 없음"])
            ei.setForeground(0, QColor(C.T3))
            ei.setFont(0, QFont(C.FUI, 10))
            self._sum_tree.addTopLevelItem(ei)
            return

        def _add_as_file_tree(parent, func_list):
            """func_list를 [파일명] 기준으로 묶어 파일→함수 트리로 추가."""
            from collections import OrderedDict
            groups = OrderedDict()
            for f_pos, f_title, f_heading in func_list:
                raw = f_title.strip('`').strip()
                m = file_re.match(raw)
                fname     = m.group(1).strip() if m else None
                func_name = m.group(2).strip() if m else raw
                groups.setdefault(fname, []).append((func_name, f_heading))

            for fname, entries in groups.items():
                if fname:
                    fi = QTreeWidgetItem([f"  📄  {fname}"])
                    fi.setForeground(0, QColor(C.BLUE))
                    fi.setFont(0, QFont(C.FUI, 9, QFont.Weight.Bold))
                    if parent is self._sum_tree:
                        self._sum_tree.addTopLevelItem(fi)
                    else:
                        parent.addChild(fi)
                    for func_name, f_heading in entries:
                        disp = func_name[:42] + "…" if len(func_name) > 42 else func_name
                        ci = QTreeWidgetItem([f"    {disp}"])
                        ci.setForeground(0, QColor(C.T1))
                        ci.setFont(0, QFont(C.FUI, 9))
                        ci.setToolTip(0, func_name)
                        fi.addChild(ci)
                        self._sum_entries[id(ci)] = f_heading
                    fi.setExpanded(True)
                else:
                    for func_name, f_heading in entries:
                        disp = func_name[:42] + "…" if len(func_name) > 42 else func_name
                        ci = QTreeWidgetItem([f"  {disp}"])
                        ci.setForeground(0, QColor(C.T1))
                        ci.setFont(0, QFont(C.FUI, 9))
                        ci.setToolTip(0, func_name)
                        if parent is self._sum_tree:
                            self._sum_tree.addTopLevelItem(ci)
                        else:
                            parent.addChild(ci)
                        self._sum_entries[id(ci)] = f_heading

        if sections:
            for si, (s_pos, s_title, s_heading) in enumerate(sections):
                pi = QTreeWidgetItem([f"  📋  {s_title}"])
                pi.setForeground(0, QColor(C.AMBER))
                pi.setFont(0, QFont(C.FUI, 10, QFont.Weight.Bold))
                pi.setToolTip(0, s_title)
                self._sum_tree.addTopLevelItem(pi)
                self._sum_entries[id(pi)] = s_heading

                next_pos = sections[si + 1][0] if si + 1 < len(sections) else len(text)
                sec_funcs = [(fp, ft, fh) for fp, ft, fh in funcs if s_pos < fp < next_pos]
                _add_as_file_tree(pi, sec_funcs)
                pi.setExpanded(True)
        else:
            _add_as_file_tree(self._sum_tree, funcs)

    def _on_sum_click(self, item):
        heading = self._sum_entries.get(id(item))
        if heading:
            self._sum_view.scroll_to(heading)
        else:
            item.setExpanded(not item.isExpanded())

    # ── [대화형AI DISABLED] 채팅 UI (하단 버튼 바 + ChatDialog 생성) ─
    # 아래 메서드 4개를 주석 해제하면 기능 복구 가능
    #
    # def _build_chat_ui(self, is_summary: bool = False) -> QFrame:
    #     """취약점/요약 탭 하단 버튼 바 반환. 클릭 시 ChatDialog 팝업 열림."""
    #     prefix = "_sum" if is_summary else ""
    #     title = "💬  AI와 대화 — 변경점 요약 질문" if is_summary else "💬  AI와 대화 — 분석 결과 수정"
    #     subtitle = (
    #         "변경점 요약에 대해 AI에게 질문하거나 추가 설명을 요청할 수 있습니다."
    #         if is_summary else
    #         "취약점이 설계 의도라면 설명해주세요. AI가 해당 항목을 재평가하고 수정합니다."
    #     )
    #     placeholder = (
    #         "변경점 요약에 대해 질문하세요..."
    #         if is_summary else
    #         "예: H-1은 의도된 설계입니다. 이유: ...  /  이 부분을 더 자세히 설명해주세요"
    #     )
    #
    #     dlg = ChatDialog(title, subtitle, placeholder, parent=self)
    #     if is_summary:
    #         self._sum_chat_dlg = dlg
    #         dlg.message_submitted.connect(self.summary_qa_submitted)
    #     else:
    #         self._chat_dlg = dlg
    #         dlg.message_submitted.connect(self.qa_submitted)
    #
    #     bar = QFrame()
    #     bar.setObjectName(f"chat_bar{prefix}")
    #     bar.setFixedHeight(44)
    #     bar.setStyleSheet(
    #         f"#chat_bar{prefix} {{ background:{C.BG_APP};"
    #         f"border-top:1px solid {C.BDR}; }}")
    #     bar.setVisible(False)
    #     bl = QHBoxLayout(bar)
    #     bl.setContentsMargins(12, 4, 12, 4); bl.addStretch()
    #
    #     open_btn = QPushButton("💬  AI와 대화")
    #     open_btn.setObjectName("btn_sub")
    #     open_btn.setFixedHeight(30); open_btn.setMinimumWidth(130)
    #     open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    #     open_btn.clicked.connect(dlg.show)
    #     open_btn.clicked.connect(dlg.raise_)
    #     bl.addWidget(open_btn)
    #
    #     return bar
    #
    # # ── 활성화 ───────────────────────────────────────────────
    # def enable_qa(self):
    #     """취약점 분석 완료 후 채팅 버튼 표시."""
    #     self._chat_bar.setVisible(True)
    #
    # def enable_summary_chat(self):
    #     """변경점 요약 완료 후 요약 탭 채팅 버튼 표시."""
    #     self._sum_chat_bar.setVisible(True)
    #
    # # ── 답변 추가 ────────────────────────────────────────────
    # def add_qa_answer(self, question: str, answer: str):
    #     self._chat_dlg.add_message(question, answer)
    #     self._chat_dlg.show(); self._chat_dlg.raise_()
    #
    # def add_summary_qa_answer(self, question: str, answer: str):
    #     self._sum_chat_dlg.add_message(question, answer)
    #     self._sum_chat_dlg.show(); self._sum_chat_dlg.raise_()

    def set_vuln(self, text: str):
        self._vuln_view.set_text(text)
        self._populate_vuln_tree(text)
        self.step_bar.advance(3)
        # [대화형AI DISABLED] self.enable_qa()

    def update_vuln_text(self, text: str):
        """취약점 분석 결과 갱신."""
        self._vuln_view.set_text(text)
        self._populate_vuln_tree(text)

    def _populate_vuln_tree(self, text: str):
        self._vuln_tree.clear(); self._vuln_entries.clear()

        # ── ① H / M / L 취약점 ──────────────────────────────
        SEV = {
            "H": ("High",   "🔴", C.RED),
            "M": ("Middle", "🟡", C.AMBER),
            "L": ("Low",    "🟢", C.GREEN),
        }
        buckets: dict[str, list] = {"H": [], "M": [], "L": []}

        pat = re.compile(r'^### (H|M|L)-(\d+)\.\s+(.+)$', re.MULTILINE)
        for m in pat.finditer(text):
            prefix, num, title = m.group(1), m.group(2), m.group(3).strip()
            heading = f"### {prefix}-{num}."
            buckets[prefix].append((heading, title))

        any_item = False
        for prefix, (sev_name, icon, col) in SEV.items():
            items = buckets[prefix]
            if not items:
                continue
            any_item = True
            pi = QTreeWidgetItem([f"  {icon}  {sev_name}  ({len(items)}건)"])
            pi.setForeground(0, QColor(col))
            pi.setFont(0, QFont(C.FUI, 10, QFont.Weight.Bold))
            self._vuln_tree.addTopLevelItem(pi)
            for heading, title in items:
                disp = title[:42] + "…" if len(title) > 42 else title
                ci = QTreeWidgetItem([f"    {disp}"])
                ci.setForeground(0, QColor(col))
                ci.setFont(0, QFont(C.FUI, 9))
                ci.setToolTip(0, title)
                pi.addChild(ci)
                self._vuln_entries[id(ci)] = heading
            pi.setExpanded(True)

        if not any_item:
            ei = QTreeWidgetItem(["  결함 없음"])
            ei.setForeground(0, QColor(C.T3))
            ei.setFont(0, QFont(C.FUI, 10))
            self._vuln_tree.addTopLevelItem(ei)

        # ── ② 정적 분석 위반 (SA-N) ─────────────────────────
        # 1차: canonical 형식 — `### SA-1. [Mandatory] 초기화되지 않은 ... — Rule 9.1`
        sa_pat = re.compile(r'^### SA-(\d+)\.\s+(.+)$', re.MULTILINE)
        sa_items = [(f"### SA-{m.group(1)}.", m.group(2).strip())
                    for m in sa_pat.finditer(text)]
        # 2차 fallback: AI 가 prompt 를 어기고 SA 항목들을 single overview 표로 합쳐
        # 출력하는 경우 (모든 항목이 H-N 크로스레퍼런스일 때 자주 발생). 표 행에서
        # `| SA-N | ... |` 패턴을 추출 → 가장 긴 비어있지 않은 셀을 제목으로.
        # 헤딩이 없으므로 scroll target 은 `SA-N` 평문 — scroll_to 가 첫 번째
        # 매칭(=표 행) 으로 폴백 검색해서 해당 영역으로 이동시킴.
        if not sa_items:
            sa_table_pat = re.compile(
                r'^\|\s*SA-(\d+)\s*\|([^\n]+)$', re.MULTILINE)
            for m in sa_table_pat.finditer(text):
                num = m.group(1)
                rest = m.group(2)
                cells = [c.strip() for c in rest.strip().strip('|').split('|')]
                # 가장 긴 비어있지 않은 셀을 제목으로 사용 (보통 위반 내용 컬럼)
                title = max((c for c in cells if c), key=len, default=f"SA-{num}")
                sa_items.append((f"SA-{num}", title))
        if sa_items:
            col_sa = "#7C3AED"   # 보라
            pi_sa = QTreeWidgetItem([f"  🔬  정적 분석 위반  ({len(sa_items)}건)"])
            pi_sa.setForeground(0, QColor(col_sa))
            pi_sa.setFont(0, QFont(C.FUI, 10, QFont.Weight.Bold))
            self._vuln_tree.addTopLevelItem(pi_sa)
            for heading, title in sa_items:
                disp = title[:42] + "…" if len(title) > 42 else title
                ci = QTreeWidgetItem([f"    {disp}"])
                ci.setForeground(0, QColor(col_sa))
                ci.setFont(0, QFont(C.FUI, 9))
                ci.setToolTip(0, title)
                pi_sa.addChild(ci)
                self._vuln_entries[id(ci)] = heading
            pi_sa.setExpanded(True)

        # ── ③ Codebeamer 연관 이슈 ────────────────────────────
        # 헤더 문자열은 prompts/system/cb_issues_section.md 의 첫 줄과 정확히 일치해야 함
        cb_header = "## ⚠️ Codebeamer 연관 이슈 경고"
        if cb_header in text:
            cb_section = text[text.index(cb_header):]
            col_cb = "#0369A1"   # 파랑
            # 하위 소제목 중 실제 테이블 행이 있는 것만 추출
            sub_pat = re.compile(
                r'^### 📌\s+(.+?)$(.+?)(?=^### |\Z)', re.MULTILINE | re.DOTALL)
            sub_items = []
            for sm in sub_pat.finditer(cb_section):
                sub_name = sm.group(1).strip()
                sub_body = sm.group(2)
                # 테이블 데이터 행 존재 여부: "| 1 |" 같은 패턴
                if re.search(r'^\|\s*\d+\s*\|', sub_body, re.MULTILINE):
                    rows = re.findall(r'^\|\s*\d+\s*\|(.+)', sub_body, re.MULTILINE)
                    sub_items.append((sub_name, len(rows), cb_header))

            if sub_items:
                total_cb = sum(n for _, n, _ in sub_items)
                pi_cb = QTreeWidgetItem(
                    [f"  🔗  과거차 연관 이슈  ({total_cb}건)"])
                pi_cb.setForeground(0, QColor(col_cb))
                pi_cb.setFont(0, QFont(C.FUI, 10, QFont.Weight.Bold))
                self._vuln_tree.addTopLevelItem(pi_cb)
                for sub_name, cnt, heading in sub_items:
                    ci = QTreeWidgetItem([f"    📌 {sub_name}  ({cnt}건)"])
                    ci.setForeground(0, QColor(col_cb))
                    ci.setFont(0, QFont(C.FUI, 9))
                    pi_cb.addChild(ci)
                    self._vuln_entries[id(ci)] = heading
                pi_cb.setExpanded(True)

    def _on_vuln_click(self, item):
        heading = self._vuln_entries.get(id(item))
        if heading:
            self._vuln_view.scroll_to(heading)
        else:
            item.setExpanded(not item.isExpanded())

    def clear(self):
        self._diff_view.clear_view(); self._sum_view.clear()
        self._vuln_view.clear(); self.step_bar.reset()
        self._func_tree.clear(); self._tree_entries.clear()
        self._sum_tree.clear();  self._sum_entries.clear()
        self._vuln_tree.clear(); self._vuln_entries.clear()
        self._folder_mode  = False
        self._folder_pairs = []
        self._file_ranges_old = []; self._file_ranges_new = []
        self._per_file_old = {};    self._per_file_new = {}
        self._full_old_lines = [];  self._full_new_lines = []
        self._full_func_list = []
        self._full_old_cmp   = None; self._full_new_cmp = None
        # [대화형AI DISABLED] 채팅 팝업 초기화 — 아래 4줄 주석 해제하면 복구
        # self._chat_bar.setVisible(False)
        # self._chat_dlg.hide(); self._chat_dlg.reset()
        # self._sum_chat_bar.setVisible(False)
        # self._sum_chat_dlg.hide(); self._sum_chat_dlg.reset()

    def auto_fetch_cb(self):
        """앱 시작 시 추가분석자료 탭의 모든 섹션 데이터를 자동으로 가져온다."""
        self._extras_panel.auto_fetch_all()

    def set_include_opt(self, key: str, checked: bool):
        """InputPanel 체크박스 변경을 ExtrasPanel에 전달 (신호 루프 방지)."""
        self._extras_panel.set_include(key, checked)

    def get_cb_filtered_md(self, key: str) -> "str | None":
        """ResultPanel → ExtrasPanel.get_filtered_md() 위임.
        반환값:
          - None : 필터링 미지원 모드 (호출 측에서 파일 폴백)
          - ""   : 모드는 지원하나 체크된 항목이 0건
          - str  : 체크된 항목만 재조립한 MD"""
        return self._extras_panel.get_filtered_md(key)

    # ── 저장 ─────────────────────────────────────────────────
    # ── 프로젝트명 주입 (main.py 에서 분석 완료 시 호출) ────────
    def set_project_name(self, name: str):
        self._project_name = name.strip()

    # ── 저장 로직: ui_save.py 로 분리 (MD/HTML/DOCX/모두) ─────
    def _show_save_popup(self, anchor_btn=None):
        """저장 팝업 메뉴를 띄운다.

        anchor_btn:
          None  → ResultPanel 내부 toolbar 의 _save_btn 기준 (기본 경로)
          위젯  → 해당 버튼 위치 기준 (예: ReviewPage 헤더의 결과물 저장 버튼).
                  외부에서 헤더 버튼으로 호출 시 메뉴가 그 버튼 아래에 뜨도록.
        """
        _show_save_popup_fn(self, anchor_btn or self._save_btn,
                            self._sum_view.text(),
                            self._vuln_view.text(),
                            self._project_name)
