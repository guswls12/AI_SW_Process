"""page_spec.py — ① 사양 변경 페이지.

구성:
  (1) 프로젝트 정보 카드 — 프로젝트명/제어기/변경 전/변경 후/설계자
  (2) 이슈 내용 카드 — 기본 1개, [+ 이슈 추가] 버튼으로 증가, [✕ 삭제] 버튼으로 제거
        각 묶음: JIRA 링크 / 현상 / 분석 내용 / 대책 / 수평전개 토글 표

수평전개 표:
  행 = [차종, 적용 여부]
  열 = [NQ5 PE, MQ4i, LX3, JW, TK1, LQ2, SP3, KU FL, SG2,
        NX5(30Ah), NX5(20Ah), SX3, NQ6]
  각 셀 토글: 미적용(회색) / 적용(하늘색)
"""

import os
import re
import json
import html
import tempfile
import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QImage
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QScrollArea, QGraphicsDropShadowEffect,
    QGridLayout, QFileDialog,
)
from PyQt6.QtGui import QColor

from config import C
from ._common import BasePage, TabStack, PlaceholderBody


# 차종 컬럼 (사용자 명세 — 중복 제거 후)
VEHICLE_COLUMNS = [
    "NQ5 PE", "MQ4i", "LX3", "JW", "TK1", "LQ2", "SP3",
    "KU FL", "SG2", "NX5(30Ah)", "NX5(20Ah)", "SX3", "Qy2i", "NQ6",
]


# ══════════════════════════════════════════════════════════════
#  마크다운 렌더링 헬퍼 — 이슈/사양변경/수평전개 본문 공용
#  (CB 업로드 본문에 임베드되는 HTML 표/라벨 카드/텍스트 정규화)
# ══════════════════════════════════════════════════════════════
_RND_LBL_ACCENT = "#3B82F6"
_RND_LBL_BG     = "#F1F5F9"
_RND_LBL_BDR    = "#E2E8F0"
_RND_LBL_FG     = "#1E293B"
_RND_ARROW_PREFIXES = ('->', '=>', '→', '⇒', '➡', '▶', '►', '⇨', '⮕', '⇾')


def _md_expand_image_markers(text: str) -> str:
    """`[📷 filename.png]` 마커를 굵은 라벨 + 안내문으로 치환.
    실제 이미지는 워커가 첨부 업로드 후 HTML 코멘트로 인라인 게시함.
    """
    def _repl(m):
        fname = m.group(1).strip()
        if not fname:
            return m.group(0)
        return (f"**📷 {html.escape(fname)}** "
                f"*(↓ 첨부/댓글 영역에 이미지 표시)*")
    return re.sub(r'\[📷\s*([^\]]+)\]', _repl, text)


def _md_normalize_user_text(text: str) -> str:
    """비표준 글머리표/화살표/체크박스 마커를 마크다운에 친화적으로 정규화.
      '•' / '·' / '◦'  → '- '
      '->' / '→' / '⇒' / '➡' / '▶' 등 → '> →  '
      '□'              → '- ☐ '
    """
    if not text:
        return text
    out = []
    for raw_line in text.split('\n'):
        line = raw_line.rstrip('\r')
        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]
        if stripped.startswith(('• ', '· ', '◦ ')):
            line = f"{indent}- {stripped[2:]}"
        elif (stripped.startswith(('•', '·', '◦'))
              and len(stripped) > 1 and stripped[1] != ' '):
            line = f"{indent}- {stripped[1:]}"
        else:
            matched = False
            for ap in _RND_ARROW_PREFIXES:
                if stripped.startswith(ap):
                    rest = stripped[len(ap):].lstrip()
                    line = f"{indent}> →  {rest}"
                    matched = True
                    break
            if not matched:
                if stripped.startswith('□ '):
                    line = f"{indent}- ☐ {stripped[2:]}"
                elif (stripped.startswith('□')
                      and len(stripped) > 1 and stripped[1] != ' '):
                    line = f"{indent}- ☐ {stripped[1:]}"
        out.append(line)
    return '\n'.join(out)


def _md_section_label(text: str) -> str:
    """섹션 라벨 카드 (HTML in markdown). 옅은 슬레이트 + 파랑 accent."""
    return (
        f'<table style="border-collapse:collapse;width:100%;'
        f'table-layout:fixed;margin:14px 0 6px;">'
        f'<tr><td style="padding:9px 14px;border:1px solid {_RND_LBL_BDR};'
        f'border-left:5px solid {_RND_LBL_ACCENT};background:{_RND_LBL_BG};'
        f'color:{_RND_LBL_FG};font-weight:700;font-size:13px;'
        f'border-radius:4px;">{html.escape(text)}</td>'
        f'</tr></table>')


def _md_jira_link_card(jira: str) -> str:
    """JIRA 링크 하이퍼링크 카드. 빈 입력 → 빈 문자열."""
    if not jira:
        return ""
    link_safe = html.escape(jira, quote=True)
    link_text = html.escape(jira)
    return (
        '<table style="border-collapse:collapse;width:100%;'
        'table-layout:fixed;margin:10px 0 14px;">'
        '<tr>'
        '<td style="width:130px;padding:9px 12px;'
        'border:1px solid #BFDBFE;background:#EFF6FF;color:#1D4ED8;'
        'font-weight:700;font-size:12px;text-align:center;">'
        '🔗 JIRA 링크</td>'
        '<td style="padding:9px 14px;border:1px solid #E2E8F0;'
        'background:#FFFFFF;font-size:12px;'
        'word-break:break-all;overflow-wrap:anywhere;">'
        f'<a href="{link_safe}" target="_blank" rel="noopener" '
        'style="color:#1D4ED8;text-decoration:underline;'
        f'font-weight:600;">{link_text}</a>'
        '</td></tr></table>')


def _md_hzt_table(hzt: dict) -> str:
    """수평전개 차종 표 (HTML in markdown). 모두 미적용이면 빈 문자열."""
    states = []
    for v in VEHICLE_COLUMNS:
        s = hzt.get(v, "미적용")
        if isinstance(s, bool):
            s = "적용" if s else "미적용"
        states.append(s)
    if not any(s != "미적용" for s in states):
        return ""
    tbl_style = ("border-collapse:collapse;width:100%;"
                 "table-layout:fixed;margin:0 0 14px;")
    th_style  = ("padding:7px 4px;border:1px solid #BFDBFE;"
                 "background:#EFF6FF;color:#1D4ED8;"
                 "text-align:center;font-weight:700;font-size:12px;")
    row_lbl_style = ("padding:6px 4px;border:1px solid #CBD5E1;"
                     "background:#F8FAFC;color:#1E293B;"
                     "text-align:center;font-weight:700;font-size:12px;")
    base_cell = ("padding:6px 4px;border:1px solid #CBD5E1;"
                 "text-align:center;font-weight:600;font-size:12px;")
    color_map = {
        "적용":   "background:#D1FAE5;color:#065F46;",
        "NA":     "background:#FEF3C7;color:#92400E;",
        "미적용": "background:#F1F5F9;color:#64748B;",
    }
    # 알 수 없는 값(레거시 커스텀 텍스트 등)은 미적용 색상으로 폴백
    default_style = color_map["미적용"]
    header_cells = "".join(
        f'<th style="{th_style}">{html.escape(v)}</th>'
        for v in VEHICLE_COLUMNS)
    data_cells = "".join(
        f'<td style="{base_cell}'
        f'{color_map.get(s, default_style)}">'
        f'{html.escape(s)}</td>'
        for s in states)
    return (f'<table style="{tbl_style}">\n'
            f'  <tr><th style="{th_style}">차종</th>{header_cells}</tr>\n'
            f'  <tr><td style="{row_lbl_style}">적용 여부</td>{data_cells}</tr>\n'
            '</table>')


def _shadow(widget, blur: int = 14, dy: int = 3, alpha: int = 18):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(0)
    eff.setYOffset(dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)


# ══════════════════════════════════════════════════════════════
#  ToggleCell — 수평전개 표의 [미적용 / 적용 / NA] 3-state 버튼
# ══════════════════════════════════════════════════════════════
class ToggleCell(QPushButton):
    """수평전개 표의 차종 셀.

    동작:
      - 좌클릭: 미적용 → 적용 → NA → 미적용 순환
    """

    STATES = ("미적용", "적용", "NA")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state_idx = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(64, 26)
        self.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
        self.clicked.connect(self._cycle)
        self._restyle()

    # ── 좌클릭: 상태 순환 ────────────────────────────────────
    def _cycle(self):
        self._state_idx = (self._state_idx + 1) % len(self.STATES)
        self._restyle()

    def _restyle(self):
        s = self.STATES[self._state_idx]
        self.setText(s)
        self.setToolTip("좌클릭: 미적용 ↔ 적용 ↔ NA 토글")
        # 스타일
        if s == "적용":
            self.setStyleSheet(
                f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
                f"  border:1px solid {C.ACCENT_H}; border-radius:5px; }}"
                f"QPushButton:hover {{ background:{C.ACCENT_H}; }}")
        elif s == "NA":
            self.setStyleSheet(
                "QPushButton { background:#FEF3C7; color:#92400E;"
                "  border:1px solid #F59E0B; border-radius:5px; }"
                "QPushButton:hover { background:#FDE68A; }")
        else:  # 미적용
            self.setStyleSheet(
                f"QPushButton {{ background:#E2E8F0; color:{C.T3};"
                f"  border:1px solid {C.BDR}; border-radius:5px; }}"
                f"QPushButton:hover {{ background:{C.BG_HOVER}; }}")

    # ── 외부 API ──────────────────────────────────────────────
    def get_state(self) -> str:
        return self.STATES[self._state_idx]

    def set_state(self, value):
        """문자열 / bool 을 받아 상태 설정.
        - bool True/False (레거시) → 적용/미적용
        - 'STATES' 중 하나 → 해당 토글 위치
        - 그 외 임의 문자열 (구버전 저장본의 커스텀 텍스트) → '미적용' 으로 폴백
        """
        if isinstance(value, bool):
            value = "적용" if value else "미적용"
        if not isinstance(value, str):
            return
        value = value.strip()
        if value in self.STATES:
            self._state_idx = self.STATES.index(value)
        else:
            # 빈 값, 또는 구버전 커스텀 텍스트 → 미적용으로 폴백
            self._state_idx = 0
        self._restyle()


# ══════════════════════════════════════════════════════════════
#  HorizontalDeployTable — 수평전개 표
# ══════════════════════════════════════════════════════════════
class HorizontalDeployTable(QFrame):
    """행 = [차종 / 적용 여부] 2행, 열 = 차종 목록."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hzt_table")
        self.setStyleSheet(
            f"#hzt_table {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:6px; }}")
        self._cells: list[ToggleCell] = []
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8); outer.setSpacing(0)

        # 가로 스크롤
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        grid = QGridLayout(inner)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6); grid.setVerticalSpacing(4)

        # 좌측 라벨 컬럼 (행 헤더) — 박스 없는 표 행 헤더 스타일
        row_lbls = ["차종", "적용 여부"]
        for r, txt in enumerate(row_lbls):
            lb = QLabel(txt)
            lb.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
            lb.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lb.setFixedSize(72, 26)
            lb.setStyleSheet(
                f"color:{C.T2}; background:transparent; border:none;"
                "padding-right:6px;")
            grid.addWidget(lb, r, 0)

        # 차종 열 + 토글 셀
        for c, vehicle in enumerate(VEHICLE_COLUMNS, start=1):
            head = QLabel(vehicle)
            head.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            head.setFixedSize(64, 26)
            head.setStyleSheet(
                f"color:{C.T1}; background:{C.BG_PANEL};"
                f"  border:1px solid {C.BDR}; border-radius:4px;")
            grid.addWidget(head, 0, c)

            cell = ToggleCell()
            grid.addWidget(cell, 1, c)
            self._cells.append(cell)

        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self.setMinimumHeight(90)
        self.setMaximumHeight(110)

    def get_state(self) -> dict[str, str]:
        """차종별 상태 ('미적용' / '적용' / 'NA') 를 dict 로 반환."""
        return {v: cell.get_state() for v, cell in zip(VEHICLE_COLUMNS, self._cells)}

    def set_state(self, state: dict):
        """문자열 상태 또는 레거시 bool 모두 허용."""
        for v, cell in zip(VEHICLE_COLUMNS, self._cells):
            cell.set_state(state.get(v, "미적용"))


# ══════════════════════════════════════════════════════════════
#  PasteableTextEdit — 이미지 클립보드 붙여넣기 지원 QTextEdit
# ══════════════════════════════════════════════════════════════
class PasteableTextEdit(QTextEdit):
    """Ctrl+V 로 이미지 붙여넣기를 지원하는 텍스트 에디터.

    이미지 페이스트 흐름:
      1) 임시 디렉터리에 PNG 로 저장 (paste_YYYYMMDD_HHMMSS[_N].png)
      2) image_pasted(path) 시그널 emit — 부모 블록이 첨부 칩에 추가
      3) 본문에 마커 텍스트 `[📷 paste_*.png]` 삽입 — render_change_item_md
         가 업로드 시점에 <img> 태그로 치환
    """
    image_pasted = pyqtSignal(str)   # 저장된 임시 PNG 경로

    # 세션 공용 임시 디렉터리 (클래스 변수 — 한 번만 생성)
    _session_tmp_dir: str = ""

    @classmethod
    def _get_tmp_dir(cls) -> str:
        if not cls._session_tmp_dir:
            cls._session_tmp_dir = tempfile.mkdtemp(prefix="cb_paste_")
        return cls._session_tmp_dir

    def canInsertFromMimeData(self, source) -> bool:
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        # 이미지 우선 처리 — 클립보드에 텍스트와 이미지가 모두 있는 스크린샷
        # 도구의 경우 일부는 hasImage() True, hasText() True 양쪽 다 — 이미지를 우선.
        if source.hasImage():
            img = source.imageData()
            if isinstance(img, QImage) and not img.isNull():
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                tmp_dir = self._get_tmp_dir()
                base = f"paste_{ts}.png"
                path = os.path.join(tmp_dir, base)
                # 같은 초 내 다중 페이스트 — 카운터로 충돌 방지
                n = 1
                while os.path.exists(path):
                    base = f"paste_{ts}_{n}.png"
                    path = os.path.join(tmp_dir, base)
                    n += 1
                if img.save(path, "PNG"):
                    self.textCursor().insertText(f"\n[📷 {base}]\n")
                    self.image_pasted.emit(path)
                    return
        # 이미지가 아니거나 저장 실패 → 기본 동작
        super().insertFromMimeData(source)


# ══════════════════════════════════════════════════════════════
#  AttachmentChip — 단일 첨부 파일 표시 칩 (파일명 + 크기 + ✕)
# ══════════════════════════════════════════════════════════════
class AttachmentChip(QFrame):
    """경로 + 크기 + 제거 버튼을 묶은 한 줄짜리 칩.

    클릭 시 부모에게 remove_requested 시그널을 전달 → 부모가 리스트에서 제거.
    """
    remove_requested = pyqtSignal(object)   # self 를 인자로

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.setObjectName("attach_chip")
        self.setStyleSheet(
            f"#attach_chip {{ background:{C.BG_PANEL};"
            f"  border:1px solid {C.BDR}; border-radius:6px; }}")
        self.setFixedHeight(30)
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0); lay.setSpacing(8)

        # 파일명 (확장자 포함, 너무 길면 자동 ellipsis 는 단순화 위해 생략)
        name = os.path.basename(self.path) or self.path
        lbl = QLabel(f"📎  {name}")
        lbl.setFont(QFont(C.FUI, 9))
        lbl.setStyleSheet(f"color:{C.T1}; background:transparent;")
        lbl.setToolTip(self.path)
        lay.addWidget(lbl, 1)

        # 파일 크기 (KB)
        try:
            kb = max(1, int(os.path.getsize(self.path) / 1024))
            size_txt = f"{kb:,} KB"
        except OSError:
            size_txt = "—"
        size_lbl = QLabel(size_txt)
        size_lbl.setFont(QFont(C.FUI, 9))
        size_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")
        lay.addWidget(size_lbl)

        # ✕ 제거 버튼
        rm = QPushButton("✕")
        rm.setFixedSize(20, 20)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.T3};"
            f"  border:none; border-radius:10px; font-size:11px;"
            f"  font-weight:bold; }}"
            f"QPushButton:hover {{ background:{C.RED}; color:#FFFFFF; }}")
        rm.setToolTip("이 첨부 파일 제거")
        rm.clicked.connect(lambda: self.remove_requested.emit(self))
        lay.addWidget(rm)


# ══════════════════════════════════════════════════════════════
#  ChangeItemBlock — 이슈 내용 한 묶음
# ══════════════════════════════════════════════════════════════
class ChangeItemBlock(QFrame):
    """JIRA 링크 / 현상 / 분석 내용 / 대책 / 수평전개 한 세트."""

    delete_requested   = pyqtSignal(object)
    register_requested = pyqtSignal(object)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.setObjectName("change_block")
        self.setStyleSheet(
            f"#change_block {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        self._index = index
        self._attach_chips: list[AttachmentChip] = []
        self._build()
        _shadow(self)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # 헤더: 이슈 N + 삭제 버튼
        hdr = QFrame(); hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 10, 0); hl.setSpacing(8)
        self._title_lbl = QLabel(f"📝  이슈  #{self._index}")
        self._title_lbl.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(self._title_lbl); hl.addStretch()

        reg_btn = QPushButton("📤  등록")
        reg_btn.setFixedHeight(24)
        reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reg_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.BLUE};"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:1px 12px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BLUE}; color:#FFFFFF; }}")
        reg_btn.setToolTip("이 이슈를 Codebeamer 에 새 이슈/코멘트로 등록")
        reg_btn.clicked.connect(lambda: self.register_requested.emit(self))
        hl.addWidget(reg_btn)

        del_btn = QPushButton("✕  삭제")
        del_btn.setFixedHeight(24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.RED};"
            f"  border:1px solid {C.RED}; border-radius:5px;"
            f"  padding:1px 12px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.RED}; color:#FFFFFF; }}")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        hl.addWidget(del_btn)
        lay.addWidget(hdr)

        # 본문
        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(10)

        # 제목
        r0, self.le_title = self._line_row("제목", "예) BLTN IPS 차감 로직 변경")
        bl.addLayout(r0)
        # JIRA 링크
        r1, self.le_jira = self._line_row("JIRA 링크", "예) https://jira.example.com/browse/ABC-123")
        bl.addLayout(r1)
        # 현상
        bl.addLayout(self._text_row("현상", "변경의 원인이 된 현상을 작성하세요"))
        # 분석 내용
        bl.addLayout(self._text_row("분석 내용", "근본 원인 분석 내용을 작성하세요"))
        # 대책
        bl.addLayout(self._text_row("대책", "적용한 대책을 작성하세요"))

        # 발생시점 + 고객OPEN — 2-column 컴팩트 행 (CB 수평전개 트래커 필드)
        bl.addLayout(self._dual_row(
            "발생시점", "예) P2 (NX5)",
            "고객OPEN", "예) X",
            ("occurrence", "customer_open")))

        # 수평전개
        sub_hdr = QLabel("수평전개")
        sub_hdr.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        sub_hdr.setStyleSheet(f"color:{C.T2}; background:transparent; padding-top:4px;")
        bl.addWidget(sub_hdr)
        self.hzt_table = HorizontalDeployTable()
        bl.addWidget(self.hzt_table)

        # ── 첨부 파일 섹션 ───────────────────────────────────
        # 헤더 행: "첨부 파일" 라벨 + [+ 파일 추가] 버튼
        atc_hdr = QHBoxLayout(); atc_hdr.setSpacing(8); atc_hdr.setContentsMargins(0, 6, 0, 0)
        atc_lbl = QLabel("첨부 파일")
        atc_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        atc_lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")
        atc_hdr.addWidget(atc_lbl); atc_hdr.addStretch()

        add_file_btn = QPushButton("➕  파일 추가")
        add_file_btn.setFixedHeight(24)
        add_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_file_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.BLUE};"
            f"  border:1px dashed {C.BLUE}; border-radius:5px;"
            f"  padding:1px 12px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
        add_file_btn.setToolTip("CB 이슈에 함께 업로드할 파일을 선택")
        add_file_btn.clicked.connect(self._on_add_files)
        atc_hdr.addWidget(add_file_btn)
        bl.addLayout(atc_hdr)

        # 칩 컨테이너 — 세로로 쌓이는 첨부 리스트
        self._attach_holder = QFrame(); self._attach_holder.setObjectName("attach_holder")
        self._attach_holder.setStyleSheet(
            "#attach_holder { background:transparent; }")
        self._attach_lay = QVBoxLayout(self._attach_holder)
        self._attach_lay.setContentsMargins(0, 4, 0, 0); self._attach_lay.setSpacing(4)
        # 비어있을 때 표시할 placeholder
        self._attach_placeholder = QLabel("선택된 파일이 없습니다.")
        self._attach_placeholder.setFont(QFont(C.FUI, 9))
        self._attach_placeholder.setStyleSheet(
            f"color:{C.T3}; background:transparent; padding:2px 4px;")
        self._attach_lay.addWidget(self._attach_placeholder)
        bl.addWidget(self._attach_holder)

        lay.addWidget(body)

    # ── 첨부 파일 핸들러 ──────────────────────────────────────
    def _on_add_files(self):
        """파일 선택 다이얼로그 → 선택된 파일들을 칩으로 추가."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "CB 첨부 파일 선택", "",
            "모든 파일 (*.*)")
        if not paths:
            return
        # 중복 제거 (이미 추가된 파일은 스킵)
        existing = {chip.path for chip in self._attach_chips}
        for p in paths:
            if p in existing:
                continue
            self._add_chip(p)

    def _add_chip(self, path: str):
        chip = AttachmentChip(path, self._attach_holder)
        chip.remove_requested.connect(self._remove_chip)
        self._attach_chips.append(chip)
        # placeholder 숨김 (보였다면)
        self._attach_placeholder.setVisible(False)
        self._attach_lay.addWidget(chip)

    def _remove_chip(self, chip: "AttachmentChip"):
        try:
            self._attach_chips.remove(chip)
        except ValueError:
            return
        chip.deleteLater()
        # 모두 비면 placeholder 다시 표시
        if not self._attach_chips:
            self._attach_placeholder.setVisible(True)

    def _line_row(self, label: str, placeholder: str):
        row = QHBoxLayout(); row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setFixedWidth(96)
        lbl.setFont(QFont(C.FUI, 10))
        lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")
        row.addWidget(lbl)
        le = QLineEdit(); le.setObjectName("le_info")
        le.setPlaceholderText(placeholder)
        le.setFixedHeight(28)
        row.addWidget(le)
        return row, le

    def _dual_row(self, label1: str, ph1: str,
                  label2: str, ph2: str,
                  attr_names: tuple):
        """한 줄에 두 입력란을 나란히 배치 (라벨1 + 입력1 + 라벨2 + 입력2).

        attr_names: (attr1, attr2) — 생성된 QLineEdit 두 개를
                    self.le_<attr1>, self.le_<attr2> 로 저장.
        """
        row = QHBoxLayout(); row.setSpacing(8)
        # 첫 번째 컬럼
        lbl1 = QLabel(label1)
        lbl1.setFixedWidth(96)
        lbl1.setFont(QFont(C.FUI, 10))
        lbl1.setStyleSheet(f"color:{C.T2}; background:transparent;")
        row.addWidget(lbl1)
        le1 = QLineEdit(); le1.setObjectName("le_info")
        le1.setPlaceholderText(ph1)
        le1.setFixedHeight(28)
        row.addWidget(le1, 1)
        setattr(self, f"le_{attr_names[0]}", le1)

        # 컬럼 간격
        row.addSpacing(12)

        # 두 번째 컬럼
        lbl2 = QLabel(label2)
        lbl2.setFixedWidth(72)
        lbl2.setFont(QFont(C.FUI, 10))
        lbl2.setStyleSheet(f"color:{C.T2}; background:transparent;")
        row.addWidget(lbl2)
        le2 = QLineEdit(); le2.setObjectName("le_info")
        le2.setPlaceholderText(ph2)
        le2.setFixedHeight(28)
        row.addWidget(le2, 1)
        setattr(self, f"le_{attr_names[1]}", le2)
        return row

    def _text_row(self, label: str, placeholder: str):
        row = QHBoxLayout(); row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setFixedWidth(96)
        lbl.setFont(QFont(C.FUI, 10))
        lbl.setStyleSheet(
            f"color:{C.T2}; background:transparent; padding-top:4px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        row.addWidget(lbl)
        te = PasteableTextEdit(); te.setObjectName("te_info")
        te.setPlaceholderText(placeholder + "  (Ctrl+V 로 이미지 붙여넣기 지원)")
        te.setFixedHeight(70)
        te.image_pasted.connect(self._on_image_pasted)
        row.addWidget(te)
        # 보관
        if label == "현상":
            self.te_phenom = te
        elif label == "분석 내용":
            self.te_analysis = te
        elif label == "대책":
            self.te_action = te
        return row

    # ── 페이스트 이미지 핸들러 ────────────────────────────────
    def _on_image_pasted(self, path: str):
        """PasteableTextEdit 가 임시 PNG 저장 후 호출 — 첨부 칩에 추가."""
        # 동일 경로 중복 방지 (이론상 발생 안하지만 안전)
        if any(c.path == path for c in self._attach_chips):
            return
        self._add_chip(path)

    def set_index(self, idx: int):
        self._index = idx
        self._title_lbl.setText(f"📝  이슈  #{idx}")

    def get_data(self) -> dict:
        return {
            "title":         self.le_title.text().strip(),
            "jira":          self.le_jira.text().strip(),
            "phenom":        self.te_phenom.toPlainText().strip(),
            "analysis":      self.te_analysis.toPlainText().strip(),
            "action":        self.te_action.toPlainText().strip(),
            "occurrence":    self.le_occurrence.text().strip(),
            "customer_open": self.le_customer_open.text().strip(),
            "hzt":           self.hzt_table.get_state(),
            "attachments":   [c.path for c in self._attach_chips],
        }

    def set_data(self, d: dict):
        """get_data() 가 반환한 dict 를 받아 위젯 상태를 복원."""
        if not isinstance(d, dict):
            return
        self.le_title.setText(d.get("title", "") or "")
        self.le_jira.setText(d.get("jira", "") or "")
        self.te_phenom.setPlainText(d.get("phenom", "") or "")
        self.te_analysis.setPlainText(d.get("analysis", "") or "")
        self.te_action.setPlainText(d.get("action", "") or "")
        self.le_occurrence.setText(d.get("occurrence", "") or "")
        self.le_customer_open.setText(d.get("customer_open", "") or "")
        hzt = d.get("hzt") or {}
        if isinstance(hzt, dict):
            self.hzt_table.set_state(hzt)
        # 첨부 파일 — 존재하는 경로만 칩 복원 (삭제된 임시 파일은 건너뜀)
        for p in (d.get("attachments") or []):
            if isinstance(p, str) and p and os.path.exists(p):
                self._add_chip(p)


# ══════════════════════════════════════════════════════════════
#  SpecChangeBlock — 사양변경 탭 본문 (제목/JIRA/변경 내용/수평전개/첨부)
# ══════════════════════════════════════════════════════════════
class SpecChangeBlock(QFrame):
    """사양변경 탭의 본문 묶음 (다중 묶음 지원).

    구성: 제목 / JIRA 링크 / 변경 내용 / 수평전개 / 첨부 파일.
    ChangeItemBlock 과 동일한 레이아웃 패턴 — 다중 추가/삭제 지원,
    Codebeamer 등록은 헤더의 [📤 등록] 버튼.
    """

    delete_requested   = pyqtSignal(object)
    register_requested = pyqtSignal(object)

    def __init__(self, index: int = 1, parent=None):
        super().__init__(parent)
        self.setObjectName("spec_block")
        self.setStyleSheet(
            f"#spec_block {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        self._index = index
        self._attach_chips: list[AttachmentChip] = []
        self._build()
        _shadow(self)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # 헤더
        hdr = QFrame(); hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 10, 0); hl.setSpacing(8)
        self._title_lbl = QLabel(f"📐  사양변경  #{self._index}")
        self._title_lbl.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(self._title_lbl); hl.addStretch()

        reg_btn = QPushButton("📤  등록")
        reg_btn.setFixedHeight(24)
        reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reg_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.BLUE};"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:1px 12px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BLUE}; color:#FFFFFF; }}")
        reg_btn.setToolTip("이 사양변경을 Codebeamer 에 새 이슈/코멘트로 등록")
        reg_btn.clicked.connect(lambda: self.register_requested.emit(self))
        hl.addWidget(reg_btn)

        del_btn = QPushButton("✕  삭제")
        del_btn.setFixedHeight(24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.RED};"
            f"  border:1px solid {C.RED}; border-radius:5px;"
            f"  padding:1px 12px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.RED}; color:#FFFFFF; }}")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        hl.addWidget(del_btn)
        lay.addWidget(hdr)

        # 본문
        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(10)

        # 제목 / JIRA 링크
        r0, self.le_title = self._line_row("제목",      "예) 사양 변경 제목")
        bl.addLayout(r0)
        r1, self.le_jira  = self._line_row("JIRA 링크", "예) https://jira.example.com/browse/ABC-123")
        bl.addLayout(r1)

        # 변경 내용 (다른 텍스트 필드보다 큰 영역)
        bl.addLayout(self._text_row("변경 내용", "사양 변경 내용을 작성하세요"))

        # 발생시점
        r2, self.le_occurrence = self._line_row("발생시점", "예) P2 (NX5)")
        bl.addLayout(r2)

        # 수평전개
        sub_hdr = QLabel("수평전개")
        sub_hdr.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        sub_hdr.setStyleSheet(f"color:{C.T2}; background:transparent; padding-top:4px;")
        bl.addWidget(sub_hdr)
        self.hzt_table = HorizontalDeployTable()
        bl.addWidget(self.hzt_table)

        # 첨부 파일 섹션
        atc_hdr = QHBoxLayout(); atc_hdr.setSpacing(8); atc_hdr.setContentsMargins(0, 6, 0, 0)
        atc_lbl = QLabel("첨부 파일")
        atc_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        atc_lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")
        atc_hdr.addWidget(atc_lbl); atc_hdr.addStretch()

        add_file_btn = QPushButton("➕  파일 추가")
        add_file_btn.setFixedHeight(24)
        add_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_file_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.BLUE};"
            f"  border:1px dashed {C.BLUE}; border-radius:5px;"
            f"  padding:1px 12px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
        add_file_btn.setToolTip("사양변경에 함께 업로드할 파일을 선택")
        add_file_btn.clicked.connect(self._on_add_files)
        atc_hdr.addWidget(add_file_btn)
        bl.addLayout(atc_hdr)

        self._attach_holder = QFrame(); self._attach_holder.setObjectName("attach_holder")
        self._attach_holder.setStyleSheet("#attach_holder { background:transparent; }")
        self._attach_lay = QVBoxLayout(self._attach_holder)
        self._attach_lay.setContentsMargins(0, 4, 0, 0); self._attach_lay.setSpacing(4)
        self._attach_placeholder = QLabel("선택된 파일이 없습니다.")
        self._attach_placeholder.setFont(QFont(C.FUI, 9))
        self._attach_placeholder.setStyleSheet(
            f"color:{C.T3}; background:transparent; padding:2px 4px;")
        self._attach_lay.addWidget(self._attach_placeholder)
        bl.addWidget(self._attach_holder)

        lay.addWidget(body)

    @staticmethod
    def _line_row(label: str, placeholder: str):
        row = QHBoxLayout(); row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setFixedWidth(96)
        lbl.setFont(QFont(C.FUI, 10))
        lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")
        row.addWidget(lbl)
        le = QLineEdit(); le.setObjectName("le_info")
        le.setPlaceholderText(placeholder)
        le.setFixedHeight(28)
        row.addWidget(le)
        return row, le

    def _text_row(self, label: str, placeholder: str):
        row = QHBoxLayout(); row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setFixedWidth(96)
        lbl.setFont(QFont(C.FUI, 10))
        lbl.setStyleSheet(
            f"color:{C.T2}; background:transparent; padding-top:4px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        row.addWidget(lbl)
        te = PasteableTextEdit(); te.setObjectName("te_info")
        te.setPlaceholderText(placeholder + "  (Ctrl+V 로 이미지 붙여넣기 지원)")
        te.setFixedHeight(120)
        te.image_pasted.connect(self._on_image_pasted)
        row.addWidget(te)
        self.te_content = te
        return row

    # ── 첨부 파일 핸들러 ──────────────────────────────────────
    def _on_add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "첨부 파일 선택", "", "모든 파일 (*.*)")
        if not paths:
            return
        existing = {chip.path for chip in self._attach_chips}
        for p in paths:
            if p in existing:
                continue
            self._add_chip(p)

    def _add_chip(self, path: str):
        chip = AttachmentChip(path, self._attach_holder)
        chip.remove_requested.connect(self._remove_chip)
        self._attach_chips.append(chip)
        self._attach_placeholder.setVisible(False)
        self._attach_lay.addWidget(chip)

    def _remove_chip(self, chip: "AttachmentChip"):
        try:
            self._attach_chips.remove(chip)
        except ValueError:
            return
        chip.deleteLater()
        if not self._attach_chips:
            self._attach_placeholder.setVisible(True)

    def _on_image_pasted(self, path: str):
        if any(c.path == path for c in self._attach_chips):
            return
        self._add_chip(path)

    # ── 외부 API ──────────────────────────────────────────────
    def set_index(self, idx: int):
        self._index = idx
        self._title_lbl.setText(f"📐  사양변경  #{idx}")

    def get_data(self) -> dict:
        return {
            "title":       self.le_title.text().strip(),
            "jira":        self.le_jira.text().strip(),
            "content":     self.te_content.toPlainText().strip(),
            "occurrence":  self.le_occurrence.text().strip(),
            "hzt":         self.hzt_table.get_state(),
            "attachments": [c.path for c in self._attach_chips],
        }

    def set_data(self, d: dict):
        if not isinstance(d, dict):
            return
        self.le_title.setText(d.get("title", "") or "")
        self.le_jira.setText(d.get("jira", "") or "")
        self.te_content.setPlainText(d.get("content", "") or "")
        self.le_occurrence.setText(d.get("occurrence", "") or "")
        hzt = d.get("hzt") or {}
        if isinstance(hzt, dict):
            self.hzt_table.set_state(hzt)
        for p in (d.get("attachments") or []):
            if isinstance(p, str) and p and os.path.exists(p):
                self._add_chip(p)

    def is_empty(self) -> bool:
        if self.le_title.text().strip():
            return False
        if self.le_jira.text().strip():
            return False
        if self.te_content.toPlainText().strip():
            return False
        if self.le_occurrence.text().strip():
            return False
        if self._attach_chips:
            return False
        for v in self.hzt_table.get_state().values():
            if v not in ("미적용", False):
                return False
        return True

    def reset(self):
        self.le_title.clear()
        self.le_jira.clear()
        self.te_content.clear()
        self.le_occurrence.clear()
        for chip in list(self._attach_chips):
            self._attach_lay.removeWidget(chip)
            chip.deleteLater()
        self._attach_chips.clear()
        self._attach_placeholder.setVisible(True)
        self.hzt_table.set_state({})


# ══════════════════════════════════════════════════════════════
#  HztBlock — 수평전개 탭 본문 (제목/JIRA/수평전개 내용/수평전개)
# ══════════════════════════════════════════════════════════════
class HztBlock(QFrame):
    """수평전개 탭의 본문 묶음 (다중 묶음 지원).

    구성: 제목 / JIRA 링크 / 수평전개 내용 / 수평전개 차종 표.
    ChangeItemBlock 과 동일한 레이아웃 패턴 — 다중 추가/삭제 지원.
    첨부 파일은 없고, 헤더의 [📤 등록] 버튼으로 Codebeamer 에 등록 가능.
    """

    delete_requested   = pyqtSignal(object)
    register_requested = pyqtSignal(object)

    def __init__(self, index: int = 1, parent=None):
        super().__init__(parent)
        self.setObjectName("hzt_block")
        self.setStyleSheet(
            f"#hzt_block {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        self._index = index
        self._build()
        _shadow(self)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # 헤더
        hdr = QFrame(); hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 10, 0); hl.setSpacing(8)
        self._title_lbl = QLabel(f"🚗  수평전개  #{self._index}")
        self._title_lbl.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(self._title_lbl); hl.addStretch()

        reg_btn = QPushButton("📤  등록")
        reg_btn.setFixedHeight(24)
        reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reg_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.BLUE};"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:1px 12px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BLUE}; color:#FFFFFF; }}")
        reg_btn.setToolTip("이 수평전개를 Codebeamer 에 새 이슈/코멘트로 등록")
        reg_btn.clicked.connect(lambda: self.register_requested.emit(self))
        hl.addWidget(reg_btn)

        del_btn = QPushButton("✕  삭제")
        del_btn.setFixedHeight(24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.RED};"
            f"  border:1px solid {C.RED}; border-radius:5px;"
            f"  padding:1px 12px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.RED}; color:#FFFFFF; }}")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        hl.addWidget(del_btn)
        lay.addWidget(hdr)

        # 본문
        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(10)

        # 제목 / JIRA 링크
        r0, self.le_title = SpecChangeBlock._line_row("제목",      "예) 수평전개 제목")
        bl.addLayout(r0)
        r1, self.le_jira  = SpecChangeBlock._line_row("JIRA 링크", "예) https://jira.example.com/browse/ABC-123")
        bl.addLayout(r1)

        # 수평전개 내용
        bl.addLayout(self._content_row())

        # 발생시점
        r2, self.le_occurrence = SpecChangeBlock._line_row("발생시점", "예) P2 (NX5)")
        bl.addLayout(r2)

        # 수평전개 표
        sub_hdr = QLabel("수평전개")
        sub_hdr.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        sub_hdr.setStyleSheet(f"color:{C.T2}; background:transparent; padding-top:4px;")
        bl.addWidget(sub_hdr)
        self.hzt_table = HorizontalDeployTable()
        bl.addWidget(self.hzt_table)

        lay.addWidget(body)

    def _content_row(self):
        row = QHBoxLayout(); row.setSpacing(8)
        lbl = QLabel("수평전개 내용")
        lbl.setFixedWidth(96)
        lbl.setFont(QFont(C.FUI, 10))
        lbl.setStyleSheet(
            f"color:{C.T2}; background:transparent; padding-top:4px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        row.addWidget(lbl)
        te = PasteableTextEdit(); te.setObjectName("te_info")
        te.setPlaceholderText(
            "수평전개 진행 내용을 작성하세요  (Ctrl+V 로 이미지 붙여넣기 지원)")
        te.setFixedHeight(120)
        # 이미지 페이스트 — 마커는 본문에 삽입되지만 첨부 chip 이 없으므로 무시
        # (CB 업로드 시 마커가 본문에 남아도 워커가 안전하게 라벨로 변환)
        row.addWidget(te)
        self.te_content = te
        return row

    # ── 외부 API ──────────────────────────────────────────────
    def set_index(self, idx: int):
        self._index = idx
        self._title_lbl.setText(f"🚗  수평전개  #{idx}")

    def get_data(self) -> dict:
        return {
            "title":      self.le_title.text().strip(),
            "jira":       self.le_jira.text().strip(),
            "content":    self.te_content.toPlainText().strip(),
            "occurrence": self.le_occurrence.text().strip(),
            "hzt":        self.hzt_table.get_state(),
        }

    def set_data(self, d: dict):
        if not isinstance(d, dict):
            return
        self.le_title.setText(d.get("title", "") or "")
        self.le_jira.setText(d.get("jira", "") or "")
        self.te_content.setPlainText(d.get("content", "") or "")
        self.le_occurrence.setText(d.get("occurrence", "") or "")
        hzt = d.get("hzt") or {}
        if isinstance(hzt, dict):
            self.hzt_table.set_state(hzt)

    def is_empty(self) -> bool:
        if self.le_title.text().strip():
            return False
        if self.le_jira.text().strip():
            return False
        if self.te_content.toPlainText().strip():
            return False
        if self.le_occurrence.text().strip():
            return False
        for v in self.hzt_table.get_state().values():
            if v not in ("미적용", False):
                return False
        return True

    def reset(self):
        self.le_title.clear()
        self.le_jira.clear()
        self.te_content.clear()
        self.le_occurrence.clear()
        self.hzt_table.set_state({})


# ══════════════════════════════════════════════════════════════
#  SpecChangePage — ① 사양 변경
# ══════════════════════════════════════════════════════════════
class SpecChangePage(BasePage):
    """① 사양 변경 페이지.

    프로젝트 정보 카드 + 이슈 묶음 동적 리스트.
    """

    # 이슈 묶음 한 개만 CB 등록 요청 — (1-based index, item dict)
    change_register_requested      = pyqtSignal(int, dict)
    # 모든 이슈를 한 번에 CB 등록 요청 — list of (idx, data dict)
    change_register_all_requested  = pyqtSignal(list)
    # 사양변경 탭 본문 CB 등록 요청 — (item dict)
    spec_register_requested        = pyqtSignal(dict)
    # 수평전개 탭 본문 CB 등록 요청 — (item dict)
    hzt_register_requested         = pyqtSignal(dict)
    # [📥 트래커에서 불러오기] 클릭 — 컨트롤러가 CB fetch + 카테고리별 분배 수행
    load_requested                 = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("①", "사양 변경", parent)
        self._items: list[ChangeItemBlock] = []
        # 사양변경 / 수평전개 탭도 이슈 탭과 동일하게 다중 묶음 지원
        self._spec_blocks: list[SpecChangeBlock] = []
        self._hzt_blocks: list[HztBlock] = []
        self._build_content()
        self._install_header_actions()

    def _install_header_actions(self):
        """기본 [💾 결과물 저장] [📤 CB 업로드] 자리에 [📥 불러오기] +
        [🧹 전체 지우기] 추가.

        사양 변경 페이지는 AI 결과물 저장/업로드 흐름이 없고, 항목별 [📤 등록]
        과 헤더 [📤 전체 등록] 으로 CB 업로드를 제공하므로 헤더의 두 기본
        버튼은 노출하지 않는다.
        """
        # 기본 버튼 숨김
        self.header.save_btn.hide()
        self.header.upload_btn.hide()

        # ── 트래커에서 불러오기 버튼 ───────────────────────────
        # 시작 다이얼로그에서 입력한 ① 트래커 ID 의 모든 이슈를 fetch 해서
        # 이슈/사양변경/수평전개 카테고리별로 자동 분배.
        self.load_btn = QPushButton("📥  트래커에서 불러오기")
        self.load_btn.setObjectName("btn_sub")
        self.load_btn.setFixedHeight(30)
        self.load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_btn.setToolTip(
            "프로젝트 정보 다이얼로그에서 입력한 ① 트래커의 모든 이슈를\n"
            "이슈 / 사양변경 / 수평전개 탭으로 자동 분배해 불러옵니다.\n"
            "(기존 입력값은 모두 새 내용으로 대체됩니다)")
        self.load_btn.clicked.connect(self.load_requested.emit)
        self.header.layout().addWidget(self.load_btn)

        # 전체 지우기 버튼
        self.clear_btn = QPushButton("🧹  전체 지우기")
        self.clear_btn.setObjectName("btn_sub")
        self.clear_btn.setFixedHeight(30)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setToolTip(
            "프로젝트 정보와 모든 이슈 입력을 초기 상태로 되돌립니다")
        self.clear_btn.clicked.connect(self._on_clear_all)
        self.header.layout().addWidget(self.clear_btn)

    def _build_content(self):
        # 레이아웃:
        #   ┌────────────────────────────────┐
        #   │ PR 정보 카드 (탭 공통, 항상 표시)        │
        #   ├────────────────────────────────┤
        #   │ [이슈] [사양변경] [수평전개]        │  ← TabBar
        #   │ 탭별 컨텐츠                          │
        #   └────────────────────────────────┘
        body = QWidget()
        body.setStyleSheet(f"background:{C.BG_APP};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0); body_lay.setSpacing(0)

        # (1) PR 정보 카드 — 탭 위에 고정 (모든 탭 공통)
        top = QWidget(); top.setStyleSheet("background:transparent;")
        top_lay = QVBoxLayout(top)
        top_lay.setContentsMargins(20, 18, 20, 12); top_lay.setSpacing(0)
        top_lay.addWidget(self._build_project_card())
        body_lay.addWidget(top)

        # (2) 탭으로 나뉜 본문 영역
        issue_tab = self._build_issue_tab()
        spec_tab  = self._build_spec_change_tab()
        hzt_tab   = self._build_hzt_tab()

        self._tabs = TabStack([
            ("issue", "📋  이슈",    issue_tab),
            ("spec",  "📐  사양변경", spec_tab),
            ("hzt",   "🚗  수평전개", hzt_tab),
        ])
        body_lay.addWidget(self._tabs, stretch=1)

        self.add_body(body)

        # 기본 1개 묶음 (각 탭마다)
        self._add_item()
        self._add_spec()
        self._add_hzt()

    def _build_issue_tab(self) -> QWidget:
        """이슈 탭 본문 — 이슈 내용 헤더 + 이슈 묶음 리스트 + 추가 버튼.
        (PR 정보 카드는 탭 위에 공통으로 고정되므로 이 탭에 포함하지 않음)
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget()
        inner.setStyleSheet(f"background:{C.BG_APP};")
        self._inner_lay = QVBoxLayout(inner)
        self._inner_lay.setContentsMargins(20, 14, 20, 20)
        self._inner_lay.setSpacing(16)

        # 이슈 내용 영역 (📝 헤더 + 📤 전체 등록 버튼)
        self._inner_lay.addWidget(self._build_change_section_header())

        # 묶음 컨테이너
        self._items_holder = QWidget()
        self._items_holder.setStyleSheet("background:transparent;")
        self._items_lay = QVBoxLayout(self._items_holder)
        self._items_lay.setContentsMargins(0, 0, 0, 0); self._items_lay.setSpacing(14)
        self._inner_lay.addWidget(self._items_holder)

        # + 이슈 추가 버튼
        add_btn = QPushButton("➕  이슈 추가")
        add_btn.setFixedHeight(34)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BG_CARD}; color:{C.BLUE};"
            f"  border:1.5px dashed {C.BLUE}; border-radius:8px;"
            f"  font-size:11px; font-weight:bold; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
        add_btn.clicked.connect(self._add_item)
        self._inner_lay.addWidget(add_btn)

        self._inner_lay.addStretch()

        scroll.setWidget(inner)
        return scroll

    def _build_spec_change_tab(self) -> QWidget:
        """사양변경 탭 본문 — 이슈 탭과 동일 레이아웃.
        섹션 헤더(📐 + 전체 등록) + 묶음 컨테이너 + [➕ 사양변경 추가] 버튼.
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget()
        inner.setStyleSheet(f"background:{C.BG_APP};")
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(20, 14, 20, 20); iv.setSpacing(16)

        # 섹션 헤더 (📐 + 📤 전체 등록)
        iv.addWidget(self._build_section_header(
            "📐  사양변경 내용",
            tip="작성한 모든 사양변경을 한 번에 Codebeamer 트래커에 등록",
            on_register_all=self._register_all_spec_items,
        ))

        # 묶음 컨테이너
        self._spec_holder = QWidget()
        self._spec_holder.setStyleSheet("background:transparent;")
        self._spec_lay = QVBoxLayout(self._spec_holder)
        self._spec_lay.setContentsMargins(0, 0, 0, 0); self._spec_lay.setSpacing(14)
        iv.addWidget(self._spec_holder)

        # + 사양변경 추가 버튼
        add_btn = QPushButton("➕  사양변경 추가")
        add_btn.setFixedHeight(34)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BG_CARD}; color:{C.BLUE};"
            f"  border:1.5px dashed {C.BLUE}; border-radius:8px;"
            f"  font-size:11px; font-weight:bold; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
        add_btn.clicked.connect(self._add_spec)
        iv.addWidget(add_btn)

        iv.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_hzt_tab(self) -> QWidget:
        """수평전개 탭 본문 — 이슈 탭과 동일 레이아웃.
        섹션 헤더(🚗 + 전체 등록) + 묶음 컨테이너 + [➕ 수평전개 추가] 버튼.
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget()
        inner.setStyleSheet(f"background:{C.BG_APP};")
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(20, 14, 20, 20); iv.setSpacing(16)

        # 섹션 헤더 (🚗 + 📤 전체 등록)
        iv.addWidget(self._build_section_header(
            "🚗  수평전개 내용",
            tip="작성한 모든 수평전개를 한 번에 Codebeamer 트래커에 등록",
            on_register_all=self._register_all_hzt_items,
        ))

        # 묶음 컨테이너
        self._hzt_holder = QWidget()
        self._hzt_holder.setStyleSheet("background:transparent;")
        self._hzt_lay = QVBoxLayout(self._hzt_holder)
        self._hzt_lay.setContentsMargins(0, 0, 0, 0); self._hzt_lay.setSpacing(14)
        iv.addWidget(self._hzt_holder)

        # + 수평전개 추가 버튼
        add_btn = QPushButton("➕  수평전개 추가")
        add_btn.setFixedHeight(34)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BG_CARD}; color:{C.BLUE};"
            f"  border:1.5px dashed {C.BLUE}; border-radius:8px;"
            f"  font-size:11px; font-weight:bold; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
        add_btn.clicked.connect(self._add_hzt)
        iv.addWidget(add_btn)

        iv.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_section_header(self, title_text: str, *,
                              tip: str, on_register_all) -> QWidget:
        """이슈/사양변경/수평전개 탭 공통 — 좌측 accent + 제목 + [📤 전체 등록]."""
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(w); lay.setContentsMargins(2, 8, 2, 0); lay.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 18)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        lay.addWidget(accent)
        t = QLabel(title_text)
        t.setFont(QFont(C.FUI, 12, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.T1}; background:transparent;")
        lay.addWidget(t); lay.addStretch()

        all_btn = QPushButton("📤  전체 등록")
        all_btn.setFixedHeight(28)
        all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        all_btn.setToolTip(tip)
        all_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:6px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H};"
            f"  border-color:{C.ACCENT_H}; }}")
        all_btn.clicked.connect(on_register_all)
        lay.addWidget(all_btn)
        return w

    def _build_project_card(self) -> QFrame:
        card = QFrame(); card.setObjectName("proj_card")
        card.setStyleSheet(
            f"#proj_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        vl = QVBoxLayout(card); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)

        hdr = QFrame(); hdr.setFixedHeight(40)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 18)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        hl.addWidget(accent)
        t = QLabel("🗂  PR 정보")
        t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()
        vl.addWidget(hdr)

        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(8)

        r0, self.proj_name      = self._info_row("프로젝트명",   "예) NX5 PLBM 30Ah, BSP 변경 사항")
        r2, self.proj_ver_old   = self._info_row("변경 전 버전", "예) 1.2.0")
        r3, self.proj_ver_new   = self._info_row("변경 후 버전", "예) 1.2.1")
        r4, self.proj_author    = self._info_row("설계자",       "예) 홍길동")
        r5, self.proj_date      = self._info_row("수행일시",     "예) 2026-05-26 14:00")
        r6, self.proj_attendees = self._info_row("참석자",       "예) 홍길동, 김철수, 이영희")
        for r in (r0, r2, r3, r4, r5, r6):
            bl.addLayout(r)

        vl.addWidget(body)
        _shadow(card)
        return card

    def _build_change_section_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(w); lay.setContentsMargins(2, 8, 2, 0); lay.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 18)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        lay.addWidget(accent)
        t = QLabel("📝  이슈 내용")
        t.setFont(QFont(C.FUI, 12, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.T1}; background:transparent;")
        lay.addWidget(t); lay.addStretch()

        # 전체 등록 버튼 — 모든 이슈를 한 번에 트래커로 일괄 등록
        all_btn = QPushButton("📤  전체 등록")
        all_btn.setFixedHeight(28)
        all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        all_btn.setToolTip("작성한 모든 이슈를 한 번에 Codebeamer 트래커에 등록")
        all_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:6px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H};"
            f"  border-color:{C.ACCENT_H}; }}")
        all_btn.clicked.connect(self._register_all_items)
        lay.addWidget(all_btn)
        return w

    @staticmethod
    def _info_row(label_text: str, placeholder: str):
        row = QHBoxLayout(); row.setSpacing(8)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(96)
        lbl.setFont(QFont(C.FUI, 10))
        lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")
        row.addWidget(lbl)
        le = QLineEdit(); le.setObjectName("le_info")
        le.setFixedHeight(28)
        le.setPlaceholderText(placeholder)
        row.addWidget(le)
        return row, le

    # ── 전체 지우기 ────────────────────────────────────────────
    def _on_clear_all(self):
        """헤더 [🧹 전체 지우기] 버튼 핸들러 — 확인 후 초기화."""
        from view.ui_dialog import ConfirmDialog
        from PyQt6.QtWidgets import QDialog
        # 빈 상태(모든 필드 공백 + 이슈 1개 빈 상태) 면 다이얼로그 생략
        if self._is_empty():
            return
        dlg = ConfirmDialog(
            self,
            title="전체 지우기",
            headline="프로젝트 정보와 모든 이슈를 초기화합니다.",
            detail="입력한 내용은 복구할 수 없습니다.",
            primary_label="🧹  초기화",
            secondary_label="취소",
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._reset_all()

    def _is_empty(self) -> bool:
        """프로젝트 정보 & 이슈가 모두 빈 상태인지 검사."""
        for fld in (self.proj_name,
                    self.proj_ver_old, self.proj_ver_new, self.proj_author,
                    self.proj_date, self.proj_attendees):
            if fld.text().strip():
                return False
        if len(self._items) != 1:
            return False
        only = self._items[0].get_data()
        if any(only.get(k) for k in ("title", "jira", "phenom",
                                      "analysis", "action",
                                      "occurrence", "customer_open")):
            return False
        if only.get("attachments"):
            return False
        # 수평전개 — 한 칸이라도 미적용 외 상태면 비어있지 않음
        for v in (only.get("hzt") or {}).values():
            if v not in ("미적용", False):
                return False
        # 사양변경 / 수평전개 탭 본문도 모두 비어있는지 확인
        if len(self._spec_blocks) != 1 or not self._spec_blocks[0].is_empty():
            if any(not b.is_empty() for b in self._spec_blocks):
                return False
            if len(self._spec_blocks) > 1:
                return False
        if len(self._hzt_blocks) != 1 or not self._hzt_blocks[0].is_empty():
            if any(not b.is_empty() for b in self._hzt_blocks):
                return False
            if len(self._hzt_blocks) > 1:
                return False
        return True

    def _reset_all(self):
        """프로젝트 정보 + 모든 이슈/사양변경/수평전개 본문 초기화."""
        # 프로젝트 정보 필드 비우기
        for fld in (self.proj_name,
                    self.proj_ver_old, self.proj_ver_new, self.proj_author,
                    self.proj_date, self.proj_attendees):
            fld.clear()
        # 이슈 묶음 모두 제거 후 빈 묶음 1개 재생성
        for block in list(self._items):
            block.deleteLater()
        self._items.clear()
        self._add_item()
        # 사양변경 묶음 모두 제거 후 빈 묶음 1개 재생성
        for block in list(self._spec_blocks):
            block.deleteLater()
        self._spec_blocks.clear()
        self._add_spec()
        # 수평전개 묶음 모두 제거 후 빈 묶음 1개 재생성
        for block in list(self._hzt_blocks):
            block.deleteLater()
        self._hzt_blocks.clear()
        self._add_hzt()

    # ── 묶음 add / delete ─────────────────────────────────────
    def _add_item(self):
        idx = len(self._items) + 1
        block = ChangeItemBlock(idx)
        block.delete_requested.connect(self._delete_item)
        block.register_requested.connect(self._register_item)
        self._items.append(block)
        self._items_lay.addWidget(block)

    def _delete_item(self, block: ChangeItemBlock):
        if len(self._items) <= 1:
            # 마지막 묶음은 삭제 불가 (최소 1개 유지)
            return
        try:
            self._items.remove(block)
        except ValueError:
            return
        block.deleteLater()
        # 인덱스 재번호
        for i, b in enumerate(self._items, start=1):
            b.set_index(i)

    def _register_item(self, block: ChangeItemBlock):
        try:
            idx = self._items.index(block) + 1
        except ValueError:
            return
        self.change_register_requested.emit(idx, block.get_data())

    def _register_all_items(self):
        """모든 이슈를 (1-based 인덱스와 함께) 일괄 등록 시그널로 emit."""
        payload = [(i, b.get_data()) for i, b in enumerate(self._items, start=1)]
        self.change_register_all_requested.emit(payload)

    # ── 사양변경 묶음 add / delete / register ─────────────────
    def _add_spec(self):
        idx = len(self._spec_blocks) + 1
        block = SpecChangeBlock(idx)
        block.delete_requested.connect(self._delete_spec)
        block.register_requested.connect(self._register_spec)
        self._spec_blocks.append(block)
        self._spec_lay.addWidget(block)

    def _delete_spec(self, block: "SpecChangeBlock"):
        if len(self._spec_blocks) <= 1:
            return
        try:
            self._spec_blocks.remove(block)
        except ValueError:
            return
        block.deleteLater()
        for i, b in enumerate(self._spec_blocks, start=1):
            b.set_index(i)

    def _register_spec(self, block: "SpecChangeBlock"):
        """블록 [📤 등록] 클릭 — 단건 등록 시그널을 그대로 emit."""
        self.spec_register_requested.emit(block.get_data())

    def _register_all_spec_items(self):
        """모든 사양변경 묶음을 순차 등록 — 컨트롤러가 단건 처리.
        (현재 컨트롤러는 단건 다이얼로그 흐름이므로 N 번 다이얼로그가 순차로 뜸)
        """
        for block in self._spec_blocks:
            data = block.get_data()
            # 빈 묶음(제목/내용 모두 공백)은 스킵
            if not any((data.get("title"), data.get("jira"),
                        data.get("content"), data.get("occurrence"))):
                continue
            self.spec_register_requested.emit(data)

    # ── 수평전개 묶음 add / delete / register ─────────────────
    def _add_hzt(self):
        idx = len(self._hzt_blocks) + 1
        block = HztBlock(idx)
        block.delete_requested.connect(self._delete_hzt)
        block.register_requested.connect(self._register_hzt)
        self._hzt_blocks.append(block)
        self._hzt_lay.addWidget(block)

    def _delete_hzt(self, block: "HztBlock"):
        if len(self._hzt_blocks) <= 1:
            return
        try:
            self._hzt_blocks.remove(block)
        except ValueError:
            return
        block.deleteLater()
        for i, b in enumerate(self._hzt_blocks, start=1):
            b.set_index(i)

    def _register_hzt(self, block: "HztBlock"):
        self.hzt_register_requested.emit(block.get_data())

    def _register_all_hzt_items(self):
        for block in self._hzt_blocks:
            data = block.get_data()
            if not any((data.get("title"), data.get("jira"),
                        data.get("content"), data.get("occurrence"))):
                continue
            self.hzt_register_requested.emit(data)

    # ── 세션 간 상태 저장 / 복원 ───────────────────────────────
    @staticmethod
    def _state_file_path() -> str:
        """spec_state.json 절대 경로 — cb_config.json 과 동일한 데이터 디렉터리 사용."""
        from integrations.codebeamer import _BASE
        return os.path.join(_BASE, "spec_state.json")

    def to_state(self) -> dict:
        """현재 페이지 전체 상태를 JSON 직렬화 가능한 dict 로 반환."""
        return {
            "project":      self.get_project_meta(),
            "items":        self.get_change_items(),
            # 신규: 다중 묶음 리스트로 저장
            "spec_changes": [b.get_data() for b in self._spec_blocks],
            "hzt_items":    [b.get_data() for b in self._hzt_blocks],
        }

    def apply_state(self, state: dict):
        """to_state() 결과를 받아 페이지 위젯들에 복원.
        구버전 단일 dict 키(`spec_change` / `hzt_item`) 도 백워드 호환.
        """
        if not isinstance(state, dict):
            return
        proj = state.get("project") or {}
        if isinstance(proj, dict):
            self.proj_name.setText(proj.get("name", "") or "")
            self.proj_ver_old.setText(proj.get("ver_old", "") or "")
            self.proj_ver_new.setText(proj.get("ver_new", "") or "")
            self.proj_author.setText(proj.get("author", "") or "")
            self.proj_date.setText(proj.get("pr_date", "") or "")
            self.proj_attendees.setText(proj.get("attendees", "") or "")
        items = state.get("items") or []
        if isinstance(items, list) and items:
            # 기존(생성자 단계에서 만든) 빈 묶음 모두 제거
            for block in list(self._items):
                block.deleteLater()
            self._items.clear()
            # 저장된 묶음 복원 (1개라도 있으면 그대로)
            for item_data in items:
                self._add_item()
                self._items[-1].set_data(item_data)
            # 인덱스 라벨 재번호 (헤더 "이슈 #N")
            for i, b in enumerate(self._items, start=1):
                b.set_index(i)

        # 사양변경 탭 본문 복원 (신규 리스트 키 우선, 없으면 구 단일 dict 폴백)
        spec_list = state.get("spec_changes")
        if not isinstance(spec_list, list):
            legacy = state.get("spec_change")
            spec_list = [legacy] if isinstance(legacy, dict) else []
        if spec_list:
            for block in list(self._spec_blocks):
                block.deleteLater()
            self._spec_blocks.clear()
            for d in spec_list:
                if isinstance(d, dict):
                    self._add_spec()
                    self._spec_blocks[-1].set_data(d)
            for i, b in enumerate(self._spec_blocks, start=1):
                b.set_index(i)

        # 수평전개 탭 본문 복원 (동일 패턴)
        hzt_list = state.get("hzt_items")
        if not isinstance(hzt_list, list):
            legacy = state.get("hzt_item")
            hzt_list = [legacy] if isinstance(legacy, dict) else []
        if hzt_list:
            for block in list(self._hzt_blocks):
                block.deleteLater()
            self._hzt_blocks.clear()
            for d in hzt_list:
                if isinstance(d, dict):
                    self._add_hzt()
                    self._hzt_blocks[-1].set_data(d)
            for i, b in enumerate(self._hzt_blocks, start=1):
                b.set_index(i)

    def save_state(self):
        """현재 상태를 spec_state.json 에 저장 — 앱 종료 시 호출."""
        try:
            path = self._state_file_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_state(), f, ensure_ascii=False, indent=2)
        except Exception:
            # 저장 실패는 무시 — 사용자 흐름을 방해하지 않음
            pass

    # ── CB 트래커 불러오기 결과 적용 ─────────────────────────
    def apply_loaded_items(self, classified: dict) -> dict:
        """spec_md_parser.classify_items() 결과를 받아 세 탭에 묶음 복원.

        Args:
          classified: {"issue":[parsed,...], "spec":[parsed,...],
                       "hzt":[parsed,...], "other":[...]}
            각 parsed dict 는 spec_md_parser.parse_item_md() 의 결과.

        Returns:
          {"issue": N, "spec": N, "hzt": N, "other": N}  — 적용된 갯수
        """
        issues = (classified or {}).get("issue") or []
        specs  = (classified or {}).get("spec")  or []
        hzts   = (classified or {}).get("hzt")   or []
        others = (classified or {}).get("other") or []

        # 1) 이슈 탭 — 기존 묶음 비우고 새로 만듦. 0건이면 빈 묶음 1개 유지.
        for b in list(self._items):
            b.deleteLater()
        self._items.clear()
        if not issues:
            self._add_item()
        else:
            for parsed in issues:
                self._add_item()
                self._items[-1].set_data({
                    "title":      parsed.get("title")    or "",
                    "jira":       parsed.get("jira")     or "",
                    "phenom":     parsed.get("phenom")   or "",
                    "analysis":   parsed.get("analysis") or "",
                    "action":     parsed.get("action")   or "",
                    # 이슈 카테고리엔 발생시점/고객OPEN 없음 — 빈 값
                    "occurrence":    "",
                    "customer_open": "",
                    "hzt":        parsed.get("hzt")      or {},
                    "attachments": [],   # CB 첨부 다운로드는 별도 작업 (1차엔 미적용)
                })
            for i, b in enumerate(self._items, start=1):
                b.set_index(i)

        # 2) 사양변경 탭
        for b in list(self._spec_blocks):
            b.deleteLater()
        self._spec_blocks.clear()
        if not specs:
            self._add_spec()
        else:
            for parsed in specs:
                self._add_spec()
                self._spec_blocks[-1].set_data({
                    "title":      parsed.get("title")    or "",
                    "jira":       parsed.get("jira")     or "",
                    "content":    parsed.get("content")  or "",
                    "occurrence": parsed.get("occurrence") or "",
                    "hzt":        parsed.get("hzt")      or {},
                    "attachments": [],
                })
            for i, b in enumerate(self._spec_blocks, start=1):
                b.set_index(i)

        # 3) 수평전개 탭
        for b in list(self._hzt_blocks):
            b.deleteLater()
        self._hzt_blocks.clear()
        if not hzts:
            self._add_hzt()
        else:
            for parsed in hzts:
                self._add_hzt()
                self._hzt_blocks[-1].set_data({
                    "title":      parsed.get("title")    or "",
                    "jira":       parsed.get("jira")     or "",
                    "content":    parsed.get("content")  or "",
                    "occurrence": parsed.get("occurrence") or "",
                    "hzt":        parsed.get("hzt")      or {},
                    "attachments": [],
                })
            for i, b in enumerate(self._hzt_blocks, start=1):
                b.set_index(i)

        return {
            "issue": len(issues),
            "spec":  len(specs),
            "hzt":   len(hzts),
            "other": len(others),
        }

    def load_state(self):
        """spec_state.json 이 있으면 페이지 상태를 복원 — 앱 시작 시 호출."""
        try:
            path = self._state_file_path()
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.apply_state(data)
        except Exception:
            pass

    # ── 외부에서 호출 — 기존 InputPanel 호환 ─────────────────
    def get_project_meta(self) -> dict:
        """CB 업로드 헤더용 메타데이터."""
        return {
            "name":      self.proj_name.text().strip(),
            "ver_old":   self.proj_ver_old.text().strip(),
            "ver_new":   self.proj_ver_new.text().strip(),
            "author":    self.proj_author.text().strip(),
            "pr_date":   self.proj_date.text().strip(),
            "attendees": self.proj_attendees.text().strip(),
            # 호환용 (_build_summary 가 meta['date'] 폴백을 today() 로 함)
            "date":      "",
        }

    def get_project_name(self) -> str:
        return self.proj_name.text().strip()

    def get_project_header_md(self) -> str:
        """CB 업로드 본문 최상단 마크다운.
        헤더는 헤딩(##) 대신 일반 텍스트로 — CB 자동섹션 번호(1.1) 가 안 붙도록.
        표는 HTML <table> 임베드 — CB 위키 마크다운 렌더러의 표 separator 버그 회피.
        트래커 모드에선 _md_to_html 이 HTML 블록을 통과시켜 동일하게 동작.
        인라인 스타일은 수평전개 표와 동일 톤으로 통일.
        """
        import html as _html
        # ── 스타일 정의 (수평전개 표와 동일 톤) ──────────────────
        tbl_style = ("border-collapse:collapse;width:100%;"
                     "table-layout:fixed;margin:6px 0 14px;")
        th_style  = ("padding:9px 12px;border:1px solid #BFDBFE;"
                     "background:#EFF6FF;color:#1D4ED8;"
                     "text-align:center;font-weight:700;font-size:13px;")
        td_lbl    = ("padding:8px 10px;border:1px solid #CBD5E1;"
                     "background:#F8FAFC;color:#1E293B;"
                     "font-weight:700;font-size:12px;width:110px;"
                     "text-align:center;")
        td_val    = ("padding:8px 14px;border:1px solid #CBD5E1;"
                     "background:#FFFFFF;color:#1E293B;font-size:12px;")
        # 헤더 라벨은 단일-셀 표 형태 — _md_to_html 의 <table> 통과
        # 분기와 호환 (다른 HTML 태그는 escape 됨)
        header_label_tbl = (
            '<table style="border-collapse:collapse;width:100%;'
            'table-layout:fixed;margin:6px 0;">'
            '<tr><td style="padding:9px 14px;border:1px solid #BFDBFE;'
            'border-left:5px solid #3B82F6;background:#EFF6FF;'
            'color:#1D4ED8;font-weight:700;font-size:13px;'
            'border-radius:4px;">📋 PR 정보</td>'
            '</tr></table>')

        rows = []
        for label, field in [
            ("변경내용요약",   self.proj_name),
            ("변경 전 (.ver)", self.proj_ver_old),
            ("변경 후 (.ver)", self.proj_ver_new),
            ("설계자",         self.proj_author),
            ("수행일시",       self.proj_date),
            ("참석자",         self.proj_attendees),
        ]:
            v = field.text().strip()
            if v:
                rows.append(
                    f'  <tr><td style="{td_lbl}">{_html.escape(label)}</td>'
                    f'<td style="{td_val}">{_html.escape(v)}</td></tr>')
        if not rows:
            return ""
        table = (f'<table style="{tbl_style}">\n'
                 f'  <tr><th style="{th_style}width:110px;">항목</th>'
                 f'<th style="{th_style}">내용</th></tr>\n'
                 + "\n".join(rows) + "\n"
                 "</table>")
        return header_label_tbl + "\n\n" + table

    def get_change_items(self) -> list[dict]:
        """현재 입력된 모든 이슈 묶음 데이터를 반환."""
        return [b.get_data() for b in self._items]

    def get_change_items_md(self) -> str:
        """CB 업로드 본문에 붙일 이슈 묶음 마크다운 (전체).
        각 이슈는 H1 (CB 자동번호 1./2./3. ...) 로 렌더링되므로
        별도 wrapper 헤딩은 두지 않는다. 모두 비어있으면 빈 문자열.
        """
        blocks = []
        for i, b in enumerate(self._items, start=1):
            md = self.render_change_item_md(i, b.get_data())
            if md:
                blocks.append(md)
        return "\n\n".join(blocks) if blocks else ""

    @staticmethod
    def render_change_item_md(idx: int, d: dict) -> str:
        """단일 이슈 묶음을 마크다운 블록으로 렌더링.
        제목/JIRA/현상/분석/대책 모두 비어있으면 빈 문자열.
        H1(`#`) 으로 렌더 — CB 자동섹션 번호가 1./2./3. 로 매겨지도록.
        """
        title    = (d.get("title")    or "").strip()
        jira     = (d.get("jira")     or "").strip()
        phenom   = (d.get("phenom")   or "").strip()
        analysis = (d.get("analysis") or "").strip()
        action   = (d.get("action")   or "").strip()
        if not any((title, jira, phenom, analysis, action)):
            return ""

        heading = f"# 📝 이슈 #{idx}"
        if title:
            heading += f" — {title}"
        lines = [heading, ""]

        jira_card = _md_jira_link_card(jira)
        if jira_card:
            lines += [jira_card, ""]

        if phenom:
            lines.append(_md_section_label("⚠️ 현상"))
            lines += ["", _md_normalize_user_text(_md_expand_image_markers(phenom)), ""]
        if analysis:
            lines.append(_md_section_label("🔍 분석 내용"))
            lines += ["", _md_normalize_user_text(_md_expand_image_markers(analysis)), ""]
        if action:
            lines.append(_md_section_label("✅ 대책"))
            lines += ["", _md_normalize_user_text(_md_expand_image_markers(action)), ""]

        hzt_table = _md_hzt_table(d.get("hzt") or {})
        if hzt_table:
            lines.append(_md_section_label("🚗 수평전개"))
            lines += ["", hzt_table]
        return "\n".join(lines)

    @staticmethod
    def render_spec_change_md(d: dict) -> str:
        """사양변경 본문(제목/JIRA/변경 내용/발생시점/수평전개) 을 마크다운으로
        렌더링. 모두 비어있으면 빈 문자열.
        """
        title      = (d.get("title")      or "").strip()
        jira       = (d.get("jira")       or "").strip()
        content    = (d.get("content")    or "").strip()
        occurrence = (d.get("occurrence") or "").strip()
        if not any((title, jira, content, occurrence)):
            return ""

        heading = "# 📐 사양변경"
        if title:
            heading += f" — {title}"
        lines = [heading, ""]

        jira_card = _md_jira_link_card(jira)
        if jira_card:
            lines += [jira_card, ""]

        if content:
            lines.append(_md_section_label("📐 변경 내용"))
            lines += ["", _md_normalize_user_text(_md_expand_image_markers(content)), ""]

        if occurrence:
            lines.append(_md_section_label("🕒 발생시점"))
            lines += ["", _md_normalize_user_text(occurrence), ""]

        hzt_table = _md_hzt_table(d.get("hzt") or {})
        if hzt_table:
            lines.append(_md_section_label("🚗 수평전개"))
            lines += ["", hzt_table]
        return "\n".join(lines)

    @staticmethod
    def render_hzt_item_md(d: dict) -> str:
        """수평전개 본문(제목/JIRA/수평전개 내용/발생시점/수평전개) 을 마크다운으로
        렌더링. 모두 비어있으면 빈 문자열.
        """
        title      = (d.get("title")      or "").strip()
        jira       = (d.get("jira")       or "").strip()
        content    = (d.get("content")    or "").strip()
        occurrence = (d.get("occurrence") or "").strip()
        if not any((title, jira, content, occurrence)):
            return ""

        heading = "# 🚗 수평전개"
        if title:
            heading += f" — {title}"
        lines = [heading, ""]

        jira_card = _md_jira_link_card(jira)
        if jira_card:
            lines += [jira_card, ""]

        if content:
            lines.append(_md_section_label("🚗 수평전개 내용"))
            lines += ["", _md_normalize_user_text(_md_expand_image_markers(content)), ""]

        if occurrence:
            lines.append(_md_section_label("🕒 발생시점"))
            lines += ["", _md_normalize_user_text(occurrence), ""]

        hzt_table = _md_hzt_table(d.get("hzt") or {})
        if hzt_table:
            lines.append(_md_section_label("🚗 적용 차종"))
            lines += ["", hzt_table]
        return "\n".join(lines)
