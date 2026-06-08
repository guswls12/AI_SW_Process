"""_upload_status_banner.py — 페이지 헤더 아래 표시되는 트래커 등록 상태 배너.

②③④ (SWE 1·2·3) 페이지 + ⑤⑥⑦ (정적/리뷰/테스트) 페이지에서 공통 사용.

[📥 불러오기] 버튼이 눌리면 컨트롤러가 CB 트래커를 fetch 한 결과를 이 배너에
반영한다. "이미 업로드된 결과가 N건 있다 / 없다" 를 사용자에게 시각적으로
알려주는 것이 목적.

상태 전이:
  idle        — 초기 (배너 숨김 또는 회색 안내)
  loading     — fetch 진행 중
  empty       — 트래커 ID 는 있지만 등록된 이슈가 없음
  has_items   — N건 등록됨 (이슈 최대 5건 표시 + "외 N건")
  error       — fetch 실패
  no_tracker  — 트래커 ID 가 비어있음

사용자는 새 업로드도 가능하다는 점을 안내문으로 명시.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QWidget,
)

from config import C
from core.project_state import build_tracker_url


# 등록된 이슈를 배너 안에 최대 몇 개까지 펼쳐 보여줄지
_MAX_ROWS = 5


class UploadStatusBanner(QFrame):
    """페이지 상단의 트래커 상태 배너 카드."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("usb")
        self.setStyleSheet(
            f"#usb {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:8px; }}")
        # 초기엔 보이지 않음 (사용자가 [📥 불러오기] 누르기 전까지)
        self.setVisible(False)
        self._build()

    def _build(self):
        # 외곽 컨테이너 — 헤더 + 본문 2단
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10); v.setSpacing(8)

        # 헤더 — 상태 아이콘/메시지
        self._hdr = QLabel("")
        self._hdr.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        self._hdr.setStyleSheet(f"color:{C.T0}; background:transparent;")
        self._hdr.setWordWrap(True)
        v.addWidget(self._hdr)

        # 본문 — 이슈 행 컨테이너 (스크롤 없이 최대 _MAX_ROWS 행)
        self._rows_holder = QWidget()
        self._rows_holder.setStyleSheet("background:transparent;")
        self._rows_lay = QVBoxLayout(self._rows_holder)
        self._rows_lay.setContentsMargins(0, 0, 0, 0); self._rows_lay.setSpacing(3)
        v.addWidget(self._rows_holder)

        # 하단 안내문 — "새 업로드도 가능합니다"
        self._hint = QLabel("")
        self._hint.setFont(QFont(C.FUI, 9))
        self._hint.setStyleSheet(f"color:{C.T3}; background:transparent;")
        self._hint.setWordWrap(True)
        v.addWidget(self._hint)

    # ── 행 클리어 헬퍼 ─────────────────────────────────────
    def _clear_rows(self):
        while self._rows_lay.count():
            it = self._rows_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None); w.deleteLater()

    # ── 상태 메서드들 ──────────────────────────────────────
    def hide_banner(self):
        """배너 자체를 숨김 (초기/리셋)."""
        self.setVisible(False)
        self._clear_rows()
        self._hdr.setText("")
        self._hint.setText("")

    def set_loading(self, tracker_id: str):
        """fetch 진행 중."""
        self.setVisible(True)
        self._clear_rows()
        self._set_hdr_style("loading")
        self._hdr.setText(f"⏳  트래커 #{tracker_id} 등록 결과 조회 중...")
        self._hint.setText("")

    def set_no_tracker(self):
        """현재 페이지의 트래커 ID 가 비어있는 경우."""
        self.setVisible(True)
        self._clear_rows()
        self._set_hdr_style("warn")
        self._hdr.setText("⚠  이 페이지의 트래커 ID 가 설정되지 않았습니다.")
        self._hint.setText(
            "프로젝트 정보 다이얼로그에서 트래커 ID 를 입력하거나, "
            "이번 세션에서 [📤 CB 업로드] 로 새 이슈를 등록하면 자동 저장됩니다.")

    def set_empty(self, tracker_id: str):
        """트래커 ID 는 있지만 등록된 이슈가 없음."""
        self.setVisible(True)
        self._clear_rows()
        self._set_hdr_style("info")
        self._hdr.setText(
            f"ℹ  트래커 #{tracker_id} 에 아직 등록된 결과가 없습니다.")
        self._hint.setText(
            "이 페이지의 [📤 CB 업로드] 버튼으로 새 결과를 등록할 수 있습니다.")

    def set_items(self, tracker_id: str, items: list):
        """등록된 이슈 N건 표시. items: [{"id":..., "name":...}, ...]"""
        self.setVisible(True)
        self._clear_rows()
        n = len(items or [])
        self._set_hdr_style("success")
        self._hdr.setText(
            f"✅  트래커 #{tracker_id} 에 {n}건의 결과가 이미 등록되어 있습니다.")

        # 최대 _MAX_ROWS 행 표시 (가장 최근 = ID 큰 순)
        sorted_items = sorted(
            (it for it in (items or []) if isinstance(it, dict)),
            key=lambda x: int(x.get("id") or 0),
            reverse=True,
        )
        shown = sorted_items[:_MAX_ROWS]
        for it in shown:
            self._rows_lay.addWidget(self._build_row(it))

        if n > _MAX_ROWS:
            more = QLabel(f"  ⋯  외 {n - _MAX_ROWS}건 더 있음")
            more.setFont(QFont(C.FUI, 9))
            more.setStyleSheet(f"color:{C.T3}; background:transparent;")
            self._rows_lay.addWidget(more)

        self._hint.setText(
            "ℹ  새 결과를 등록하려면 헤더의 [📤 CB 업로드] 버튼을 사용하세요.")

    def set_error(self, msg: str):
        """fetch 실패."""
        self.setVisible(True)
        self._clear_rows()
        self._set_hdr_style("error")
        self._hdr.setText(f"❌  트래커 조회 실패")
        self._hint.setText((msg or "")[:200])

    # ── 헤더 색상 톤 ──────────────────────────────────────
    def _set_hdr_style(self, kind: str):
        """kind: 'loading'/'success'/'info'/'warn'/'error'"""
        if kind == "success":
            self.setStyleSheet(
                f"#usb {{ background:#F0FDF4;"
                f"  border:1px solid #86EFAC; border-radius:8px; }}")
            self._hdr.setStyleSheet(
                f"color:#15803D; background:transparent;")
        elif kind == "warn":
            self.setStyleSheet(
                f"#usb {{ background:#FFFBEB;"
                f"  border:1px solid #FCD34D; border-radius:8px; }}")
            self._hdr.setStyleSheet(
                f"color:#92400E; background:transparent;")
        elif kind == "error":
            self.setStyleSheet(
                f"#usb {{ background:#FEF2F2;"
                f"  border:1px solid #FCA5A5; border-radius:8px; }}")
            self._hdr.setStyleSheet(
                f"color:#B91C1C; background:transparent;")
        elif kind == "info":
            self.setStyleSheet(
                f"#usb {{ background:{C.BLUE_LT};"
                f"  border:1px solid {C.BLUE}; border-radius:8px; }}")
            self._hdr.setStyleSheet(
                f"color:{C.BLUE_DK}; background:transparent;")
        else:   # loading / 기본
            self.setStyleSheet(
                f"#usb {{ background:{C.BG_PANEL};"
                f"  border:1px solid {C.BDR}; border-radius:8px; }}")
            self._hdr.setStyleSheet(
                f"color:{C.T2}; background:transparent;")

    # ── 이슈 행 ─────────────────────────────────────────
    def _build_row(self, it: dict) -> QFrame:
        item_id = str(it.get("id") or "")
        name    = str(it.get("name") or it.get("summary")
                      or it.get("title") or "(제목 없음)").strip()

        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background:rgba(255,255,255,0.6);"
            f"  border:1px solid {C.BDR}; border-radius:4px; }}"
            f"QFrame:hover {{ background:{C.BG_HOVER}; }}")
        row.setFixedHeight(26)
        rl = QHBoxLayout(row); rl.setContentsMargins(8, 0, 8, 0); rl.setSpacing(8)

        id_lbl = QLabel(f"#{item_id}")
        id_lbl.setFont(QFont(C.FUI, 9, QFont.Weight.Bold))
        id_lbl.setFixedWidth(72)
        id_lbl.setStyleSheet(f"color:{C.BLUE_DK}; background:transparent;")
        rl.addWidget(id_lbl)

        name_lbl = QLabel(name)
        name_lbl.setFont(QFont(C.FUI, 10))
        name_lbl.setStyleSheet(f"color:{C.T1}; background:transparent;")
        rl.addWidget(name_lbl, 1)

        if item_id:
            url = build_tracker_url(item_id).replace("/tracker/", "/issue/")
            # build_tracker_url 은 /tracker/<id> 패턴 — 이슈 링크는 /issue/<id>
            open_btn = QPushButton("🔗 열기")
            open_btn.setFixedHeight(20)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{C.BLUE};"
                f"  border:1px solid {C.BLUE}; border-radius:3px;"
                f"  font-size:9px; font-weight:600; padding:0 8px; }}"
                f"QPushButton:hover {{ background:{C.BLUE}; color:#FFFFFF; }}")
            open_btn.clicked.connect(
                lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            rl.addWidget(open_btn)
        return row
