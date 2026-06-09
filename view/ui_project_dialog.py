"""ui_project_dialog.py — 프로그램 시작 시 표시되는 프로젝트 정보 입력 다이얼로그.

CB 연결 설정 다이얼로그 다음에 표시된다.

사용자 시나리오:
  1) **새 프로젝트** — 프로젝트명 + 버전 + (선택) 9개 트래커 ID 입력 → [✓ 시작]
                       → <project>_<version>.json 자동 생성.
  2) **기존 파일 이어서** — [📂 기존 파일 불러오기] 클릭 → %APPDATA%\\CodeReviewer
                            폴더가 QFileDialog 로 열림 → JSON 선택 → 입력 칸 자동
                            채움 → 필요 시 수정 후 [✓ 시작].

다이얼로그 결과 (accepted 시 result_data 프로퍼티):
  {
    "project_name": str,
    "version":      str,
    "trackers":     {page_key: tracker_id_or_url, ...},   # 9개 (빈 값 포함)
  }
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QWidget,
    QMessageBox,
)

from config import C
from core import project_state as ps


class ProjectStartDialog(QDialog):
    """프로그램 시작 시 (CB 다이얼로그 다음) 표시되는 프로젝트 정보 입력창."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("프로젝트 정보")
        self.setModal(True)
        self.setFixedSize(620, 720)
        self.setStyleSheet(
            f"QDialog {{ background:{C.BG_PANEL}; }}")

        self._result: dict | None = None
        # 페이지 키 → QLineEdit 매핑 (9개)
        self._tracker_inputs: dict[str, QLineEdit] = {}
        self._build()

    # ── UI 구성 ──────────────────────────────────────────────
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 16); outer.setSpacing(12)

        # ── 헤더 ───────────────────────────────────────────
        title = QLabel("📋  프로젝트 정보 입력")
        title.setFont(QFont(C.FUI, 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{C.T0}; background:transparent;")
        outer.addWidget(title)

        subtitle = QLabel(
            "프로젝트명과 버전, 그리고 ①~⑨ 페이지별 Codebeamer 트래커 ID/URL 을 "
            "입력하세요.\n"
            "기존에 작성중이던 프로젝트라면 우측 [📂 불러오기] 버튼으로 JSON 파일을 "
            "선택하면 자동 채워집니다.")
        subtitle.setFont(QFont(C.FUI, 9))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color:{C.T3}; background:transparent;")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)
        outer.addSpacing(6)

        # ── 카드 1 : 프로젝트명 / 버전 + 불러오기 버튼 ────────
        outer.addWidget(self._build_project_meta_card())

        # ── 카드 2 : 9개 트래커 ID ─────────────────────────
        outer.addWidget(self._build_trackers_card(), stretch=1)

        # ── 하단 버튼 (취소 / 시작) ─────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(8); btn_row.addStretch()
        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedHeight(36); cancel_btn.setFixedWidth(96)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BG_CARD}; color:{C.T2};"
            f"  border:1px solid {C.BDR}; border-radius:6px;"
            f"  font-size:11px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BG_HOVER}; color:{C.T0}; }}")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        start_btn = QPushButton("✓  시작")
        start_btn.setFixedHeight(36); start_btn.setMinimumWidth(140)
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:none; border-radius:6px;"
            f"  font-size:12px; font-weight:700; padding:0 22px; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:pressed {{ background:{C.BLUE_DK}; }}")
        start_btn.setDefault(True)
        start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(start_btn)
        outer.addLayout(btn_row)

        # 부모 중앙 정렬
        if self.parent() and self.parent().isVisible():
            geo = self.parent().geometry()
            self.move(geo.x() + (geo.width() - self.width()) // 2,
                      geo.y() + (geo.height() - self.height()) // 2)

    # ── 카드 1 : 프로젝트 메타 + 불러오기 ─────────────────────
    def _build_project_meta_card(self) -> QFrame:
        card = QFrame(); card.setObjectName("pj_meta")
        card.setStyleSheet(
            f"#pj_meta {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        lay = QVBoxLayout(card); lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(10)

        # 프로젝트명
        self._le_project = QLineEdit()
        self._le_project.setPlaceholderText("예: SW 배포 파이프라인 / NX5 PLBM 등")
        self._apply_input_style(self._le_project)
        lay.addLayout(self._row("프로젝트명", self._le_project))

        # 버전
        self._le_version = QLineEdit()
        self._le_version.setPlaceholderText("예: 1.2.1 / v2.0 / 2026-Q2")
        self._apply_input_style(self._le_version)
        lay.addLayout(self._row("버전",       self._le_version))

        # 불러오기 버튼 행
        load_row = QHBoxLayout(); load_row.setSpacing(8); load_row.addStretch()

        info = QLabel(
            f"저장 폴더: <code style='color:{C.T2};'>{ps.state_dir()}</code>")
        info.setStyleSheet(f"color:{C.T3}; background:transparent; font-size:9px;")
        info.setTextFormat(Qt.TextFormat.RichText)
        load_row.addWidget(info)

        load_btn = QPushButton("📂  기존 파일 불러오기")
        load_btn.setFixedHeight(30); load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.setToolTip(
            "프로젝트_버전.json 파일을 선택하면 프로젝트명/버전/9개 트래커 ID 가 "
            "자동으로 채워집니다.")
        load_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:6px;"
            f"  padding:0 14px; font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}")
        load_btn.clicked.connect(self._on_load_file)
        load_row.addWidget(load_btn)
        lay.addLayout(load_row)
        return card

    # ── 카드 2 : 9개 트래커 ID ────────────────────────────
    def _build_trackers_card(self) -> QFrame:
        card = QFrame(); card.setObjectName("pj_trackers")
        card.setStyleSheet(
            f"#pj_trackers {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # 카드 헤더
        hdr = QFrame(); hdr.setFixedHeight(40)
        hdr.setStyleSheet(
            f"background:{C.BG_PANEL}; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(8)
        accent = QFrame(); accent.setFixedSize(3, 20)
        accent.setStyleSheet(f"background:{C.BLUE}; border-radius:2px;")
        hl.addWidget(accent)
        t = QLabel("🔗  항목별 Codebeamer 트래커")
        t.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()
        hint = QLabel("URL 또는 숫자 ID — 모든 칸은 선택 입력")
        hint.setFont(QFont(C.FUI, 8))
        hint.setStyleSheet(f"color:{C.T3}; background:transparent;")
        hl.addWidget(hint)
        cl.addWidget(hdr)

        # 스크롤 영역 (9개 행이 작은 화면에서도 잘리지 않도록)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        il = QVBoxLayout(inner); il.setContentsMargins(16, 12, 16, 14); il.setSpacing(6)

        # 9 행 — 각 페이지의 트래커 입력
        for key in ps.PAGE_KEYS:
            label = ps.PAGE_LABELS.get(key, key)
            le = QLineEdit()
            le.setPlaceholderText(
                "예 : 트래커 URL 또는 트래커 ID 입력")
            self._apply_input_style(le)
            self._tracker_inputs[key] = le
            il.addLayout(self._row(label, le, label_width=140))

        scroll.setWidget(inner)
        cl.addWidget(scroll, stretch=1)
        return card

    # ── 헬퍼 ──────────────────────────────────────────────
    def _row(self, label_text: str, widget,
             label_width: int = 80) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(10)
        lb = QLabel(label_text)
        lb.setFixedWidth(label_width)
        lb.setFont(QFont(C.FUI, 10))
        lb.setStyleSheet(f"color:{C.T1}; background:transparent;")
        row.addWidget(lb); row.addWidget(widget, 1)
        return row

    def _apply_input_style(self, le: QLineEdit):
        le.setMinimumHeight(28)
        le.setStyleSheet(
            f"QLineEdit {{ background:{C.BG_INPUT}; color:{C.T0};"
            f"  border:1px solid {C.BDR}; border-radius:5px;"
            f"  padding:4px 10px; font-size:11px; }}"
            f"QLineEdit:focus {{ border-color:{C.BLUE}; }}")

    # ── 불러오기 ─────────────────────────────────────────
    def _on_load_file(self):
        """[📂 기존 파일 불러오기] — QFileDialog 로 state_dir 자동 팝업.

        선택된 JSON 을 load_state_from_path() 로 읽어 입력 칸을 모두 갱신.
        시스템 JSON (cb_config / srs_review_state / spec_state) 은 필터에서
        제외 (필터 패턴 + 안내).
        """
        start_dir = ps.state_dir()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "프로젝트 JSON 파일 선택  (저장 폴더에서 자동 표시됨)",
            start_dir,
            "프로젝트 상태 (*.json);;모든 파일 (*.*)",
        )
        if not path:
            return

        # 시스템 JSON 인지 확인 (cb_config.json 등)
        base = os.path.basename(path)
        if base in {"cb_config.json", "srs_review_state.json", "spec_state.json"}:
            QMessageBox.warning(
                self, "시스템 파일 선택됨",
                f"'{base}' 은 시스템 설정 파일입니다.\n"
                "프로젝트 상태 파일은 '<프로젝트명>_<버전>.json' 형식입니다.")
            return

        try:
            state = ps.load_state_from_path(path)
        except Exception as e:
            QMessageBox.warning(self, "로드 실패", f"파일을 읽을 수 없습니다:\n{e}")
            return

        # 프로젝트명/버전 채움
        self._le_project.setText(state.get("project_name") or "")
        self._le_version.setText(state.get("version") or "")
        # 9개 트래커 ID 채움
        trk = state.get("trackers") or {}
        for key, le in self._tracker_inputs.items():
            le.setText(str(trk.get(key) or ""))

    # ── 시작 ──────────────────────────────────────────────
    def _on_start(self):
        """[✓ 시작] — 입력값 검증 + JSON 즉시 생성 + accept."""
        project = self._le_project.text().strip()
        version = self._le_version.text().strip()

        if not project or not version:
            QMessageBox.warning(
                self, "필수 입력",
                "프로젝트명과 버전은 필수 입력입니다.")
            return

        # 트래커 ID 정규화 (URL → 숫자 ID, 빈 값은 그대로)
        trackers = {
            key: ps.url_to_tracker_id(le.text())
            for key, le in self._tracker_inputs.items()
        }

        # JSON 즉시 생성 (트래커 ID 만 우선 저장 — 페이지별 입력값은 추후 갱신)
        if not ps.set_all_trackers(project, version, trackers):
            QMessageBox.warning(
                self, "저장 실패",
                "프로젝트 상태 파일을 저장할 수 없습니다.\n"
                "프로젝트명/버전에 사용할 수 없는 문자가 있는지 확인해주세요.")
            return

        self._result = {
            "project_name": project,
            "version":      version,
            "trackers":     trackers,
        }
        self.accept()

    # ── 결과 dict ─────────────────────────────────────────
    @property
    def result_data(self) -> dict | None:
        return self._result
