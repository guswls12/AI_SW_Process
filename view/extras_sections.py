"""extras_sections.py — ⑥ 코드리뷰 결과 > INPUT > 추가 분석 자료의 섹션 위젯.

ExtrasPanel 의 [code_info / static] 키에 들어가는 자체 위젯 두 개.
'past' 섹션은 기존 CbSectionWidget 을 그대로 사용한다.

CbSpecSection   — CB 사양변경 트래커에서 이슈를 가져와 체크리스트로 선택.
                  선택된 사양변경들이 AI 분석의 컨텍스트로 주입되어, AI 가
                  각 코드 변경점을 어떤 사양변경에 매칭되는지 식별한다.
                  (이전 'MCU/통신/...' 5필드 자유 입력은 폐기)
StaticOptSection — CERT-C / MISRA-C 2012 / MISRA-C 2023 체크박스
                  (기존 InputPanel '정적 검증' 카드 복제, MISRA 두 버전 상호 배타)
"""

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel,
    QLineEdit, QCheckBox, QScrollArea, QPushButton, QTextBrowser,
)

from config import C


# ══════════════════════════════════════════════════════════════
#  CbSpecFetchWorker — 백그라운드 트래커 이슈 페치
# ══════════════════════════════════════════════════════════════
class _CbSpecFetchWorker(QObject):
    """트래커 ID → 이슈 리스트 [{id, name, description}] 페치."""
    done  = pyqtSignal(list)   # list[dict]
    error = pyqtSignal(str)

    def __init__(self, tracker_id: str):
        super().__init__()
        self.tracker_id = (tracker_id or "").strip()

    def run(self):
        try:
            from integrations.codebeamer import (
                load_config, CbFetcher,
            )
            cfg = load_config()
            url, user, pw = (cfg.get("url",""), cfg.get("username",""),
                             cfg.get("password",""))
            if not (url and user and pw):
                raise RuntimeError(
                    "Codebeamer 설정이 비어있습니다. 좌측 CB 설정을 먼저 입력해주세요.")
            fetcher = CbFetcher(url, user, pw)
            items = fetcher.fetch_tracker_items(self.tracker_id) or []
            # 본문이 빠진 경량 리스트면 각 아이템 detail 추가 조회
            # — 본문이 필요하므로 처음부터 풍부한 응답을 기대하지만,
            #   비어있으면 fetch_item_detail 로 한 번 더 가져옴.
            enriched: list[dict] = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                iid = str(it.get("id") or it.get("itemId") or "").strip()
                name = (it.get("name") or "").strip()
                desc = (it.get("description") or "").strip()
                if iid and not desc:
                    try:
                        d = fetcher.fetch_item_detail(iid) or {}
                        desc = (d.get("description") or "").strip()
                        if not name:
                            name = (d.get("name") or "").strip()
                    except Exception:
                        pass
                enriched.append({
                    "id":          iid,
                    "name":        name or f"#{iid}",
                    "description": desc,
                })
            self.done.emit(enriched)
        except Exception as e:
            self.error.emit(str(e))


# ══════════════════════════════════════════════════════════════
#  _SpecItemCard — 사양변경 아이템 하나 (체크박스 + 펼침/접힘)
# ══════════════════════════════════════════════════════════════
class _SpecItemCard(QFrame):
    """체크박스 + 제목 한 줄 + 클릭 시 본문 펼침."""

    def __init__(self, item: dict, parent=None):
        super().__init__(parent)
        self.item = item
        self._expanded = False
        self.setObjectName("spec_card")
        self.setStyleSheet(
            f"#spec_card {{ background:{C.BG_PANEL};"
            f"  border:1px solid {C.BDR}; border-radius:6px; }}")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # 헤더 행 — 체크박스 + 제목 + 펼침 버튼
        hdr = QHBoxLayout(); hdr.setContentsMargins(10, 6, 10, 6); hdr.setSpacing(8)
        self.chk = QCheckBox()
        self.chk.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr.addWidget(self.chk)

        iid = self.item.get("id", "")
        name = self.item.get("name", "") or f"#{iid}"
        title = QLabel(f"<b>#{iid}</b>  {name}")
        title.setFont(QFont(C.FUI, 10))
        title.setStyleSheet(f"color:{C.T1}; background:transparent;")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setWordWrap(True)
        hdr.addWidget(title, 1)

        self._toggle_btn = QPushButton("▸")
        self._toggle_btn.setFixedSize(22, 22)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C.T2};"
            f"  border:none; font-size:11px; }}"
            f"QPushButton:hover {{ color:{C.T0}; }}")
        self._toggle_btn.setToolTip("본문 펼치기/접기")
        self._toggle_btn.clicked.connect(self._toggle)
        hdr.addWidget(self._toggle_btn)
        lay.addLayout(hdr)

        # 본문 영역 (펼침 시 표시)
        self._body = QTextBrowser()
        self._body.setOpenExternalLinks(True)
        self._body.setMinimumHeight(120)
        self._body.setMaximumHeight(240)
        self._body.setStyleSheet(
            f"QTextBrowser {{ background:#FFFFFF; color:{C.T1};"
            f"  border-top:1px solid {C.BDR}; border-radius:0;"
            f"  padding:8px 12px; font-size:11px; }}")
        # CB 본문은 위키마크업/HTML 혼합 — _clean_text 로 평문화
        try:
            from integrations.codebeamer.text import _clean_text
            cleaned = _clean_text(self.item.get("description") or "")
        except Exception:
            cleaned = self.item.get("description") or ""
        self._body.setPlainText(cleaned or "(본문 없음)")
        self._body.setVisible(False)
        lay.addWidget(self._body)

    def _toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._toggle_btn.setText("▾" if self._expanded else "▸")

    def is_checked(self) -> bool:
        return self.chk.isChecked()

    def set_checked(self, b: bool):
        self.chk.setChecked(bool(b))


# ══════════════════════════════════════════════════════════════
#  CbSpecSection — CB 사양변경 트래커 가져오기 + 체크리스트
# ══════════════════════════════════════════════════════════════
class CbSpecSection(QWidget):
    """⑥ INPUT > 추가 분석 자료 > 사양변경 트래커 섹션.

    트래커 ID 입력 → [가져오기] → 아이템 체크리스트.
    선택된 아이템들의 본문이 AI 컨텍스트로 주입되어, AI 가 각 코드 변경점을
    어떤 사양변경에 매칭되는지 식별한다.
    """

    CONFIG_KEY = "last_spec_tracker_id"

    def __init__(self, parent=None):
        super().__init__(parent)
        # transparent: ExtrasPanel.card 의 rounded BG_CARD 가 하단 코너에
        # 자연스럽게 노출되도록 (analysis_file_card 와 동일 패턴).
        self.setStyleSheet("background:transparent;")
        self._cards: list[_SpecItemCard] = []
        self._fetch_thread: QThread | None = None
        self._fetch_worker: _CbSpecFetchWorker | None = None
        self._build()
        self._load_last_tracker_id()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        inner = QWidget()
        # transparent — 부모 (CbSpecSection→ExtrasPanel.card) 의 BG_CARD 가 비치도록.
        inner.setStyleSheet("background:transparent;")
        il = QVBoxLayout(inner)
        il.setContentsMargins(18, 16, 18, 16); il.setSpacing(10)

        # 헤더
        hdr = QLabel("💡  사양변경 트래커  (선택)")
        hdr.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{C.T1}; background:transparent;")
        il.addWidget(hdr)

        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C.BDR};")
        il.addWidget(sep)
        il.addSpacing(4)

        # 안내 문구
        hint = QLabel(
            "선택한 사양변경들이 AI 분석의 컨텍스트로 들어가서, 각 코드 변경점이 "
            "어떤 사양변경에 매칭되는지 자동 식별됩니다.")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{C.T3}; background:transparent; font-size:10px;")
        il.addWidget(hint)
        il.addSpacing(4)

        # 트래커 ID 입력 + 가져오기 버튼
        ctrl = QHBoxLayout(); ctrl.setSpacing(8)
        ctrl_lbl = QLabel("트래커 ID")
        ctrl_lbl.setFixedWidth(60)
        ctrl_lbl.setFont(QFont(C.FUI, 10))
        ctrl_lbl.setStyleSheet(f"color:{C.T2}; background:transparent;")
        ctrl.addWidget(ctrl_lbl)

        self._tracker_input = QLineEdit()
        self._tracker_input.setObjectName("le_info")
        self._tracker_input.setFixedHeight(28)
        self._tracker_input.setPlaceholderText(
            "예 : 트래커 URL 또는 트래커 ID 입력")
        ctrl.addWidget(self._tracker_input, 1)

        self._fetch_btn = QPushButton("📥  가져오기")
        self._fetch_btn.setFixedHeight(28)
        self._fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fetch_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:1px solid {C.BLUE}; border-radius:5px;"
            f"  padding:2px 14px; font-size:10px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H};"
            f"  border-color:{C.ACCENT_H}; }}"
            f"QPushButton:disabled {{ background:{C.BG_PANEL};"
            f"  color:{C.T3}; border-color:{C.BDR}; }}")
        self._fetch_btn.clicked.connect(self._on_fetch)
        ctrl.addWidget(self._fetch_btn)
        il.addLayout(ctrl)

        # 상태바
        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color:{C.T3}; background:transparent; font-size:10px;")
        il.addWidget(self._status)

        # 전체 선택 / 해제
        bulk = QHBoxLayout(); bulk.setSpacing(6); bulk.setContentsMargins(0, 4, 0, 0)
        self._chk_all = QCheckBox("전체 선택")
        self._chk_all.setStyleSheet(f"color:{C.T2}; font-size:10px;")
        self._chk_all.stateChanged.connect(self._toggle_all)
        self._chk_all.setVisible(False)
        bulk.addWidget(self._chk_all)
        bulk.addStretch()
        il.addLayout(bulk)

        # 아이템 리스트 영역 (스크롤)
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }")

        self._list_inner = QWidget()
        self._list_inner.setStyleSheet("background:transparent;")
        self._list_lay = QVBoxLayout(self._list_inner)
        self._list_lay.setContentsMargins(0, 4, 0, 0); self._list_lay.setSpacing(6)
        self._list_lay.addStretch()
        self._list_scroll.setWidget(self._list_inner)
        il.addWidget(self._list_scroll, stretch=1)

        lay.addWidget(inner)

    # ── 트래커 ID 마지막값 자동 채움 ──────────────────────────
    def _load_last_tracker_id(self):
        try:
            from integrations.codebeamer import load_config
            cfg = load_config()
            tid = (cfg.get(self.CONFIG_KEY) or "").strip()
            if tid:
                self._tracker_input.setText(tid)
        except Exception:
            pass

    def _save_last_tracker_id(self, tid: str):
        try:
            from integrations.codebeamer import load_config, save_config
            cfg = load_config()
            cfg[self.CONFIG_KEY] = tid
            save_config(cfg)
        except Exception:
            pass

    # ── 가져오기 버튼 핸들러 ──────────────────────────────────
    def _on_fetch(self):
        raw = self._tracker_input.text().strip()
        if not raw:
            self._status.setText("⚠  트래커 ID 를 입력해주세요.")
            return
        # URL 이면 트래커 ID 만 추출
        try:
            from integrations.codebeamer import parse_tracker_id_from_url
            tid = parse_tracker_id_from_url(raw) or raw
        except Exception:
            tid = raw
        tid = (tid or "").strip()
        if not tid:
            self._status.setText("⚠  트래커 ID 를 인식할 수 없습니다.")
            return

        # 마지막 사용값 저장
        self._save_last_tracker_id(raw)

        # 기존 카드 제거
        self._clear_cards()
        self._fetch_btn.setEnabled(False)
        self._status.setText(f"📥  트래커 #{tid} 가져오는 중...")

        # 백그라운드 페치
        self._fetch_thread = QThread()
        self._fetch_worker = _CbSpecFetchWorker(tid)
        self._fetch_worker.moveToThread(self._fetch_thread)
        self._fetch_thread.started.connect(self._fetch_worker.run)
        self._fetch_worker.done.connect(self._on_fetch_done)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_worker.done.connect(self._fetch_thread.quit)
        self._fetch_worker.error.connect(self._fetch_thread.quit)
        self._fetch_thread.start()

    def _on_fetch_done(self, items: list):
        self._fetch_btn.setEnabled(True)
        if not items:
            self._status.setText("ℹ  트래커에 이슈가 없습니다.")
            self._chk_all.setVisible(False)
            return
        self._status.setText(f"✓  {len(items)}개 이슈 로드됨")
        self._populate(items)
        self._chk_all.setVisible(True)
        self._chk_all.setChecked(False)

    def _on_fetch_error(self, msg: str):
        self._fetch_btn.setEnabled(True)
        self._status.setText(f"❌  실패: {msg[:140]}")

    def _clear_cards(self):
        for c in self._cards:
            c.deleteLater()
        self._cards.clear()
        # 레이아웃의 stretch 외 모든 카드 제거 (deleteLater 만으로는 layout
        # 슬롯이 안 비워지므로 take 처리)
        while self._list_lay.count() > 1:
            it = self._list_lay.takeAt(0)
            w = it.widget() if it else None
            if w:
                w.deleteLater()

    def _populate(self, items: list):
        # stretch 항목을 위해 마지막은 그대로 두고 그 앞에 카드 추가
        for it in items:
            card = _SpecItemCard(it)
            self._cards.append(card)
            self._list_lay.insertWidget(self._list_lay.count() - 1, card)

    def _toggle_all(self, state):
        checked = (state == Qt.CheckState.Checked.value)
        for c in self._cards:
            c.set_checked(checked)

    # ── 외부 API ──────────────────────────────────────────────
    def get_spec_changes_list(self) -> list[dict]:
        """체크된 사양변경 dict 리스트 반환.
        포맷: [{"id": "1071064", "name": "MCU ...", "description": "..."}, ...]
        매핑 다이얼로그가 드롭다운 옵션으로 사용한다.
        """
        out = []
        try:
            from integrations.codebeamer.text import _clean_text
        except Exception:
            _clean_text = lambda s: s   # noqa: E731
        for c in self._cards:
            if not c.is_checked():
                continue
            it = c.item
            out.append({
                "id":          it.get("id", ""),
                "name":        it.get("name", "") or f"#{it.get('id','')}",
                "description": _clean_text(it.get("description") or "").strip(),
            })
        return out

    # ── ExtrasPanel.get_code_info 가 호출 ─────────────────────
    def get_code_info(self) -> str:
        """선택된 사양변경들을 AI 프롬프트용 마크다운으로 반환.
        포맷:
          ※ 매칭 안내문 (선택된 항목이 있을 때만)
          ## 사양변경 #N — 제목
          {본문 (clean text)}
          ---
          ...
        선택된 항목이 없으면 빈 문자열.
        ★ 시스템 프롬프트 (.md) 는 건드리지 않음. user body 에 들어가는
          컨텍스트 앞에 짧은 매칭 지시문 한 줄만 prepend 하여 AI 가 각
          코드 변경점을 사양변경에 매칭해 인라인으로 표시하도록 유도한다.
        """
        try:
            from integrations.codebeamer.text import _clean_text
        except Exception:
            _clean_text = lambda s: s   # noqa: E731

        blocks = []
        for c in self._cards:
            if not c.is_checked():
                continue
            it = c.item
            iid = it.get("id", "")
            name = it.get("name", "") or f"#{iid}"
            body = _clean_text(it.get("description") or "").strip()
            blk = f"## 사양변경 #{iid} — {name}"
            if body:
                blk += f"\n\n{body}"
            blocks.append(blk)
        if not blocks:
            return ""

        # 짧은 사양변경 라벨 리스트 — 안내문의 출력 예시에 그대로 인용
        labels = []
        for c in self._cards:
            if not c.is_checked():
                continue
            it = c.item
            iid = it.get("id", "")
            name = it.get("name", "") or f"#{iid}"
            labels.append(f"#{iid} — {name}")

        n = len(blocks)
        # ★ 출력 구조 강화 안내문 — 시스템 프롬프트(.md) 는 건드리지 않고
        #   user body 에만 사양변경별 그룹화 지시를 추가한다. AI 가 변경점 요약
        #   탭과 취약점 분석 탭 양쪽에서 사양변경별 섹션으로 결과를 묶어 출력
        #   하도록 유도.
        example_lines = []
        for i, lab in enumerate(labels, start=1):
            example_lines.append(f"  # {i}. 사양변경 {lab}")
            example_lines.append(f"     [이 사양변경에 매칭되는 코드 변경점들의 표 — 기존 형식 그대로]")
        example_lines.append(f"  # {len(labels)+1}. 미매칭")
        example_lines.append(f"     [어느 사양변경에도 매칭되지 않는 코드 변경점들]")
        example_block = "\n".join(example_lines)

        guide = (
            f"※ 본 코드 변경의 배경이 되는 사양변경 {n}건입니다.\n\n"
            f"【출력 구조 지시】\n"
            f"분석 결과 (변경점 요약 / 취약점 분석) 를 **사양변경별로 그룹화**해 "
            f"주세요.\n"
            f"각 사양변경마다 H1 헤더 (`# N. 사양변경 #ID — 제목`) 를 만들고, "
            f"그 사양변경에 해당하는 코드 변경점들만 그 섹션 안에 넣어 분석해 "
            f"주세요.\n"
            f"각 섹션 안의 표/항목 형식은 기존 그대로 유지하되, 표 자체를 "
            f"사양변경별로 N+1개 (미매칭 포함) 출력합니다.\n\n"
            f"출력 예시:\n```\n{example_block}\n```\n\n"
            f"코드 변경점이 어느 사양변경에도 명확히 매칭되지 않으면 마지막 "
            f"`미매칭` 섹션에 모아주세요. 한 변경점이 여러 사양변경에 걸쳐 있는 "
            f"경우엔 가장 직접적인 것 하나에만 배치하고 본문에 다른 관련 사양변경 "
            f"ID 를 함께 언급해주세요.\n"
        )
        body_md = "\n\n---\n\n".join(blocks)
        return f"{guide}\n\n=== 사양변경 컨텍스트 ===\n\n{body_md}"


# ══════════════════════════════════════════════════════════════
#  StaticOptSection — 정적 검증 옵션 (체크박스)
# ══════════════════════════════════════════════════════════════
class StaticOptSection(QWidget):
    """⑥ INPUT > 추가 분석 자료 > 정적 검증 섹션.

    MISRA-C 2012 와 MISRA-C 2023 은 상호 배타적으로 토글된다.
    """

    OPT_ITEMS = [
        ("cert_c",    "① CERT-C"),
        ("misra_c",   "② MISRA-C (2012)"),
        ("misra_c23", "③ MISRA-C (2023)"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        # transparent: ExtrasPanel.card 의 rounded BG_CARD 가 하단 코너에
        # 자연스럽게 노출되도록 (analysis_file_card 와 동일 패턴).
        self.setStyleSheet("background:transparent;")
        self._opts: dict[str, QCheckBox] = {}
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        inner = QWidget()
        # transparent — 카드 rounded BG_CARD 가 비치도록.
        inner.setStyleSheet("background:transparent;")
        il = QVBoxLayout(inner)
        il.setContentsMargins(18, 16, 18, 16); il.setSpacing(6)

        # 헤더
        hdr = QLabel("☑  정적 검증 규칙")
        hdr.setFont(QFont(C.FUI, 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{C.T1}; background:transparent;")
        il.addWidget(hdr)

        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C.BDR};")
        il.addWidget(sep)
        il.addSpacing(4)

        # 전체 선택
        ar = QHBoxLayout()
        self._chk_all = QCheckBox("전체 선택")
        self._chk_all.setFont(QFont(C.FUI, 10, QFont.Weight.Bold))
        self._chk_all.setStyleSheet(f"color:{C.T0};")
        self._chk_all.stateChanged.connect(self._toggle_all)
        ar.addWidget(self._chk_all); ar.addStretch()
        il.addLayout(ar)

        sep2 = QFrame(); sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{C.BDR};")
        il.addWidget(sep2)

        # 옵션
        for key, label in self.OPT_ITEMS:
            chk = QCheckBox(f"  {label}")
            chk.setChecked(False)
            self._opts[key] = chk
            il.addWidget(chk)

        # MISRA 상호 배타 핸들러
        def _make_handler(excl_key):
            def _h(state):
                if (excl_key and
                        state == Qt.CheckState.Checked.value and
                        excl_key in self._opts):
                    self._opts[excl_key].blockSignals(True)
                    self._opts[excl_key].setChecked(False)
                    self._opts[excl_key].blockSignals(False)
                self._sync_all()
            return _h
        for k in self._opts:
            if k == "misra_c":
                self._opts[k].stateChanged.connect(_make_handler("misra_c23"))
            elif k == "misra_c23":
                self._opts[k].stateChanged.connect(_make_handler("misra_c"))
            else:
                self._opts[k].stateChanged.connect(_make_handler(None))

        il.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll)

    def _toggle_all(self, state):
        checked = (state == Qt.CheckState.Checked.value)
        for k, chk in self._opts.items():
            # 전체선택 시 misra_c23 은 제외 (misra_c 와 동시 선택 불가)
            val = False if (checked and k == "misra_c23") else checked
            chk.blockSignals(True); chk.setChecked(val); chk.blockSignals(False)

    def _sync_all(self):
        all_on = all(c.isChecked() for c in self._opts.values())
        self._chk_all.blockSignals(True)
        self._chk_all.setChecked(all_on)
        self._chk_all.blockSignals(False)

    def get_opts(self) -> dict[str, bool]:
        """ReviewWorker / ai_controller 가 기대하는 형식의 dict 반환."""
        return {k: c.isChecked() for k, c in self._opts.items()}
