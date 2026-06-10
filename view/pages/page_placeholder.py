"""page_placeholder.py — ⑤ 정적 검증 결과 / ⑦ 설계자 테스트 결과.

⑤ StaticResultPage / ⑦ TestResultPage — Codebeamer 트래커 조회 페이지.
  · 사용자는 CB 에 직접 결과 파일을 업로드 (이 프로그램에서 업로드 X).
  · 페이지의 [📥 불러오기] 버튼은 트래커의 모든 이슈 + 첨부/댓글을 fetch.
  · 결과 표시: 첨부 OK/NG 상태 + 이슈별 코멘트(리뷰 내용) 리스트.

⑧ OpenItemsPage  → view.pages.page_open_items 으로 이동
⑨ DeployReviewPage → view.pages.page_deploy_review 으로 이동
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea,
)

from config import C
from ._common import BasePage


# ══════════════════════════════════════════════════════════════
#  공용 — CB 리뷰 조회 결과 본문 (⑤ 정적 검증 / ⑦ 설계자 테스트 공용)
# ══════════════════════════════════════════════════════════════
class CbReviewResultBody(QWidget):
    """CB 트래커에 등록된 결과를 표시하는 본문 위젯.

    상단 카드: 첨부 OK/NG 상태 + 트래커 정보
    본문      : 이슈별 (제목 + 첨부 개수 + 코멘트 리스트) 카드 누적
    """

    def __init__(self, *,
                 hint_text: str = "",
                 parent=None):
        super().__init__(parent)
        self._hint_text = hint_text or (
            "이 페이지의 결과 파일은 Codebeamer 에 직접 업로드해 주세요.\n"
            "[📥 불러오기] 버튼을 누르면 트래커의 첨부 상태와 모든 리뷰 댓글을 "
            "이 곳에서 확인할 수 있습니다.")
        self.setStyleSheet(f"background:{C.BG_APP};")
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)

        # ── 상단 상태 카드 ────────────────────────────────────
        self._status_card = QFrame()
        self._status_card.setObjectName("status_card")
        self._status_card.setStyleSheet(
            f"#status_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:10px;"
            f"  padding:14px 16px; }}")
        sc = QVBoxLayout(self._status_card)
        sc.setContentsMargins(0, 0, 0, 0); sc.setSpacing(6)

        # 첨부 OK/NG 라벨
        self._status_lbl = QLabel("📥  [불러오기] 를 눌러 트래커 상태를 확인하세요.")
        self._status_lbl.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        self._status_lbl.setStyleSheet(
            f"color:{C.T1}; background:transparent;")
        sc.addWidget(self._status_lbl)

        self._tracker_lbl = QLabel("")
        self._tracker_lbl.setFont(QFont(C.FUI, 9))
        self._tracker_lbl.setStyleSheet(
            f"color:{C.T3}; background:transparent;")
        sc.addWidget(self._tracker_lbl)

        self._hint_lbl = QLabel(self._hint_text)
        self._hint_lbl.setFont(QFont(C.FUI, 9))
        self._hint_lbl.setStyleSheet(
            f"color:{C.T3}; background:transparent;")
        self._hint_lbl.setWordWrap(True)
        sc.addWidget(self._hint_lbl)

        outer.addWidget(self._status_card)

        # ── 본문 — 이슈 리스트 스크롤 ──────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        self._items_holder = QWidget()
        self._items_holder.setStyleSheet("background:transparent;")
        self._items_lay = QVBoxLayout(self._items_holder)
        self._items_lay.setContentsMargins(0, 0, 0, 0)
        self._items_lay.setSpacing(8)
        self._items_lay.addStretch(1)

        scroll.setWidget(self._items_holder)
        outer.addWidget(scroll, stretch=1)

        # 내부 상태 — 결과 데이터
        self._result_data: dict = {}

    # ── 공개 API ──────────────────────────────────────────────
    def apply_result(self, data: dict):
        """워커가 emit 한 done(dict) 결과를 받아 화면에 반영."""
        self._result_data = dict(data or {})
        tid    = str(data.get("tracker_id") or "")
        has    = bool(data.get("has_attachment"))
        n_att  = int(data.get("total_attachments") or 0)
        items  = data.get("items") or []

        # 상단 상태
        if has:
            self._status_lbl.setText(
                f"✅  OK — 첨부 파일 {n_att} 개 확인됨")
            self._status_lbl.setStyleSheet(
                "color:#15803D; background:transparent;")
        else:
            self._status_lbl.setText(
                "❌  NG — 트래커에 결과 파일 첨부가 없습니다")
            self._status_lbl.setStyleSheet(
                "color:#B91C1C; background:transparent;")
        self._tracker_lbl.setText(
            f"📂  트래커 #{tid} — 이슈 {len(items)} 건 조회")

        # 본문 — 기존 카드 제거 후 새로 그림
        self._clear_items()
        if not items:
            empty = QLabel("등록된 이슈가 없습니다.")
            empty.setFont(QFont(C.FUI, 10))
            empty.setStyleSheet(
                f"color:{C.T3}; background:transparent; padding:30px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._items_lay.insertWidget(0, empty)
            return
        for idx, it in enumerate(items):
            card = self._build_item_card(it)
            # stretch(1) 가 마지막에 있으니 그 전에 삽입
            insert_idx = self._items_lay.count() - 1
            self._items_lay.insertWidget(insert_idx, card)

    def reset(self):
        """초기 상태로 — [불러오기] 누르기 전 표시."""
        self._result_data = {}
        self._status_lbl.setText(
            "📥  [불러오기] 를 눌러 트래커 상태를 확인하세요.")
        self._status_lbl.setStyleSheet(
            f"color:{C.T1}; background:transparent;")
        self._tracker_lbl.setText("")
        self._clear_items()

    def has_result(self) -> bool:
        """⑧ OPEN 항목 페이지에서 OK/NG 판정용."""
        return bool(self._result_data.get("has_attachment"))

    # ── 내부: 이슈 카드 ───────────────────────────────────────
    def _build_item_card(self, item: dict) -> QFrame:
        cid   = str(item.get("id") or "")
        name  = str(item.get("name") or "")
        atts  = item.get("attachments") or []
        cmts  = item.get("comments") or []

        card = QFrame()
        card.setObjectName("item_card")
        card.setStyleSheet(
            f"#item_card {{ background:{C.BG_CARD};"
            f"  border:1px solid {C.BDR}; border-radius:8px; }}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 10, 12, 10); cl.setSpacing(6)

        # 헤더 — #이슈ID 제목 + 첨부 N개 / 댓글 N개
        hdr = QHBoxLayout(); hdr.setSpacing(8)
        t = QLabel(f"📝  #{cid}  {name}")
        t.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{C.BLUE}; background:transparent;")
        hdr.addWidget(t, 1)

        att_lbl = QLabel(f"📎 {len(atts)}")
        att_lbl.setFont(QFont(C.FUI, 9))
        att_lbl.setStyleSheet(
            f"color:{C.T2}; background:#F1F5F9;"
            f" border:1px solid {C.BDR}; border-radius:4px;"
            f" padding:1px 8px;")
        hdr.addWidget(att_lbl)

        cmt_lbl = QLabel(f"💬 {len(cmts)}")
        cmt_lbl.setFont(QFont(C.FUI, 9))
        cmt_lbl.setStyleSheet(
            f"color:{C.T2}; background:#F1F5F9;"
            f" border:1px solid {C.BDR}; border-radius:4px;"
            f" padding:1px 8px;")
        hdr.addWidget(cmt_lbl)
        cl.addLayout(hdr)

        # 첨부 파일명 리스트 (있으면)
        if atts:
            names = [str(a.get("name") or a.get("fileName") or a.get("id") or "?")
                     for a in atts if isinstance(a, dict)]
            att_text = QLabel("📎  " + "   ".join(f"{n}" for n in names))
            att_text.setFont(QFont(C.FUI, 9))
            att_text.setStyleSheet(
                f"color:{C.T2}; background:transparent;"
                f" padding:2px 0;")
            att_text.setWordWrap(True)
            cl.addWidget(att_text)

        # 코멘트 리스트 (있으면)
        if cmts:
            for c in cmts:
                if not isinstance(c, dict):
                    continue
                body = (c.get("comment") or c.get("text")
                        or c.get("description") or "")
                submitter = (c.get("submitter") or c.get("user")
                             or c.get("author") or "")
                if isinstance(submitter, dict):
                    submitter = submitter.get("name") or submitter.get("id") or ""
                date = c.get("submittedAt") or c.get("createdAt") or c.get("date") or ""
                if not str(body).strip():
                    continue
                meta = " · ".join([s for s in (str(submitter), str(date)[:19]) if s])
                # 코멘트 카드 (들여쓰기 + 좌측 borderline)
                row = QFrame()
                row.setStyleSheet(
                    f"background:#F8FAFC; border-left:3px solid {C.BLUE};"
                    f" border-radius:3px;")
                rl = QVBoxLayout(row)
                rl.setContentsMargins(10, 6, 10, 6); rl.setSpacing(2)
                if meta:
                    m = QLabel(meta)
                    m.setFont(QFont(C.FUI, 8))
                    m.setStyleSheet(f"color:{C.T3}; background:transparent;")
                    rl.addWidget(m)
                b = QLabel(str(body))
                b.setFont(QFont(C.FUI, 9))
                b.setStyleSheet(f"color:{C.T1}; background:transparent;")
                b.setWordWrap(True)
                b.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse)
                rl.addWidget(b)
                cl.addWidget(row)
        return card

    def _clear_items(self):
        """본문 영역의 모든 위젯 제거 (마지막 stretch 는 유지)."""
        # 마지막 stretch 제외하고 전부 제거
        i = self._items_lay.count() - 2  # 마지막 = stretch
        while i >= 0:
            it = self._items_lay.itemAt(i)
            w  = it.widget() if it else None
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            self._items_lay.removeItem(it) if it else None
            i -= 1


# ══════════════════════════════════════════════════════════════
#  ⑤ 정적 검증 결과 페이지
# ══════════════════════════════════════════════════════════════
class StaticResultPage(BasePage):
    """⑤ 정적 검증 결과 — CB 트래커 조회 페이지."""

    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("⑤", "정적 검증 결과", parent)
        self.attach_status_banner()
        self.install_load_button(self.load_requested.emit)

        self._body = CbReviewResultBody(
            hint_text=(
                "정적 분석 결과 파일(Coverity / Polyspace / Klocwork 등) 은 "
                "Codebeamer 트래커에 직접 업로드해 주세요.\n"
                "[📥 불러오기] 를 누르면 트래커의 첨부 상태와 등록된 모든 리뷰 "
                "댓글을 이곳에서 확인할 수 있습니다."),
        )
        self.add_body(self._body)

    # ── 공개 API ──────────────────────────────────────────────
    def apply_result(self, data: dict):
        """컨트롤러가 워커 done(dict) 결과를 위젯에 적용."""
        self._body.apply_result(data)

    def has_result(self) -> bool:
        """⑧ OPEN 항목에서 OK/NG 판정 시 호출."""
        return self._body.has_result()

    # ── 레거시 호환 (외부에서 get_attachments() 호출하던 곳) ────
    def get_attachments(self) -> list:
        """파일 업로드 흐름 폐기 — 항상 빈 리스트.
        ⑧ 페이지가 이 메서드를 호출해도 안전하게 동작하도록 유지.
        실제 OK/NG 판정은 has_result() 사용 권장.
        """
        return []

    def clear_attachments(self):
        """레거시 호환 — 결과 표시 초기화."""
        self._body.reset()


# ══════════════════════════════════════════════════════════════
#  ⑦ 설계자 테스트 결과 페이지
# ══════════════════════════════════════════════════════════════
class TestResultPage(BasePage):
    """⑦ 설계자 테스트 결과 — CB 트래커 조회 페이지."""

    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("⑦", "설계자 테스트 결과", parent)
        self.attach_status_banner()
        self.install_load_button(self.load_requested.emit)

        self._body = CbReviewResultBody(
            hint_text=(
                "설계자가 수행한 테스트 결과 파일(단위/통합/회귀 시험 보고서, "
                "테스트 실행 로그, 커버리지 리포트 등) 은 Codebeamer 트래커에 "
                "직접 업로드해 주세요.\n"
                "[📥 불러오기] 를 누르면 트래커의 첨부 상태와 등록된 모든 리뷰 "
                "댓글을 이곳에서 확인할 수 있습니다."),
        )
        self.add_body(self._body)

    def apply_result(self, data: dict):
        self._body.apply_result(data)

    def has_result(self) -> bool:
        return self._body.has_result()

    def get_attachments(self) -> list:
        return []

    def clear_attachments(self):
        self._body.reset()


# ⑧ OpenItemsPage / ⑨ DeployReviewPage 는 별도 파일로 분리됨:
#   from view.pages.page_open_items   import OpenItemsPage
#   from view.pages.page_deploy_review import DeployReviewPage
