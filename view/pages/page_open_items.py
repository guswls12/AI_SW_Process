"""page_open_items.py — ⑧ OPEN 항목 및 잔여 조치 페이지 (4단계 양식, 2026-06).

새 양식 (사용자 명세):

  ┌──────┬─────────────────────┬─────┬─────┬─────┬─────┬──────┬──────┬───────┬─────────┐
  │ 분류 │ 사양변경 리스트     │ SRS │ SAD │ SDD │ 정적│ 코드 │ 테스트│ 상태  │ 코멘트  │
  ├──────┼─────────────────────┼─────┼─────┼─────┼─────┼──────┼──────┼───────┼─────────┤
  │ 사양  │ 1. [사양변경] 제목  │  O  │ N/A │ N/A │  O  │      │  O   │ CLOSE │   -     │
  │ 이슈  │ 2. [이슈] 제목      │  O  │  O  │  O  │  O  │  X   │  X   │ OPEN  │ 진행 중 │
  └──────┴─────────────────────┴─────┴─────┴─────┴─────┴──────┴──────┴───────┴─────────┘

행 생성 데이터:
  · 변경점 = ① 사양변경 페이지의 [이슈 / 사양변경 / 수평전개] 묶음 모두 합침
  · 각 변경점의 카테고리(이슈/사양변경)와 제목으로 행 라벨 구성

결과 셀 채우기 ([📥 불러오기] 클릭 시):
  · SRS/SAD/SDD :
      ② ③ ④ 페이지의 change_load_card.is_no_change() 인 경우  → N/A
      매칭 결과(change_match_card.get_mappings()) 에 이 변경점 ID 가 있으면 → O
      없으면                                                       → X
  · 정적/테스트 : 변경점 무관 — 트래커에 첨부 있으면 모든 행에 O, 없으면 X
                  (사용자 협의 완료: 같은 정적 트래커 링크)
  · 코드리뷰   : 보류 (사용자 협의 대기) — 일단 "—" 표시

사용자가 직접 편집: 상태 (OPEN/CLOSE) + 코멘트
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QGridLayout, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QScrollArea,
)

from config import C
from ._common import BasePage


# ── 컬럼 폭 ───────────────────────────────────────────────────
_W_CAT     = 70    # [분류]
_W_TITLE   = 280   # 사양변경 리스트
_W_RESULT  = 60    # SRS/SAD/SDD/정적/코드리뷰/테스트 각각
_W_STATE   = 90    # 상태 (OPEN/CLOSE)
# 코멘트는 stretch

_ROW_H    = 36
_HEADER_H = 34


# ══════════════════════════════════════════════════════════════
#  공용 셀 헬퍼
# ══════════════════════════════════════════════════════════════
_TBL_HDR_BG = C.BLUE   # 하늘색 (#8BBDD0) — ⑧⑨ 표 헤더 공통


def _hdr_cell(text: str, width: int = 0) -> QLabel:
    lb = QLabel(text)
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
    lb.setStyleSheet(
        f"color:#FFFFFF; background:{_TBL_HDR_BG};"
        f" border:1px solid {_TBL_HDR_BG};"
        f" border-right:2px solid #FFFFFF;"
        f" padding:0;")
    lb.setMinimumHeight(_HEADER_H)
    lb.setMaximumHeight(_HEADER_H)
    if width > 0:
        lb.setFixedWidth(width)
    return lb


_DATA_CELL_BORDER = "border:1px solid #E2E8F0; border-right:2px solid #FFFFFF;"


def _cat_cell(category: str) -> QLabel:
    """[분류] 셀 — 사양변경 / 이슈 / 수평전개 카테고리 배지."""
    text_map = {
        "spec":  "사양변경",
        "issue": "이슈",
        "hzt":   "수평전개",
    }
    text = text_map.get(category, category or "-")
    lb = QLabel(text)
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
    color_map = {
        "사양변경": ("#1D4ED8", "#EFF6FF"),
        "이슈":     ("#92400E", "#FEF3C7"),
        "수평전개": ("#15803D", "#DCFCE7"),
    }
    fg, bg = color_map.get(text, (C.T3, C.BG_PANEL))
    lb.setStyleSheet(
        f"color:{fg}; background:{bg};"
        f" {_DATA_CELL_BORDER} padding:4px 6px;")
    lb.setFixedWidth(_W_CAT)
    lb.setMinimumHeight(_ROW_H)
    return lb


def _title_cell(idx: int, title: str) -> QLabel:
    lb = QLabel(f"{idx}. {title or '(제목 없음)'}")
    lb.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    lb.setFont(QFont(C.FUI, 10))
    lb.setStyleSheet(
        f"color:{C.T0}; background:{C.BG_CARD};"
        f" {_DATA_CELL_BORDER} padding:4px 12px;")
    lb.setFixedWidth(_W_TITLE)
    lb.setMinimumHeight(_ROW_H)
    return lb


def _result_cell() -> QLabel:
    """O / X / N/A / - 표시. apply_result 로 색상 동적 변경."""
    lb = QLabel("-")
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lb.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
    lb.setStyleSheet(
        f"color:{C.T3}; background:{C.BG_CARD};"
        f" {_DATA_CELL_BORDER} padding:4px 6px;")
    lb.setFixedWidth(_W_RESULT)
    lb.setMinimumHeight(_ROW_H)
    return lb


def _apply_result(lbl: QLabel, value: str):
    v = (value or "").strip().upper()
    if v == "O":
        fg, bg = "#15803D", "#DCFCE7"
    elif v == "X":
        fg, bg = "#B91C1C", "#FEE2E2"
    elif v == "N/A":
        fg, bg = "#92400E", "#FEF3C7"
    else:
        fg, bg = C.T3, C.BG_CARD
        v = "-"
    lbl.setText(v)
    lbl.setStyleSheet(
        f"color:{fg}; background:{bg};"
        f" {_DATA_CELL_BORDER} padding:4px 6px;"
        f" font-weight:700;")


class _StateToggle(QFrame):
    """OPEN / CLOSE 토글 — 두 버튼 중 하나만 활성색."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "OPEN"
        self.setFixedWidth(_W_STATE)
        self.setMinimumHeight(_ROW_H)
        self.setStyleSheet(
            f"background:{C.BG_CARD};"
            f" {_DATA_CELL_BORDER} padding:0;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2); lay.setSpacing(2)
        self._btn_open  = QPushButton("OPEN")
        self._btn_close = QPushButton("CLOSE")
        for b in (self._btn_open, self._btn_close):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFlat(True)
        self._btn_open.clicked.connect(lambda: self.set_state("OPEN"))
        self._btn_close.clicked.connect(lambda: self.set_state("CLOSE"))
        lay.addWidget(self._btn_open); lay.addWidget(self._btn_close)
        self._restyle()

    def _restyle(self):
        for b, key, on_fg, on_bg in (
            (self._btn_open,  "OPEN",  "#FFFFFF", "#B91C1C"),
            (self._btn_close, "CLOSE", "#FFFFFF", "#15803D"),
        ):
            if self._state == key:
                b.setStyleSheet(
                    f"QPushButton {{ background:{on_bg}; color:{on_fg};"
                    f"  border:none; border-radius:3px;"
                    f"  font-size:9px; font-weight:700; padding:2px 0; }}")
            else:
                b.setStyleSheet(
                    f"QPushButton {{ background:transparent; color:{C.T3};"
                    f"  border:none; border-radius:3px;"
                    f"  font-size:9px; font-weight:600; padding:2px 0; }}"
                    f"QPushButton:hover {{ color:{C.T1};"
                    f"  background:{C.BG_PANEL}; }}")

    def set_state(self, value: str):
        v = (value or "").strip().upper()
        if v not in ("OPEN", "CLOSE"):
            return
        self._state = v
        self._restyle()

    def currentText(self) -> str:
        return self._state


def _state_combo():
    """레거시 호환 — 새 _StateToggle 위젯 반환."""
    return _StateToggle()


def _comment_edit() -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText("코멘트 입력 (예: 테스트 진행 중)")
    le.setMinimumHeight(_ROW_H)
    le.setStyleSheet(
        f"QLineEdit {{ background:{C.BG_INPUT}; color:{C.T0};"
        f"  border:1px solid {C.BDR}; padding:4px 10px;"
        f"  font-size:10px; }}"
        f"QLineEdit:focus {{ border-color:{C.BLUE}; }}")
    return le


# ══════════════════════════════════════════════════════════════
#  OpenItemsPage
# ══════════════════════════════════════════════════════════════
class OpenItemsPage(BasePage):
    """⑧ OPEN 항목 및 잔여 조치 — 4단계 새 양식.

    변경점 N 개 행 + 각 ②~⑦ 페이지 결과 + 상태/코멘트.
    [📥 불러오기] 시 컨트롤러가 set_change_items(items) 와 apply_results(...) 호출.
    """

    load_requested = pyqtSignal()
    saved_now      = pyqtSignal()   # [💾 페이지 저장] 클릭 — main.py 가 project_state 저장

    # 행 row dict 키
    RESULT_COLS = ("srs", "sad", "sdd", "static", "review", "test")

    def __init__(self, parent=None):
        super().__init__("⑧", "OPEN 항목 및 잔여 조치", parent)
        self._rows: list[dict] = []   # [{cat, title, change_id, widgets:{...}}, ...]
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

        # ── 헤더 (제목 + 불러오기 버튼) ───────────────────────
        hdr_card = QFrame(); hdr_card.setFixedHeight(44)
        hdr_card.setStyleSheet(
            f"background:{C.BG_PANEL}; border-bottom:1px solid {C.BDR};"
            f" border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr_card); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
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
            "① 사양변경 페이지의 변경점 목록 + ②~⑦ 페이지 결과를 자동으로 채웁니다.")
        self.load_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}")
        self.load_btn.clicked.connect(self.load_requested.emit)
        hl.addWidget(self.load_btn)

        # 페이지 저장 버튼 — 다른 페이지의 [💾 페이지 저장] 과 동일 동작
        self.save_now_btn = QPushButton("💾  페이지 저장")
        self.save_now_btn.setFixedHeight(28)
        self.save_now_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_now_btn.setToolTip(
            "현재 입력한 상태/코멘트 + 결과 셀 값을 즉시 저장합니다.")
        self.save_now_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.BLUE};"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
        self.save_now_btn.clicked.connect(self.saved_now.emit)
        hl.addWidget(self.save_now_btn)
        cl.addWidget(hdr_card)

        # ── 표 본문 ────────────────────────────────────────────
        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 14, 14, 14); bl.setSpacing(0)

        # 표 그리드 — 헤더 + 행 누적
        self._grid_wrap = QFrame(); self._grid_wrap.setStyleSheet("background:transparent;")
        self._grid = QGridLayout(self._grid_wrap)
        self._grid.setContentsMargins(0, 0, 0, 0); self._grid.setSpacing(0)
        bl.addWidget(self._grid_wrap)

        # 헤더 행
        self._build_header_row()

        # 빈 상태 메시지
        self._empty_row_idx = 1
        self._empty_msg = QLabel(
            "📭  [📥 불러오기] 를 누르면 ① 사양변경 페이지의 변경점이 여기에 표시됩니다.")
        self._empty_msg.setFont(QFont(C.FUI, 10))
        self._empty_msg.setStyleSheet(
            f"color:{C.T3}; background:{C.BG_CARD};"
            f" border:1px solid {C.BDR}; padding:20px;"
            f" qproperty-alignment:'AlignCenter';")
        self._grid.addWidget(self._empty_msg, self._empty_row_idx, 0, 1, 10)

        # 안내 문구
        hint = QLabel(
            "ℹ  결과 셀(SRS/SAD/SDD/정적/코드리뷰/테스트) 은 자동 채워지며, "
            "상태(OPEN/CLOSE) 와 코멘트만 사용자가 편집 가능합니다.")
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

    def _build_header_row(self):
        cols = [
            ("[분류]",          _W_CAT),
            ("사양변경 리스트",   _W_TITLE),
            ("SRS",             _W_RESULT),
            ("SAD",             _W_RESULT),
            ("SDD",             _W_RESULT),
            ("정적",             _W_RESULT),
            ("코드리뷰",         _W_RESULT),
            ("테스트",           _W_RESULT),
            ("상태",             _W_STATE),
            ("코멘트",           0),
        ]
        for c, (label, w) in enumerate(cols):
            self._grid.addWidget(_hdr_cell(label, width=w), 0, c)
        # 마지막 컬럼(코멘트) stretch
        self._grid.setColumnStretch(9, 1)

    # ── 행 생성 / 초기화 ─────────────────────────────────────
    def set_change_items(self, items: list):
        """① 사양변경 페이지의 변경점 dict 리스트로 행 생성.

        items: [{"cat": "spec"/"issue"/"hzt", "title": str, "id": str(optional)}, ...]
        """
        # 기존 행 제거
        self._clear_data_rows()
        # 빈 상태 메시지 숨김
        self._empty_msg.setVisible(False)

        if not items:
            self._empty_msg.setVisible(True)
            self._empty_msg.setText(
                "📭  변경점이 없습니다. ① 사양변경 페이지에서 먼저 입력하세요.")
            return

        for i, it in enumerate(items, start=1):
            self._add_row(i, it)

    def _add_row(self, idx: int, item: dict):
        row = self._grid.rowCount()    # 헤더(0) 다음 행
        cat   = str(item.get("cat") or "")
        title = str(item.get("title") or "")
        cid   = str(item.get("id") or "")

        widgets = {
            "cat":     _cat_cell(cat),
            "title":   _title_cell(idx, title),
            "srs":     _result_cell(),
            "sad":     _result_cell(),
            "sdd":     _result_cell(),
            "static":  _result_cell(),
            "review":  _result_cell(),
            "test":    _result_cell(),
            "state":   _state_combo(),
            "comment": _comment_edit(),
        }
        col_order = ("cat", "title", "srs", "sad", "sdd",
                     "static", "review", "test", "state", "comment")
        for c, key in enumerate(col_order):
            self._grid.addWidget(widgets[key], row, c)

        self._rows.append({
            "cat":      cat,
            "title":    title,
            "change_id": cid,
            "widgets":  widgets,
        })

    def _clear_data_rows(self):
        """헤더(row 0) 외 모든 행 위젯 제거."""
        # _rows 의 모든 위젯 delete
        for r in self._rows:
            for w in r["widgets"].values():
                try:
                    w.setParent(None); w.deleteLater()
                except Exception:
                    pass
        self._rows.clear()

    # ── 결과 적용 ────────────────────────────────────────────
    def apply_results(self, results_by_change_id: dict, *,
                      static: str = "", review: str = "",
                      test: str = "") -> None:
        """컨트롤러가 [📥 불러오기] 시 호출.

        Args:
          results_by_change_id: {change_id: {"srs":"O/X/N/A","sad":...,"sdd":...,
                                              "review":"O/X/-" (선택)}}
          static, review, test : 모든 행에 동일 적용할 값 (협의 완료)
          ─ review 가 "" 면 results_by_change_id[cid]["review"] 를 행별로 적용
            (⑥ 코드리뷰 AI 매핑 결과 — 변경점별 OK/NG)
        """
        for r in self._rows:
            cid = r["change_id"]
            res = results_by_change_id.get(cid, {}) if isinstance(results_by_change_id, dict) else {}
            _apply_result(r["widgets"]["srs"],    res.get("srs", "X"))
            _apply_result(r["widgets"]["sad"],    res.get("sad", "X"))
            _apply_result(r["widgets"]["sdd"],    res.get("sdd", "X"))
            _apply_result(r["widgets"]["static"], static or "X")
            # 코드리뷰 — review 인자 우선, 없으면 행별 res["review"], 그것도 없으면 "X"
            review_val = review or res.get("review", "X")
            _apply_result(r["widgets"]["review"], review_val)
            _apply_result(r["widgets"]["test"],   test   or "X")

    # ── 직렬화 ───────────────────────────────────────────────
    def to_state(self) -> dict:
        rows = []
        for r in self._rows:
            w = r["widgets"]
            rows.append({
                "cat":       r["cat"],
                "title":     r["title"],
                "change_id": r["change_id"],
                "srs":       w["srs"].text(),
                "sad":       w["sad"].text(),
                "sdd":       w["sdd"].text(),
                "static":    w["static"].text(),
                "review":    w["review"].text(),
                "test":      w["test"].text(),
                "state":     w["state"].currentText(),
                "comment":   w["comment"].text().strip(),
            })
        return {"rows": rows}

    def apply_state(self, st: dict):
        if not isinstance(st, dict):
            return
        rows = st.get("rows") or []
        # 기존 행 재구성
        items = [{"cat": r.get("cat"), "title": r.get("title"),
                  "id":  r.get("change_id")} for r in rows]
        self.set_change_items(items)
        for r_dict, r in zip(rows, self._rows):
            w = r["widgets"]
            _apply_result(w["srs"],    r_dict.get("srs"))
            _apply_result(w["sad"],    r_dict.get("sad"))
            _apply_result(w["sdd"],    r_dict.get("sdd"))
            _apply_result(w["static"], r_dict.get("static"))
            _apply_result(w["review"], r_dict.get("review"))
            _apply_result(w["test"],   r_dict.get("test"))
            state = r_dict.get("state")
            if state in ("OPEN", "CLOSE"):
                w["state"].set_state(state)
            w["comment"].setText(r_dict.get("comment") or "")

    # ── CB 업로드용 마크다운 ──────────────────────────────────
    def render_markdown(self) -> str:
        lines = []
        lines.append("## ⑧ OPEN 항목 및 잔여 조치")
        lines.append("")
        if not self._rows:
            lines.append("(변경점 없음)")
            return "\n".join(lines)
        lines.append("| 분류 | 사양변경 리스트 | SRS | SAD | SDD | 정적 | 코드리뷰 | 테스트 | 상태 | 코멘트 |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in self._rows:
            w = r["widgets"]
            cat_text_map = {"spec": "사양변경", "issue": "이슈", "hzt": "수평전개"}
            cat_text = cat_text_map.get(r["cat"], r["cat"] or "-")
            title = r["title"] or "(제목 없음)"
            lines.append(
                f"| {cat_text} | {title} | "
                f"{w['srs'].text()} | {w['sad'].text()} | {w['sdd'].text()} | "
                f"{w['static'].text()} | {w['review'].text()} | {w['test'].text()} | "
                f"{w['state'].currentText()} | {w['comment'].text() or '-'} |"
            )
        return "\n".join(lines)


# ── 기존 컨트롤러 호환 (parse_vuln_severity_counts) — 코드리뷰 보류 ──
def parse_vuln_severity_counts(vuln_md: str) -> dict:
    """⑥ 코드리뷰 취약점 마크다운에서 High/Mid/Low 카운트 추정.
    4단계 보류 항목 (사용자 협의 대기) — 기존 동작 유지를 위해 함수만 보존.
    """
    import re
    text = vuln_md or ""
    counts = {"high": 0, "mid": 0, "low": 0}
    for sev_key, patterns in (
        ("high", [r"H-\d+", r"🔴"]),
        ("mid",  [r"M-\d+", r"🟡"]),
        ("low",  [r"L-\d+", r"🟢"]),
    ):
        cnt = 0
        for p in patterns:
            cnt = max(cnt, len(re.findall(p, text)))
        counts[sev_key] = cnt
    return counts
