"""page_placeholder.py — ⑤ 정적 검증 결과 / ⑦ 설계자 테스트 결과.

⑤ StaticResultPage / ⑦ TestResultPage — 결과 파일 첨부 기능 제공
  (공용 AttachmentBody 위젯을 페이지별 라벨/필터로 인스턴스화).

⑧ OpenItemsPage  → view.pages.page_open_items 으로 이동
⑨ DeployReviewPage → view.pages.page_deploy_review 으로 이동
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QScrollArea,
)

from config import C
from ._common import BasePage, PlaceholderBody
from .page_spec import AttachmentChip


class PlaceholderPage(BasePage):
    """추후 설계 예정 페이지 공통 클래스."""

    def __init__(self, number: str, title: str, parent=None):
        super().__init__(number, title, parent)
        self.add_body(PlaceholderBody(
            message=f"{title} — 추후 설계 예정",
            icon="🛠",
        ))


# ══════════════════════════════════════════════════════════════
#  공용 — 결과 파일 첨부 본문 (⑤ 정적 검증 / ⑦ 설계자 테스트 공용)
# ══════════════════════════════════════════════════════════════
class AttachmentBody(QWidget):
    """결과 파일 첨부 페이지 본문 — 결과 파일을 칩 리스트로 관리.

    페이지별 라벨/필터/안내문을 파라미터로 받아 재사용한다.
    ⑤ 정적 검증 결과 (Coverity/Polyspace/Klocwork 등) +
    ⑦ 설계자 테스트 결과 양쪽에서 사용.

    Args:
        dialog_title : QFileDialog 헤더 제목
        file_filter  : QFileDialog 필터 (";;" 로 그룹 구분)
        hint_text    : 카드 본문 상단에 표시할 안내 문구

    공개 API:
      - get_attachments() -> list[str] : 첨부된 파일 경로 리스트
      - clear_attachments()             : 첨부 리스트 비우기
    """

    def __init__(self, *,
                 dialog_title: str = "결과 파일 선택",
                 file_filter:  str = "모든 파일 (*.*)",
                 hint_text:    str = "",
                 parent=None):
        super().__init__(parent)
        self._dialog_title = dialog_title
        self._file_filter  = file_filter
        self._hint_text    = hint_text
        self.setStyleSheet(f"background:{C.BG_APP};")
        self._attach_chips: list[AttachmentChip] = []
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)

        # ── 카드 컨테이너 ─────────────────────────────────────
        card = QFrame()
        card.setObjectName("static_card")
        card.setStyleSheet(
            f"#static_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px; }}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # ── 카드 헤더 (제목 + 파일 추가 버튼) ─────────────────
        hdr = QFrame()
        hdr.setFixedHeight(40)
        hdr.setStyleSheet(
            f"background:#EEF2F7; border-bottom:1px solid {C.BDR};"
            f"border-top-left-radius:10px; border-top-right-radius:10px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 12, 0)
        hl.setSpacing(8)

        title = QLabel("📎  결과 파일 첨부")
        title.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hl.addWidget(title)
        hl.addStretch()

        self._count_lbl = QLabel("0개")
        self._count_lbl.setFont(QFont(C.FUI, 9))
        self._count_lbl.setStyleSheet(
            f"color:{C.T3}; background:transparent; padding-right:4px;")
        hl.addWidget(self._count_lbl)

        add_btn = QPushButton("➕  파일 추가")
        add_btn.setFixedHeight(26)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.BLUE};"
            f"  border:1px dashed {C.BLUE}; border-radius:5px;"
            f"  padding:1px 12px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BLUE_LT}; }}")
        add_btn.setToolTip(
            "정적 분석 결과 파일(Coverity / Polyspace / Klocwork 등) 선택")
        add_btn.clicked.connect(self._on_add_files)
        hl.addWidget(add_btn)

        clear_btn = QPushButton("🗑  전체 제거")
        clear_btn.setFixedHeight(26)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.RED};"
            f"  border:1px solid {C.RED}; border-radius:5px;"
            f"  padding:1px 12px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.RED}; color:#FFFFFF; }}")
        clear_btn.setToolTip("첨부된 파일 전체 제거")
        clear_btn.clicked.connect(self.clear_attachments)
        hl.addWidget(clear_btn)

        cl.addWidget(hdr)

        # ── 본문 — 안내문 + 첨부 칩 리스트 (스크롤 가능) ───
        body_outer = QWidget()
        body_outer.setStyleSheet("background:transparent;")
        bo = QVBoxLayout(body_outer)
        bo.setContentsMargins(14, 12, 14, 14)
        bo.setSpacing(8)

        hint = QLabel(self._hint_text or
            "결과 파일을 여기에 첨부할 수 있습니다. 여러 파일을 한 번에 선택할 "
            "수도 있고, 각 항목 우측 ✕ 버튼으로 개별 제거가 가능합니다.")
        hint.setFont(QFont(C.FUI, 9))
        hint.setStyleSheet(f"color:{C.T3}; background:transparent;")
        hint.setWordWrap(True)
        bo.addWidget(hint)

        # 스크롤 영역 — 첨부 파일이 많아져도 페이지 레이아웃 안 깨지도록
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; }")

        self._attach_holder = QFrame()
        self._attach_holder.setObjectName("attach_holder")
        self._attach_holder.setStyleSheet(
            "#attach_holder { background:transparent; }")
        self._attach_lay = QVBoxLayout(self._attach_holder)
        self._attach_lay.setContentsMargins(0, 4, 0, 0)
        self._attach_lay.setSpacing(4)

        # 비어있을 때 표시할 placeholder (점선 박스 + 안내문)
        self._empty_box = QFrame()
        self._empty_box.setObjectName("empty_box")
        self._empty_box.setStyleSheet(
            f"#empty_box {{ background:transparent;"
            f"  border:1px dashed {C.BDR2}; border-radius:8px; }}")
        eb = QVBoxLayout(self._empty_box)
        eb.setContentsMargins(20, 24, 20, 24)
        eb.setSpacing(6)
        em_icon = QLabel("📂")
        em_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        em_icon.setStyleSheet("background:transparent; font-size:28px;")
        eb.addWidget(em_icon)
        em_msg = QLabel("선택된 파일이 없습니다.\n우측 [➕ 파일 추가] 버튼으로 첨부하세요.")
        em_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        em_msg.setFont(QFont(C.FUI, 9))
        em_msg.setStyleSheet(f"color:{C.T3}; background:transparent;")
        eb.addWidget(em_msg)
        self._attach_lay.addWidget(self._empty_box)
        self._attach_lay.addStretch()

        scroll.setWidget(self._attach_holder)
        bo.addWidget(scroll, stretch=1)

        cl.addWidget(body_outer, stretch=1)
        outer.addWidget(card, stretch=1)

    # ── 파일 추가/제거 핸들러 ─────────────────────────────────
    def _on_add_files(self):
        """파일 선택 다이얼로그 → 선택된 파일들을 칩으로 추가."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, self._dialog_title, "", self._file_filter)
        if not paths:
            return
        # 중복 제거 — 이미 추가된 절대경로는 스킵
        existing = {os.path.abspath(chip.path) for chip in self._attach_chips}
        added = 0
        for p in paths:
            if os.path.abspath(p) in existing:
                continue
            self._add_chip(p)
            existing.add(os.path.abspath(p))
            added += 1
        if added > 0:
            self._refresh_state()

    def _add_chip(self, path: str):
        chip = AttachmentChip(path, self._attach_holder)
        chip.remove_requested.connect(self._remove_chip)
        self._attach_chips.append(chip)
        # placeholder/stretch 앞에 삽입 — 항상 칩이 위에 쌓이도록
        # placeholder(_empty_box)는 idx 0, stretch 는 마지막. 그 사이에 삽입.
        insert_idx = self._attach_lay.count() - 1   # stretch 직전
        self._attach_lay.insertWidget(insert_idx, chip)

    def _remove_chip(self, chip):
        try:
            self._attach_chips.remove(chip)
        except ValueError:
            pass
        chip.setParent(None)
        chip.deleteLater()
        self._refresh_state()

    def _refresh_state(self):
        """첨부 개수에 따라 placeholder 표시/숨김 + 카운트 라벨 갱신."""
        n = len(self._attach_chips)
        self._empty_box.setVisible(n == 0)
        self._count_lbl.setText(f"{n}개")

    # ── 공개 API ───────────────────────────────────────────────
    def get_attachments(self) -> list[str]:
        """현재 첨부된 파일 경로 리스트 (원본 경로 그대로)."""
        return [chip.path for chip in self._attach_chips]

    def clear_attachments(self):
        """첨부 리스트 전체 제거."""
        for chip in list(self._attach_chips):
            chip.setParent(None)
            chip.deleteLater()
        self._attach_chips.clear()
        self._refresh_state()


class StaticResultPage(BasePage):
    """⑤ 정적 검증 결과 — 결과 파일 첨부 페이지."""

    # 컨트롤러가 받는 시그널 — [📥 불러오기] 헤더 버튼 클릭
    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("⑤", "정적 검증 결과", parent)
        # 헤더 [📥 불러오기] + 상단 상태 배너 마운트 (BasePage 헬퍼 사용)
        self.attach_status_banner()
        self.install_load_button(self.load_requested.emit)

        self._body = AttachmentBody(
            dialog_title="정적 검증 결과 파일 선택",
            file_filter=(
                "정적 분석 결과 "
                "(*.html *.htm *.xml *.json *.csv *.txt *.log *.pdf "
                "*.xlsx *.xls *.zip);;"
                "모든 파일 (*.*)"),
            hint_text=(
                "정적 분석 도구(Coverity / Polyspace / Klocwork 등) 의 결과 "
                "파일을 여기에 첨부할 수 있습니다. 여러 파일을 한 번에 선택할 "
                "수도 있고, 각 항목 우측 ✕ 버튼으로 개별 제거가 가능합니다."),
        )
        self.add_body(self._body)

    # 편의 메서드 — 컨트롤러가 첨부 리스트 조회 시 사용
    def get_attachments(self) -> list[str]:
        return self._body.get_attachments()

    def clear_attachments(self):
        self._body.clear_attachments()


class TestResultPage(BasePage):
    """⑦ 설계자 테스트 결과 — 결과 파일 첨부 페이지.
    ⑤ 와 동일한 AttachmentBody 위젯을 라벨/필터만 바꿔 재사용.
    """

    # 컨트롤러가 받는 시그널 — [📥 불러오기] 헤더 버튼 클릭
    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("⑦", "설계자 테스트 결과", parent)
        self.attach_status_banner()
        self.install_load_button(self.load_requested.emit)

        self._body = AttachmentBody(
            dialog_title="설계자 테스트 결과 파일 선택",
            file_filter=(
                "테스트 결과 "
                "(*.html *.htm *.xml *.json *.csv *.txt *.log *.pdf "
                "*.xlsx *.xls *.docx *.zip);;"
                "모든 파일 (*.*)"),
            hint_text=(
                "설계자가 수행한 테스트 결과 파일(단위/통합/회귀 시험 보고서, "
                "테스트 실행 로그, 커버리지 리포트 등) 을 여기에 첨부할 수 "
                "있습니다. 여러 파일 동시 선택 / 개별 ✕ 제거 가능."),
        )
        self.add_body(self._body)

    # 편의 메서드 — 컨트롤러가 첨부 리스트 조회 시 사용
    def get_attachments(self) -> list[str]:
        return self._body.get_attachments()

    def clear_attachments(self):
        self._body.clear_attachments()


# ⑧ OpenItemsPage / ⑨ DeployReviewPage 는 별도 파일로 분리됨:
#   from view.pages.page_open_items   import OpenItemsPage
#   from view.pages.page_deploy_review import DeployReviewPage
