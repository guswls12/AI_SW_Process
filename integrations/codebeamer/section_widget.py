"""section_widget.py — CbSectionWidget (과거차 섹션 패널).

Codebeamer 트래커 그룹 → 이슈 행 → 상세 아코디언으로 표시하는 위젯.
accordion_list_mode 가 실사용 모드이며, 미설정 시 단순 텍스트 뷰로 폴백한다.
"""

import os
import re

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QTextEdit, QVBoxLayout, QWidget, QWidgetAction,
)

from config import C

from .api import CbFetcher
from .config import _BASE, load_config, save_config
from .dialogs import _FetchSelectDialog
from .ui_primitives import _ca, _ClickableWidget, _ElidedLabel, _FetchWorker


# ══════════════════════════════════════════════════════════════
#  CbSectionWidget — 4분할 탭 개별 섹션
# ══════════════════════════════════════════════════════════════
class CbSectionWidget(QWidget):
    """과거차 / L&L / SWE1 / SWE3 각 섹션 패널"""

    def __init__(self, title: str, icon: str, color: str,
                 section_key: str = "",
                 default_select_all: bool = False,
                 accordion_list_mode: bool = False,
                 compact_header: bool = False,
                 parent=None):
        super().__init__(parent)
        self.title              = title
        self._color             = color
        self._section_key       = section_key
        self._default_all       = default_select_all
        self._accordion_list_mode = accordion_list_mode  # 트래커 그룹 + 아이템 아코디언
        self._compact_header    = compact_header       # ExtrasPanel 내장 시 간소화 헤더
        self._thread            = self._worker = None
        self._chips: dict[str, QPushButton] = {}
        self._tracker_id_map: dict[str, str] = {}
        self._sel_lbl: QLabel  = None
        self._chip_hl           = None
        # ── 텍스트 모드 전용 ──────────────────────────────────
        self._text: QTextEdit          = None
        # ── 트래커별 MD 캐시 (accordion 일괄/개별 fetch 공용) ──
        self._tracker_content: dict[str, str]      = {}
        # ── accordion_list_mode 전용 ──────────────────────────
        self._acc_layout: QVBoxLayout              = None
        self._acc_group_frames: dict[str, QFrame]  = {}   # tracker → 그룹 프레임
        self._acc_group_bodies: dict[str, QFrame]  = {}   # tracker → 그룹 body
        self._acc_group_arrows: dict[str, QLabel]  = {}   # tracker → 펼침 화살표
        self._acc_group_counts: dict[str, QLabel]  = {}   # tracker → "N건" 뱃지
        self._acc_group_fetch_btns: dict[str, QPushButton] = {}
        self._acc_group_checkboxes: dict[str, QCheckBox] = {}  # tracker → 그룹 트라이스테이트 체크박스
        self._acc_item_rows: list[dict]            = []   # [{tracker, badge, title, ...}]
        self._acc_item_boxes: list[QCheckBox]      = []   # 아이템별 체크박스
        self._acc_item_frames: list[QFrame]        = []   # 아이템 아코디언 프레임
        self._acc_updating_group: bool             = False  # 그룹 체크 루프 방지 플래그
        self._acc_count_lbl: QLabel                = None
        self._acc_search_edit: QLineEdit           = None
        # ── 라벨 필터 상태 (전역 통합 — 모든 트래커 공통) ───────
        # {field_key: {선택된_값, ...}}
        self._global_filters: dict                 = {}
        # {tracker_name: [{"item": it, "widget": row_widget, "container": child_container_or_None}, ...]}
        # _apply_global_filter() 에서 visibility 토글용 (아이템은 여전히 트래커별로 그룹핑)
        self._tracker_rows: dict                   = {}
        # {field_key: QPushButton(with QMenu)}  — 상단 전역 필터 버튼
        self._global_filter_btns: dict             = {}
        # {field_key: {value: QCheckBox}}  — 필터 해제 시 체크박스 동기화용
        self._global_filter_cbs: dict              = {}
        # 전역 필터 버튼을 담는 레이아웃 — _populate_global_filter_options() 에서 재사용
        self._global_filter_layout                 = None
        self._build(icon)

    # 라벨로 노출할 커스텀 필드 — (표시명, 색상).
    # 헤더 칩 + 트래커 상단 필터 드롭다운에 공통 사용.
    _LABEL_FIELDS = [
        ("SW Layer",     "#2563EB"),   # 파랑
        ("1차 기능분류",  "#16A34A"),   # 초록
        ("2차 기능분류",  "#D97706"),   # 주황
    ]

    # ── UI 구성 ──────────────────────────────────────────────
    def _build(self, icon: str):
        self.setObjectName("cb_sec_frame")
        if self._compact_header:
            self.setStyleSheet(
                "#cb_sec_frame { background:" + C.BG_APP + "; border:none; }")
        else:
            self.setStyleSheet(
                "#cb_sec_frame {"
                f"  background:{C.BG_CARD};"
                f"  border:1px solid {C.BDR};"
                "  border-radius:10px;"
                "}"
            )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── 헤더 바 ───────────────────────────────────────────
        hdr_bar = QFrame()

        self._count_badge = QLabel("")
        self._count_badge.setFont(QFont(C.FUI, 9))

        self._fetch_btn = QPushButton("📥  CB 불러오기")
        self._fetch_btn.setFixedHeight(26)
        self._fetch_btn.setMinimumWidth(100)
        self._fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fetch_btn.setToolTip(
            "Codebeamer에서 선택된 트래커의 이슈 목록을 불러옵니다.\n"
            "왼쪽 패널 CB 연동 탭에서 URL/ID/PW를 먼저 설정해주세요.")
        self._fetch_btn.setStyleSheet(
            f"QPushButton {{ background:{self._color}; color:#FFF;"
            f"  border-radius:5px; font-size:11px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{_ca(self._color, 'BB')}; }}"
            f"QPushButton:disabled {{ background:{C.BDR2}; color:{C.T3}; }}"
        )
        self._fetch_btn.clicked.connect(self._on_fetch)

        # ── 검색 QLineEdit (accordion_list_mode 전용) ─────────
        # 헤더 바 왼쪽(총N건/불러오기 좌측)에 노출하기 위해 여기서 미리 생성.
        if self._accordion_list_mode:
            self._acc_search_edit = QLineEdit()
            self._acc_search_edit.setPlaceholderText("🔍  ID·제목·상태로 검색...")
            self._acc_search_edit.setFixedHeight(24)
            self._acc_search_edit.setStyleSheet(
                f"background:{C.BG_CARD}; color:{C.T0}; font-size:10px;"
                f"border:1px solid {C.BDR}; border-radius:4px; padding:1px 8px;")
            self._acc_search_edit.textChanged.connect(self._acc_filter)

        if self._compact_header:
            # 컴팩트 헤더: [검색(stretch)] + 카운트 뱃지 + 버튼 (제목은 ExtrasPanel chk_bar에 표시)
            hdr_bar.setFixedHeight(36)
            hdr_bar.setStyleSheet(
                f"background:{C.BG_CARD}; border-bottom:1px solid {C.BDR};")
            hl = QHBoxLayout(hdr_bar)
            hl.setContentsMargins(14, 0, 10, 0); hl.setSpacing(8)
            self._count_badge.setStyleSheet(f"color:{C.T2}; background:transparent;"
                                            f" font-weight:600;")
            if self._accordion_list_mode:
                hl.addWidget(self._acc_search_edit, stretch=1)
            else:
                hl.addStretch()
            hl.addWidget(self._count_badge)
            hl.addWidget(self._fetch_btn)
        else:
            # 일반 헤더: [제목] + [검색(stretch)] + 카운트 + 버튼
            hdr_bar.setFixedHeight(40)
            hdr_bar.setStyleSheet(
                f"background:{_ca(self._color, '22')};"
                f"border-bottom:1px solid {_ca(self._color, '44')};"
                "border-top-left-radius:10px;"
                "border-top-right-radius:10px;"
            )
            hl = QHBoxLayout(hdr_bar)
            hl.setContentsMargins(12, 0, 10, 0); hl.setSpacing(8)
            title_lbl = QLabel(f"{icon}  {self.title}")
            title_lbl.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
            title_lbl.setStyleSheet(f"color:{self._color}; background:transparent;")
            self._count_badge.setStyleSheet(f"color:{C.T3}; background:transparent;")
            hl.addWidget(title_lbl)
            if self._accordion_list_mode:
                hl.addSpacing(12)
                hl.addWidget(self._acc_search_edit, stretch=1)
            else:
                hl.addStretch()
            hl.addWidget(self._count_badge)
            hl.addWidget(self._fetch_btn)

        lay.addWidget(hdr_bar)

        # ── 트래커 선택 바 ────────────────────────────────────
        chip_wrap = QFrame()
        chip_wrap.setStyleSheet(
            f"background:{C.BG_PANEL}; border-bottom:1px solid {C.BDR};")
        cl = QVBoxLayout(chip_wrap)
        cl.setContentsMargins(10, 6, 10, 6)
        cl.setSpacing(4)

        # 상단 행: 라벨 + 전체/해제 버튼 + 선택 카운터
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        ctrl_lbl = QLabel("트래커 선택")
        ctrl_lbl.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
        ctrl_lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")

        all_btn = QPushButton("전체")
        none_btn = QPushButton("해제")
        for _b in (all_btn, none_btn):
            _b.setFixedHeight(18)
            _b.setFixedWidth(36)
            _b.setCursor(Qt.CursorShape.PointingHandCursor)
            _b.setStyleSheet(
                f"QPushButton {{ background:{C.BDR2}; color:{C.T2};"
                f"  border-radius:3px; font-size:9px; }}"
                f"QPushButton:hover {{ background:{C.BG_HOVER}; color:{C.T0}; }}"
            )
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn.clicked.connect(lambda: self._set_all(False))

        self._sel_lbl = QLabel("")
        self._sel_lbl.setFont(QFont(C.FUI, 9))
        self._sel_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")

        ctrl_row.addWidget(ctrl_lbl)
        ctrl_row.addWidget(all_btn)
        ctrl_row.addWidget(none_btn)
        ctrl_row.addStretch()
        ctrl_row.addWidget(self._sel_lbl)
        cl.addLayout(ctrl_row)

        # ── 트래커 표시: 그리드 박스 / 목록 / 수평 칩 ─────────
        self._load_trackers_from_cfg()

        if self._accordion_list_mode:
            # accordion_list_mode: 트래커 선택 바 자체를 숨기고
            # 메인 콘텐츠 영역의 그룹 헤더가 트래커 역할을 겸하도록 한다.
            # (ctrl_row 는 아코디언 전용 컨트롤바로 교체됨 — _build_accordion_view 에서)
            ctrl_lbl.hide()
            all_btn.hide()
            none_btn.hide()
            self._sel_lbl.hide()
            # add_row / chip_wrap 자체도 숨김 — 트래커 추가는 CB 설정 다이얼로그로 일원화
            chip_wrap.hide()

        else:
            # 수평 칩 스크롤 (텍스트 폴백 모드)
            scroll = QScrollArea()
            scroll.setFixedHeight(36)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet(
                "QScrollArea { border:none; background:transparent; }"
                "QScrollBar:horizontal { height:4px; background:transparent; }"
                f"QScrollBar::handle:horizontal {{ background:{C.BDR2}; border-radius:2px; }}"
            )
            chip_container = QWidget()
            chip_container.setStyleSheet("background:transparent;")
            chip_hl = QHBoxLayout(chip_container)
            chip_hl.setContentsMargins(0, 0, 0, 0)
            chip_hl.setSpacing(5)
            self._chip_hl = chip_hl
            self._rebuild_chips()
            scroll.setWidget(chip_container)
            cl.addWidget(scroll)

        # 트래커 추가 인라인 행
        self._add_name_edit = QLineEdit()
        self._add_id_edit   = QLineEdit()
        add_row = QHBoxLayout()
        add_row.setSpacing(5)
        self._add_name_edit.setPlaceholderText("표시 이름 (예: SWE1)")
        self._add_name_edit.setFixedHeight(22)
        self._add_name_edit.setStyleSheet(
            f"background:{C.BG_CARD}; color:{C.T0}; font-size:10px;"
            f"border:1px solid {C.BDR}; border-radius:4px; padding:1px 5px;")
        self._add_id_edit.setPlaceholderText("트래커 ID (예: 8688001)")
        self._add_id_edit.setFixedHeight(22)
        self._add_id_edit.setStyleSheet(
            f"background:{C.BG_CARD}; color:{C.T0}; font-size:10px;"
            f"border:1px solid {C.BDR}; border-radius:4px; padding:1px 5px;")
        add_btn = QPushButton("＋")
        add_btn.setFixedSize(24, 22)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setToolTip("트래커 추가")
        add_btn.setStyleSheet(
            f"QPushButton {{ background:{self._color}; color:#FFF;"
            f"  border-radius:4px; font-size:12px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:{_ca(self._color, 'BB')}; }}")
        add_btn.clicked.connect(self._on_add_tracker)
        add_row.addWidget(self._add_name_edit, 2)
        add_row.addWidget(self._add_id_edit, 2)
        add_row.addWidget(add_btn)
        cl.addLayout(add_row)

        lay.addWidget(chip_wrap)

        # 선택 카운터 초기화
        self._update_sel_label()

        # ── 진행 바 ───────────────────────────────────────────
        self._pb = QProgressBar()
        self._pb.setRange(0, 100)
        self._pb.setValue(0)
        self._pb.setFixedHeight(3)
        self._pb.setTextVisible(False)
        self._pb.setVisible(False)
        self._pb.setStyleSheet(
            f"QProgressBar {{ background:{C.BDR}; border:none; }}"
            f"QProgressBar::chunk {{ background:{self._color}; }}"
        )
        lay.addWidget(self._pb)

        # ── 하단 컨텐츠 영역 (모드에 따라 분기) ─────────────────
        if self._accordion_list_mode:
            self._build_accordion_view(lay)
        else:
            self._build_text_view(lay)

    # ── 텍스트 뷰 (기본 모드) ────────────────────────────────
    def _build_text_view(self, lay: QVBoxLayout):
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet(
            f"background:{C.BG_APP}; color:{C.T1}; border:none; font-size:11px;")
        self._text.setPlaceholderText(
            f"① 아래 입력란에 트래커 이름·ID를 입력하고 ＋ 버튼으로 추가\n"
            f"② 추가된 트래커를 선택 후 '📥 CB 불러오기' 클릭\n"
            f"→ {self.title} 이슈 목록이 여기에 표시됩니다.")
        lay.addWidget(self._text, stretch=1)
        self._load_saved()

    # ══════════════════════════════════════════════════════════
    #  아코디언 리스트 뷰 (accordion_list_mode=True)
    #  — 과거차 / L&L / SWE3 공통: 트래커 그룹 → 이슈 행 → 상세
    # ══════════════════════════════════════════════════════════
    def _build_accordion_view(self, lay: QVBoxLayout):
        # 검색 QLineEdit 은 _build() 단계에서 hdr_bar 에 이미 삽입됨 — 여기서는 생성하지 않는다.

        # 컨트롤 바: 전체/해제 + 펼치기/접기 + 전역 라벨 필터 + 카운터
        ctrl = QFrame()
        ctrl.setFixedHeight(34)
        ctrl.setStyleSheet(
            f"background:{C.BG_INPUT}; border-bottom:1px solid {C.BDR};")
        cl = QHBoxLayout(ctrl)
        cl.setContentsMargins(10, 0, 10, 0)
        cl.setSpacing(6)

        for label, checked in [("전체 선택", True), ("전체 해제", False)]:
            b = QPushButton(label)
            b.setFixedHeight(22)
            b.setFixedWidth(62)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background:{C.BDR2}; color:{C.T2};"
                f"  border-radius:3px; font-size:10px; }}"
                f"QPushButton:hover {{ background:{C.BG_HOVER}; color:{C.T0}; }}")
            b.clicked.connect(lambda _, c=checked: self._acc_set_all(c))
            cl.addWidget(b)

        # 전체 펼치기/접기 버튼
        for label, expand in [("모두 펼치기", True), ("모두 접기", False)]:
            b = QPushButton(label)
            b.setFixedHeight(22)
            b.setFixedWidth(70)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background:{_ca(self._color, '22')}; color:{self._color};"
                f"  border-radius:3px; font-size:10px; font-weight:600; }}"
                f"QPushButton:hover {{ background:{_ca(self._color, '44')}; }}")
            b.clicked.connect(lambda _, e=expand: self._acc_expand_all_groups(e))
            cl.addWidget(b)

        cl.addSpacing(8)
        # ── 전역 라벨 필터 바 (검색이 있던 자리) ──────────────────
        # 빈 컨테이너만 만들어두고, 실제 필터 버튼은
        # _populate_global_filter_options() 에서 데이터 로드 후 동적으로 추가.
        _filter_tag = QLabel("🏷  필터:")
        _filter_tag.setFont(QFont(C.FUI, 9))
        _filter_tag.setStyleSheet(f"color:{C.T3}; background:transparent;")
        cl.addWidget(_filter_tag)
        _filter_container = QWidget()
        _filter_container.setStyleSheet("background:transparent;")
        gfl = QHBoxLayout(_filter_container)
        gfl.setContentsMargins(0, 0, 0, 0)
        gfl.setSpacing(6)
        self._global_filter_layout = gfl
        cl.addWidget(_filter_container, stretch=1)

        init_msg = (
            "트래커 미설정 — 좌측 CB 연동 버튼에서 설정 후 불러오세요."
            if not self._tracker_id_map
            else "불러오기 버튼을 눌러 이슈를 가져오세요."
        )
        self._acc_count_lbl = QLabel(init_msg)
        self._acc_count_lbl.setFont(QFont(C.FUI, 9))
        self._acc_count_lbl.setStyleSheet(f"color:{C.T3}; background:transparent;")
        cl.addWidget(self._acc_count_lbl)
        lay.addWidget(ctrl)

        # 2) 트래커 그룹 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border:none; background:{C.BG_APP}; }}"
            f"QScrollBar:vertical {{ width:6px; background:transparent; }}"
            f"QScrollBar::handle:vertical {{ background:{C.BDR2}; border-radius:3px; }}")
        container = QWidget()
        container.setStyleSheet(f"background:{C.BG_APP};")
        self._acc_layout = QVBoxLayout(container)
        self._acc_layout.setContentsMargins(8, 6, 8, 6)
        self._acc_layout.setSpacing(4)
        self._acc_layout.addStretch()
        scroll.setWidget(container)
        lay.addWidget(scroll, stretch=1)
        self._load_saved()

    # ── 과거차/L&L/SWE3 MD 파서 ─────────────────────────────
    def _parse_past_md_items(self, md_text: str) -> list[dict]:
        """
        과거차·L&L·SWE3 포맷 MD에서 이슈를 파싱한다.
        포맷 예:
          ## 🔧 PLBM 이슈
          ### [630992] [PLBM_19] [HKMCJGRLBM-52] 제목...
          - **상태**: New
          - **설명**: __NX5__
          문제점
           ...
          원인
           ...
          문제점 개선
           ...
          * 자료 첨부 : [https://...]
        """
        items = []
        # '## 🔧 TRACKER 이슈' 블록으로 먼저 분리
        section_re = re.compile(r'(?m)^## 🔧 (.+?) 이슈\s*$')
        section_bounds = []
        for m in section_re.finditer(md_text):
            section_bounds.append((m.group(1).strip(), m.start(), m.end()))

        if not section_bounds:
            # 트래커 헤더 없이 바로 ### 가 있는 경우
            section_bounds = [("", 0, 0)]

        for idx, (tracker_name, _s, e) in enumerate(section_bounds):
            end = section_bounds[idx + 1][1] if idx + 1 < len(section_bounds) else len(md_text)
            section_body = md_text[e:end]
            # ### [id] 와 #### [id] 둘 다 아이템 경계로 취급.
            # (#### 는 하위 아이템 — 부모와 별개로 아코디언에 독립 행으로 표시)
            for block in re.split(r'(?m)^(?=#{3,4}\s*\[)', section_body):
                block = block.strip()
                header_m = re.match(r'(#{3,4})\s*\[(\d+)\]\s*(.+?)(?:\n|$)', block)
                if not header_m:
                    continue
                hashes    = header_m.group(1)
                is_child  = len(hashes) >= 4
                cb_id     = header_m.group(2)
                rest_title = header_m.group(3).strip()

                # [BADGE] / [JIRA-ID] 등 태그 추출
                tags = re.findall(r'\[([^\]]+)\]', rest_title)
                clean_title = re.sub(r'\[[^\]]+\]\s*', '', rest_title).strip()

                # 대표 뱃지: 트래커_번호 패턴(PLBM_4) 우선, 없으면 첫 태그
                badge = ""
                for t in tags:
                    if re.match(r'^[A-Z0-9]+_\d+$', t):
                        badge = t
                        break
                if not badge and tags:
                    badge = tags[0]
                if not badge:
                    badge = cb_id

                # Jira 링크 후보 (HKMCJGRLBM-NN 패턴)
                jira_id = ""
                for t in tags:
                    if re.match(r'^[A-Z]{3,}-\d+$', t):
                        jira_id = t
                        break

                # 상태
                sm = re.search(r'- \*\*상태\*\*:\s*(.+)', block)
                status = sm.group(1).strip() if sm else ""

                # 필드 목록 파싱: "- **필드**:" 라벨 뒤로 이어지는
                # "  - **fieldname**: value" 형식의 들여쓴 줄들을 dict 로 수집.
                # (1차/2차/3차 분류, SW Layer, 1차/2차 기능분류 등)
                fields_dict: dict = {}
                _in_fields = False
                for _line in block.split("\n"):
                    _stripped = _line.strip()
                    if _stripped == "- **필드**:":
                        _in_fields = True
                        continue
                    if _in_fields:
                        _fm = re.match(
                            r'\s+-\s*\*\*([^*\n]+)\*\*:\s*(.+)', _line)
                        if _fm:
                            fields_dict[_fm.group(1).strip()] = \
                                _fm.group(2).strip()
                        elif _stripped:
                            _in_fields = False

                # 설명 본문 — 다음 '하위 아이템' 마커나 다음 ####/### 직전까지만.
                # (이전엔 $ 까지 먹어서 자식 아이템 MD 가 부모 설명 안으로 새어 들어갔음)
                dm = re.search(
                    r'- \*\*설명\*\*:\s*([\s\S]*?)'
                    r'(?=\n\s*-\s*\*\*하위\s*아이템\*\*'
                    r'|\n\s*#{3,4}\s*\[|\Z)',
                    block)
                desc_raw = dm.group(1).strip() if dm else ""

                # 자료 첨부 추출 (* 자료 첨부 : [URL])
                attach_urls = re.findall(
                    r'(?m)^\*\s*자료\s*첨부[^:]*:\s*\[?(https?://\S+?)\]?$',
                    desc_raw)

                # 본문에서 자료 첨부 라인 제거 → 상세 섹션 파싱에 사용
                body_wo_attach = re.sub(
                    r'(?m)^\*\s*자료\s*첨부[^\n]*\n?', '', desc_raw).strip()

                # 구조화된 섹션(문제점 / 원인 / 문제점 개선 등) 추출
                sections = self._extract_loose_sections(body_wo_attach)

                items.append({
                    "tracker": tracker_name,
                    "cb_id":   cb_id,
                    "badge":   badge,
                    "jira_id": jira_id,
                    "title":   clean_title,
                    "status":  status,
                    "fields":  fields_dict,        # {필드명: 값} — UI 상단 그리드용
                    "sections": sections,          # [(label, body)]
                    "attachments": attach_urls,
                    "raw_desc": body_wo_attach,    # 폴백용 원본
                    "raw_block": block,            # 원본 ###/#### 블록
                    "is_child": is_child,          # True = 하위(####) 아이템
                })
        return items

    @staticmethod
    def _group_problem_sections(sections: list) -> list[list]:
        """
        _extract_loose_sections 결과를 '문제점/현상' 라벨 기준으로 그룹핑.
        한 아이템 설명 안에 문제점/원인/개선 세트가 여러 번 반복되는 경우,
        각 세트를 별개의 '문제'로 묶어서 UI 에 '문제 1', '문제 2' 로 표시할 수 있게 함.

        returns:
          [[(label, content), ...], [(label, content), ...], ...]
          — 각 내부 리스트가 하나의 '문제' 단위.
          문제점/현상 라벨이 한 번도 안 나오면 전체를 단일 그룹으로 반환.
        """
        if not sections:
            return []
        groups: list[list] = []
        current: list = []
        for label, content in sections:
            # 새로운 '문제점' / '현상' 을 만났고 이미 수집된 게 있으면 그룹 확정
            if label in ("문제점", "현상") and current:
                groups.append(current)
                current = [(label, content)]
            else:
                current.append((label, content))
        if current:
            groups.append(current)
        return groups

    @staticmethod
    def _extract_loose_sections(body: str) -> list[tuple[str, str]]:
        """
        본문에서 '문제점', '원인', '문제점 개선' 등 섹션 헤더를 탐지해
        [(label, content), ...] 리스트로 반환. 헤더 매칭 실패 시 빈 리스트.
        """
        # 흔한 헤더 라벨 (한국어).
        # 긴 것 먼저! 안 그러면 "문제점" 이 "문제점 개선" 을 먼저 먹어치움.
        HEADERS = [
            "문제점 개선", "개선 방안", "개선", "문제점", "원인", "현상",
            "내용", "설명", "참조", "비고", "결론", "확인 방법", "조치",
        ]
        # 헤더 앞에 ')', '>', '#', '-', '*', '•' 등 위키 잔여 찌꺼기가 붙어도 인식.
        # 헤더 뒤는 선택적 ':' 또는 공백 + 줄바꿈/문장 끝.
        pattern = re.compile(
            r'(?m)^[\)\s>#\-\*•・]*'
            r'(' + '|'.join(re.escape(h) for h in HEADERS) + r')'
            r'\s*[:：]?\s*$')
        matches = list(pattern.finditer(body))
        if not matches:
            return []
        result = []
        for i, m in enumerate(matches):
            label = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            content = body[start:end].strip()
            # 선행 __태그__ 제거 (예: __NX5__)
            content = re.sub(r'^_{1,2}[^\n_]+_{1,2}\s*\n', '', content)
            # 이스케이프된 백슬래시 정리
            content = content.replace("\\\\", "\n").replace("~-", "-")
            content = re.sub(r'\n{3,}', '\n\n', content).strip()
            if content:
                result.append((label, content))
        return result

    # ── 아코디언 채우기 ─────────────────────────────────────
    def _populate_accordion(self, md_text: str):
        """MD 텍스트를 파싱해 트래커 그룹 + 아이템 아코디언으로 표시."""
        if self._acc_layout is None:
            return

        # 기존 위젯 제거
        while self._acc_layout.count():
            it = self._acc_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._acc_group_frames.clear()
        self._acc_group_bodies.clear()
        self._acc_group_arrows.clear()
        self._acc_group_counts.clear()
        self._acc_group_fetch_btns.clear()
        self._acc_group_checkboxes.clear()
        self._acc_item_rows.clear()
        self._acc_item_boxes.clear()
        self._acc_item_frames.clear()
        self._global_filters.clear()
        self._tracker_rows.clear()
        self._global_filter_btns.clear()
        self._global_filter_cbs.clear()

        items = self._parse_past_md_items(md_text)
        if not items:
            empty = QLabel(
                f"표시할 이슈가 없습니다.\n"
                f"📥 CB 불러오기 버튼을 눌러 데이터를 가져오세요.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{C.T3}; background:transparent; padding:40px;"
                f"font-size:11px;")
            self._acc_layout.addWidget(empty)
            self._acc_layout.addStretch()
            self._count_badge.setText("총 0건")
            if self._acc_count_lbl:
                self._acc_count_lbl.setText("0 / 0 선택")
            return

        # 트래커별 그룹핑
        from collections import OrderedDict
        groups: OrderedDict[str, list] = OrderedDict()
        for it in items:
            groups.setdefault(it["tracker"] or "기타", []).append(it)

        for tracker_name, tracker_items in groups.items():
            self._build_accordion_group(tracker_name, tracker_items)

        self._acc_layout.addStretch()

        # ★ 전역 라벨 필터 옵션 재생성 — 모든 트래커의 아이템을 통합해
        #   SW Layer / 1차 / 2차 기능분류 고유값으로 드롭다운 구성.
        self._populate_global_filter_options(items)

        # 카운트는 '대분류(최상위) 아이템' 만 집계 — 하위(####) 는 제외
        total = sum(1 for it in items if not it.get("is_child"))
        # default_select_all 이 True 면 아이템 체크박스가 기본 체크 상태이므로
        # 초기 선택 카운트도 total 로 맞추고, 그룹 체크박스 상태도 동기화한다.
        checked = total if self._default_all else 0
        self._count_badge.setText(f"총 {total}건")
        if self._acc_count_lbl:
            self._acc_count_lbl.setText(f"{checked} / {total} 선택")
        if self._default_all:
            # 그룹 헤더의 트라이스테이트 체크박스를 Checked 로 동기화
            from PyQt6.QtCore import Qt as _Qt
            for grp_cb in self._acc_group_checkboxes.values():
                grp_cb.blockSignals(True)
                grp_cb.setCheckState(_Qt.CheckState.Checked)
                grp_cb.blockSignals(False)

    def _build_accordion_group(self, tracker_name: str, tracker_items: list[dict]):
        """단일 트래커 그룹 UI (접을 수 있는 헤더 + 아이템 목록) 생성."""
        # 그룹 프레임
        grp = QFrame()
        grp.setObjectName("acc_group")
        grp.setStyleSheet(
            f"#acc_group {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:6px; }}")
        gv = QVBoxLayout(grp)
        gv.setContentsMargins(0, 0, 0, 0)
        gv.setSpacing(0)

        # ── 그룹 헤더 ───────────────────────────────────
        hdr = _ClickableWidget()
        hdr.setObjectName("acc_grp_hdr")
        hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr.setStyleSheet(
            f"#acc_grp_hdr {{ background:{_ca(self._color, '14')};"
            f"  border-bottom:1px solid {_ca(self._color, '33')};"
            f"  border-top-left-radius:6px; border-top-right-radius:6px; }}"
            f"#acc_grp_hdr:hover {{ background:{_ca(self._color, '22')}; }}")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 10, 0)
        hl.setSpacing(8)
        hdr.setFixedHeight(36)

        arrow = QLabel("▶")
        arrow.setFixedWidth(14)
        arrow.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
        arrow.setStyleSheet(
            f"color:{self._color}; background:transparent;")

        name_lbl = QLabel(tracker_name)
        name_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        name_lbl.setStyleSheet(
            f"color:{self._color}; background:transparent;")

        # 트래커 헤더 카운트도 대분류(최상위)만 집계
        _top_cnt = sum(1 for it in tracker_items if not it.get("is_child"))
        cnt_lbl = QLabel(f"{_top_cnt}건")
        cnt_lbl.setFont(QFont(C.FUI, 9))
        cnt_lbl.setStyleSheet(
            f"color:{C.T2}; background:transparent;")

        # 개별 fetch 버튼 (이 트래커만 다시 불러오기)
        fetch_btn = QPushButton("☁  불러오기")
        fetch_btn.setFixedHeight(22)
        fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fetch_btn.setToolTip(f"{tracker_name} 데이터만 다시 불러오기")
        fetch_btn.setStyleSheet(
            f"QPushButton {{ background:{_ca(self._color, '33')}; color:{self._color};"
            f"  border-radius:4px; font-size:10px; border:none; padding:0 8px; }}"
            f"QPushButton:hover {{ background:{_ca(self._color, '66')}; color:#FFF; }}"
            f"QPushButton:disabled {{ background:{C.BDR2}; color:{C.T3}; }}")
        if tracker_name in self._tracker_id_map:
            fetch_btn.clicked.connect(
                lambda _, n=tracker_name: self._on_fetch_single(n))
        else:
            fetch_btn.setVisible(False)

        hl.addWidget(arrow)
        hl.addWidget(name_lbl)
        hl.addSpacing(6)
        hl.addWidget(cnt_lbl)
        hl.addStretch()
        hl.addWidget(fetch_btn)

        # 그룹 체크박스 → 하위 아이템 전체 선택/해제
        grp_cb = QCheckBox()
        grp_cb.setTristate(True)
        grp_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        grp_cb.setToolTip(f"{tracker_name} 하위 아이템 전체 선택/해제")
        grp_cb.setStyleSheet(
            f"QCheckBox {{ color:{C.T1}; font-size:10px; background:transparent; spacing:6px; }}"
            f"QCheckBox::indicator {{ width:14px; height:14px; }}"
            f"QCheckBox::indicator:checked {{"
            f"  background:{self._color}; border:2px solid {self._color};"
            f"  border-radius:3px; }}"
            f"QCheckBox::indicator:indeterminate {{"
            f"  background:{_ca(self._color, '99')}; border:2px solid {self._color};"
            f"  border-radius:3px; }}"
            f"QCheckBox::indicator:unchecked {{"
            f"  background:{C.BG_CARD}; border:1px solid {C.BDR2};"
            f"  border-radius:3px; }}")

        def _on_grp_cb_clicked(_checked, tn=tracker_name):
            from PyQt6.QtCore import Qt as _Qt
            # clicked 시그널은 체크 상태 변화 후의 새로운 상태를 전달
            new_state = grp_cb.checkState()
            # Partial 상태였다면 사용자 클릭으로 Checked 처리
            if new_state == _Qt.CheckState.PartiallyChecked:
                new_state = _Qt.CheckState.Checked
                grp_cb.blockSignals(True)
                grp_cb.setCheckState(new_state)
                grp_cb.blockSignals(False)
            target = (new_state == _Qt.CheckState.Checked)
            self._acc_updating_group = True
            try:
                for row, cb, frame in zip(self._acc_item_rows, self._acc_item_boxes,
                                          self._acc_item_frames):
                    if (row.get("tracker") or "기타") == tn and frame.isVisible():
                        cb.setChecked(target)
            finally:
                self._acc_updating_group = False
            self._on_acc_check_changed()

        grp_cb.clicked.connect(_on_grp_cb_clicked)

        # ── 그룹 Body (아이템 목록) ──────────────────────
        body = QFrame()
        body.setObjectName("acc_grp_body")
        body.setStyleSheet(f"#acc_grp_body {{ background:{C.BG_APP}; }}")
        body.setVisible(False)   # 기본 접힘
        bv = QVBoxLayout(body)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(0)

        # 전체선택 행 (body 상단)
        sel_row = QWidget()
        sel_row.setStyleSheet(
            f"background:{_ca(self._color, '0d')};"
            f"border-bottom:1px solid {_ca(self._color, '22')};")
        sel_hl = QHBoxLayout(sel_row)
        sel_hl.setContentsMargins(14, 6, 14, 6)
        sel_hl.setSpacing(6)
        grp_cb.setParent(sel_row)
        sel_hl.addWidget(grp_cb)
        sel_all_lbl = QLabel("전체선택")
        sel_all_lbl.setFont(QFont(C.FUI, 10))
        sel_all_lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")
        sel_hl.addWidget(sel_all_lbl)
        sel_hl.addStretch()
        bv.addWidget(sel_row)

        # ── 라벨 필터 바는 전역(상단 컨트롤 바)으로 이전됨.
        #    트래커별 필터 UI는 여기서 생성하지 않는다.

        # ── 부모/자식 그룹핑: 순차적으로 나오는 is_child 아이템을
        #   바로 앞 부모에 귀속시켜 트리 구조로 묶는다. ─────────────
        parent_children: list = []   # [(parent_it, [child_its...]), ...]
        cur_parent = None
        cur_children: list = []
        for it in tracker_items:
            if it.get("is_child"):
                if cur_parent is None:
                    # 부모가 아직 안 나왔으면 고아 → 단독 행으로 추가
                    parent_children.append((it, []))
                else:
                    cur_children.append(it)
            else:
                if cur_parent is not None:
                    parent_children.append((cur_parent, cur_children))
                cur_parent = it
                cur_children = []
        if cur_parent is not None:
            parent_children.append((cur_parent, cur_children))

        # ── Pass 1: 자식 컨테이너(빈 상태) + 부모 프레임 생성 ───
        #   별도 트리 토글 버튼을 두지 않고, 부모 헤더/▼ 클릭으로
        #   상세 패널과 하위 컨테이너가 '동시에' 펼쳐지도록 companion 연결.
        parent_built = []   # [(parent_it, children, parent_frame, parent_cb, child_container), ...]
        cb_to_frame: dict = {}
        cb_to_checkbox: dict = {}   # ★ cb_id → 해당 최상위 아이템의 체크박스 (link_row 캐스케이드용)
        for parent_it, children in parent_children:
            if children:
                child_container = QFrame()
                child_container.setObjectName("child_container")
                child_container.setStyleSheet(
                    f"#child_container {{"
                    f"  background:{_ca(self._color, '06')}; }}")
                child_container.setVisible(False)   # 기본 접힘
                cc_l = QVBoxLayout(child_container)
                cc_l.setContentsMargins(0, 0, 0, 0)
                cc_l.setSpacing(0)
            else:
                child_container = None

            parent_frame = self._build_accordion_item(
                parent_it, companion=child_container)
            # ★ _build_accordion_item 이 self._acc_item_boxes 끝에 cb 를 append 하므로
            #    방금 추가된 부모 체크박스를 [-1] 로 안전하게 잡는다.
            parent_cb = self._acc_item_boxes[-1] if self._acc_item_boxes else None
            _pid = str(parent_it.get("cb_id", ""))
            cb_to_frame[_pid] = parent_frame
            if parent_cb is not None:
                cb_to_checkbox[_pid] = parent_cb
            parent_built.append(
                (parent_it, children, parent_frame, parent_cb, child_container))

        # ── Pass 2: 레이아웃 배치 + 자식 채우기 + 필터용 행 추적 ───
        _rows_for_filter: list = []
        for parent_it, children, parent_frame, parent_cb, child_container in parent_built:
            bv.addWidget(parent_frame)
            _rows_for_filter.append({
                "item": parent_it,
                "widget": parent_frame,
                "container": child_container,
            })
            if not children or child_container is None:
                continue
            cc_l = child_container.layout()
            child_cbs: list = []   # ★ 이번 부모에 캐스케이드 시킬 체크박스 모음
            for c_it in children:
                c_cb_id = str(c_it.get("cb_id", ""))
                target = cb_to_frame.get(c_cb_id)
                # 자식 cb_id 가 이미 상위(최상위) 아이템으로 존재하면
                # 중복 렌더하지 말고 클릭 시 해당 상위로 점프하는 링크 행만 표시.
                if target is not None and target is not parent_frame:
                    cf = self._build_link_row(c_it, target)
                    # ★ link_row 는 체크박스가 없지만, 가리키는 최상위 아이템의
                    #   체크박스를 캐스케이드 대상에 포함 → 부모 체크 시 원본도 같이 체크
                    linked_cb = cb_to_checkbox.get(c_cb_id)
                    if linked_cb is not None:
                        child_cbs.append(linked_cb)
                else:
                    cf = self._build_accordion_item(c_it)
                    # _build_accordion_item 이 방금 append 한 자식 cb 를 잡는다
                    if self._acc_item_boxes:
                        child_cbs.append(self._acc_item_boxes[-1])
                cc_l.addWidget(cf)
                _rows_for_filter.append({
                    "item": c_it,
                    "widget": cf,
                    "container": None,
                })
            bv.addWidget(child_container)

            # ── ★ 상위 체크 → 하위 자동 체크 캐스케이드 ──────────
            if parent_cb is not None and child_cbs:
                def _cascade(checked, _children=child_cbs):
                    for ccb in _children:
                        if ccb.isChecked() != checked:
                            ccb.setChecked(checked)
                parent_cb.toggled.connect(_cascade)

        self._tracker_rows[tracker_name] = _rows_for_filter

        gv.addWidget(hdr)
        gv.addWidget(body)

        # 그룹 토글 연결 — _ClickableWidget.clicked 시그널 사용
        def _toggle_group(b=body, a=arrow):
            visible = not b.isVisible()
            b.setVisible(visible)
            a.setText("▼" if visible else "▶")
        hdr.clicked.connect(_toggle_group)

        # stretch 앞에 삽입
        idx = max(0, self._acc_layout.count() - 1)
        self._acc_layout.insertWidget(idx, grp)

        self._acc_group_frames[tracker_name] = grp
        self._acc_group_bodies[tracker_name] = body
        self._acc_group_arrows[tracker_name] = arrow
        self._acc_group_counts[tracker_name] = cnt_lbl
        self._acc_group_fetch_btns[tracker_name] = fetch_btn
        self._acc_group_checkboxes[tracker_name] = grp_cb

    # ══════════════════════════════════════════════════════════
    #  전역 라벨 필터 (SW Layer / 1차·2차 기능분류) — 모든 트래커 통합
    # ══════════════════════════════════════════════════════════
    def _populate_global_filter_options(self, items: list[dict]):
        """아코디언 로드 후, 모든 아이템 기준으로 전역 필터 드롭다운을 재생성.
        SW Layer / 1차·2차 기능분류 세 필드의 '전체 아이템 내 고유값'을 각 버튼의 메뉴로 구성.
        """
        gfl = self._global_filter_layout
        if gfl is None:
            return

        # 기존 버튼/메뉴 제거
        while gfl.count():
            it = gfl.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._global_filter_btns.clear()
        self._global_filter_cbs.clear()

        for _f_key, _f_color in self._LABEL_FIELDS:
            _unique = sorted({
                ((it.get("fields") or {}).get(_f_key) or "").strip()
                for it in items
            } - {""})
            if not _unique:
                continue

            _btn = QPushButton(f"{_f_key}  ▾")
            _btn.setFixedHeight(22)
            _btn.setCursor(Qt.CursorShape.PointingHandCursor)
            _btn.setToolTip(f"{_f_key} 값으로 필터링 (다중 선택 가능)")
            _btn.setStyleSheet(
                f"QPushButton {{ color:{_f_color};"
                f"  background:{_ca(_f_color, '12')};"
                f"  border:1px solid {_ca(_f_color, '44')};"
                f"  border-radius:10px; padding:2px 10px;"
                f"  font-size:9pt; font-weight:600; }}"
                f"QPushButton:hover {{ background:{_ca(_f_color, '26')}; }}"
                f"QPushButton::menu-indicator {{ image:none; width:0; }}")

            _menu = QMenu(_btn)
            _menu.setStyleSheet(
                f"QMenu {{"
                f"  background:{C.BG_CARD};"
                f"  border:1px solid {_ca(_f_color, '66')};"
                f"  border-radius:10px;"
                f"  padding:0;"
                f"}}")

            # 메뉴 상단 헤더 (필드 타이틀)
            _hdr_w = QWidget()
            _hdr_w.setFixedHeight(32)
            _hdr_w.setStyleSheet(
                f"background:{_ca(_f_color, '16')};"
                f"border-top-left-radius:10px;"
                f"border-top-right-radius:10px;"
                f"border-bottom:1px solid {_ca(_f_color, '44')};")
            _hl = QHBoxLayout(_hdr_w)
            _hl.setContentsMargins(14, 0, 14, 0)
            _hl.setSpacing(6)
            _hdr_lbl = QLabel(f"🏷  {_f_key}")
            _hdr_lbl.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
            _hdr_lbl.setStyleSheet(
                f"color:{_f_color}; background:transparent; border:none;")
            _hl.addWidget(_hdr_lbl)
            _hl.addStretch()
            _hdr_act = QWidgetAction(_menu)
            _hdr_act.setDefaultWidget(_hdr_w)
            _hdr_act.setDisabled(True)
            _menu.addAction(_hdr_act)

            # 값 목록 (QCheckBox 행)
            _cbs_in_field: dict = {}
            for _v in _unique:
                _row = QWidget()
                _row.setCursor(Qt.CursorShape.PointingHandCursor)
                _row.setStyleSheet(
                    f"QWidget {{ background:transparent; }}"
                    f"QWidget:hover {{ background:{_ca(_f_color, '14')}; }}")
                _rl = QHBoxLayout(_row)
                _rl.setContentsMargins(14, 6, 20, 6)
                _rl.setSpacing(10)
                _chk = QCheckBox(_v)
                _chk.setFont(QFont(C.FUI, 10))
                _chk.setCursor(Qt.CursorShape.PointingHandCursor)
                _chk.setStyleSheet(
                    f"QCheckBox {{"
                    f"  color:{C.T0}; background:transparent;"
                    f"  spacing:10px; border:none;"
                    f"  padding:2px; }}"
                    f"QCheckBox:hover {{ color:{_f_color}; }}"
                    f"QCheckBox::indicator {{"
                    f"  width:15px; height:15px;"
                    f"  border-radius:3px;"
                    f"  border:1.5px solid {C.BDR2};"
                    f"  background:{C.BG_INPUT}; }}"
                    f"QCheckBox::indicator:hover {{"
                    f"  border-color:{_f_color}; }}"
                    f"QCheckBox::indicator:checked {{"
                    f"  background:{_f_color};"
                    f"  border-color:{_f_color};"
                    f"  image:url(none); }}")
                _chk.toggled.connect(
                    lambda checked, k=_f_key, v=_v:
                        self._set_global_filter(k, v, checked))
                _rl.addWidget(_chk)
                _rl.addStretch()
                _cbs_in_field[_v] = _chk

                _row_act = QWidgetAction(_menu)
                _row_act.setDefaultWidget(_row)
                _menu.addAction(_row_act)

            # 하단 '필터 해제' 행
            _menu.addSeparator()
            _foot = QWidget()
            _foot.setCursor(Qt.CursorShape.PointingHandCursor)
            _foot.setStyleSheet(
                f"QWidget {{ background:transparent; }}"
                f"QWidget:hover {{ background:{_ca('#EF4444', '14')}; }}")
            _fl = QHBoxLayout(_foot)
            _fl.setContentsMargins(14, 6, 20, 8)
            _clear_lbl = QLabel(f"✕  {_f_key} 필터 해제")
            _clear_lbl.setFont(QFont(C.FUI, 9))
            _clear_lbl.setStyleSheet(
                f"color:{C.T3}; background:transparent; border:none;")
            _fl.addWidget(_clear_lbl)
            _fl.addStretch()
            def _make_clear_handler(k):
                def _handler(event):
                    self._clear_global_filter(k)
                return _handler
            _foot.mousePressEvent = _make_clear_handler(_f_key)
            _foot_act = QWidgetAction(_menu)
            _foot_act.setDefaultWidget(_foot)
            _menu.addAction(_foot_act)

            _btn.setMenu(_menu)
            gfl.addWidget(_btn)
            self._global_filter_btns[_f_key] = _btn
            self._global_filter_cbs[_f_key] = _cbs_in_field

        gfl.addStretch()

    def _set_global_filter(self, field_key: str, value: str, enabled: bool):
        """전역 필터 드롭다운 체크 변경 → 필터 set 업데이트 + 적용."""
        cur = self._global_filters.setdefault(field_key, set())
        if enabled:
            cur.add(value)
        else:
            cur.discard(value)
        self._apply_global_filter()

    def _clear_global_filter(self, field_key: str):
        """특정 필드의 전역 필터 전체 해제 + 해당 필드 체크박스 모두 해제."""
        if field_key in self._global_filters:
            self._global_filters[field_key].clear()
        cbs = self._global_filter_cbs.get(field_key) or {}
        for cb in cbs.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        btn = self._global_filter_btns.get(field_key)
        if btn and btn.menu():
            btn.menu().close()
        self._apply_global_filter()

    def _apply_global_filter(self):
        """전역 필터 상태로 모든 트래커의 모든 행 visibility 업데이트."""
        filters = self._global_filters
        any_active = any(v for v in filters.values())

        # 필터 버튼 라벨에 선택된 값 직접 표시
        for key, btn in self._global_filter_btns.items():
            sel = sorted(filters.get(key) or set())
            if not sel:
                btn.setText(f"{key}  ▾")
                btn.setToolTip(f"{key} 값으로 필터링 (다중 선택 가능)")
            else:
                first = sel[0]
                first_short = first if len(first) <= 18 \
                              else first[:16] + "…"
                if len(sel) == 1:
                    btn.setText(f"{key}: {first_short}  ▾")
                else:
                    btn.setText(
                        f"{key}: {first_short} +{len(sel)-1}  ▾")
                btn.setToolTip(
                    f"{key} 활성 필터 ({len(sel)}):\n"
                    + "\n".join(f"• {v}" for v in sel))

        # 모든 트래커의 모든 행 순회
        for rows in self._tracker_rows.values():
            for info in rows:
                it = info["item"]
                widget = info["widget"]
                container = info.get("container")

                if not any_active:
                    widget.setVisible(True)
                    continue

                match = True
                for key, allowed in filters.items():
                    if not allowed:
                        continue
                    v = ((it.get("fields") or {}).get(key) or "").strip()
                    if v not in allowed:
                        match = False
                        break
                widget.setVisible(match)
                if container is not None and not match:
                    container.setVisible(False)

    # ── 자식이 상위(최상위) 아이템을 참조할 때 쓰는 '링크 행' ─────
    def _build_link_row(self, it: dict, target_frame: QFrame) -> QWidget:
        """
        자식 아이템이 같은 트래커의 최상위 아이템과 cb_id 가 같을 때 표시.
        별개 내용을 복제해서 보여주는 대신, 클릭하면 해당 최상위 행으로
        스크롤 + 잠깐 강조하는 컴팩트한 행으로 표시한다.
        """
        row = _ClickableWidget()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setObjectName("acc_link_row")
        row.setStyleSheet(
            f"#acc_link_row {{ background:transparent;"
            f"  border-bottom:1px dashed {_ca(self._color, '44')}; }}"
            f"#acc_link_row:hover {{ background:{_ca(self._color, '1A')}; }}")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(48, 6, 10, 6)    # 자식 기본 들여쓰기보다 조금 더 깊게
        hl.setSpacing(8)

        sub_icon = QLabel("↳")
        sub_icon.setFixedWidth(12)
        sub_icon.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        sub_icon.setStyleSheet(
            f"color:{_ca(self._color, 'AA')}; background:transparent;")
        hl.addWidget(sub_icon)

        badge = QLabel(it.get("badge", ""))
        badge.setFixedHeight(20)
        badge.setFont(QFont(C.FUI, 8, QFont.Weight.Bold))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color:{self._color}; background:{_ca(self._color, '10')};"
            f"border:1px solid {_ca(self._color, '33')}; border-radius:4px;"
            f"padding:0 6px; min-width:60px;")
        hl.addWidget(badge)

        title = QLabel(it.get("title", ""))
        title.setFont(QFont(C.FUI, 10))
        title.setStyleSheet(
            f"color:{C.T2}; background:transparent;"
            f"font-style:italic;")
        hl.addWidget(title, stretch=1)

        jump_icon = QLabel("↗")
        jump_icon.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        jump_icon.setStyleSheet(
            f"color:{_ca(self._color, 'CC')}; background:transparent;")
        hl.addWidget(jump_icon)

        row.clicked.connect(lambda: self._jump_to_item(target_frame))
        return row

    def _jump_to_item(self, target_frame: QFrame):
        """대상 아이템 프레임으로 스크롤 + 잠깐 배경 강조."""
        if target_frame is None:
            return
        # 부모 위젯을 타고 올라가 QScrollArea 를 찾으면 ensureWidgetVisible 호출
        p = target_frame.parentWidget()
        while p is not None and not isinstance(p, QScrollArea):
            p = p.parentWidget()
        if isinstance(p, QScrollArea):
            p.ensureWidgetVisible(target_frame, 50, 80)

        # 1.2초간 연한 하이라이트
        try:
            orig_ss = target_frame.styleSheet()
            target_frame.setStyleSheet(
                (orig_ss or "")
                + f"\n#acc_item {{ background:{_ca(self._color, '3A')}; }}")
            QTimer.singleShot(1200,
                              lambda: target_frame.setStyleSheet(orig_ss))
        except Exception:
            pass

    def _build_accordion_item(self, it: dict, companion: QWidget = None) -> QFrame:
        """단일 이슈 행 (체크박스 + 뱃지 + 제목 + 상태 + 펼치기) 생성.

        :param companion: 선택 — 이 위젯의 visibility 가 아이템의 상세 패널과
                          동기화되어 함께 펼쳐지고 접힘. (부모 아이템의 자식 컨테이너 등)
        """
        cb_ss = (
            f"QCheckBox::indicator {{ width:15px; height:15px; }}"
            f"QCheckBox::indicator:checked {{"
            f"  background:{self._color}; border:2px solid {self._color};"
            f"  border-radius:3px; }}"
            f"QCheckBox::indicator:unchecked {{"
            f"  background:{C.BG_CARD}; border:1px solid {C.BDR2};"
            f"  border-radius:3px; }}")

        acc = QFrame()
        acc.setObjectName("acc_item")
        acc.setStyleSheet(
            f"#acc_item {{ border-bottom:1px solid {C.BDR};"
            f"  background:transparent; }}")
        al = QVBoxLayout(acc)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)

        is_child = bool(it.get("is_child"))

        # 헤더 행 — 자식(하위) 아이템은 왼쪽 들여쓰기로 시각 구분
        hdr = _ClickableWidget()
        hdr.setObjectName("acc_item_hdr")
        hdr.setStyleSheet(
            f"#acc_item_hdr {{ background:transparent; }}"
            f"#acc_item_hdr:hover {{ background:{C.BG_HOVER}; }}")
        hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr_l = QHBoxLayout(hdr)
        left_margin = 34 if is_child else 14   # 자식은 들여쓰기
        hdr_l.setContentsMargins(left_margin, 6, 10, 6)
        hdr_l.setSpacing(8)

        # 자식 아이템에 '↳' 연결 아이콘 표시
        if is_child:
            sub_icon = QLabel("↳")
            sub_icon.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
            sub_icon.setFixedWidth(12)
            sub_icon.setStyleSheet(
                f"color:{_ca(self._color, 'AA')}; background:transparent;")
            hdr_l.addWidget(sub_icon)

        cb = QCheckBox()
        cb.setFixedWidth(18)
        cb.setStyleSheet(cb_ss)
        # default_select_all=True 로 생성된 섹션(과거차/L&L/SWE3)은
        # 아이템 로드 시 기본 체크 상태로 시작해야 AI 컨텍스트에 자동 포함됨.
        cb.setChecked(bool(self._default_all))
        cb.toggled.connect(self._on_acc_check_changed)

        # 자식은 뱃지 배경/테두리를 살짝 연하게(구분용)
        badge_bg_alpha  = '10' if is_child else '1A'
        badge_brd_alpha = '33' if is_child else '55'
        badge_lbl = QLabel(it["badge"])
        badge_lbl.setFixedHeight(20)
        badge_lbl.setFont(QFont(C.FUI, 8, QFont.Weight.Bold))
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_lbl.setStyleSheet(
            f"color:{self._color}; background:{_ca(self._color, badge_bg_alpha)};"
            f"border:1px solid {_ca(self._color, badge_brd_alpha)}; border-radius:4px;"
            f"padding:0 6px; min-width:60px;")

        title_lbl = _ElidedLabel(it["title"])
        title_lbl.setFont(QFont(C.FUI, 10))
        title_lbl.setStyleSheet(f"color:{C.T1}; background:transparent;")

        status = it.get("status", "")
        sc = ("#16A34A" if any(k in status.lower()
                               for k in ["완료", "close", "done", "resolved"])
              else "#D97706" if "진행" in status or "progress" in status.lower()
              else C.T3)
        st_lbl = QLabel(status)
        st_lbl.setFont(QFont(C.FUI, 8))
        st_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        st_lbl.setStyleSheet(
            f"color:{sc}; background:transparent; font-weight:600;"
            f"min-width:46px;")

        expand_btn = QPushButton("▼")
        expand_btn.setFixedSize(20, 20)
        expand_btn.setFlat(True)
        expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        expand_btn.setStyleSheet(
            f"QPushButton {{ color:{C.T3}; font-size:9px;"
            f"  background:transparent; border:none; }}"
            f"QPushButton:hover {{ color:{C.T0}; }}")

        hdr_l.addWidget(cb)
        hdr_l.addWidget(badge_lbl)
        hdr_l.addWidget(title_lbl, stretch=1)

        # ── 라벨 칩 (SW Layer / 1차·2차 기능분류) ─────────────
        # 행마다 라벨 칩 위치가 세로로 일치하도록 각 슬롯을 고정 폭으로 생성.
        # 값이 없는 필드는 같은 폭의 투명 스페이서로 자리만 확보한다.
        # 클릭 동작은 제거 — 단순 표시용 라벨.
        _fields = it.get("fields") or {}
        _CHIP_WIDTHS = {"SW Layer": 92, "1차 기능분류": 130, "2차 기능분류": 150}
        for _key, _color in self._LABEL_FIELDS:
            _val = (_fields.get(_key) or "").strip()
            _fixed_w = _CHIP_WIDTHS.get(_key, 110)
            if not _val:
                # 빈 슬롯 — 같은 폭의 투명 스페이서로 자리만 차지 (세로 정렬 유지)
                _spacer = QWidget()
                _spacer.setFixedWidth(_fixed_w)
                _spacer.setStyleSheet("background:transparent;")
                hdr_l.addWidget(_spacer)
                continue
            _short = _val if len(_val) <= 16 else _val[:14] + "…"
            _chip = QLabel(_short)
            _chip.setFixedWidth(_fixed_w)   # ★ 고정 폭으로 행간 세로 정렬
            _chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _chip.setToolTip(f"{_key}: {_val}")
            _chip.setStyleSheet(
                f"QLabel {{ color:{_color};"
                f"  background:{_ca(_color, '18')};"
                f"  border:1px solid {_ca(_color, '55')};"
                f"  border-radius:8px; padding:1px 7px;"
                f"  font-size:8pt; min-height:16px; }}")
            hdr_l.addWidget(_chip)

        hdr_l.addWidget(st_lbl)
        hdr_l.addWidget(expand_btn)

        # 상세 패널 (접힘)
        detail = QFrame()
        detail.setVisible(False)
        detail.setObjectName("acc_item_detail")
        detail.setStyleSheet(
            f"#acc_item_detail {{ background:{C.BG_CARD};"
            f"  border-top:1px solid {C.BDR}; }}")
        dt_l = QVBoxLayout(detail)
        dt_l.setContentsMargins(36, 12, 16, 14)
        dt_l.setSpacing(10)

        def _sec_lbl(text, color=C.T2):
            l = QLabel(text)
            l.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
            l.setStyleSheet(
                f"color:{color}; background:transparent;"
                f"border-bottom:1px solid {C.BDR}; padding-bottom:2px;")
            return l

        def _body_lbl(text):
            l = QLabel(text)
            l.setFont(QFont(C.FUI, 10))
            l.setStyleSheet(f"color:{C.T1}; background:transparent;")
            l.setWordWrap(True)
            l.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            return l

        # ── 필드 그리드 (분류/SW Layer/기능분류 등) ─────────────
        # MD 의 "- **필드**:" 블록에서 파싱된 메타 정보를 3열 그리드로
        # 상세 패널 맨 위에 먼저 출력.
        fields = it.get("fields") or {}
        if fields:
            from html import escape as _esc
            fields_frame = QFrame()
            fields_frame.setStyleSheet(
                f"background:{_ca(self._color, '0A')};"
                f"border:1px solid {_ca(self._color, '22')};"
                f"border-radius:4px;")
            f_grid = QGridLayout(fields_frame)
            f_grid.setContentsMargins(12, 10, 12, 10)
            f_grid.setHorizontalSpacing(22)
            f_grid.setVerticalSpacing(8)
            _cols = 3
            for _idx, (_k, _v) in enumerate(fields.items()):
                _r, _c = divmod(_idx, _cols)
                _cell = QLabel(
                    f'<span style="color:{C.T3};font-weight:bold;">'
                    f'{_esc(_k)}:</span>&nbsp; '
                    f'<span style="color:{C.T1};">{_esc(_v)}</span>')
                _cell.setTextFormat(Qt.TextFormat.RichText)
                _cell.setFont(QFont(C.FUI, 9))
                _cell.setStyleSheet("background:transparent;")
                _cell.setWordWrap(True)
                _cell.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse)
                f_grid.addWidget(_cell, _r, _c)
            # 각 열을 균등 분배
            for _c in range(_cols):
                f_grid.setColumnStretch(_c, 1)
            dt_l.addWidget(fields_frame)

        sections = it.get("sections", [])
        if sections:
            # '문제점/현상' 기준으로 그룹핑해서 '문제 1', '문제 2' 헤더를 붙임
            problem_groups = self._group_problem_sections(sections)
            multiple = len(problem_groups) > 1

            def _render_section_row(lbl: str, cont: str):
                """단일 (label, content) 를 렌더.

                CSS border-left 로 왼쪽 바를 그리면 Qt QSS 가 기본 QFrame
                프레임과 겹쳐 두 줄로 보이는 렌더링 아티팩트가 있음.
                → 좌측 3px 컬러 바를 '독립 QFrame' 으로 분리하고,
                   내용 박스에는 아예 border 를 넣지 않는다.
                """
                # 프로그램 BLUE 통일 — 기존 sky blue(#0EA5E9) 였음
                color = C.BLUE
                dt_l.addWidget(_sec_lbl(lbl, color))

                wrapper = QWidget()
                wrapper.setStyleSheet("background:transparent;")
                hl = QHBoxLayout(wrapper)
                hl.setContentsMargins(0, 0, 0, 0)
                hl.setSpacing(0)

                # 좌측 3px 컬러 바 (단순 배경색 위젯)
                bar = QFrame()
                bar.setFrameShape(QFrame.Shape.NoFrame)
                bar.setFixedWidth(3)
                bar.setStyleSheet(
                    f"QFrame {{ background:{color}; border:none; }}")
                hl.addWidget(bar)

                # 내용 박스 — 보더 없이 배경 틴트만
                content_frame = QFrame()
                content_frame.setFrameShape(QFrame.Shape.NoFrame)
                content_frame.setStyleSheet(
                    f"QFrame {{"
                    f"  background:{_ca(color, '0D')};"
                    f"  border:none;"
                    f"}}")
                fl = QVBoxLayout(content_frame)
                fl.setContentsMargins(10, 6, 10, 6)
                fl.addWidget(_body_lbl(cont))
                hl.addWidget(content_frame, 1)

                dt_l.addWidget(wrapper)

            if multiple:
                group_color = self._color   # 트래커 카테고리 색 (과거차: 보라색)
                for g_idx, group in enumerate(problem_groups, 1):
                    # ── '문제 N' 그룹 헤더 ─────────────────────
                    g_hdr = QLabel(f"📌  문제 {g_idx}")
                    g_hdr.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
                    g_hdr.setStyleSheet(
                        f"color:#FFFFFF;"
                        f"background:{group_color};"
                        f"padding:6px 12px;"
                        f"border-radius:4px;"
                        f"margin-top:{'12px' if g_idx > 1 else '0px'};"
                    )
                    dt_l.addWidget(g_hdr)
                    # 그룹 내 섹션들
                    for lbl, cont in group:
                        _render_section_row(lbl, cont)
            else:
                # 문제가 하나뿐이면 기존대로 헤더 없이 렌더
                for lbl, cont in sections:
                    _render_section_row(lbl, cont)
        else:
            # 파싱 실패 시 원본 설명 폴백 — 단, 실제 내용이 있을 때만
            # "(없음)", "--", "-" 같은 플레이스홀더는 표시하지 않음.
            raw = it.get("raw_desc", "").strip()
            if raw and raw not in ("(없음)", "--", "-", "—"):
                dt_l.addWidget(_sec_lbl("원본 설명"))
                fb = _body_lbl(raw[:2000])
                dt_l.addWidget(fb)

        # 자료 첨부 링크 — 프로그램 BLUE 통일 (기존 sky blue #0EA5E9)
        if it.get("attachments"):
            dt_l.addWidget(_sec_lbl("자료 첨부", C.BLUE_DK))
            for url in it["attachments"]:
                link = QLabel(f'<a href="{url}" style="color:{C.BLUE_DK};">🔗 {url}</a>')
                link.setFont(QFont(C.FUI, 9))
                link.setStyleSheet(f"background:transparent; color:{C.BLUE_DK};")
                link.setOpenExternalLinks(True)
                link.setWordWrap(True)
                dt_l.addWidget(link)

        # CB 원문 ID 표시 (링크 버튼은 미구현 — 태그는 추후 구현 예정)
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        cbid_lbl = QLabel(f"CB #{it['cb_id']}")
        cbid_lbl.setFont(QFont(C.FUI, 8))
        cbid_lbl.setStyleSheet(
            f"color:{C.T3}; background:{C.BG_APP};"
            f"border:1px solid {C.BDR}; border-radius:4px;"
            f"padding:1px 6px;")
        meta_row.addWidget(cbid_lbl)
        if it.get("jira_id"):
            jira_lbl = QLabel(f"JIRA {it['jira_id']}")
            jira_lbl.setFont(QFont(C.FUI, 8))
            jira_lbl.setStyleSheet(
                f"color:{C.T3}; background:{C.BG_APP};"
                f"border:1px solid {C.BDR}; border-radius:4px;"
                f"padding:1px 6px;")
            meta_row.addWidget(jira_lbl)
        meta_row.addStretch()
        dt_l.addLayout(meta_row)

        al.addWidget(hdr)
        al.addWidget(detail)

        def _toggle_item(d=detail, b=expand_btn, comp=companion):
            v = not d.isVisible()
            d.setVisible(v)
            if comp is not None:
                comp.setVisible(v)
            b.setText("▲" if v else "▼")

        expand_btn.clicked.connect(lambda _: _toggle_item())
        hdr.clicked.connect(_toggle_item)

        self._acc_item_rows.append(it)
        self._acc_item_boxes.append(cb)
        self._acc_item_frames.append(acc)
        return acc

    # ── 아코디언 컨트롤 핸들러 ───────────────────────────────
    def _acc_set_all(self, checked: bool):
        for cb in self._acc_item_boxes:
            cb.setChecked(checked)

    def _acc_expand_all_groups(self, expand: bool):
        for name, body in self._acc_group_bodies.items():
            body.setVisible(expand)
            arrow = self._acc_group_arrows.get(name)
            if arrow:
                arrow.setText("▼" if expand else "▶")

    def _acc_filter(self, text: str):
        """검색어로 아이템 행 필터 (트래커 그룹은 내부 매칭 있을 때만 표시)."""
        q = text.strip().lower()
        # 먼저 모든 아이템 visibility 설정
        for row, cb, frame in zip(
                self._acc_item_rows, self._acc_item_boxes, self._acc_item_frames):
            show = (not q
                    or q in row["title"].lower()
                    or q in row["badge"].lower()
                    or q in row["cb_id"]
                    or q in (row.get("jira_id") or "").lower()
                    or q in (row.get("status") or "").lower())
            frame.setVisible(show)

        # 그룹별로 매칭된 아이템 수를 세어, 0이면 그룹 숨김
        from collections import Counter
        group_hits: Counter = Counter()
        for row, frame in zip(self._acc_item_rows, self._acc_item_frames):
            if frame.isVisible():
                group_hits[row["tracker"] or "기타"] += 1

        for name, grp_frame in self._acc_group_frames.items():
            if q:
                visible = group_hits.get(name, 0) > 0
                grp_frame.setVisible(visible)
                # 검색 중엔 자동 펼치기
                body = self._acc_group_bodies.get(name)
                arrow = self._acc_group_arrows.get(name)
                if visible and body is not None and not body.isVisible():
                    body.setVisible(True)
                    if arrow:
                        arrow.setText("▼")
            else:
                grp_frame.setVisible(True)

    def _on_acc_check_changed(self):
        # "X / Y 선택" 카운터도 대분류(최상위) 아이템만 집계
        top_pairs = [(row, cb) for row, cb in
                     zip(self._acc_item_rows, self._acc_item_boxes)
                     if not row.get("is_child")]
        checked = sum(1 for _, cb in top_pairs if cb.isChecked())
        total   = len(top_pairs)
        if self._acc_count_lbl:
            self._acc_count_lbl.setText(f"{checked} / {total} 선택")

        # 그룹 체크박스 트라이스테이트 재계산
        # (그룹 체크박스 클릭 중에는 스킵해서 루프 방지)
        if self._acc_updating_group:
            return
        from PyQt6.QtCore import Qt as _Qt
        # 트래커별 (total, checked) 집계 — 대분류만 기준
        stats: dict[str, list[int]] = {}
        for row, cb in zip(self._acc_item_rows, self._acc_item_boxes):
            if row.get("is_child"):
                continue
            tn = row.get("tracker") or "기타"
            s = stats.setdefault(tn, [0, 0])
            s[0] += 1
            if cb.isChecked():
                s[1] += 1
        for tn, grp_cb in self._acc_group_checkboxes.items():
            tot, chk = stats.get(tn, [0, 0])
            if tot == 0 or chk == 0:
                new_state = _Qt.CheckState.Unchecked
            elif chk == tot:
                new_state = _Qt.CheckState.Checked
            else:
                new_state = _Qt.CheckState.PartiallyChecked
            grp_cb.blockSignals(True)
            grp_cb.setCheckState(new_state)
            grp_cb.blockSignals(False)

    def get_checked_accordion_items(self) -> list[dict]:
        """체크된 아이템(원본 dict) 목록 반환."""
        return [row for row, cb in zip(self._acc_item_rows, self._acc_item_boxes)
                if cb.isChecked()]

    def get_filtered_md(self) -> str | None:
        """
        선택(체크)된 아이템만 모아 MD 문자열로 재조립한다.
        - accordion_list_mode: 트래커별 `## 🔧 TRACKER 이슈` 헤더 + 체크된 `### [..]` 블록
        - 그 외 모드        : None (호출 측에서 파일 폴백)
        체크된 항목이 하나도 없으면 빈 문자열 반환.
        """
        # ── 아코디언 모드 (과거차) ──────────────────────────
        if self._accordion_list_mode and self._acc_item_boxes:
            from collections import OrderedDict
            groups: OrderedDict[str, list] = OrderedDict()
            for row, cb in zip(self._acc_item_rows, self._acc_item_boxes):
                if cb.isChecked():
                    tn = row.get("tracker") or "기타"
                    groups.setdefault(tn, []).append(row)
            if not groups:
                return ""
            parts = []
            for tn, rows in groups.items():
                if tn:
                    parts.append(f"## 🔧 {tn} 이슈")
                for r in rows:
                    blk = r.get("raw_block", "").strip()
                    if blk:
                        parts.append(blk)
            return "\n\n".join(parts)

        return None

    # ── 공통 메시지 표시 헬퍼 ────────────────────────────────
    def _show_msg(self, msg: str):
        if self._accordion_list_mode:
            if self._acc_count_lbl:
                self._acc_count_lbl.setText(msg)
        else:
            if self._text:
                self._text.setPlainText(msg)

    # ── 트래커 맵 로드 ───────────────────────────────────────
    def _load_trackers_from_cfg(self):
        """섹션 전용 트래커 맵을 cfg 에서 읽어온다."""
        self._tracker_id_map.clear()
        try:
            cfg = load_config()
            sec_key = f"section_{self._section_key}"
            sec_map: dict = cfg.get(sec_key, {})

            if sec_map:
                # 섹션 전용 트래커가 있으면 그것만 사용
                self._tracker_id_map.update(sec_map)
            elif self._section_key == "past":
                # tracker_* 레거시 항목 먼저 확인
                for k, v in cfg.items():
                    if k.startswith("tracker_") and v.strip():
                        name = k[len("tracker_"):].upper()
                        self._tracker_id_map[name] = v.strip()

                # 그래도 비어있으면 빈 상태 유지 (사용자가 직접 추가)
                # (TRACKER_DEFS 기본값 자동 삽입 제거 — 헷갈리는 기본 트래커 표시 방지)
        except Exception:
            pass

    def _rebuild_chips(self):
        """트래커 목록을 수평 칩 스크롤로 재생성 (텍스트 폴백 모드)."""
        self._chips.clear()

        if self._chip_hl is None:
            return
        while self._chip_hl.count():
            item = self._chip_hl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._tracker_id_map:
            for name in self._tracker_id_map:
                self._add_chip(name, checked=self._default_all)
            self._chip_hl.addStretch()
        else:
            no_lbl = QLabel("아래 입력란에 이름·ID를 입력하고 ＋를 누르세요.")
            no_lbl.setStyleSheet(
                f"color:{C.T3}; font-size:10px; background:transparent;")
            self._chip_hl.addWidget(no_lbl)

        self._update_sel_label()

    def _add_chip(self, name: str, checked: bool = True):
        """칩 하나를 수평 스크롤 레이아웃에 추가."""
        btn = QPushButton(name)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(
            lambda _, n=name: self._remove_tracker(n))
        btn.setToolTip(f"ID: {self._tracker_id_map.get(name, '')}\n우클릭 → 삭제")
        btn.toggled.connect(lambda _, b=btn: self._on_chip_toggle(b))
        self._chips[name] = btn

        btn.setFixedHeight(26)
        btn.setMinimumWidth(max(44, len(name) * 8 + 18))
        self._apply_chip_style(btn)
        # stretch 앞에 삽입
        idx = max(0, self._chip_hl.count() - 1)
        self._chip_hl.insertWidget(idx, btn)

    # ── 트래커 개별 MD 경로 / 개별 fetch (accordion 그룹 헤더 공용) ──
    def _md_path_for(self, name: str) -> str:
        """트래커 개별 md 파일 경로."""
        safe_title = re.sub(r"[^\w가-힣]", "_", self.title)
        safe_name  = re.sub(r"[^\w가-힣]", "_", name)
        return os.path.join(_BASE, f"cb_sec_{safe_title}_{safe_name}.md")

    def _on_fetch_single(self, name: str):
        """트래커 행의 ☁ 버튼 — 단일 트래커만 fetch."""
        if name not in self._tracker_id_map:
            return
        tid = self._tracker_id_map[name]
        if not tid:
            return
        cfg = load_config()
        if not cfg.get("url") or not cfg.get("username"):
            self._show_msg("⚠️  Codebeamer 연결 정보가 없습니다.")
            return

        self._pb.setValue(0)
        self._pb.setVisible(True)

        fetcher = CbFetcher(cfg["url"], cfg["username"], cfg["password"])
        self._thread = QThread()
        self._worker = _FetchWorker(
            fetcher, {name: tid}, self._md_path_for(name))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.success.connect(
            lambda md, n=name: self._on_single_success(n, md))
        self._worker.error.connect(self._on_error)
        self._worker.success.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(
            lambda n=name: self._on_single_done(n))
        self._thread.start()

    def _on_single_success(self, name: str, md_text: str):
        """단일 트래커 fetch 완료 — 캐시 업데이트 + 뷰 갱신."""
        self._tracker_content[name] = md_text
        if self._accordion_list_mode:
            # 아코디언 모드: 전체 트래커를 합쳐 재렌더
            combined = "\n\n".join(
                self._tracker_content.get(n, "") for n in self._tracker_id_map
                if self._tracker_content.get(n, "").strip()
            )
            if combined.strip():
                self._render(combined)

    def _on_single_done(self, name: str):
        """단일 트래커 thread 종료 후 진행바 숨김."""
        self._pb.setVisible(False)

    def _parse_and_cache_trackers(self, md_text: str):
        """일괄 fetch MD를 ## 🔧 섹션으로 분리해 트래커별 캐시 저장."""
        sections = re.split(r'\n(?=## 🔧 )', md_text)
        for section in sections:
            m = re.match(r'## 🔧 (.+?) 이슈', section)
            if not m:
                continue
            name = m.group(1).strip()
            if name not in self._tracker_id_map:
                continue
            self._tracker_content[name] = section
            # 트래커별 개별 파일 저장
            try:
                with open(self._md_path_for(name), "w", encoding="utf-8") as f:
                    f.write(section)
            except Exception:
                pass

    # ── 트래커 추가 / 삭제 ───────────────────────────────────
    def _on_add_tracker(self):
        """입력란에서 이름·ID를 읽어 칩 추가 + config 저장."""
        name = self._add_name_edit.text().strip()
        tid  = self._add_id_edit.text().strip()
        if not tid:
            return
        if not name:
            name = tid  # 이름 없으면 ID를 그대로 표시

        already_exists = name in self._tracker_id_map
        self._tracker_id_map[name] = tid
        self._save_section_to_cfg()

        if already_exists:
            # 기존 항목(빈 ID였던 것)의 스타일 + 툴팁 갱신
            btn = self._chips.get(name)
            if btn:
                btn.setText(name)
                btn.setToolTip(f"ID: {tid}\n클릭하여 선택 / 우클릭 → 삭제")
                self._apply_chip_style(btn)
        else:
            self._add_chip(name, checked=True)
            self._update_sel_label()

        self._add_name_edit.clear()
        self._add_id_edit.clear()

    def _remove_tracker(self, name: str):
        """우클릭으로 칩 삭제 + config 저장."""
        if name not in self._tracker_id_map:
            return
        del self._tracker_id_map[name]
        self._save_section_to_cfg()
        self._rebuild_chips()

    def _save_section_to_cfg(self):
        """현재 _tracker_id_map 을 cfg 의 section_{key} 로 저장."""
        try:
            cfg = load_config()
            cfg[f"section_{self._section_key}"] = dict(self._tracker_id_map)
            save_config(cfg)
        except Exception:
            pass

    # ── 칩 스타일 (수평 칩 모드) ─────────────────────────────
    def _apply_chip_style(self, btn: QPushButton):
        checked = btn.isChecked()
        if checked:
            btn.setStyleSheet(
                f"QPushButton {{ background:{self._color}; color:#FFF;"
                f"  border-radius:5px; font-size:10px; font-weight:700;"
                f"  padding:0 8px; border:none; }}"
                f"QPushButton:hover {{ background:{_ca(self._color, 'BB')}; }}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton {{ background:{C.BG_APP}; color:{C.T2};"
                f"  border-radius:5px; font-size:10px;"
                f"  padding:0 8px; border:1px solid {C.BDR2}; }}"
                f"QPushButton:hover {{ background:{C.BG_HOVER}; color:{C.T0}; }}"
            )

    def _on_chip_toggle(self, btn: QPushButton):
        self._apply_chip_style(btn)
        self._update_sel_label()

    def _set_all(self, checked: bool):
        for btn in self._chips.values():
            btn.setChecked(checked)
            self._apply_chip_style(btn)
        self._update_sel_label()

    def _update_sel_label(self):
        if self._sel_lbl is None:
            return
        total = len(self._chips)
        sel   = sum(1 for b in self._chips.values() if b.isChecked())
        if total:
            self._sel_lbl.setText(f"{sel} / {total} 선택")
        else:
            self._sel_lbl.setText("")

    # ── 파일 자동 로드 ────────────────────────────────────────
    def _md_path(self) -> str:
        safe = re.sub(r"[^\w가-힣]", "_", self.title)
        return os.path.join(_BASE, f"cb_sec_{safe}.md")

    def _load_saved(self):
        if self._accordion_list_mode:
            # 트래커별 개별 파일 로드 → 전체 합쳐서 아코디언 렌더
            combined_parts = []
            for name in list(self._tracker_id_map.keys()):
                path = self._md_path_for(name)
                if os.path.exists(path):
                    try:
                        with open(path, encoding="utf-8") as f:
                            md = f.read()
                        self._tracker_content[name] = md
                        combined_parts.append(md)
                    except Exception:
                        pass
            # 트래커별 파일이 없다면 통합 md 파일 시도
            if not combined_parts:
                single_path = self._md_path()
                if os.path.exists(single_path):
                    try:
                        with open(single_path, encoding="utf-8") as f:
                            combined_parts.append(f.read())
                    except Exception:
                        pass
            combined = "\n\n".join(combined_parts)
            if combined.strip():
                self._render(combined)
            return

        # 텍스트 폴백 모드: 통합 md 파일 로드
        path = self._md_path()
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    md = f.read()
                self._render(md)
            except Exception:
                pass

    def _render(self, md_text: str):
        cnt = md_text.count("### [")
        self._count_badge.setText(f"총 {cnt}건")
        if self._accordion_list_mode:
            self._populate_accordion(md_text)
        elif self._text:
            self._text.setMarkdown(md_text)

    # ── 가져오기 ──────────────────────────────────────────────
    def _on_fetch(self):
        # accordion_list_mode (과거차/L&L/SWE3): 팝업으로 트래커 선택
        if self._accordion_list_mode:
            if not self._tracker_id_map:
                QMessageBox.information(
                    self, "트래커 미설정",
                    "Codebeamer 트래커가 설정되지 않았습니다.\n\n"
                    "좌측 패널 [Codebeamer 연동] 버튼에서\n"
                    "URL · 계정 · 트래커를 먼저 추가해주세요.")
                return
            dlg = _FetchSelectDialog(
                dict(self._tracker_id_map), self._color, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return   # 사용자가 취소
            tracker_map = dlg.get_selected()
            if not tracker_map:
                self._show_msg("⚠️  선택된 트래커가 없습니다.")
                return
        else:
            # 텍스트 폴백 모드: 칩 기반 선택 로직 (없으면 전체)
            tracker_map = {
                name: self._tracker_id_map[name]
                for name, btn in self._chips.items()
                if btn.isChecked() and name in self._tracker_id_map
            }
            if not tracker_map:
                tracker_map = dict(self._tracker_id_map)
            if not tracker_map:
                self._show_msg(
                    "⚠️  가져올 트래커가 없습니다. 트래커를 추가하거나 선택해주세요.")
                return

        cfg = load_config()
        if not cfg.get("url") or not cfg.get("username"):
            self._show_msg("⚠️  Codebeamer 연결 정보가 없습니다.\n좌측 [Codebeamer 연동] 버튼에서 설정하세요.")
            return

        self._fetch_btn.setEnabled(False)
        self._pb.setValue(0)
        self._pb.setVisible(True)
        names_str = ", ".join(tracker_map.keys())
        self._show_msg(f"⏳  [{names_str}] 데이터를 가져오는 중...")

        fetcher = CbFetcher(cfg["url"], cfg["username"], cfg["password"])
        self._thread = QThread()
        self._worker = _FetchWorker(fetcher, tracker_map, self._md_path())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.success.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.success.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_progress(self, msg: str, pct: int):
        self._pb.setValue(pct)
        self._show_msg(f"⏳  {msg}")

    def _on_success(self, md_text: str):
        self._fetch_btn.setEnabled(True)
        self._pb.setVisible(False)
        if self._accordion_list_mode:
            # 일괄 fetch → 트래커별로 분리 캐싱 + 전체를 아코디언으로 재렌더
            self._parse_and_cache_trackers(md_text)
            combined = "\n\n".join(
                self._tracker_content.get(n, "") for n in self._tracker_id_map
                if self._tracker_content.get(n, "").strip()
            )
            if not combined.strip():
                combined = md_text
            self._render(combined)
        else:
            self._render(md_text)

    def _on_error(self, msg: str):
        self._fetch_btn.setEnabled(True)
        self._pb.setVisible(False)
        self._show_msg(f"❌  오류: {msg}")

    def auto_fetch(self):
        """앱 시작 시 자동으로 데이터를 가져온다 (트래커가 설정된 경우만)."""
        if self._tracker_id_map:
            self._on_fetch()
