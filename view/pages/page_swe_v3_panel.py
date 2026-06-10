"""page_swe_v3_panel.py — ② SWE.1 SRS / ③ SWE.2 SAD / ④ SWE.3 SDD 페이지의
재설계된 위젯들 (3단계, 2026-06).

새 구조 (사용자 명세):
  INPUT 탭 2개:
    1) 변경 전/후 입력 + 변경점 불러오기 + 변경 없음 체크
    2) ASPICE 체크리스트 (xlsx 로드 + 표시)

  OUTPUT 탭 3개:
    1) 변경점 VIEW (기존 ReqDiffView 재사용)
    2) 변경점 매칭 결과 (사용자가 변경점 ↔ 요구사항 ID 매핑)
    3) 체크리스트 AI 분석 결과 (기존 AiResultDropdownPanel 재사용)

이 파일은 새 위젯 클래스만 정의:
  · ChangePointLoadCard      — 변경점 트래커 불러오기 + 변경 없음 체크
  · AspiceChecklistCard      — ASPICE 체크리스트 xlsx 로드/표시/편집
  · ChangePointMatchingCard  — 변경점 ↔ 요구사항 ID 매칭 입력
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QPlainTextEdit, QTextEdit, QCheckBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QComboBox,
    QSplitter, QListWidget, QListWidgetItem,
)

from config import C


# ══════════════════════════════════════════════════════════════
#  ChangePointLoadCard — 변경점 트래커 불러오기 + 변경 없음 체크
# ══════════════════════════════════════════════════════════════
class ChangePointLoadCard(QFrame):
    """변경점 불러오기 + 변경 없음 체크 카드.

    이 페이지 (SRS/SAD/SDD) 의 변경점이 있다면 변경점 트래커에서 fetch.
    변경점이 없으면 체크박스 + 코멘트로 N/A 처리 (⑧⑨ 에서 N/A 표시용).

    Signals:
      load_clicked() — [📥 변경점 불러오기] 클릭
    """

    load_clicked = pyqtSignal()

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self._name = name
        self.setObjectName("cp_load_card")
        self.setStyleSheet(
            f"#cp_load_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        self._items: list[dict] = []   # fetch 된 변경점 목록 (id, name)
        self._build()

    def _build(self):
        cl = QVBoxLayout(self)
        cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # 헤더
        hdr = QFrame(); hdr.setFixedHeight(40)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 18)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        hl.addWidget(accent)
        t = QLabel("📦  변경점 불러오기")
        t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()

        self._load_btn = QPushButton("📥  변경점 불러오기")
        self._load_btn.setFixedHeight(28)
        self._load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_btn.setToolTip(
            "사양변경 트래커에서 변경점 목록을 가져옵니다.\n"
            "변경 없음 체크 시 비활성화됩니다.")
        self._load_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:disabled {{ background:#E2E8F0; color:#94A3B8;"
            f"  border-color:#CBD5E1; }}")
        self._load_btn.clicked.connect(self.load_clicked.emit)
        hl.addWidget(self._load_btn)
        cl.addWidget(hdr)

        # 본문
        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(10)

        # 변경 없음 체크박스
        self._no_change_chk = QCheckBox(
            f"이번 변경점에 {self._name} 변경 없음 — ⑧⑨ 단계에서 N/A 처리")
        self._no_change_chk.setStyleSheet(
            f"QCheckBox {{ color:{C.T1}; font-size:11px; font-weight:600;"
            f"  background:transparent; }}"
            f"QCheckBox::indicator {{ width:16px; height:16px; }}")
        self._no_change_chk.setCursor(Qt.CursorShape.PointingHandCursor)
        self._no_change_chk.stateChanged.connect(self._on_no_change_changed)
        bl.addWidget(self._no_change_chk)

        # 변경 없음 코멘트 (체크 시에만 활성화)
        self._no_change_comment = QPlainTextEdit()
        self._no_change_comment.setPlaceholderText(
            "변경 없음 사유를 입력 (예: 본 PR 에서는 요구사항 변경 없음 — System 단계만 수정)")
        self._no_change_comment.setFixedHeight(60)
        self._no_change_comment.setEnabled(False)
        self._no_change_comment.setStyleSheet(
            f"QPlainTextEdit {{ background:{C.BG_INPUT}; color:{C.T0};"
            f"  border:1px solid {C.BDR}; border-radius:5px;"
            f"  padding:6px 10px; font-size:11px; }}"
            f"QPlainTextEdit:focus {{ border-color:{C.BLUE}; }}"
            f"QPlainTextEdit:disabled {{ background:#F1F5F9;"
            f"  color:#94A3B8; }}")
        bl.addWidget(self._no_change_comment)

        # 변경점 목록 표시 영역
        self._items_label = QLabel("📂  [불러오기] 를 누르면 변경점 목록이 여기에 표시됩니다.")
        self._items_label.setStyleSheet(
            f"color:{C.T3}; background:transparent; padding:12px 0 4px 0;"
            f" font-size:10px;")
        bl.addWidget(self._items_label)

        # 변경점 리스트 영역
        self._items_holder = QFrame()
        self._items_holder.setObjectName("items_holder")
        self._items_holder.setStyleSheet(
            "#items_holder { background:#F8FAFC; border:1px solid #E2E8F0;"
            " border-radius:5px; }")
        self._items_lay = QVBoxLayout(self._items_holder)
        self._items_lay.setContentsMargins(10, 8, 10, 8); self._items_lay.setSpacing(4)
        self._items_lay.addStretch(1)
        bl.addWidget(self._items_holder, stretch=1)

        cl.addWidget(body, stretch=1)

    # ── 시그널 핸들러 ─────────────────────────────────────────
    def _on_no_change_changed(self, state):
        checked = state == Qt.CheckState.Checked.value
        self._no_change_comment.setEnabled(checked)
        self._load_btn.setEnabled(not checked)
        if checked:
            self._items_label.setText(
                "ℹ  변경 없음으로 처리됨 — 변경점 불러오기 비활성화")

    # ── 외부 API ──────────────────────────────────────────────
    def apply_items(self, items: list):
        """워커가 fetch 한 변경점 목록을 반영."""
        self._items = list(items or [])
        # 기존 라벨들 제거
        while self._items_lay.count() > 1:   # stretch 만 남기기
            it = self._items_lay.takeAt(0)
            if it is None:
                break
            w = it.widget()
            if w is not None:
                w.setParent(None); w.deleteLater()
        if not self._items:
            self._items_label.setText("📭  등록된 변경점이 없습니다.")
            return
        self._items_label.setText(
            f"📋  변경점 {len(self._items)} 건 — 매칭 결과 탭에서 요구사항 ID 와 연결하세요.")
        for it in self._items:
            cid = str(it.get("id") or "")
            name = str(it.get("name") or "")
            row = QLabel(f"  • #{cid}  {name}")
            row.setFont(QFont(C.FUI, 10))
            row.setStyleSheet(
                f"color:{C.T1}; background:transparent; padding:2px 0;")
            row.setWordWrap(True)
            self._items_lay.insertWidget(self._items_lay.count() - 1, row)

    def get_items(self) -> list:
        return list(self._items)

    def is_no_change(self) -> bool:
        return self._no_change_chk.isChecked()

    def get_no_change_comment(self) -> str:
        return self._no_change_comment.toPlainText().strip()

    def to_state(self) -> dict:
        return {
            "no_change": self._no_change_chk.isChecked(),
            "comment":   self._no_change_comment.toPlainText().strip(),
        }

    def apply_state(self, st: dict):
        if not isinstance(st, dict):
            return
        no_change = bool(st.get("no_change", False))
        self._no_change_chk.setChecked(no_change)
        self._no_change_comment.setPlainText(str(st.get("comment", "") or ""))


# ══════════════════════════════════════════════════════════════
#  AspiceChecklistCard — ASPICE 체크리스트 xlsx 로드/표시/편집
# ══════════════════════════════════════════════════════════════
class AspiceChecklistCard(QFrame):
    """체크리스트 xlsx 를 로드해서 표 형태로 표시/편집.

    컬럼: No | 체크리스트 | AI 분석 가능 여부 | 판정 | 상세 심사 내용
    (의견 컬럼은 보존하되 화면엔 미표시 — 사용자 명세에 없음)

    파일 로드 후 사용자가 K/L 컬럼만 직접 편집 가능.
    AI 분석 결과는 컨트롤러가 apply_ai_results() 로 채움.

    Signals:
      file_loaded(str)  — xlsx 파일이 로드됨 (경로 인자)
      ai_run_clicked()  — [🤖 AI 분석 실행] 클릭
    """

    file_loaded   = pyqtSignal(str)
    ai_run_clicked = pyqtSignal()

    JUDGE_OPTIONS = ["", "OK", "OK But", "NG", "N/A"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aspice_card")
        self.setStyleSheet(
            f"#aspice_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        self._state: dict = {}
        self._build()

    def _build(self):
        cl = QVBoxLayout(self)
        cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # 헤더
        hdr = QFrame(); hdr.setFixedHeight(40)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 18)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        hl.addWidget(accent)
        t = QLabel("📊  ASPICE 체크리스트")
        t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()

        self._load_btn = QPushButton("📂  체크리스트 파일 로드")
        self._load_btn.setFixedHeight(28)
        self._load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.BLUE};"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
        self._load_btn.clicked.connect(self._on_load_clicked)
        hl.addWidget(self._load_btn)

        self._ai_btn = QPushButton("🤖  AI 분석 실행")
        self._ai_btn.setFixedHeight(28)
        self._ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_btn.setToolTip(
            "변경된 요구사항 카테고리에 매칭된 체크리스트 항목만 AI 가 분석.\n"
            "나머지는 '(이전 버전 기준) 동일하며 변경없음' 으로 자동 채워집니다.")
        self._ai_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:disabled {{ background:#E2E8F0; color:#94A3B8;"
            f"  border-color:#CBD5E1; }}")
        self._ai_btn.clicked.connect(self.ai_run_clicked.emit)
        hl.addWidget(self._ai_btn)
        cl.addWidget(hdr)

        # 본문 — 메타 정보 + 표
        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(8)

        # 메타 정보 (리뷰대상 문서 + 참조 문서 개수)
        self._meta_lbl = QLabel(
            "📭  체크리스트 파일이 로드되지 않았습니다. [📂 체크리스트 파일 로드] 를 누르세요.")
        self._meta_lbl.setFont(QFont(C.FUI, 9))
        self._meta_lbl.setStyleSheet(
            f"color:{C.T3}; background:transparent;")
        self._meta_lbl.setWordWrap(True)
        bl.addWidget(self._meta_lbl)

        # 체크리스트 표
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["No", "체크리스트", "AI 가능", "판정", "상세 심사 내용"])
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            f"QTableWidget {{ background:#FFFFFF; color:{C.T0};"
            f"  border:1px solid {C.BDR}; border-radius:5px;"
            f"  font-size:10px; gridline-color:#E2E8F0;"
            f"  alternate-background-color:#F8FAFC; }}"
            f"QHeaderView::section {{ background:#EFF6FF; color:#1D4ED8;"
            f"  border:none; border-right:1px solid #BFDBFE;"
            f"  border-bottom:1px solid #BFDBFE;"
            f"  padding:6px 8px; font-size:10px; font-weight:700; }}"
            f"QTableWidget::item {{ padding:4px 6px; }}"
            f"QTableWidget::item:selected {{ background:#DBEAFE; color:{C.T0}; }}")
        hdr_v = self._table.horizontalHeader()
        hdr_v.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr_v.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr_v.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr_v.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr_v.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        bl.addWidget(self._table, stretch=1)

        cl.addWidget(body, stretch=1)

    # ── 파일 로드 ─────────────────────────────────────────────
    def _on_load_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "ASPICE 체크리스트 파일 선택", "",
            "Excel (*.xlsx);;모든 파일 (*.*)")
        if not path:
            return
        try:
            from core.checklist_parser import load_checklist
            self._state = load_checklist(path)
        except Exception as e:
            self._meta_lbl.setText(f"❌  로드 실패: {str(e)[:200]}")
            return
        self._render_state()
        self.file_loaded.emit(path)

    def load_from_path(self, path: str):
        """외부에서 경로를 직접 지정해 로드 (디폴트 체크리스트 등)."""
        try:
            from core.checklist_parser import load_checklist
            self._state = load_checklist(path)
        except Exception as e:
            self._meta_lbl.setText(f"❌  로드 실패: {str(e)[:200]}")
            return
        self._render_state()

    # ── 상태 → UI ─────────────────────────────────────────────
    def _render_state(self):
        st = self._state
        if not st:
            return
        td   = st.get("target_doc") or ""
        refs = st.get("references") or []
        items = st.get("items") or []
        self._meta_lbl.setText(
            f"📄 {td}   ·   참조 문서 {len(refs)} 건   ·   체크 항목 {len(items)} 건"
            if td else
            f"📄 (리뷰대상 미지정)   ·   참조 문서 {len(refs)} 건   ·   체크 항목 {len(items)} 건"
        )

        # 표 갱신
        self._table.setRowCount(len(items))
        for r, it in enumerate(items):
            # No (편집 불가)
            no_item = QTableWidgetItem(str(it.get("no", "")))
            no_item.setFlags(no_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(r, 0, no_item)
            # 체크리스트 본문 (편집 불가, 다줄)
            cl_item = QTableWidgetItem(str(it.get("content", "")))
            cl_item.setFlags(cl_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(r, 1, cl_item)
            # AI 가능 여부 (편집 불가)
            ai_item = QTableWidgetItem(str(it.get("ai_ok", "")))
            ai_item.setFlags(ai_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            ai_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(r, 2, ai_item)
            # 판정 — 콤보박스
            combo = QComboBox()
            combo.addItems(self.JUDGE_OPTIONS)
            current = (it.get("judge") or "").strip()
            if current in self.JUDGE_OPTIONS:
                combo.setCurrentText(current)
            combo.setStyleSheet(
                f"QComboBox {{ background:transparent; color:{C.T0};"
                f"  border:none; padding:4px 8px; font-size:10px; }}")
            combo.currentTextChanged.connect(
                lambda txt, _r=r: self._on_judge_changed(_r, txt))
            self._table.setCellWidget(r, 3, combo)
            # 상세 심사 내용 (편집 가능)
            det_item = QTableWidgetItem(str(it.get("detail", "")))
            self._table.setItem(r, 4, det_item)

        # 행 높이 자동 조정
        self._table.resizeRowsToContents()
        # detail 컬럼 변경 시 state 동기화
        try:
            self._table.itemChanged.disconnect()
        except Exception:
            pass
        self._table.itemChanged.connect(self._on_item_changed)

    def _on_judge_changed(self, row: int, value: str):
        items = self._state.get("items") or []
        if 0 <= row < len(items):
            items[row]["judge"] = value

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() != 4:
            return
        r = item.row()
        items = self._state.get("items") or []
        if 0 <= r < len(items):
            items[r]["detail"] = item.text()

    # ── AI 결과 반영 ───────────────────────────────────────────
    def apply_ai_results(self, results_by_no: dict):
        """AI 분석 결과를 해당 No 의 판정/상세에 채움.

        results_by_no: {no: {"judge": "OK", "detail": "..."}}
        AI 분석 가능 항목 (results_by_no 키) 만 채우고, 나머지는
        '(이전 버전 기준) 내용과 동일하며 변경없음' 으로 채움.
        """
        items = self._state.get("items") or []
        for it in items:
            no = it.get("no")
            res = results_by_no.get(no) if isinstance(results_by_no, dict) else None
            if res:
                it["judge"]  = res.get("judge")  or it.get("judge", "")
                it["detail"] = res.get("detail") or it.get("detail", "")
        # 표 다시 그리기
        self._render_state()

    # ── 외부 호출 ─────────────────────────────────────────────
    def get_state(self) -> dict:
        return dict(self._state)

    def set_state(self, st: dict):
        self._state = dict(st or {})
        self._render_state()


# ══════════════════════════════════════════════════════════════
#  ChangePointMatchingCard — 변경점 ↔ 요구사항 ID 매칭 입력
# ══════════════════════════════════════════════════════════════
class ChangePointMatchingCard(QFrame):
    """변경점 ↔ 요구사항 ID 매칭 카드.

    상단: 변경점 목록 + 요구사항 ID 입력 칸
    하단: 요구사항 ID 별로 정렬된 요구사항 DIFF (참조용)

    Signals:
      upload_clicked(list) — [📤 매칭 CB 업로드] 클릭 시 (mapping 리스트 인자)
    """

    upload_clicked = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cpm_card")
        self.setStyleSheet(
            f"#cpm_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        self._items: list[dict] = []     # 변경점 목록
        # 변경점별 입력칸 — [[QLineEdit, QLineEdit, ...], [], [QLineEdit], ...]
        self._req_inputs: list[list] = []
        # 변경점별 입력칸 레이아웃 (행 추가/제거용)
        self._inputs_layouts: list = []
        # 변경점별 N/A 상태 — [{na: bool, reason: str, btn: QPushButton}]
        self._na_states: list = []
        self._build()

    def _build(self):
        cl = QVBoxLayout(self)
        cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # 헤더
        hdr = QFrame(); hdr.setFixedHeight(40)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 18)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        hl.addWidget(accent)
        t = QLabel("🔗  변경점 매칭 결과")
        t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()

        self._upload_btn = QPushButton("📤  매칭 결과 CB 업로드")
        self._upload_btn.setFixedHeight(28)
        self._upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upload_btn.setToolTip(
            "매칭된 (변경점 ↔ 요구사항 ID) 결과를 Codebeamer 에 업로드합니다.")
        self._upload_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}")
        self._upload_btn.clicked.connect(self._on_upload)
        hl.addWidget(self._upload_btn)
        cl.addWidget(hdr)

        # 본문
        body = QWidget(); body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(body); bl.setContentsMargins(14, 12, 14, 14); bl.setSpacing(8)

        # 안내문
        hint = QLabel(
            "ℹ  각 변경점 옆에 해당 요구사항 ID 를 입력하세요. (예: SwR_IF_001, SwR_FR_012)\n"
            "    하단 영역에는 요구사항 DIFF (ID 별 정렬) 가 표시됩니다.")
        hint.setFont(QFont(C.FUI, 9))
        hint.setStyleSheet(f"color:{C.T3}; background:transparent;")
        hint.setWordWrap(True)
        bl.addWidget(hint)

        # 변경점 ↔ 요구사항 ID 매칭 영역
        self._mapping_scroll = QScrollArea()
        self._mapping_scroll.setWidgetResizable(True)
        self._mapping_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._mapping_scroll.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }")
        self._mapping_inner = QWidget()
        self._mapping_inner.setStyleSheet("background:transparent;")
        self._mapping_lay = QVBoxLayout(self._mapping_inner)
        self._mapping_lay.setContentsMargins(0, 6, 0, 6); self._mapping_lay.setSpacing(6)
        self._mapping_lay.addStretch(1)
        self._mapping_scroll.setWidget(self._mapping_inner)
        bl.addWidget(self._mapping_scroll, stretch=2)

        # 요구사항 DIFF 영역 — 좌측 ID 리스트 + 우측 변경 전/후 내용
        diff_lbl = QLabel("📑  요구사항 DIFF (ID 별 정렬)")
        diff_lbl.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        diff_lbl.setStyleSheet(
            f"color:{C.T1}; background:transparent; padding:6px 0 0 0;")
        bl.addWidget(diff_lbl)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setStyleSheet(
            f"QSplitter::handle {{ background:{C.BDR}; }}")

        # 좌측: ID 리스트
        self._id_list = QListWidget()
        self._id_list.setStyleSheet(
            f"QListWidget {{ background:#FFFFFF; color:{C.T0};"
            f"  border:1px solid {C.BDR}; border-radius:5px;"
            f"  padding:4px; font-size:10px; }}"
            f"QListWidget::item {{ padding:5px 8px; border-radius:3px; }}"
            f"QListWidget::item:selected {{ background:#DBEAFE; color:{C.T0}; }}"
            f"QListWidget::item:hover {{ background:#F1F5F9; }}")
        self._id_list.currentRowChanged.connect(self._on_id_selected)
        split.addWidget(self._id_list)

        # 우측: 선택된 ID 의 변경 전/후 (HTML 하이라이트)
        self._diff_text = QTextEdit()
        self._diff_text.setReadOnly(True)
        self._diff_text.setPlaceholderText(
            "좌측에서 요구사항 ID 를 선택하면 변경 전/후 내용이 표시됩니다.")
        self._diff_text.setStyleSheet(
            f"QTextEdit {{ background:#F8FAFC; color:{C.T1};"
            f"  border:1px solid {C.BDR}; border-radius:5px;"
            f"  padding:8px 12px; font-family:Consolas; font-size:11px; }}")
        split.addWidget(self._diff_text)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        bl.addWidget(split, stretch=3)

        # 그룹 데이터 — {id: {"before": str, "after": str, "type": "🔴/🟡/🟢"}}
        self._diff_groups: dict = {}

        cl.addWidget(body, stretch=1)

    def _on_id_selected(self, row: int):
        if row < 0:
            self._diff_text.clear(); return
        item = self._id_list.item(row)
        if item is None:
            return
        rid = item.data(Qt.ItemDataRole.UserRole)
        grp = self._diff_groups.get(rid)
        if not grp:
            self._diff_text.clear(); return
        import html as _html
        before = (grp.get("before") or "").strip()
        after  = (grp.get("after")  or "").strip()

        # 색상 — 변경 전 = 빨강 배경, 변경 후 = 초록 배경
        RED_BG, RED_FG   = "#FEE2E2", "#991B1B"
        GREEN_BG, GREEN_FG = "#DCFCE7", "#166534"
        HDR_STYLE = (
            "padding:4px 8px; font-weight:700; border-radius:3px;"
            " margin:4px 0 2px 0; display:block;")
        LINE_STYLE = (
            "padding:2px 8px; display:block; white-space:pre-wrap;"
            " font-family:Consolas;")

        def _block(lines: str, bg: str, fg: str, header: str) -> str:
            parts = [
                f'<div style="background:{bg}; color:{fg}; {HDR_STYLE}">'
                f'{_html.escape(header)}</div>'
            ]
            for ln in (lines or "").split("\n"):
                parts.append(
                    f'<div style="background:{bg}; color:{fg}; {LINE_STYLE}">'
                    f'{_html.escape(ln) or "&nbsp;"}</div>'
                )
            return "".join(parts)

        html_parts = []
        if before:
            html_parts.append(_block(before, RED_BG, RED_FG, "━━━ [변경 전] ━━━"))
        if after:
            html_parts.append(_block(after, GREEN_BG, GREEN_FG, "━━━ [변경 후] ━━━"))
        self._diff_text.setHtml("".join(html_parts))

    # ── 데이터 입력 ───────────────────────────────────────────
    def apply_items(self, items: list):
        """변경점 목록 반영 → 매핑 입력 행 생성. 각 변경점 옆에 [+] 로 입력칸 추가."""
        self._items = list(items or [])
        # 기존 행 제거
        while self._mapping_lay.count() > 1:
            it = self._mapping_lay.takeAt(0)
            if it is None:
                break
            w = it.widget()
            if w is not None:
                w.setParent(None); w.deleteLater()
        self._req_inputs.clear()
        self._inputs_layouts.clear()
        self._na_states.clear()
        if not self._items:
            empty = QLabel("📭  변경점이 없습니다. [변경점 불러오기] 를 먼저 실행하세요.")
            empty.setStyleSheet(
                f"color:{C.T3}; background:transparent; padding:20px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._mapping_lay.insertWidget(0, empty)
            return
        for ridx, it in enumerate(self._items):
            cid  = str(it.get("id") or "")
            name = str(it.get("name") or "")
            row = QFrame()
            row.setStyleSheet(
                f"background:#F8FAFC; border:1px solid {C.BDR}; border-radius:5px;")
            # 한 줄 가로 배치: [라벨] [ID칸들...] [+ 추가]
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 6, 10, 6); rl.setSpacing(8)

            # 좌측: 변경점 라벨 (충분한 폭)
            lbl = QLabel(f"#{cid}  {name}")
            lbl.setFont(QFont(C.FUI, 10))
            lbl.setStyleSheet(f"color:{C.T0}; background:transparent;")
            lbl.setMinimumWidth(440)
            lbl.setWordWrap(True)
            rl.addWidget(lbl)

            # 중간: 입력칸들 + [+ 추가] 버튼이 가로로 쌓일 컨테이너
            inputs_lay = QHBoxLayout()
            inputs_lay.setContentsMargins(0, 0, 0, 0); inputs_lay.setSpacing(4)

            # [+ 추가] 버튼 — 항상 끝부분에 위치 (입력칸이 그 앞에 누적됨)
            add_btn = QPushButton("➕  ID 추가")
            add_btn.setFixedHeight(26)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setToolTip("ID 입력칸 추가")
            add_btn.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{C.BLUE};"
                f"  border:1px dashed {C.BLUE}; border-radius:4px;"
                f"  padding:1px 10px; font-size:10px; font-weight:600; }}"
                f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
            add_btn.clicked.connect(
                lambda _checked=False, _r=ridx: self._add_input_for_row(_r))
            inputs_lay.addWidget(add_btn)

            # [🟡 N/A] 토글 — 해당 변경점이 이 페이지 (SRS/SAD/SDD) 와 무관한 경우
            na_btn = QPushButton("🟡  N/A")
            na_btn.setFixedHeight(26)
            na_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            na_btn.setToolTip(
                "이 변경점이 해당 페이지와 무관한 경우 — 클릭으로 토글.\n"
                "⑧/⑨ 점검표에서 X 대신 N/A (노랑) 로 표시됩니다.")
            na_btn.setCheckable(False)   # 토글 상태는 self._na_states 로 관리
            na_btn.setStyleSheet(self._na_btn_style_off())
            na_btn.clicked.connect(
                lambda _checked=False, _r=ridx: self._toggle_na(_r))
            inputs_lay.addWidget(na_btn)

            # N/A 사유 인라인 입력칸 — 토글 ON 시에만 표시 (사유는 선택)
            na_reason_le = QLineEdit()
            na_reason_le.setPlaceholderText("사유 (선택)")
            na_reason_le.setFixedHeight(26)
            na_reason_le.setMinimumWidth(160)
            na_reason_le.setMaximumWidth(260)
            na_reason_le.setStyleSheet(
                f"QLineEdit {{ background:#FFFBEB; color:#92400E;"
                f"  border:1px solid #EAB308; border-radius:4px;"
                f"  padding:2px 8px; font-size:10px; }}"
                f"QLineEdit:focus {{ border-color:#A16207; }}")
            na_reason_le.setVisible(False)
            inputs_lay.addWidget(na_reason_le)
            inputs_lay.addStretch(1)
            rl.addLayout(inputs_lay, 1)

            self._mapping_lay.insertWidget(self._mapping_lay.count() - 1, row)
            self._req_inputs.append([])
            # add_btn 도 보관해서 입력칸 추가 시 그 앞에 삽입
            self._inputs_layouts.append((inputs_lay, add_btn))
            self._na_states.append({
                "na": False, "reason": "",
                "btn": na_btn, "reason_le": na_reason_le,
            })

    def _add_input_for_row(self, row_idx: int):
        """변경점 row_idx 에 입력칸 1 개 추가 — [+ 추가] 버튼 바로 앞에 삽입."""
        if row_idx < 0 or row_idx >= len(self._inputs_layouts):
            return
        inputs_lay, add_btn = self._inputs_layouts[row_idx]

        wrap = QFrame()
        wrap.setStyleSheet("background:transparent; border:none;")
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0); wl.setSpacing(2)

        le = QLineEdit()
        le.setPlaceholderText("예: SwR_FR_001")
        le.setFixedHeight(26)
        le.setMinimumWidth(120)
        le.setMaximumWidth(180)
        le.setStyleSheet(
            f"QLineEdit {{ background:#FFFFFF; color:{C.T0};"
            f"  border:1px solid {C.BDR}; border-radius:4px;"
            f"  padding:2px 8px; font-size:10px; }}"
            f"QLineEdit:focus {{ border-color:{C.BLUE}; }}")
        wl.addWidget(le)

        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(20, 20)
        rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rm_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.T3};"
            f"  border:none; border-radius:10px; font-size:10px; }}"
            f"QPushButton:hover {{ background:{C.RED}; color:#FFFFFF; }}")
        rm_btn.clicked.connect(
            lambda _checked=False, _r=row_idx, _w=wrap, _le=le:
                self._remove_input(_r, _le, _w))
        wl.addWidget(rm_btn)

        # [+ 추가] 버튼 바로 앞에 삽입
        add_idx = inputs_lay.indexOf(add_btn)
        if add_idx < 0:
            add_idx = inputs_lay.count() - 1
        inputs_lay.insertWidget(add_idx, wrap)

        self._req_inputs[row_idx].append(le)

    def _remove_input(self, row_idx: int, le, wrap):
        if row_idx < 0 or row_idx >= len(self._req_inputs):
            return
        try:
            self._req_inputs[row_idx].remove(le)
        except ValueError:
            pass
        try:
            wrap.setParent(None); wrap.deleteLater()
        except Exception:
            pass

    # ── N/A 토글 ────────────────────────────────────────────
    @staticmethod
    def _na_btn_style_off() -> str:
        return (f"QPushButton {{ background:transparent; color:#A16207;"
                f"  border:1px dashed #EAB308; border-radius:4px;"
                f"  padding:1px 10px; font-size:10px; font-weight:600; }}"
                f"QPushButton:hover {{ background:#FEF9C3; }}")

    @staticmethod
    def _na_btn_style_on() -> str:
        return (f"QPushButton {{ background:#FEF3C7; color:#92400E;"
                f"  border:1px solid #EAB308; border-radius:4px;"
                f"  padding:1px 10px; font-size:10px; font-weight:700; }}"
                f"QPushButton:hover {{ background:#FDE68A; }}")

    def _toggle_na(self, row_idx: int):
        """N/A 토글 — 옆의 인라인 사유 입력칸 show/hide. 사유는 선택 (필수 아님)."""
        if row_idx < 0 or row_idx >= len(self._na_states):
            return
        state = self._na_states[row_idx]
        btn = state.get("btn")
        reason_le = state.get("reason_le")
        if state.get("na"):
            # 이미 N/A → 해제
            state["na"] = False
            if btn:
                btn.setText("🟡  N/A")
                btn.setStyleSheet(self._na_btn_style_off())
            if reason_le is not None:
                reason_le.setVisible(False)
            return
        # OFF → ON: 인라인 사유 칸만 노출 (사유는 비어있어도 OK)
        state["na"] = True
        if btn:
            btn.setText("🟡  N/A")
            btn.setStyleSheet(self._na_btn_style_on())
        if reason_le is not None:
            reason_le.setVisible(True)
            reason_le.setFocus()

    def set_req_diff(self, text: str):
        """레거시 호환 — 텍스트 한 덩어리. ID 그룹화 없이 그냥 표시."""
        self._diff_groups = {}
        self._id_list.clear()
        self._diff_text.setPlainText(text or "")

    def set_req_diff_groups(self, groups: dict):
        """ID 별 그룹 dict 로 좌측 리스트 + 우측 본문 갱신.

        groups: {id: {"before": str, "after": str, "type": "🔴"|"🟡"|"🟢"}}
          · 🔴 = 신규 (after 만 있음)
          · 🟢 = 삭제 (before 만 있음)
          · 🟡 = 변경 (둘 다 있고 내용 다름)
        """
        self._diff_groups = dict(groups or {})
        self._id_list.clear()
        if not self._diff_groups:
            self._diff_text.setPlainText(
                "(요구사항 ID 패턴이 감지되지 않았습니다)")
            return
        for rid in sorted(self._diff_groups.keys()):
            grp = self._diff_groups[rid]
            mark = grp.get("type") or ""
            item = QListWidgetItem(f"{mark}  {rid}")
            item.setData(Qt.ItemDataRole.UserRole, rid)
            self._id_list.addItem(item)
        # 첫 항목 자동 선택
        self._id_list.setCurrentRow(0)

    def get_req_diff(self) -> str:
        """현재 우측 텍스트 (AI 분석용 컨텍스트)."""
        # ID 그룹이 있으면 전체 합쳐서 반환
        if self._diff_groups:
            parts = []
            for rid in sorted(self._diff_groups.keys()):
                grp = self._diff_groups[rid]
                parts.append(f"━━━ {rid} ━━━")
                if grp.get("before"):
                    parts.append("[변경 전]\n" + grp["before"])
                if grp.get("after"):
                    parts.append("[변경 후]\n" + grp["after"])
                parts.append("")
            return "\n".join(parts)
        return self._diff_text.toPlainText()

    # ── 결과 수집 ─────────────────────────────────────────────
    def get_mappings(self) -> list:
        """[{"change_id":..., "change_name":..., "req_ids": [str,...],
            "na": bool, "na_reason": str}, ...]

        각 변경점의 입력칸 N 개에서 ID 를 모음 (빈 칸은 제외).
        na/na_reason 은 [🟡 N/A] 토글 상태.
        """
        out = []
        for ridx, (it, les) in enumerate(zip(self._items, self._req_inputs)):
            req_ids = []
            for le in (les or []):
                try:
                    text = (le.text() or "").strip()
                except Exception:
                    text = ""
                if text:
                    req_ids.append(text)
            # N/A 상태 — _na_states 인덱스 일치
            na_state = (self._na_states[ridx]
                        if ridx < len(self._na_states) else {})
            # 사유는 인라인 입력칸에서 그때그때 읽음 (사용자가 토글 후 입력한 최신값)
            reason_le = na_state.get("reason_le")
            na_reason = ""
            if reason_le is not None:
                try:
                    na_reason = (reason_le.text() or "").strip()
                except Exception:
                    na_reason = ""
            out.append({
                "change_id":   str(it.get("id") or ""),
                "change_name": str(it.get("name") or ""),
                "req_ids":     req_ids,
                "na":          bool(na_state.get("na", False)),
                "na_reason":   na_reason,
            })
        return out

    def _on_upload(self):
        self.upload_clicked.emit(self.get_mappings())
