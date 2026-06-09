"""checklist_ai_worker.py — ASPICE 체크리스트 항목별 AI 분석 워커.

입력: 체크리스트 항목 리스트 (No / 체크리스트 본문) + 컨텍스트 (요구사항 DIFF
+ 변경점 매칭 결과 + 요구사항서 메타).

출력: {no: {"judge": "OK/OK But/NG/N/A", "detail": "AI 가 작성한 상세 내용"}}

AI 호출은 anthropic (Claude) API 사용. 분석 대상 항목만 실제 호출하고,
나머지는 자동 텍스트 ('이전 버전 기준 변경 없음') 로 채운다.

Signals:
  progress(str)  : 상태 메시지
  done(dict)     : {no: {"judge", "detail"}}
  error(str)     : 실패 사유
"""

import os
import json
import re

from PyQt6.QtCore import QObject, pyqtSignal


# 분석 대상이 아닌 항목 (변경 없음) 에 자동으로 채워줄 텍스트
NO_CHANGE_JUDGE  = "N/A"
NO_CHANGE_DETAIL_FMT = "(이전 버전 {old_ver} 기준) 금번 내용과 동일하며 변경없음"


# AI 분석 시스템 프롬프트 — 항목별 응답 JSON 형식 지정
_SYS_PROMPT = """\
당신은 자동차 SW 의 ASPICE 검토 보조 AI 입니다. 사용자가 제공한 요구사항 DIFF \
+ 변경점 매칭 정보를 기반으로, 주어진 ASPICE 체크리스트 항목 각각에 대해 다음 \
JSON 형식으로 응답해 주세요.

[{"no": <int>, "judge": "<OK/OK But/NG/N/A>", "detail": "<상세 심사 내용>"}, ...]

판정 기준:
  · OK     : 체크리스트 문항을 만족
  · OK But : 부적합 사항이 협의로 수용 가능 (조건부 만족)
  · NG     : 내용이 미비하여 만족하지 않음
  · N/A    : 검토 시점에 항목이 확인되지 않거나 미적용

상세 심사 내용은 1~3 문장의 한국어로, 실제 변경점/요구사항 ID 를 인용하여 \
구체적으로 작성하세요. JSON 외 텍스트는 출력하지 마세요.
"""


class ChecklistAiWorker(QObject):
    progress = pyqtSignal(str)
    done     = pyqtSignal(dict)   # {no: {"judge", "detail"}}
    error    = pyqtSignal(str)

    def __init__(self, *,
                 items_to_analyze: list,
                 context_md: str,
                 old_version: str = "",
                 api_key: str = "",
                 model: str = "claude-sonnet-4-5",
                 max_tokens: int = 8000):
        """
        items_to_analyze: [{"no":int, "content":str}, ...] — AI 분석 대상만
        context_md      : 요구사항 DIFF + 매칭 결과 + 메타데이터 (시스템 user body)
        old_version     : 자동 채우기에 들어갈 이전 버전 텍스트
        api_key         : ANTHROPIC API key (없으면 env var 사용)
        """
        super().__init__()
        self.items     = list(items_to_analyze or [])
        self.context   = context_md or ""
        self.old_ver   = old_version or "v?.?"
        self.api_key   = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model     = model
        self.max_tokens = max_tokens

    def run(self):
        try:
            if not self.items:
                self.done.emit({})
                return

            try:
                import anthropic
            except ImportError as e:
                self.error.emit(
                    f"anthropic 패키지 미설치 — pip install anthropic ({e})")
                return

            if not self.api_key:
                self.error.emit(
                    "ANTHROPIC_API_KEY 가 설정되지 않았습니다. "
                    "환경변수 또는 설정에서 입력해주세요.")
                return

            self.progress.emit(
                f"🤖  체크리스트 {len(self.items)}개 항목 AI 분석 시작...")

            # user body — 컨텍스트 + 항목 리스트
            items_block = json.dumps(
                [{"no": it["no"], "content": it["content"]} for it in self.items],
                ensure_ascii=False, indent=2)
            user_body = (
                f"=== 변경점 + 요구사항 DIFF 컨텍스트 ===\n{self.context}\n\n"
                f"=== 분석할 체크리스트 항목 ===\n{items_block}\n\n"
                f"위 컨텍스트를 기반으로 각 체크리스트 항목에 대해 JSON 형식으로 "
                f"응답해 주세요.")

            client = anthropic.Anthropic(api_key=self.api_key)
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=_SYS_PROMPT,
                messages=[{"role": "user", "content": user_body}],
            )

            # 응답 텍스트 추출
            text_parts = []
            for blk in resp.content:
                t = getattr(blk, "text", None)
                if t:
                    text_parts.append(t)
            raw = "".join(text_parts).strip()

            # JSON 파싱 — 가끔 markdown 코드펜스로 감싸므로 제거
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                # JSON 추출 — 본문 어딘가의 [ ... ] 블록 시도
                m = re.search(r"\[\s*\{.*\}\s*\]", cleaned, flags=re.DOTALL)
                if not m:
                    self.error.emit(
                        f"AI 응답 JSON 파싱 실패. 원본 응답 일부:\n{raw[:300]}")
                    return
                parsed = json.loads(m.group(0))

            results: dict = {}
            for entry in parsed or []:
                if not isinstance(entry, dict):
                    continue
                try:
                    no = int(entry.get("no"))
                except (TypeError, ValueError):
                    continue
                results[no] = {
                    "judge":  str(entry.get("judge") or "").strip(),
                    "detail": str(entry.get("detail") or "").strip(),
                }
            self.progress.emit(f"✅  AI 분석 완료 — {len(results)}개 항목")
            self.done.emit(results)
        except Exception as e:
            self.error.emit(str(e))


def make_no_change_result(no: int, old_version: str = "") -> dict:
    """분석 대상이 아닌 항목의 자동 결과 (judge=N/A, detail='변경 없음')."""
    detail = NO_CHANGE_DETAIL_FMT.format(
        old_ver=old_version or "이전 버전")
    return {"judge": NO_CHANGE_JUDGE, "detail": detail}
