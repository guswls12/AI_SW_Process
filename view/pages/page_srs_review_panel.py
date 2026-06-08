"""page_srs_review_panel.py — SRS 검토 워크플로우 UI 위젯 (SrsPage 에 임베드).

공개 위젯 (SwePage 가 마운트):
  - CbHistoricalSubTab    : INPUT 탭 2 — 변경점 트래커 + 과거차 트래커 fetch
  - ChecklistReviewSubTab : INPUT 탭 3 — 공통 체크리스트 + 4역할 검토 + 회의록 + AI 버튼
  - AiResultDropdownPanel : OUTPUT 탭 — 변경점별 AI 인사이트 결과 (드롭다운 선택)

내부 헬퍼:
  - _ItemListRenderer : CB fetch 결과 항목을 체크박스 리스트로 렌더링
  - _card_frame       : 공통 카드 컨테이너 (헤더 + 본문)

체크리스트/검토/회의록 템플릿:
  prompts/checklists/srs_review_default.json 에서 로드 (정적 파일 — JSON 직접 편집).

컨트롤러:
  SrsReviewV2Controller 가 시그널을 받아 CbFetcher / SrsReviewV2Worker /
  CbUploadWorker 흐름을 조율한다. 이 위젯은 순수 UI + 데이터 노출만 담당.
"""

import json
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QScrollArea, QCheckBox,
    QGraphicsDropShadowEffect, QComboBox,
)
from PyQt6.QtGui import QColor

from config import C


# ── 체크리스트 프리셋 로드 ─────────────────────────────────────
_DEFAULT_CHECKLIST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "prompts", "checklists", "srs_review_default.json",
)


def _load_default_checklist() -> list[dict]:
    """프리셋 JSON 에서 체크리스트 항목 로드.

    각 항목: {idx, name, question}
    파일이 없거나 손상되면 빈 리스트 반환 (컨트롤러가 경고 처리).
    """
    try:
        with open(_DEFAULT_CHECKLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items") or []
        out: list[dict] = []
        for j, it in enumerate(items, start=1):
            out.append({
                "idx":      it.get("idx") or j,
                "name":     str(it.get("name") or "").strip(),
                "question": str(it.get("question") or it.get("name") or "").strip(),
            })
        return out
    except (OSError, json.JSONDecodeError):
        return []


# ── 새 SRS 검토 템플릿 로더 (Phase 1 신규 구조, 2026-06-04) ─
def _load_srs_template() -> dict:
    """새 srs_review_default.json (재설계 v2) 통째 로드.

    반환 dict 구조:
      {
        "fixed_checklist": [
          {"id": ..., "section": ..., "question": ..., "guide": ...}, x5
        ],
        "engineer_review_template": {
          "sys":  {"label": ..., "icon": ..., "guides": [...]},
          "sw":   {...}, "hw": {...}, "test": {...}
        },
        "meeting_template": {
          "issues_placeholder":    "...",
          "decisions_placeholder": "...",
          "action_items_default":  [
            {"action": ..., "owner": ..., "due": ..., "status": ...}, x3
          ]
        }
      }
    파일 없거나 손상 시 빈 dict 반환 (UI 폴백).
    """
    try:
        with open(_DEFAULT_CHECKLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _shadow(widget, blur: int = 14, dy: int = 3, alpha: int = 18):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(0); eff.setYOffset(dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)


# ══════════════════════════════════════════════════════════════════════
#                                                                      |
#  ↓↓↓  Phase 2-1 신규 — 새 SRS 검토 워크플로우 UI 골격  ↓↓↓             |
#                                                                      |
#  사진의 5단계 운영 플로우를 반영한 새 입력 UI.                          |
#  Phase 2-1: 레이아웃 + 위젯만 (실제 fetch/AI 호출은 Phase 3).            |
#  Phase 2-2: 잠금/수정 토글 + 액션아이템 추가/삭제 로직.                   |
#                                                                      |
# ══════════════════════════════════════════════════════════════════════


def _card_frame(title: str, icon: str = "🔗") -> tuple:
    """공통 카드 컨테이너 — 헤더(액센트 바 + 제목) + 본문 QFrame 반환.

    Returns: (card QFrame, body QWidget) — caller 가 body 에 레이아웃 추가.
    """
    card = QFrame()
    card.setObjectName("srs_card")
    card.setStyleSheet(
        f"#srs_card {{ background:{C.BG_CARD};"
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
    t = QLabel(f"{icon}  {title}")
    t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
    t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
    hl.addWidget(t); hl.addStretch()
    vl.addWidget(hdr)

    body = QWidget(); body.setStyleSheet("background:transparent;")
    vl.addWidget(body)
    _shadow(card)
    return card, body


# ══════════════════════════════════════════════════════════════════════
#  _ItemListRenderer — CB fetch 결과 항목 리스트 카드 (체크박스 + #ID + 제목)
# ══════════════════════════════════════════════════════════════════════
class _ItemListRenderer(QFrame):
    """fetch 한 CB 트래커 항목 N개를 카드 안에 행으로 렌더링.

    각 행: [체크박스] [#ID] [제목]  (체크박스 default 체크됨)
    빈 상태에서는 안내 라벨만 표시. fetch 진행 중에는 set_loading_text() 로 표시.

    그룹핑:
      아이템 dict 에 `tracker_name` 키가 있고 서로 다른 트래커가 2개 이상이면
      트래커별 그룹 헤더 (이름 + 카운트 + 그룹 전체선택 체크박스) 로 분류해 표시.
      모두 같은 트래커거나 tracker_name 이 없으면 기존처럼 평면 리스트로 표시.

    공개 API:
      set_items(items)         — items 리스트로 행 재생성 (체크 상태 초기화 = 모두 체크)
      get_selected_items()     — 체크된 항목만 dict 리스트 반환
      get_all_items()          — 모든 항목 반환 (체크 무관)
      set_loading_text(text)   — 빈 영역에 로딩/오류 메시지 표시
    """

    def __init__(self, title: str, *, icon: str = "📋",
                 empty_text: str = "아직 불러온 항목이 없습니다.",
                 parent=None):
        super().__init__(parent)
        self._empty_text = empty_text
        self._items: list = []
        self._rows: list = []
        # 그룹 헤더 위젯 보관 — clear 시 일괄 제거용
        self._group_headers: list = []
        # 그룹 단위 선택 체크박스 — {tracker_name: (QCheckBox, [row, row, ...])}
        self._group_cbs: dict = {}
        # 그룹 체크박스 → 멤버 row 체크박스 사이 동기화 시 신호 루프 방지
        self._syncing_group: bool = False
        self.setObjectName("list_card")
        self.setStyleSheet(
            f"#list_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        self._build(title, icon)
        _shadow(self)

    def _build(self, title: str, icon: str):
        vl = QVBoxLayout(self); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)

        # 헤더 — 제목 + 카운트 + [☑ 전체선택/해제]
        hdr = QFrame(); hdr.setFixedHeight(40)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 18)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        hl.addWidget(accent)
        t = QLabel(f"{icon}  {title}")
        t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()

        self._count_lbl = QLabel("0개")
        self._count_lbl.setFont(QFont(C.FUI, 9))
        self._count_lbl.setStyleSheet(
            f"color:{C.T3}; background:transparent; padding-right:6px;")
        hl.addWidget(self._count_lbl)

        self._sel_all_btn = QPushButton("☑  전체 선택/해제")
        self._sel_all_btn.setFixedHeight(24)
        self._sel_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sel_all_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.T2};"
            f"  border:1px solid {C.BDR}; border-radius:5px;"
            f"  padding:1px 10px; font-size:10px; }}"
            f"QPushButton:hover {{ background:{C.BG_HOVER}; }}")
        self._sel_all_btn.clicked.connect(self._toggle_select_all)
        self._sel_all_btn.setEnabled(False)   # 항목 없으면 비활성
        hl.addWidget(self._sel_all_btn)
        vl.addWidget(hdr)

        # 본문 — 스크롤 + 행 컨테이너
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        scroll.setMinimumHeight(140)
        scroll.setMaximumHeight(360)

        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        self._rows_lay = QVBoxLayout(inner)
        self._rows_lay.setContentsMargins(10, 8, 10, 8)
        self._rows_lay.setSpacing(4)

        # 빈 상태 안내 라벨 (행 컨테이너 안에 항상 존재 — show/hide 로 제어)
        self._empty_lbl = QLabel(self._empty_text)
        self._empty_lbl.setFont(QFont(C.FUI, 9))
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color:{C.T3}; background:transparent; padding:24px;")
        self._rows_lay.addWidget(self._empty_lbl)
        self._rows_lay.addStretch()   # 행 들이 위로 쌓이도록

        scroll.setWidget(inner)
        vl.addWidget(scroll)

    # ── 행 렌더 ──────────────────────────────────────────────
    def _build_row(self, item: dict, *, indent: bool = False) -> QFrame:
        item_id = str(item.get("id") or "")
        title = str(item.get("name") or item.get("summary")
                    or item.get("title") or "(제목 없음)")

        row = QFrame(); row.setObjectName("list_row")
        row.setStyleSheet(
            f"#list_row {{ background:{C.BG_PANEL};"
            f"  border:1px solid {C.BDR}; border-radius:5px; }}"
            f"#list_row:hover {{ background:{C.BG_HOVER}; }}")
        row.setFixedHeight(34)
        rl = QHBoxLayout(row)
        # 그룹 모드일 때는 좌측 들여쓰기로 트리 느낌
        rl.setContentsMargins(22 if indent else 10, 0, 10, 0)
        rl.setSpacing(10)

        cb = QCheckBox(); cb.setChecked(True)
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        rl.addWidget(cb)

        id_lbl = QLabel(f"#{item_id}")
        id_lbl.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
        id_lbl.setFixedWidth(80)
        id_lbl.setStyleSheet(f"color:{C.BLUE_DK}; background:transparent;")
        rl.addWidget(id_lbl)

        t_lbl = QLabel(title)
        t_lbl.setFont(QFont(C.FUI, 10))
        t_lbl.setStyleSheet(f"color:{C.T1}; background:transparent;")
        rl.addWidget(t_lbl, 1)

        row._cb = cb
        row._item_data = item
        return row

    def _build_group_header(self, tracker_name: str, count: int) -> QFrame:
        """트래커별 그룹 헤더 — [체크박스] 트래커명 + 카운트 뱃지."""
        hdr = QFrame(); hdr.setObjectName("grp_hdr")
        hdr.setStyleSheet(
            f"#grp_hdr {{ background:{C.BLUE_LT};"
            f"  border:1px solid {C.BLUE}; border-radius:5px; }}")
        hdr.setFixedHeight(30)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(10, 0, 10, 0); hl.setSpacing(8)

        cb = QCheckBox(); cb.setChecked(True)
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.setToolTip(f"'{tracker_name}' 그룹 전체 선택/해제")
        hl.addWidget(cb)

        name_lbl = QLabel(f"🗂  {tracker_name}")
        name_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color:{C.BLUE_DK}; background:transparent;")
        hl.addWidget(name_lbl)
        hl.addStretch()

        cnt_lbl = QLabel(f"{count}개")
        cnt_lbl.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
        cnt_lbl.setStyleSheet(
            f"color:#FFFFFF; background:{C.BLUE};"
            f" border-radius:8px; padding:1px 8px;")
        hl.addWidget(cnt_lbl)

        hdr._cb = cb
        return hdr

    # ── 공개 API ────────────────────────────────────────────
    def set_items(self, items):
        """fetch 결과로 행 재생성 — 기존 체크 상태 폐기, 모두 체크된 상태로 새로 표시.

        items 에 tracker_name 키가 있고 트래커가 2개 이상이면 트래커별 그룹으로
        분류해 렌더링. 그렇지 않으면 평면 리스트.
        """
        # Clear 기존 행 + 그룹 헤더
        self._clear_rendered_widgets()
        self._items = list(items or [])

        # 빈 라벨 표시/숨김 + 카운트
        if not self._items:
            self._empty_lbl.setText(self._empty_text)
            self._empty_lbl.setVisible(True)
            self._sel_all_btn.setEnabled(False)
            self._count_lbl.setText("0개")
            return

        self._empty_lbl.setVisible(False)
        self._sel_all_btn.setEnabled(True)
        self._count_lbl.setText(f"{len(self._items)}개")

        # 트래커별 그룹핑 — 순서 보존을 위해 dict (insertion-ordered) 사용
        groups: dict = {}
        for it in self._items:
            tn = ""
            if isinstance(it, dict):
                tn = str(it.get("tracker_name") or "").strip()
            groups.setdefault(tn, []).append(it)

        use_groups = len(groups) >= 2 and all(k for k in groups.keys())

        if not use_groups:
            # 평면 렌더 — 기존 동작 유지
            for item in self._items:
                row = self._build_row(item)
                insert_idx = self._rows_lay.count() - 1   # stretch 직전
                self._rows_lay.insertWidget(insert_idx, row)
                self._rows.append(row)
            return

        # 그룹 렌더 — 트래커별로 헤더 + 들여쓴 행
        for tracker_name, grp_items in groups.items():
            hdr = self._build_group_header(tracker_name, len(grp_items))
            insert_idx = self._rows_lay.count() - 1   # stretch 직전
            self._rows_lay.insertWidget(insert_idx, hdr)
            self._group_headers.append(hdr)

            grp_rows: list = []
            for item in grp_items:
                row = self._build_row(item, indent=True)
                insert_idx = self._rows_lay.count() - 1
                self._rows_lay.insertWidget(insert_idx, row)
                self._rows.append(row)
                grp_rows.append(row)

            # 그룹 체크박스 ↔ 멤버 체크박스 양방향 동기화
            self._group_cbs[tracker_name] = (hdr._cb, grp_rows)
            hdr._cb.stateChanged.connect(
                lambda _state, tn=tracker_name: self._on_group_toggled(tn))
            for r in grp_rows:
                r._cb.stateChanged.connect(
                    lambda _state, tn=tracker_name: self._sync_group_state(tn))

    def _clear_rendered_widgets(self):
        """렌더된 행 + 그룹 헤더 모두 제거 (상태 초기화)."""
        for r in self._rows:
            self._rows_lay.removeWidget(r)
            r.setParent(None); r.deleteLater()
        self._rows.clear()
        for h in self._group_headers:
            self._rows_lay.removeWidget(h)
            h.setParent(None); h.deleteLater()
        self._group_headers.clear()
        self._group_cbs.clear()

    def get_all_items(self) -> list:
        return list(self._items)

    def get_selected_items(self) -> list:
        return [r._item_data for r in self._rows if r._cb.isChecked()]

    def set_loading_text(self, text: str):
        """fetch/처리 중 빈 라벨에 표시할 임시 텍스트."""
        self._empty_lbl.setText(text)
        self._empty_lbl.setVisible(True)
        # 기존 행 + 그룹 헤더 제거 (로딩 상태 진입 시)
        self._clear_rendered_widgets()
        self._items = []
        self._count_lbl.setText("0개")
        self._sel_all_btn.setEnabled(False)

    def _toggle_select_all(self):
        """체크박스 전체 토글 — 하나라도 체크 안 됐으면 모두 체크, 모두 체크면 모두 해제."""
        if not self._rows:
            return
        any_unchecked = any(not r._cb.isChecked() for r in self._rows)
        target = any_unchecked   # 하나라도 미체크면 모두 체크로 만든다
        # 그룹 체크박스 stateChanged 가 _on_group_toggled 를 다시 호출하지 않도록
        # block 처리 (어차피 아래에서 직접 토글)
        self._syncing_group = True
        try:
            for r in self._rows:
                r._cb.setChecked(target)
            # 그룹 헤더 체크박스도 동기화
            for cb, _rows in self._group_cbs.values():
                cb.setChecked(target)
        finally:
            self._syncing_group = False

    def _on_group_toggled(self, tracker_name: str):
        """그룹 헤더 체크박스 변경 — 그룹 내 모든 행을 동일 상태로 설정."""
        if self._syncing_group:
            return
        entry = self._group_cbs.get(tracker_name)
        if entry is None:
            return
        cb, rows = entry
        target = cb.isChecked()
        self._syncing_group = True
        try:
            for r in rows:
                r._cb.setChecked(target)
        finally:
            self._syncing_group = False

    def _sync_group_state(self, tracker_name: str):
        """그룹 내 개별 행 체크박스 변경 시 그룹 헤더 체크박스 동기화 —
        하나라도 체크되어 있으면 그룹 체크 ON (전체 미체크일 때만 OFF).
        """
        if self._syncing_group:
            return
        entry = self._group_cbs.get(tracker_name)
        if entry is None:
            return
        cb, rows = entry
        any_checked = any(r._cb.isChecked() for r in rows)
        self._syncing_group = True
        try:
            cb.setChecked(any_checked)
        finally:
            self._syncing_group = False


# ══════════════════════════════════════════════════════════════════════
#  CbHistoricalSubTab — INPUT 탭 2. 변경점 + 과거차 사례 불러오기
# ══════════════════════════════════════════════════════════════════════
class CbHistoricalSubTab(QWidget):
    """변경점 트래커 + 과거차 트래커 — fetch 카드 2종.

    CbFetcher 로 트래커 항목을 fetch → _ItemListRenderer 로 렌더링.

    Signals:
      change_fetch_requested(str)  — 변경점 트래커 ID 와 함께 fetch 요청
      historical_fetch_requested() — 과거차 fetch 요청 (트래커는 컨트롤러가
                                     cb_config.json 의 section_past 에서 로드 +
                                     _FetchSelectDialog 로 사용자가 선택)
    """

    change_fetch_requested     = pyqtSignal(str)
    historical_fetch_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background:{C.BG_APP};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        outer.addWidget(scroll)

        inner = QWidget(); inner.setStyleSheet(f"background:{C.BG_APP};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(14)

        # ── 1) 변경점 트래커 (사양변경) ────────────────────────────
        lay.addWidget(self._build_fetch_card(
            title="사양변경 트래커 — 변경점 목록",
            icon="🔗",
            id_label="변경점 트래커 ID",
            id_attr="le_change_tracker",
            btn_text="📥  변경점 목록 불러오기",
            btn_attr="change_fetch_btn",
            on_click=lambda: self.change_fetch_requested.emit(
                self.le_change_tracker.text().strip()),
        ))
        # 변경점 목록 — fetch 결과 렌더링
        self.change_list = _ItemListRenderer(
            "변경점 목록",
            icon="📋", empty_text="아직 불러온 변경점이 없습니다.")
        lay.addWidget(self.change_list)

        # ── 2) 전사 과거차 트래커 ─────────────────────────────────
        # 코드리뷰 ⑥ > 과거차 섹션에 등록된 트래커를 그대로 사용 — 불러오기
        # 클릭 시 컨트롤러가 cb_config.json 의 section_past 에서 트래커 목록을
        # 읽어 _FetchSelectDialog 로 다중 선택 받음.
        lay.addWidget(self._build_simple_fetch_card(
            title="전사 과거차 트래커",
            icon="🗂",
            desc=(""),
            btn_text="📥  과거차 목록 불러오기",
            btn_attr="historical_fetch_btn",
            on_click=lambda: self.historical_fetch_requested.emit(),
        ))
        # 과거차 목록 — fetch 결과 렌더링
        self.historical_list = _ItemListRenderer(
            "과거차 목록",
            icon="🗂", empty_text="아직 불러온 과거차가 없습니다.")
        lay.addWidget(self.historical_list)

        lay.addStretch()
        scroll.setWidget(inner)

    def _build_simple_fetch_card(self, *, title, icon, desc,
                                 btn_text, btn_attr, on_click) -> QFrame:
        """ID 입력 없이 안내 텍스트 + fetch 버튼만 있는 카드.

        과거차처럼 트래커가 외부 (cb_config.json) 에서 관리되어 입력란이 필요
        없는 경우 사용. 컨트롤러가 _FetchSelectDialog 로 선택 흐름을 처리.
        """
        card, body = _card_frame(title, icon=icon)
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(8)

        if desc:
            d_lbl = QLabel(desc)
            d_lbl.setFont(QFont(C.FUI, 9))
            d_lbl.setWordWrap(True)
            d_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")
            bl.addWidget(d_lbl)

        # 버튼 행
        btn_row = QHBoxLayout(); btn_row.addStretch()
        btn = QPushButton(btn_text)
        btn.setFixedHeight(30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:6px;"
            f"  padding:4px 16px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H};"
            f"  border-color:{C.ACCENT_H}; }}"
            f"QPushButton:disabled {{ background:#CBD5E1;"
            f"  color:#94A3B8; border-color:#CBD5E1; }}")
        btn.clicked.connect(on_click)
        setattr(self, btn_attr, btn)
        btn_row.addWidget(btn)
        bl.addLayout(btn_row)
        return card

    def _build_fetch_card(self, *, title, icon, id_label, id_attr,
                          btn_text, btn_attr, on_click) -> QFrame:
        """트래커 ID 입력 + fetch 버튼 카드."""
        card, body = _card_frame(title, icon=icon)
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(8)

        # ID 입력 행
        row = QHBoxLayout(); row.setSpacing(8)
        lbl = QLabel(id_label)
        lbl.setFixedWidth(160)
        lbl.setFont(QFont(C.FUI, 10))
        lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")
        row.addWidget(lbl)
        le = QLineEdit(); le.setObjectName("le_info")
        le.setPlaceholderText("숫자 ID 또는 URL")
        le.setFixedHeight(28)
        row.addWidget(le)
        setattr(self, id_attr, le)
        bl.addLayout(row)

        # 버튼 행
        btn_row = QHBoxLayout(); btn_row.addStretch()
        btn = QPushButton(btn_text)
        btn.setFixedHeight(30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:6px;"
            f"  padding:4px 16px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H};"
            f"  border-color:{C.ACCENT_H}; }}"
            f"QPushButton:disabled {{ background:#CBD5E1;"
            f"  color:#94A3B8; border-color:#CBD5E1; }}")
        btn.clicked.connect(on_click)
        setattr(self, btn_attr, btn)
        btn_row.addWidget(btn)
        bl.addLayout(btn_row)
        return card

    # ── 외부 접근용 (컨트롤러가 사용 예정) ────────────────────
    def get_change_tracker_id(self) -> str: return self.le_change_tracker.text().strip()

    # ── 리스트 렌더 위임 ──────────────────────────────────────
    def set_change_items(self, items: list):
        """fetch 결과로 변경점 목록 채움."""
        self.change_list.set_items(items)

    def set_historical_items(self, items: list):
        """fetch 결과로 과거차 목록 채움."""
        self.historical_list.set_items(items)

    def get_selected_change_items(self) -> list:
        """체크된 변경점만 반환 (AI 분석 대상)."""
        return self.change_list.get_selected_items()

    def get_selected_historical_items(self) -> list:
        """체크된 과거차만 반환 (AI 컨텍스트)."""
        return self.historical_list.get_selected_items()

    def set_change_fetch_running(self, running: bool):
        """변경점 fetch 진행 중 상태 — 버튼 비활성 + 로딩 표시."""
        self.change_fetch_btn.setEnabled(not running)
        self.change_fetch_btn.setText(
            "⏳  불러오는 중..." if running else "📥  변경점 목록 불러오기")
        if running:
            self.change_list.set_loading_text("⏳  불러오는 중...")

    def set_historical_fetch_running(self, running: bool):
        """과거차 fetch 진행 중 상태."""
        self.historical_fetch_btn.setEnabled(not running)
        self.historical_fetch_btn.setText(
            "⏳  불러오는 중..." if running else "📥  과거차 목록 불러오기")
        if running:
            self.historical_list.set_loading_text("⏳  불러오는 중...")

    def get_tracker_ids(self) -> dict:
        """세션 저장용 — 변경점 트래커 ID. (과거차 트래커는 cb_config 의
        section_past 에서 공유 관리하므로 별도 저장 불필요.)
        """
        return {
            "change_tracker_id": self.get_change_tracker_id(),
        }

    def apply_tracker_ids(self, d: dict):
        """세션 복원용 — dict 에서 변경점 트래커 ID 복원."""
        if not isinstance(d, dict):
            return
        self.le_change_tracker.setText(str(d.get("change_tracker_id") or ""))


# ══════════════════════════════════════════════════════════════════════
#  ChecklistReviewSubTab — INPUT 탭 3. 체크시트 입력 + 검토
# ══════════════════════════════════════════════════════════════════════
class ChecklistReviewSubTab(QWidget):
    """공통 체크리스트 5행 + 4역할 검토 의견 + 회의록 + AI 인사이트 실행 버튼.

    체크리스트 잠금/수정 토글 + 액션아이템 ➕/✕ 행 추가 기능 포함.
    AI 버튼 → SrsReviewV2Controller 가 변경점 N개 병렬 분석 + OUTPUT 라우팅.

    Signals:
      save_checklist_requested() — [💾 저장] 클릭 (잠금)
      edit_checklist_requested() — [✏ 수정] 클릭 (잠금 해제)
      ai_run_requested()         — [🤖 AI 인사이트 실행] 클릭
    """

    save_checklist_requested = pyqtSignal()
    edit_checklist_requested = pyqtSignal()
    ai_run_requested         = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._template = _load_srs_template()
        # 5행 체크리스트 입력 위젯들 — {section_id: QTextEdit}
        self.checklist_inputs: dict = {}
        # 4역할 검토 의견 위젯들 — {role: QTextEdit}
        self.review_inputs: dict = {}
        # 회의록 위젯들
        self.meeting_issues_te:    "QTextEdit | None" = None
        self.meeting_decisions_te: "QTextEdit | None" = None
        self.action_items_holder:  "QWidget   | None" = None
        # 액션아이템 행 리스트 — Phase 2-2 에서 add/remove 로 관리
        self.action_item_rows: list = []
        self._build()

    def _build(self):
        self.setStyleSheet(f"background:{C.BG_APP};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        outer.addWidget(scroll)

        inner = QWidget(); inner.setStyleSheet(f"background:{C.BG_APP};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(14)

        # ── 1) 공통 체크리스트 (5행) + 저장/수정 버튼 ─────────────
        lay.addWidget(self._build_checklist_card())

        # ── 2) 4역할 설계자 검토 의견 카드 ─────────────────────────
        lay.addWidget(self._build_reviews_card())

        # ── 3) 회의록 (쟁점/결정/액션아이템) ────────────────────────
        lay.addWidget(self._build_meeting_card())

        # ── 4) AI 인사이트 실행 버튼 (큰 액션) ────────────────────
        lay.addWidget(self._build_ai_button())

        lay.addStretch()
        scroll.setWidget(inner)

    # ── 1) 체크리스트 카드 ───────────────────────────────────────
    def _build_checklist_card(self) -> QFrame:
        card, body = _card_frame("변경점 체크리스트 (5항목)", icon="📝")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(10)

        rows = self._template.get("fixed_checklist") or []
        for row in rows:
            sec_id   = str(row.get("id") or "").strip()
            section  = str(row.get("section") or "").strip()
            question = str(row.get("question") or "").strip()
            guide    = str(row.get("guide") or "").strip()
            if not sec_id:
                continue

            # 라벨 (구분 + 가이드 한 줄)
            hdr = QHBoxLayout(); hdr.setSpacing(6)
            sec_lbl = QLabel(f"📌 {section}")
            sec_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
            sec_lbl.setStyleSheet(f"color:{C.BLUE_DK}; background:transparent;")
            hdr.addWidget(sec_lbl)
            q_lbl = QLabel(f"— {question}")
            q_lbl.setFont(QFont(C.FUI, 9))
            q_lbl.setWordWrap(True)
            q_lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")
            hdr.addWidget(q_lbl, 1)
            bl.addLayout(hdr)

            # 가이드 (작은 회색 문구)
            if guide:
                g_lbl = QLabel(f"  {guide}")
                g_lbl.setFont(QFont(C.FUI, 8))
                g_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")
                bl.addWidget(g_lbl)

            # 입력 TextEdit
            te = QTextEdit(); te.setObjectName("te_info")
            te.setPlaceholderText(f"({section}) 작성 결과 입력")
            te.setFixedHeight(52)
            bl.addWidget(te)
            self.checklist_inputs[sec_id] = te

        # 저장/수정 토글 버튼 + 상태 라벨 (Phase 2-2)
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        # 잠금 상태 라벨 — 잠금 시 "🔒 잠김 — 수정하려면 [수정] 클릭" 표시
        self._lock_status_lbl = QLabel("")
        self._lock_status_lbl.setFont(QFont(C.FUI, 9))
        self._lock_status_lbl.setStyleSheet(
            f"color:{C.T3}; background:transparent;")
        btn_row.addWidget(self._lock_status_lbl)
        btn_row.addStretch()

        self.save_btn = QPushButton("💾  저장 (잠금)")
        self.save_btn.setFixedHeight(28)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:10px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:disabled {{ background:{C.BDR}; color:{C.T3};"
            f"  border-color:{C.BDR}; }}")
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(self.save_btn)

        self.edit_btn = QPushButton("✏  수정")
        self.edit_btn.setFixedHeight(28)
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.T2};"
            f"  border:1px solid {C.BDR}; border-radius:5px;"
            f"  padding:2px 14px; font-size:10px; }}"
            f"QPushButton:hover {{ background:{C.BG_HOVER}; color:{C.T0}; }}"
            f"QPushButton:disabled {{ background:transparent; color:{C.T3};"
            f"  border-color:{C.BDR}; }}")
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        self.edit_btn.setEnabled(False)   # 초기: 미잠금 상태이므로 수정 버튼 비활성
        btn_row.addWidget(self.edit_btn)

        bl.addLayout(btn_row)
        return card

    # ── 체크리스트 잠금 / 수정 토글 핸들러 ──────────────────────
    def _on_save_clicked(self):
        """[💾 저장] — 5행 체크리스트 readonly 잠금 + 회색 처리."""
        self._set_checklist_locked(True)
        self.save_checklist_requested.emit()

    def _on_edit_clicked(self):
        """[✏ 수정] — 잠금 해제 + 다시 편집 가능."""
        self._set_checklist_locked(False)
        self.edit_checklist_requested.emit()

    def _set_checklist_locked(self, locked: bool):
        """체크리스트 5행 입력 위젯의 잠금 상태 + 버튼/라벨 UI 동기화."""
        self._checklist_locked = locked
        # 5행 TextEdit readonly + 시각 스타일
        locked_style = (
            f"QTextEdit#te_info {{ background:{C.BG_PANEL};"
            f"  border:1px solid {C.BDR2}; color:{C.T2};"
            f"  border-radius:6px; padding:8px 10px;"
            f"  font-size:11px; }}")
        unlocked_style = ""   # config.py QSS 기본값 사용
        for te in self.checklist_inputs.values():
            te.setReadOnly(locked)
            te.setStyleSheet(locked_style if locked else unlocked_style)
        # 버튼 상태
        self.save_btn.setEnabled(not locked)
        self.edit_btn.setEnabled(locked)
        # 상태 라벨
        if locked:
            self._lock_status_lbl.setText("🔒  잠김 — 수정하려면 [수정] 클릭")
            self._lock_status_lbl.setStyleSheet(
                f"color:{C.BLUE_DK}; background:transparent; font-weight:600;")
        else:
            self._lock_status_lbl.setText("")
            self._lock_status_lbl.setStyleSheet(
                f"color:{C.T3}; background:transparent;")

    def is_checklist_locked(self) -> bool:
        """외부 (세션 저장 등) 에서 잠금 상태 조회용."""
        return getattr(self, "_checklist_locked", False)

    # ── 2) 4역할 검토 의견 카드 ─────────────────────────────────
    def _build_reviews_card(self) -> QFrame:
        card, body = _card_frame("설계자 직접 검토 의견 (SYS / SW / HW / TEST)",
                                 icon="👥")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(12)

        reviewers = (self._template.get("engineer_review_template") or {})
        for role in ("sys", "sw", "hw", "test"):
            cfg = reviewers.get(role) or {}
            label  = cfg.get("label") or f"{role.upper()} 설계자"
            icon   = cfg.get("icon")  or "👤"
            guides = cfg.get("guides") or []

            # 역할 헤더
            hdr_lbl = QLabel(f"{icon}  {label}")
            hdr_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
            hdr_lbl.setStyleSheet(f"color:{C.BLUE_DK}; background:transparent;")
            bl.addWidget(hdr_lbl)

            # 가이드 리스트 (작은 회색 글씨)
            for g in guides:
                g_lbl = QLabel(f"  • {g}")
                g_lbl.setFont(QFont(C.FUI, 8))
                g_lbl.setWordWrap(True)
                g_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")
                bl.addWidget(g_lbl)

            # 의견 입력
            te = QTextEdit(); te.setObjectName("te_info")
            te.setPlaceholderText(f"{label} 검토 의견 입력")
            te.setFixedHeight(70)
            bl.addWidget(te)
            self.review_inputs[role] = te

        return card

    # ── 3) 회의록 카드 ────────────────────────────────────────
    def _build_meeting_card(self) -> QFrame:
        card, body = _card_frame("검토 회의록 — 쟁점 / 결정 / 액션아이템",
                                 icon="🗣")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(10)

        mt = self._template.get("meeting_template") or {}

        # 쟁점
        lbl1 = QLabel("쟁점")
        lbl1.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        lbl1.setStyleSheet(f"color:{C.BLUE_DK}; background:transparent;")
        bl.addWidget(lbl1)
        self.meeting_issues_te = QTextEdit(); self.meeting_issues_te.setObjectName("te_info")
        self.meeting_issues_te.setPlaceholderText(
            mt.get("issues_placeholder") or "회의 쟁점 작성")
        self.meeting_issues_te.setFixedHeight(60)
        bl.addWidget(self.meeting_issues_te)

        # 결정사항
        lbl2 = QLabel("결정 사항")
        lbl2.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        lbl2.setStyleSheet(f"color:{C.BLUE_DK}; background:transparent;")
        bl.addWidget(lbl2)
        self.meeting_decisions_te = QTextEdit(); self.meeting_decisions_te.setObjectName("te_info")
        self.meeting_decisions_te.setPlaceholderText(
            mt.get("decisions_placeholder") or "결정 사항 작성")
        self.meeting_decisions_te.setFixedHeight(60)
        bl.addWidget(self.meeting_decisions_te)

        # 액션아이템 표
        act_hdr = QHBoxLayout(); act_hdr.setSpacing(6)
        act_lbl = QLabel("액션아이템")
        act_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        act_lbl.setStyleSheet(f"color:{C.BLUE_DK}; background:transparent;")
        act_hdr.addWidget(act_lbl); act_hdr.addStretch()
        self.add_action_btn = QPushButton("➕  행 추가")
        self.add_action_btn.setFixedHeight(24)
        self.add_action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_action_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.BLUE};"
            f"  border:1px dashed {C.BLUE}; border-radius:5px;"
            f"  padding:1px 10px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
        # 빈 행 추가 (사용자 직접 작성)
        self.add_action_btn.clicked.connect(lambda: self._add_action_row())
        act_hdr.addWidget(self.add_action_btn)
        bl.addLayout(act_hdr)

        # 액션아이템 표 — 헤더 행 + 데이터 행 컨테이너
        self.action_items_holder = QWidget()
        self.action_items_holder.setStyleSheet("background:transparent;")
        self._action_lay = QVBoxLayout(self.action_items_holder)
        self._action_lay.setContentsMargins(0, 4, 0, 0); self._action_lay.setSpacing(6)
        # 헤더 행 (액션아이템 / 담당 / 기한 / 상태) — 사진의 파란 헤더 스타일
        self._action_lay.addWidget(self._build_action_header())
        bl.addWidget(self.action_items_holder)

        # 기본 액션아이템 3개 로드
        for ai in (mt.get("action_items_default") or []):
            self._add_action_row(
                action=ai.get("action") or "",
                owner=ai.get("owner") or "",
                due=ai.get("due") or "",
                status=ai.get("status") or "대기",
            )

        return card

    # 액션아이템 표 컬럼 폭 — 헤더와 데이터 행이 정확히 정렬되도록 상수화
    _AI_COL_OWNER  = 140
    _AI_COL_DUE    = 140
    _AI_COL_STATUS = 90
    _AI_COL_DEL    = 28    # ✕ 버튼 자리 (헤더에서는 빈 칸)

    def _build_action_header(self) -> QFrame:
        """액션아이템 표의 헤더 행 — 파란 톤 + 컬럼 라벨."""
        hdr = QFrame(); hdr.setObjectName("ai_hdr")
        hdr.setStyleSheet(
            f"#ai_hdr {{ background:{C.BLUE_LT};"
            f"  border:1px solid {C.BLUE}; border-radius:5px; }}")
        hdr.setFixedHeight(34)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12, 0, 12, 0); hl.setSpacing(8)

        def _hdr_lbl(text, w=None):
            lb = QLabel(text)
            lb.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
            lb.setStyleSheet(f"color:{C.BLUE_DK}; background:transparent;")
            if w:
                lb.setFixedWidth(w)
            return lb

        hl.addWidget(_hdr_lbl("액션아이템"), 1)
        hl.addWidget(_hdr_lbl("담당",   w=self._AI_COL_OWNER))
        hl.addWidget(_hdr_lbl("기한",   w=self._AI_COL_DUE))
        hl.addWidget(_hdr_lbl("상태",   w=self._AI_COL_STATUS))
        # ✕ 컬럼 자리 (헤더는 빈 칸 — 데이터 행과 폭 맞춤)
        spacer = QWidget(); spacer.setFixedWidth(self._AI_COL_DEL)
        hl.addWidget(spacer)
        return hdr

    def _add_action_row(self, action="", owner="", due="", status="대기"):
        """액션아이템 한 행 추가 — 표 스타일 (헤더와 컬럼 정렬).

        컬럼: 액션아이템(stretch) / 담당 / 기한 / 상태(토글버튼) / ✕
        """
        row_w = QFrame(); row_w.setObjectName("ai_row")
        row_w.setStyleSheet(
            f"#ai_row {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:5px; }}")
        row_w.setFixedHeight(44)
        rl = QHBoxLayout(row_w); rl.setContentsMargins(12, 6, 12, 6); rl.setSpacing(8)

        def _mk_le(text, ph, w=None):
            le = QLineEdit(text); le.setObjectName("le_info")
            le.setPlaceholderText(ph); le.setFixedHeight(30)
            if w: le.setFixedWidth(w)
            return le

        le_action = _mk_le(action, "액션 내용")
        le_owner  = _mk_le(owner,  "담당", w=self._AI_COL_OWNER)
        le_due    = _mk_le(due,    "기한", w=self._AI_COL_DUE)
        rl.addWidget(le_action, 1)
        rl.addWidget(le_owner)
        rl.addWidget(le_due)

        # 상태 토글 버튼 — 대기 ↔ 완료
        status_btn = QPushButton()
        status_btn.setFixedSize(self._AI_COL_STATUS, 30)
        status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        status_btn.setToolTip("클릭하여 대기 ↔ 완료 토글")
        self._apply_status_style(status_btn, status)
        status_btn.clicked.connect(
            lambda _checked=False, b=status_btn: self._toggle_status(b))
        rl.addWidget(status_btn)

        # ✕ 삭제 버튼 (행별로 개별 제거)
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(self._AI_COL_DEL - 2, 26)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setToolTip("이 액션아이템 삭제")
        del_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.RED};"
            f"  border:1px solid {C.RED}; border-radius:4px;"
            f"  font-size:10px; font-weight:700; padding:0; }}"
            f"QPushButton:hover {{ background:{C.RED}; color:#FFFFFF; }}")
        rl.addWidget(del_btn)

        # 행 메타 dict 보관 (✕/상태 클로저가 참조)
        row_data = {
            "frame":  row_w,
            "action": le_action, "owner":  le_owner,
            "due":    le_due,    "status": status_btn,   # 토글 버튼 자체 보관
        }
        del_btn.clicked.connect(lambda _checked=False, r=row_data:
                                self._remove_action_row(r))

        self._action_lay.addWidget(row_w)
        self.action_item_rows.append(row_data)

    def _apply_status_style(self, btn: QPushButton, state: str):
        """상태 토글 버튼의 텍스트 + 색상을 state ('대기'|'완료') 에 맞춰 적용."""
        state = (state or "").strip()
        if state == "완료":
            btn.setText("✓  완료")
            btn.setStyleSheet(
                f"QPushButton {{ background:{C.ADD_BG}; color:{C.ADD_FG};"
                f"  border:1px solid {C.ADD_LN}; border-radius:5px;"
                f"  font-size:10px; font-weight:700; padding:0 8px; }}"
                f"QPushButton:hover {{ background:{C.ADD_LN}; }}")
        else:   # '대기' (또는 알 수 없는 값 폴백)
            btn.setText("⏳  대기")
            btn.setStyleSheet(
                f"QPushButton {{ background:{C.BG_PANEL}; color:{C.T2};"
                f"  border:1px solid {C.BDR2}; border-radius:5px;"
                f"  font-size:10px; font-weight:700; padding:0 8px; }}"
                f"QPushButton:hover {{ background:{C.BG_HOVER}; }}")

    def _toggle_status(self, btn: QPushButton):
        """상태 토글 — 현재 텍스트 보고 대기 ↔ 완료 전환."""
        current = btn.text()
        new_state = "대기" if "완료" in current else "완료"
        self._apply_status_style(btn, new_state)

    def _remove_action_row(self, row_data: dict):
        """액션아이템 한 행 제거 — 위젯 + self.action_item_rows 동기화."""
        try:
            self.action_item_rows.remove(row_data)
        except ValueError:
            return
        frame = row_data.get("frame")
        if frame is not None:
            self._action_lay.removeWidget(frame)
            frame.setParent(None)
            frame.deleteLater()

    # ── 4) AI 인사이트 실행 버튼 ─────────────────────────────
    def _build_ai_button(self) -> QPushButton:
        btn = QPushButton("  🤖   AI 인사이트 실행")
        btn.setObjectName("btn_ai_srs")
        btn.setFixedHeight(44)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton#btn_ai_srs {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {C.BLUE_DK}, stop:1 {C.BLUE});
                color:#FFFFFF; border:2px solid {C.BLUE_DK}; border-radius:10px;
                font-size:13px; font-weight:bold;
            }}
            QPushButton#btn_ai_srs:hover {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {C.BLUE}, stop:1 {C.BLUE_LT});
                border-color:{C.ACCENT_H};
            }}
            QPushButton#btn_ai_srs:pressed {{ background:{C.BLUE_DK}; }}
            QPushButton#btn_ai_srs:disabled {{
                background:{C.BDR}; color:{C.T3}; border-color:{C.BDR2};
            }}""")
        btn.setToolTip("입력된 체크리스트/검토의견/회의록 + 변경점 + 과거차 로 AI 분석 실행")
        btn.clicked.connect(self.ai_run_requested.emit)
        self.ai_btn = btn
        return btn

    # ── 외부 접근용 데이터 ──────────────────────────────────
    def get_common_inputs(self) -> dict:
        """현재 입력된 모든 공통 데이터를 dict 로 반환.
        core.srs_review_model.CommonInputs 와 동일 키 구조.
        """
        return {
            "checklist": {sid: te.toPlainText().strip()
                          for sid, te in self.checklist_inputs.items()},
            "reviews":   {r: te.toPlainText().strip()
                          for r, te in self.review_inputs.items()},
            "meeting": {
                "issues":    (self.meeting_issues_te.toPlainText().strip()
                              if self.meeting_issues_te else ""),
                "decisions": (self.meeting_decisions_te.toPlainText().strip()
                              if self.meeting_decisions_te else ""),
                "action_items": [
                    {
                        "action": r["action"].text().strip(),
                        "owner":  r["owner"].text().strip(),
                        "due":    r["due"].text().strip(),
                        # 상태는 토글 버튼 — 텍스트에서 "대기"/"완료" 정규화
                        "status": ("완료" if "완료" in r["status"].text()
                                   else "대기"),
                    }
                    for r in self.action_item_rows
                ],
            },
            "checklist_locked": self.is_checklist_locked(),
        }

    # ── AI 버튼 활성/비활성 (외부 컨트롤러가 분석 중 호출) ──────
    def set_ai_running(self, running: bool):
        """AI 분석 중에는 [🤖 AI 인사이트 실행] 버튼 비활성화 + 텍스트 변경."""
        btn = getattr(self, "ai_btn", None)
        if btn is None:
            return
        btn.setEnabled(not running)
        btn.setText("  ⏳   AI 분석 중..." if running
                    else "  🤖   AI 인사이트 실행")

    def apply_common_inputs(self, d: dict):
        """세션 복원 — dict 에서 5행 체크리스트 + 4역할 검토 + 회의록 복원.
        잠금 상태도 복원 (저장 시점에 잠겨있었으면 readonly 로 복원).
        """
        if not isinstance(d, dict):
            return
        # 5행 체크리스트
        for sid, val in (d.get("checklist") or {}).items():
            te = self.checklist_inputs.get(sid)
            if te is not None:
                te.setPlainText(str(val or ""))
        # 4역할 검토 의견
        for role, val in (d.get("reviews") or {}).items():
            te = self.review_inputs.get(role)
            if te is not None:
                te.setPlainText(str(val or ""))
        # 회의록
        meeting = d.get("meeting") or {}
        if self.meeting_issues_te is not None:
            self.meeting_issues_te.setPlainText(str(meeting.get("issues") or ""))
        if self.meeting_decisions_te is not None:
            self.meeting_decisions_te.setPlainText(str(meeting.get("decisions") or ""))
        # 액션아이템 — 기존 행 모두 제거 후 저장된 행 재생성
        for row in list(self.action_item_rows):
            self._remove_action_row(row)
        for ai in (meeting.get("action_items") or []):
            if isinstance(ai, dict):
                self._add_action_row(
                    action=ai.get("action") or "",
                    owner=ai.get("owner") or "",
                    due=ai.get("due") or "",
                    status=ai.get("status") or "대기",
                )
        # 잠금 상태
        if bool(d.get("checklist_locked", False)):
            self._set_checklist_locked(True)
        else:
            self._set_checklist_locked(False)


# ══════════════════════════════════════════════════════════════════════
#  AiResultDropdownPanel — OUTPUT 탭 🤖 AI 인사이트 결과
# ══════════════════════════════════════════════════════════════════════
class AiResultDropdownPanel(QWidget):
    """변경점 N개의 AI 분석 결과를 드롭다운으로 선택해서 보여주는 패널.

    사용자 결정사항:
      - 변경점 1개 = AI 호출 1회 (병렬)
      - OUTPUT 결과는 드롭다운으로 1개씩 표시 (Phase 결정 B안)
      - 결과는 마크다운 5(+1)섹션 — _md_to_html 로 HTML 렌더링
      - CB 업로드: 변경점 1개 = CB 이슈 1개 (A안)

    공개 API:
      set_change_items(items)           — 분석 대상 N개 등록 (드롭다운 채우기)
      set_progress(done, total)         — 상단 상태 라벨 갱신 ("2/3 완료")
      set_result(card_id, markdown)     — 변경점 1개의 AI 결과 저장 + 표시 갱신
      set_error(card_id, msg)           — 변경점 1개 실패 사유 표시
      clear_all()                       — 결과 dict + 드롭다운 초기화
      get_result(card_id) -> str|None   — 저장된 마크다운 (CB 업로드용)
      get_all_results() -> dict         — {card_id: markdown}
      get_change_item(card_id) -> dict  — 변경점 메타 (제목/ID — CB 업로드 시 제목 만들기)
      set_upload_enabled(bool)          — 결과 N개 ≥ 1 일 때만 업로드 버튼 활성

    Signals:
      upload_all_requested()  — [📤 CB 업로드] 클릭 (전체 결과 일괄)
    """

    upload_all_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # 변경점 메타 보관 — {card_id: cb_item dict}
        self._items: dict = {}
        # AI 결과 마크다운 보관 — {card_id: markdown_text}
        self._results: dict = {}
        # 에러 보관 — {card_id: error_msg}
        self._errors: dict = {}
        self._build()

    def _build(self):
        self.setStyleSheet(f"background:{C.BG_APP};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14); outer.setSpacing(10)

        # ── 상단 컨트롤 행 — 드롭다운 + 진행 상태 라벨 ───────────
        ctl_row = QHBoxLayout(); ctl_row.setSpacing(10)
        sel_lbl = QLabel("변경점 선택:")
        sel_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        sel_lbl.setStyleSheet(f"color:{C.T1}; background:transparent;")
        ctl_row.addWidget(sel_lbl)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(420)
        self._combo.setFixedHeight(30)
        self._combo.setStyleSheet(
            f"QComboBox {{ background:{C.BG_INPUT}; color:{C.T0};"
            f"  border:1px solid {C.BDR}; border-radius:5px;"
            f"  padding:4px 8px; font-size:11px; }}"
            f"QComboBox:hover {{ border-color:{C.BLUE}; }}"
            f"QComboBox::drop-down {{ border:none; width:20px; }}")
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        ctl_row.addWidget(self._combo, 1)

        self._progress_lbl = QLabel("")
        self._progress_lbl.setFont(QFont(C.FUI, 10))
        self._progress_lbl.setStyleSheet(
            f"color:{C.BLUE_DK}; background:transparent;")
        ctl_row.addWidget(self._progress_lbl)

        # [📤 CB 업로드] — 결과 ≥1개 일 때 활성
        self._upload_btn = QPushButton("📤  CB 업로드")
        self._upload_btn.setFixedHeight(30)
        self._upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upload_btn.setToolTip(
            "분석 완료된 변경점들을 각각 별도의 Codebeamer 이슈로 업로드")
        self._upload_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:0 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:disabled {{ background:{C.BDR}; color:{C.T3};"
            f"  border-color:{C.BDR}; }}")
        self._upload_btn.setEnabled(False)
        self._upload_btn.clicked.connect(self.upload_all_requested.emit)
        ctl_row.addWidget(self._upload_btn)
        outer.addLayout(ctl_row)

        # ── 결과 본문 — 마크다운 → HTML QTextEdit ────────────────
        self._result_view = QTextEdit()
        self._result_view.setReadOnly(True)
        self._result_view.setStyleSheet(
            f"QTextEdit {{ background:{C.BG_CARD}; color:{C.T0};"
            f"  border:1px solid {C.BDR}; border-radius:8px;"
            f"  padding:14px 18px; font-family:'{C.FUI}'; "
            f"  font-size:11px; }}")
        # 초기 안내 — fetch 전
        self._show_initial_placeholder()
        outer.addWidget(self._result_view, 1)

    def _show_initial_placeholder(self):
        self._result_view.setHtml(
            f"<div style='color:{C.T3}; font-family:{C.FUI}; "
            f"font-size:12px; text-align:center; padding:60px 20px;'>"
            f"<div style='font-size:42px; margin-bottom:12px;'>🤖</div>"
            f"<div style='font-weight:600; color:{C.T2}; margin-bottom:6px;'>"
            f"AI 인사이트 결과가 여기에 표시됩니다</div>"
            f"<div>INPUT 탭에서 변경점 + 과거차 fetch → 체크리스트 작성 → "
            f"[🤖 AI 인사이트 실행] 클릭</div>"
            f"</div>")

    # ── 공개 API ────────────────────────────────────────────
    def set_change_items(self, items: list):
        """분석 대상 변경점 N개로 드롭다운 채우기. 기존 결과 모두 폐기."""
        self.clear_all()
        for it in (items or []):
            cid = str(it.get("id") or "")
            if not cid:
                continue
            self._items[cid] = it
            title = str(it.get("name") or it.get("title")
                        or it.get("summary") or "(제목 없음)").strip()
            # 드롭다운 라벨: "#100 — 변경점 제목 (분석 중)"
            self._combo.addItem(f"#{cid} — {title}  ⏳ 분석 중", userData=cid)
        if self._items:
            self._combo.setCurrentIndex(0)
            self._result_view.setHtml(
                f"<div style='color:{C.T3}; font-family:{C.FUI}; "
                f"font-size:12px; text-align:center; padding:60px 20px;'>"
                f"<div style='font-size:36px; margin-bottom:12px;'>⏳</div>"
                f"<div>AI 분석 진행 중 — 변경점 {len(self._items)}개 병렬 호출...</div>"
                f"</div>")
        else:
            self._show_initial_placeholder()

    def set_progress(self, done: int, total: int):
        """상단 진행 상태 라벨 갱신."""
        if total <= 0:
            self._progress_lbl.setText("")
            return
        if done >= total:
            self._progress_lbl.setText(f"✅  {done}/{total} 완료")
        else:
            self._progress_lbl.setText(f"⏳  {done}/{total} 분석 중...")

    def set_result(self, card_id: str, markdown: str):
        """워커 done 시 호출 — 결과 저장 + 드롭다운 라벨 갱신 + 현재 선택 시 재렌더."""
        cid = str(card_id or "")
        self._results[cid] = str(markdown or "")
        self._errors.pop(cid, None)
        # 드롭다운 라벨에서 ⏳ → ✅ 교체
        self._update_combo_label(cid, suffix="✅ 완료")
        # 현재 선택된 항목이면 즉시 표시
        if self._current_card_id() == cid:
            self._render_current()
        # 업로드 가능 상태로 전환
        self._upload_btn.setEnabled(True)

    def set_error(self, card_id: str, msg: str):
        """워커 error 시 호출."""
        cid = str(card_id or "")
        self._errors[cid] = str(msg or "")
        self._update_combo_label(cid, suffix="❌ 실패")
        if self._current_card_id() == cid:
            self._render_current()

    def clear_all(self):
        self._items.clear()
        self._results.clear()
        self._errors.clear()
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.blockSignals(False)
        self._progress_lbl.setText("")
        self._upload_btn.setEnabled(False)
        self._show_initial_placeholder()

    def get_result(self, card_id: str) -> "str | None":
        return self._results.get(str(card_id))

    def get_all_results(self) -> dict:
        return dict(self._results)

    def get_change_item(self, card_id: str) -> dict:
        """CB 업로드 시 제목 / parent_item_id 만들기에 사용."""
        return dict(self._items.get(str(card_id)) or {})

    def set_upload_enabled(self, enabled: bool):
        """컨트롤러가 업로드 진행 중 비활성 / 완료 후 재활성."""
        self._upload_btn.setEnabled(bool(enabled))
        self._upload_btn.setText(
            "⏳  업로드 중..." if not enabled and self._results
            else "📤  CB 업로드")

    # ── 내부 ────────────────────────────────────────────────
    def _current_card_id(self) -> str:
        idx = self._combo.currentIndex()
        if idx < 0:
            return ""
        return str(self._combo.itemData(idx) or "")

    def _update_combo_label(self, card_id: str, *, suffix: str):
        """드롭다운 항목 텍스트에서 상태 접미사 교체 (⏳/✅/❌)."""
        for i in range(self._combo.count()):
            if str(self._combo.itemData(i) or "") == card_id:
                meta = self._items.get(card_id) or {}
                title = str(meta.get("name") or meta.get("title")
                            or meta.get("summary") or "(제목 없음)").strip()
                self._combo.setItemText(i, f"#{card_id} — {title}  {suffix}")
                break

    def _on_combo_changed(self, _idx: int):
        self._render_current()

    def _render_current(self):
        cid = self._current_card_id()
        if not cid:
            self._show_initial_placeholder()
            return
        # 우선순위: 결과 있으면 결과, 없고 에러 있으면 에러, 둘 다 없으면 진행 중
        if cid in self._results:
            self._render_markdown(self._results[cid])
        elif cid in self._errors:
            self._render_error(cid, self._errors[cid])
        else:
            self._render_pending(cid)

    def _render_markdown(self, md: str):
        """마크다운 → HTML 변환 + QTextEdit setHtml."""
        try:
            from view.ui_md import _md_to_html
            html = _md_to_html(md or "")
        except Exception:
            # 변환 실패 시 plain text 폴백
            from html import escape as _esc
            html = (f"<pre style='font-family:{C.FCODE}; font-size:11px; "
                    f"white-space:pre-wrap;'>{_esc(md or '')}</pre>")
        # body 래퍼 (배경 + 폰트 기본값)
        wrap = (f"<div style='font-family:{C.FUI}; font-size:12px; "
                f"color:{C.T0}; line-height:1.6;'>{html}</div>")
        self._result_view.setHtml(wrap)

    def _render_pending(self, card_id: str):
        meta = self._items.get(card_id) or {}
        title = str(meta.get("name") or "(제목 없음)").strip()
        self._result_view.setHtml(
            f"<div style='color:{C.T3}; font-family:{C.FUI}; "
            f"font-size:12px; text-align:center; padding:60px 20px;'>"
            f"<div style='font-size:36px; margin-bottom:12px;'>⏳</div>"
            f"<div style='color:{C.T2}; font-weight:600;'>"
            f"변경점 #{card_id} — {title}</div>"
            f"<div style='margin-top:8px;'>AI 분석 진행 중...</div>"
            f"</div>")

    def _render_error(self, card_id: str, msg: str):
        from html import escape as _esc
        self._result_view.setHtml(
            f"<div style='color:{C.RED}; font-family:{C.FUI}; "
            f"font-size:12px; padding:24px;'>"
            f"<div style='font-size:32px;'>❌</div>"
            f"<div style='font-weight:700; margin-top:8px;'>"
            f"변경점 #{card_id} 분석 실패</div>"
            f"<pre style='color:{C.T1}; background:{C.BG_PANEL}; "
            f"border:1px solid {C.BDR}; border-radius:6px; padding:10px; "
            f"margin-top:12px; white-space:pre-wrap; font-family:{C.FCODE};'>"
            f"{_esc(msg)}</pre>"
            f"</div>")
