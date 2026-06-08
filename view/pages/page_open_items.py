"""page_open_items.py — ⑧ OPEN 항목 및 잔여 조치 사항 페이지.

표 구조 (사진의 표 양식과 동일한 그리드 셀):

  ┌────┬───────────────┬─────────────────────────┬───────────────────┐
  │ No │ 내용          │ 결과                    │ 코멘트            │
  ├────┼───────────────┼─────────────────────────┼───────────────────┤
  │ 1  │ 정적 검증     │ O / X                  │ (사용자 작성)      │
  ├────┼───────────────┼─────────────────────────┼───────────────────┤
  │    │               │ 🔴 High   N건           │ n/m건 조치 완료   │
  │ 2  │ 코드 리뷰     │ 🟡 Middle N건           │       〃          │
  │    │               │ 🟢 Low    N건           │       〃          │
  ├────┼───────────────┼─────────────────────────┼───────────────────┤
  │ 3  │ 설계자 테스트 │ O / X                  │ (사용자 작성)      │
  └────┴───────────────┴─────────────────────────┴───────────────────┘

사용자 입력 가능한 셀: **코멘트 칼럼만**.
나머지 결과 칼럼은 [📥 불러오기] 클릭 시 ⑤⑥⑦ 페이지 상태에서 자동 채움.

⑥ 코드 리뷰 High/Mid/Low 카운트:
  취약점 분석 마크다운 (sys_vuln_template.md 의 위험도 표) 에서 정규식 파싱.
  → 1차 구현은 현재 ⑥ 페이지의 마지막 vuln_md 한 건만 사용.
  향후 CB 의 다중 보고서 (처음 vs 마지막) 비교로 확장 예정.
"""

import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QGridLayout, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QScrollArea,
)

from config import C
from ._common import BasePage


# ── 컬럼 폭 (헤더와 데이터 셀이 동일 폭이라 정렬 보장) ────────────
_W_NO     = 50
_W_LABEL  = 150
_W_RESULT = 200
# 코멘트는 stretch

_ROW_H = 38       # 단일 행 높이
_HEADER_H = 36    # 헤더 행 높이


# ══════════════════════════════════════════════════════════════
#  공용 셀 헬퍼 — 모두 QLabel 기반 (사용자 편집 불가)
# ══════════════════════════════════════════════════════════════
def _hdr_cell(text: str, width: int = 0) -> QLabel:
    """파란 헤더 셀."""
    lb = QLabel(text)
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
    lb.setStyleSheet(
        f"color:#FFFFFF; background:{C.BLUE_DK};"
        f" border:1px solid {C.BLUE_DK}; padding:0;")
    lb.setMinimumHeight(_HEADER_H)
    lb.setMaximumHeight(_HEADER_H)
    if width > 0:
        lb.setFixedWidth(width)
    return lb


def _data_cell(text: str, *, width: int = 0, center: bool = False,
               bold: bool = False) -> QLabel:
    """일반 데이터 셀 (No / 내용)."""
    lb = QLabel(text)
    if center:
        lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    else:
        lb.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    weight = QFont.Weight.DemiBold if bold else QFont.Weight.Normal
    lb.setFont(QFont(C.FUI, 10, weight))
    lb.setStyleSheet(
        f"color:{C.T0}; background:{C.BG_CARD};"
        f" border:1px solid {C.BDR}; padding:4px 12px;")
    lb.setMinimumHeight(_ROW_H)
    if width > 0:
        lb.setFixedWidth(width)
    return lb


def _result_cell(width: int = 0) -> QLabel:
    """결과 셀 — apply_loaded() 호출 전엔 '-' 표시, 호출 후 색상 반영."""
    lb = QLabel("-")
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
    lb.setStyleSheet(
        f"color:{C.T3}; background:{C.BG_CARD};"
        f" border:1px solid {C.BDR}; padding:4px 8px;")
    lb.setMinimumHeight(_ROW_H)
    if width > 0:
        lb.setFixedWidth(width)
    return lb


def _comment_cell(placeholder: str = "코멘트 입력") -> QLineEdit:
    """사용자가 직접 입력할 수 있는 유일한 셀 — 단일행 QLineEdit."""
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setMinimumHeight(_ROW_H)
    le.setStyleSheet(
        f"QLineEdit {{ background:{C.BG_INPUT}; color:{C.T0};"
        f"  border:1px solid {C.BDR}; padding:4px 10px;"
        f"  font-size:10px; }}"
        f"QLineEdit:focus {{ border-color:{C.BLUE}; }}")
    return le


def _apply_result_style(lbl: QLabel, value: str):
    """O / X / N/A 결과에 따라 셀 색상 적용."""
    v = (value or "").strip().upper()
    if v == "O":
        fg, bg = "#15803D", "#DCFCE7"      # 초록
    elif v == "X":
        fg, bg = "#B91C1C", "#FEE2E2"      # 빨강
    elif v == "N/A":
        fg, bg = C.T3, C.BG_PANEL          # 회색
    else:
        fg, bg = C.T3, C.BG_CARD           # 기본 (미설정)
    lbl.setText(value or "-")
    lbl.setStyleSheet(
        f"color:{fg}; background:{bg};"
        f" border:1px solid {C.BDR}; padding:4px 8px;"
        f" font-weight:700;")


def _apply_severity_text(lbl: QLabel, name: str, count_initial: int,
                         count_remaining: int = None):
    """심각도 셀 텍스트 + 색상.

    name             : "🔴 High" / "🟡 Middle" / "🟢 Low"
    count_initial    : 처음 발견 건수
    count_remaining  : 마지막 보고서 미해결 (None 이면 표시 안 함)
    """
    if count_initial == 0:
        text = f"{name}  0건"
    elif count_remaining is None:
        text = f"{name}  {count_initial}건"
    else:
        text = f"{name}  {count_initial}건 (남음 {count_remaining})"
    lbl.setText(text)
    # 심각도 색상은 항상 동일 (이름 안의 emoji 와 매칭)
    if name.startswith("🔴"):
        fg, bg = "#B91C1C", "#FEF2F2"
    elif name.startswith("🟡"):
        fg, bg = "#92400E", "#FEF3C7"
    else:
        fg, bg = "#15803D", "#F0FDF4"
    lbl.setStyleSheet(
        f"color:{fg}; background:{bg};"
        f" border:1px solid {C.BDR}; padding:4px 10px;"
        f" font-weight:700;")


# ══════════════════════════════════════════════════════════════
#  OpenItemsPage
# ══════════════════════════════════════════════════════════════
class OpenItemsPage(BasePage):
    """⑧ OPEN 항목 및 잔여 조치 사항."""

    load_requested = pyqtSignal()   # [📥 불러오기] 클릭

    # 코드 리뷰 sub-row 정의 (순서대로 그리드에 들어감)
    _SEVERITIES = [
        ("high", "🔴 High"),
        ("mid",  "🟡 Middle"),
        ("low",  "🟢 Low"),
    ]

    def __init__(self, parent=None):
        super().__init__("⑧", "OPEN 항목 및 잔여 조치 사항", parent)
        # 결과 라벨 / 코멘트 위젯 핸들
        self.static_result:  QLabel    = None
        self.static_comment: QLineEdit = None
        self.test_result:    QLabel    = None
        self.test_comment:   QLineEdit = None
        # {sev_key: {"result": QLabel, "comment": QLineEdit}}
        self.sev_widgets: dict = {}
        self._build_content()

    # ── UI 구성 ──────────────────────────────────────────────
    def _build_content(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget(); inner.setStyleSheet(f"background:{C.BG_APP};")
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(20, 18, 20, 18); outer.setSpacing(12)

        # 카드 컨테이너
        card = QFrame(); card.setObjectName("oi_card")
        card.setStyleSheet(
            f"#oi_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # 카드 헤더 (제목 + 불러오기 버튼)
        cl.addWidget(self._build_card_header())

        # 본문 — 그리드 표
        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 14, 14, 14); bl.setSpacing(0)
        bl.addWidget(self._build_grid_table())

        # 안내 문구
        hint = QLabel(
            "ℹ  결과(O/X·건수) 칸은 [📥 불러오기] 시 ⑤ 정적 / ⑥ 리뷰 / ⑦ 테스트 에서 "
            "자동 채워집니다. 사용자가 입력할 수 있는 칸은 코멘트 칸 뿐입니다.")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{C.T3}; background:transparent;"
            f" font-size:10px; padding:10px 2px 0 2px;")
        bl.addWidget(hint)

        cl.addWidget(body)
        outer.addWidget(card)
        outer.addStretch()
        scroll.setWidget(inner)
        self.add_body(scroll)

    def _build_card_header(self) -> QFrame:
        hdr = QFrame(); hdr.setFixedHeight(44)
        hdr.setStyleSheet(
            f"background:{C.BG_PANEL}; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 22)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        hl.addWidget(accent)
        t = QLabel("📋  OPEN 항목 점검표")
        t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()

        self.load_btn = QPushButton("📥  불러오기")
        self.load_btn.setFixedHeight(28)
        self.load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_btn.setToolTip(
            "⑤ 정적 검증 / ⑥ 코드리뷰 / ⑦ 설계자 테스트 결과를 자동으로 채웁니다.\n"
            "코멘트만 직접 작성하세요.")
        self.load_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}")
        self.load_btn.clicked.connect(self.load_requested.emit)
        hl.addWidget(self.load_btn)
        return hdr

    # ── 그리드 표 ────────────────────────────────────────────
    def _build_grid_table(self) -> QFrame:
        wrap = QFrame()
        wrap.setStyleSheet("background:transparent;")
        g = QGridLayout(wrap)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(0)   # 셀 사이 간격 0 — 셀 border 가 표 선 역할

        # ── 헤더 행 ─────────────────────────────────────────
        g.addWidget(_hdr_cell("No",     width=_W_NO),     0, 0)
        g.addWidget(_hdr_cell("내용",   width=_W_LABEL),  0, 1)
        g.addWidget(_hdr_cell("결과",   width=_W_RESULT), 0, 2)
        g.addWidget(_hdr_cell("코멘트"),                  0, 3)

        # ── 행 1 : 정적 검증 ─────────────────────────────────
        g.addWidget(_data_cell("1", width=_W_NO, center=True, bold=True), 1, 0)
        g.addWidget(_data_cell("정적 검증", width=_W_LABEL, bold=True),    1, 1)
        self.static_result = _result_cell(width=_W_RESULT)
        g.addWidget(self.static_result, 1, 2)
        self.static_comment = _comment_cell(
            "결과가 X 일 때 사유 / 조치 예정 등 코멘트 작성")
        g.addWidget(self.static_comment, 1, 3)

        # ── 행 2~4 : 코드 리뷰 (3-row span) ──────────────────
        # No / 내용 셀은 3행에 걸쳐 표시 (rowspan=3)
        g.addWidget(_data_cell("2", width=_W_NO, center=True, bold=True),
                    2, 0, 3, 1)
        g.addWidget(_data_cell("코드 리뷰", width=_W_LABEL, bold=True),
                    2, 1, 3, 1)

        for i, (key, name) in enumerate(self._SEVERITIES):
            row = 2 + i
            res = _result_cell(width=_W_RESULT)
            # 초기 상태 — 심각도 이름만 회색 안내로
            res.setText(f"{name}  -")
            res.setStyleSheet(
                f"color:{C.T3}; background:{C.BG_CARD};"
                f" border:1px solid {C.BDR}; padding:4px 10px;"
                f" font-weight:600;")
            g.addWidget(res, row, 2)

            cmt = _comment_cell(
                "조치 안된 항목 코멘트 작성 (예: '이러한 사유로 미반영')")
            g.addWidget(cmt, row, 3)
            self.sev_widgets[key] = {"result": res, "comment": cmt, "name": name}

        # ── 행 5 : 설계자 테스트 ─────────────────────────────
        g.addWidget(_data_cell("3", width=_W_NO, center=True, bold=True), 5, 0)
        g.addWidget(_data_cell("설계자 테스트", width=_W_LABEL, bold=True), 5, 1)
        self.test_result = _result_cell(width=_W_RESULT)
        g.addWidget(self.test_result, 5, 2)
        self.test_comment = _comment_cell(
            "O / X 무관 — 시험 누락 / 추가 시험 계획 등 코멘트 작성")
        g.addWidget(self.test_comment, 5, 3)

        # 코멘트 칼럼 stretch
        g.setColumnStretch(3, 1)

        return wrap

    # ── 공개 API : 컨트롤러가 호출 ──────────────────────────
    def apply_loaded(self, *,
                     static_has: bool,
                     test_has:   bool,
                     review_counts: dict,
                     review_remaining: dict = None):
        """⑤⑦ 첨부 + ⑥ 취약점 건수로 결과 칼럼 자동 채움.

        Args:
            static_has       : ⑤ 첨부 파일 ≥ 1 여부
            test_has         : ⑦ 첨부 파일 ≥ 1 여부
            review_counts    : {"high": N, "mid": N, "low": N}
                                ⑥ 페이지 첫 보고서 (또는 현재) 발견 건수
            review_remaining : 마지막 보고서 미해결 건수 (None 이면 표시 생략).
                                향후 CB 다중 보고서 비교 시 채워짐.
        """
        # 정적 검증 / 설계자 테스트
        _apply_result_style(self.static_result, "O" if static_has else "X")
        _apply_result_style(self.test_result,   "O" if test_has   else "X")

        # 코드 리뷰 — 심각도별 텍스트 + 코멘트 placeholder 갱신
        review_remaining = review_remaining or {}
        for key, name in self._SEVERITIES:
            w = self.sev_widgets.get(key)
            if w is None:
                continue
            m = int((review_counts    or {}).get(key) or 0)
            r = (review_remaining or {}).get(key)
            r_int = int(r) if r is not None else None
            _apply_severity_text(w["result"], name, m, r_int)

            # 코멘트 placeholder 자동 갱신 — 사용자가 어떤 형식으로 쓰면 좋을지 가이드
            if r_int is None:
                w["comment"].setPlaceholderText(
                    f"발견 {m}건. 조치 안된 항목 코멘트")
            else:
                done = max(m - r_int, 0)
                w["comment"].setPlaceholderText(
                    f"{done}/{m}건 조치 완료, 잔여 {r_int}건. 조치 안된 항목 코멘트")

    # ── CB 업로드용 마크다운 ──────────────────────────────────
    def render_markdown(self) -> str:
        lines = [
            "## ⑧ OPEN 항목 및 잔여 조치 사항",
            "",
            "| No | 내용 | 결과 | 코멘트 |",
            "|---|---|---|---|",
        ]

        s_val = (self.static_result.text() or "-").replace("\n", " ")
        s_cmt = self.static_comment.text().strip() or "-"
        lines.append(f"| 1 | 정적 검증 | {s_val} | {s_cmt} |")

        first = True
        for key, name in self._SEVERITIES:
            w = self.sev_widgets.get(key) or {}
            r_lbl = w.get("result")
            c_lbl = w.get("comment")
            result_txt = (r_lbl.text() if r_lbl else "-").replace("\n", " ")
            cmt        = (c_lbl.text().strip() if c_lbl else "") or "-"
            no    = "2" if first else " "
            label = "코드 리뷰" if first else " "
            lines.append(f"| {no} | {label} | {result_txt} | {cmt} |")
            first = False

        t_val = (self.test_result.text() or "-").replace("\n", " ")
        t_cmt = self.test_comment.text().strip() or "-"
        lines.append(f"| 3 | 설계자 테스트 | {t_val} | {t_cmt} |")

        return "\n".join(lines)

    # ── 세션 직렬화 ─────────────────────────────────────────
    def to_state(self) -> dict:
        """project_state.json 의 open_items 섹션에 저장할 dict."""
        out = {
            "static": {
                "result":  self.static_result.text() if self.static_result else "",
                "comment": self.static_comment.text() if self.static_comment else "",
            },
            "test": {
                "result":  self.test_result.text() if self.test_result else "",
                "comment": self.test_comment.text() if self.test_comment else "",
            },
        }
        for key, name in self._SEVERITIES:
            w = self.sev_widgets.get(key) or {}
            out[f"review_{key}"] = {
                "result":  w["result"].text() if w.get("result") else "",
                "comment": w["comment"].text() if w.get("comment") else "",
            }
        return out

    def apply_state(self, d: dict):
        """저장된 project_state.open_items 에서 복원 (결과 텍스트도 그대로 복원)."""
        if not isinstance(d, dict):
            return

        s = d.get("static") or {}
        v = s.get("result") or ""
        if v in ("O", "X"):
            _apply_result_style(self.static_result, v)
        elif v:
            self.static_result.setText(v)
        self.static_comment.setText(str(s.get("comment") or ""))

        t = d.get("test") or {}
        tv = t.get("result") or ""
        if tv in ("O", "X"):
            _apply_result_style(self.test_result, tv)
        elif tv:
            self.test_result.setText(tv)
        self.test_comment.setText(str(t.get("comment") or ""))

        for key, name in self._SEVERITIES:
            r = d.get(f"review_{key}") or {}
            w = self.sev_widgets.get(key) or {}
            if w.get("result") and r.get("result"):
                w["result"].setText(str(r["result"]))
            if w.get("comment"):
                w["comment"].setText(str(r.get("comment") or ""))


# ══════════════════════════════════════════════════════════════
#  취약점 마크다운 파서 — High / Mid / Low 건수 추출
# ══════════════════════════════════════════════════════════════
_VULN_TABLE_RE = re.compile(
    r"\|\s*🔴\s*High\s*\|\s*(\d+)\s*건"
    r"[\s\S]*?\|\s*🟡\s*Middle\s*\|\s*(\d+)\s*건"
    r"[\s\S]*?\|\s*🟢\s*Low\s*\|\s*(\d+)\s*건",
    re.MULTILINE,
)


def parse_vuln_severity_counts(md_text: str) -> dict:
    """⑥ 페이지 취약점 분석 마크다운에서 High/Mid/Low 건수 추출.

    예상 형식 (prompts/system/sys_vuln_template.md 참조):
      | 🔴 High   | N건 | ... |
      | 🟡 Middle | N건 | ... |
      | 🟢 Low    | N건 | ... |

    파싱 실패 시 {high:0, mid:0, low:0} 반환.
    """
    text = str(md_text or "")
    out = {"high": 0, "mid": 0, "low": 0}
    m = _VULN_TABLE_RE.search(text)
    if m:
        try:
            out["high"] = int(m.group(1))
            out["mid"]  = int(m.group(2))
            out["low"]  = int(m.group(3))
        except (TypeError, ValueError):
            pass
        return out
    # 폴백 — 표 형식이 깨졌을 때 라인 단위 검색
    for key, marker in (("high", "🔴 High"),
                        ("mid",  "🟡 Middle"),
                        ("low",  "🟢 Low")):
        mm = re.search(rf"{re.escape(marker)}[^\n|]*\|\s*(\d+)\s*건", text)
        if mm:
            try:
                out[key] = int(mm.group(1))
            except (TypeError, ValueError):
                pass
    return out
