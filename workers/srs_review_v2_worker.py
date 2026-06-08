"""srs_review_v2_worker.py — SRS 검토 AI 인사이트 워커.

구 12항목 체크리스트 검증 워커(JSON 출력)는 제거됨. 이 워커는 사진 5단계
운영 플로우 기반 — 5종 입력 → 마크다운 5(+1)섹션.

입력 (단일 변경점 1건):
  - cb_item    : CB 트래커 변경점 dict (id, name, description, ...)
  - common     : 공통 입력 dict
                 {checklist:{sid:value}, reviews:{sys|sw|hw|test:str},
                  meeting:{issues, decisions, action_items:[...]}}
  - historical : 과거차 dict 리스트 (id, name, description, ...)
  - req_diff   : (옵션) 요구사항 DIFF 텍스트 — 비어있지 않으면 6번 매칭 섹션 추가

출력 (done 시그널):
  dict — {
    'card_id':      변경점 식별자 (보통 cb_item['id']),
    'markdown':     마크다운 5(+1)섹션 본문 (시스템 프롬프트 형식 그대로),
    'input_tokens': 입력 토큰 수,
  }

시그널:
  - progress(str)        : 단계별 진행 메시지
  - token_counted(int)   : count_tokens 결과
  - done(dict)           : 정상 완료 (위 형식)
  - error(str)           : 실패 사유

시스템 프롬프트는 prompts/system/srs_review.md (Phase 1 재작성본) 외부화.
변경점 N개 병렬 처리는 컨트롤러가 N개 인스턴스를 QThread 로 동시 실행.
"""

import os
import json

try:
    import anthropic
except ImportError:
    anthropic = None

from PyQt6.QtCore import QObject, pyqtSignal


_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SYS_PROMPT_PATH = os.path.join(_BASE_DIR, "prompts", "system", "srs_review.md")
_CHECKLIST_JSON  = os.path.join(_BASE_DIR, "prompts", "checklists",
                                "srs_review_default.json")


def _load_sys_prompt() -> str:
    """prompts/system/srs_review.md 로드. 파일 누락 시 최소 폴백."""
    try:
        with open(_SYS_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return (
            "너는 자동차 전장 SW 변경 영향 검토 보조자다. "
            "체크리스트와 회의록을 기반으로 유사 과거차/누락/질문/재발 위험 "
            "을 마크다운 형식으로 제안한다. OK/NG 단정 금지.")


def _load_checklist_labels() -> dict:
    """체크리스트 JSON 에서 {section_id: section_label} 매핑 로드.
    워커가 사용자 입력 {sid: value} 를 보기 좋은 라벨 + 질문으로 풀어내기 위함.
    """
    try:
        with open(_CHECKLIST_JSON, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        out = {}
        for row in (data.get("fixed_checklist") or []):
            sid = str(row.get("id") or "").strip()
            if sid:
                out[sid] = {
                    "section":  str(row.get("section") or "").strip(),
                    "question": str(row.get("question") or "").strip(),
                }
        return out
    except (OSError, json.JSONDecodeError):
        return {}


def _load_review_labels() -> dict:
    """{role: label} 매핑 — 사용자 입력 'sys' 키를 'SYS 설계자' 라벨로 풀이."""
    try:
        with open(_CHECKLIST_JSON, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        out = {}
        for role, cfg in (data.get("engineer_review_template") or {}).items():
            if isinstance(cfg, dict):
                out[role] = str(cfg.get("label") or role.upper()).strip()
        return out
    except (OSError, json.JSONDecodeError):
        return {}


# ══════════════════════════════════════════════════════════════
#  SrsReviewV2Worker — 단일 변경점 AI 분석 워커
# ══════════════════════════════════════════════════════════════
class SrsReviewV2Worker(QObject):
    """단일 변경점 1건에 대한 AI 인사이트 호출.

    여러 변경점을 동시에 분석하려면 컨트롤러가 N개 인스턴스를 QThread 로
    각각 띄워 병렬 실행 (사용자 결정 — B안: 변경점 N개 병렬 호출).
    """

    progress      = pyqtSignal(str)
    token_counted = pyqtSignal(int)
    done          = pyqtSignal(dict)
    error         = pyqtSignal(str)

    def __init__(self, card_id: str, cb_item: dict, common: dict,
                 historical: list, req_diff: str = "",
                 max_tokens: int = 16000,
                 model: str = "claude-sonnet-4-6"):
        super().__init__()
        self.card_id    = str(card_id or "")
        self.cb_item    = cb_item or {}
        self.common     = common or {}
        self.historical = list(historical or [])
        self.req_diff   = (req_diff or "").strip()
        self.max_tokens = max_tokens
        self.model      = model
        self._cancel    = False
        # JSON 라벨 한 번만 로드 (워커별 캐시)
        self._cl_labels = _load_checklist_labels()
        self._rv_labels = _load_review_labels()

    def cancel(self):
        self._cancel = True

    # ── 메인 실행 ────────────────────────────────────────────
    def run(self):
        try:
            if anthropic is None:
                raise RuntimeError(
                    "anthropic 패키지가 설치되지 않았습니다.\n"
                    "pip install anthropic 으로 설치해주세요.")
            if not self.cb_item:
                raise RuntimeError("변경점 메타 (cb_item) 가 비어있습니다.")

            client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY"))
            sys_prompt = _load_sys_prompt()
            user_body  = self._build_user_body()
            messages   = [{"role": "user", "content": user_body}]

            # ── 1) 입력 토큰 카운트 (실패 시 0 폴백) ──────────────
            self.progress.emit(
                f"🔢  토큰 계산 중 (변경점 #{self.cb_item.get('id', '?')})...")
            input_tokens = 0
            try:
                tk = client.messages.count_tokens(
                    model=self.model,
                    system=sys_prompt,
                    messages=messages,
                )
                input_tokens = int(getattr(tk, "input_tokens", 0) or 0)
            except Exception:
                input_tokens = 0
            self.token_counted.emit(input_tokens)
            if self._cancel:
                return

            # ── 2) Claude API 본 호출 ──────────────────────────────
            self.progress.emit(
                f"🤖  AI 분석 중 — 변경점 #{self.cb_item.get('id', '?')} "
                f"(입력 {input_tokens:,} tokens)...")
            msg = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0,
                system=sys_prompt,
                messages=messages,
            )
            if self._cancel:
                return

            # ── 3) 응답 텍스트 추출 ────────────────────────────────
            text_out = ""
            for block in (msg.content or []):
                if getattr(block, "type", "") == "text":
                    text_out += getattr(block, "text", "") or ""
            text_out = text_out.strip()
            if not text_out:
                raise RuntimeError("AI 응답이 비어있습니다.")

            self.done.emit({
                "card_id":      self.card_id,
                "markdown":     text_out,
                "input_tokens": input_tokens,
            })
        except Exception as e:
            self.error.emit(str(e))

    # ── User body 빌더 — 5(+1) 종 입력 직렬화 ─────────────────
    def _build_user_body(self) -> str:
        parts: list[str] = []

        # ── 1) 변경점 메타 ───────────────────────────────────
        item_id = str(self.cb_item.get("id") or "?")
        title   = str(self.cb_item.get("name") or self.cb_item.get("title")
                      or self.cb_item.get("summary") or "(제목 없음)").strip()
        desc    = str(self.cb_item.get("description") or
                      self.cb_item.get("descriptionText") or "").strip()
        parts.append("=== 1. 변경점 메타 (현재 분석 대상) ===")
        parts.append(f"ID: #{item_id}")
        parts.append(f"제목: {title}")
        if desc:
            parts.append("본문:")
            parts.append(desc)
        parts.append("")

        # ── 2) 공통 체크리스트 (5항목) ───────────────────────
        parts.append("=== 2. 공통 체크리스트 (변경점 묶음 전체 공통, 5항목) ===")
        cl = self.common.get("checklist") or {}
        if not cl:
            parts.append("(체크리스트 미작성)")
        else:
            for sid, value in cl.items():
                meta = self._cl_labels.get(sid) or {}
                section = meta.get("section") or sid
                question = meta.get("question") or ""
                value_str = str(value or "").strip() or "(미작성)"
                parts.append(f"[{section}]")
                if question:
                    parts.append(f"  질문: {question}")
                parts.append(f"  작성결과: {value_str}")
                parts.append("")

        # ── 3) 4역할 설계자 검토 의견 ────────────────────────
        parts.append("=== 3. 설계자 직접 검토 의견 (SYS/SW/HW/TEST) ===")
        reviews = self.common.get("reviews") or {}
        for role in ("sys", "sw", "hw", "test"):
            label = self._rv_labels.get(role) or f"{role.upper()} 설계자"
            content = str(reviews.get(role) or "").strip() or "(의견 미작성)"
            parts.append(f"[{label}]")
            parts.append(content)
            parts.append("")

        # ── 4) 검토 회의록 ────────────────────────────────────
        parts.append("=== 4. 검토 회의록 ===")
        meeting = self.common.get("meeting") or {}
        issues    = str(meeting.get("issues") or "").strip() or "(쟁점 미작성)"
        decisions = str(meeting.get("decisions") or "").strip() or "(결정사항 미작성)"
        actions   = meeting.get("action_items") or []
        parts.append("[쟁점]")
        parts.append(issues)
        parts.append("")
        parts.append("[결정사항]")
        parts.append(decisions)
        parts.append("")
        parts.append("[액션아이템]")
        if not actions:
            parts.append("(액션아이템 없음)")
        else:
            parts.append("| # | 액션 | 담당 | 기한 | 상태 |")
            parts.append("|---|---|---|---|---|")
            for i, ai in enumerate(actions, 1):
                if not isinstance(ai, dict):
                    continue
                a = str(ai.get("action") or "").strip() or "-"
                o = str(ai.get("owner")  or "").strip() or "-"
                d = str(ai.get("due")    or "").strip() or "-"
                s = str(ai.get("status") or "").strip() or "-"
                parts.append(f"| {i} | {a} | {o} | {d} | {s} |")
        parts.append("")

        # ── 5) Codebeamer 전사 과거차 목록 ────────────────────
        parts.append("=== 5. Codebeamer 전사 과거차 목록 ===")
        if not self.historical:
            parts.append("(과거차 데이터 없음 — fetch 미실행 또는 선택 0건)")
        else:
            for i, h in enumerate(self.historical, 1):
                if not isinstance(h, dict):
                    continue
                hid = str(h.get("id") or "?")
                hti = str(h.get("name") or h.get("title")
                          or h.get("summary") or "(제목 없음)").strip()
                hde = str(h.get("description") or "").strip()
                parts.append(f"[{i}] #{hid} — {hti}")
                if hde:
                    # 너무 길면 자름 (각 과거차당 ~1500자 상한)
                    parts.append(hde[:1500] + ("..." if len(hde) > 1500 else ""))
                parts.append("")
        parts.append("")

        # ── 6) (옵션) 요구사항 DIFF — 있을 때만 ───────────────
        if self.req_diff:
            parts.append("=== 6. 요구사항 변경점 DIFF (선택 입력) ===")
            parts.append(self.req_diff)
            parts.append("")
            parts.append(
                "위 요구사항 DIFF 가 제공되었으므로 시스템 프롬프트의 "
                "**6번 섹션 (요구사항 DIFF — 변경점 매칭)** 도 출력에 포함하라.")
        else:
            parts.append(
                "(요구사항 DIFF 미제공 — 시스템 프롬프트의 6번 섹션은 출력하지 말 것.)")
        parts.append("")

        # ── 최종 지시 ────────────────────────────────────────
        parts.append("---")
        parts.append(
            "위 입력 5(+1)종을 바탕으로 system 프롬프트에 정의된 "
            "마크다운 형식으로만 출력하라. 첫 줄부터 바로 '### 1. 유사 과거차' "
            "로 시작하며, 머리말/꼬리말/JSON/코드 펜스 일체 금지.")
        return "\n".join(parts)
