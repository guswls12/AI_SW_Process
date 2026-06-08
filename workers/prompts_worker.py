"""
prompts_worker.py — Claude API 호출 워커
  - ReviewWorker : QThread 에서 실행되는 API 호출 객체
프롬프트 상수/템플릿은 worker.py 에서 import.
UI 의존성 없음.
"""

import os

try:
    import anthropic
except ImportError:
    anthropic = None

from PyQt6.QtCore import QObject, pyqtSignal

from core.worker import (
    CAT_PROMPTS,
    _SYS_SUMMARY,
    _SYS_VULN_TMPL,
    _RULE_VIOLATION_SECTION,
    _CB_ISSUES_SECTION,
    _CB_VULN_SECTION,
)


# ══════════════════════════════════════════════════════════════
#  워커
# ══════════════════════════════════════════════════════════════
class ReviewWorker(QObject):
    # 시그널 시그니처: (text, was_truncated)
    # was_truncated 는 stop_reason == "max_tokens" 일 때 True →
    # UI 가 사용자에게 토큰 한도 경고를 띄울 수 있게 함
    summary_done = pyqtSignal(str, bool)
    vuln_done    = pyqtSignal(str, bool)
    error        = pyqtSignal(str)
    cancelled    = pyqtSignal()     # ★ 사용자 중단 시 emit

    def __init__(self, old_code: str, new_code: str, diff_code: str,
                 code_info: str, req_text: str, opts: dict[str, bool],
                 changed_text: str = "",
                 cb_context: str = "",             # ★ Codebeamer 컨텍스트
                 option_contents: dict[str, str] = None,  # ★ 리뷰 옵션 MD 내용
                 max_tokens: int = 16000,                  # ★ 사용자 지정 응답 토큰 한도
                 include_full_context: bool = False):      # ★ 옛/새 파일 본문 포함 여부
        super().__init__()
        self.old_code        = old_code
        self.new_code        = new_code
        self.diff_code       = diff_code
        self.code_info       = code_info
        self.req_text        = req_text
        self.opts            = opts
        self.changed_text    = changed_text       # ★ 함수별 +/- diff 텍스트
        self.cb_context      = cb_context         # ★ Codebeamer md 텍스트
        self.option_contents = option_contents or {}  # ★ 옵션별 MD 파일 내용
        self.max_tokens      = max_tokens         # ★ 취약점 분석 max_tokens
        self.include_full_context = bool(include_full_context)
        self._cancel_req = False  # ★ UI 스레드에서 set → 워커 스레드에서 check
        # 이어서 분석(continuation) 컨텍스트 — vuln 스트림 완료 후 채워짐.
        # 잘림 시 컨트롤러가 ContinueVulnWorker 에 전달.
        self.last_vuln_system_prompt: str = ""
        self.last_vuln_user_body:     str = ""
        self.last_vuln_raw_text:      str = ""   # 경고 blockquote 미포함 원본

    def cancel(self):
        """UI 스레드에서 호출 — 스트리밍 루프에서 조기 종료."""
        self._cancel_req = True

    @staticmethod
    def _truncation_warning(limit: int) -> str:
        """응답이 max_tokens 한도에서 잘렸을 때 결과 상단에 끼우는 경고 블록.
        마크다운 blockquote 로 렌더되어 결과 패널에서 시선이 잡히게 한다."""
        return (
            f"> ⚠️ **응답이 토큰 한도에서 잘렸습니다.** "
            f"(한도: {limit:,} 토큰)\n"
            f"> \n"
            f"> 분석 시작 다이얼로그의 슬라이더에서 토큰을 더 높여 재시도하세요.\n"
            f"> 아래 결과는 한도까지만 출력된 부분입니다.\n\n"
            f"---\n\n"
        )

    # ── 입력 바디 조립 ────────────────────────────────────────
    @staticmethod
    def _body(old_code, new_code, diff_code, code_info, req_text,
              changed_text="", cb_context="",
              option_contents: dict = None,
              include_full_context: bool = False) -> str:
        """
        include_full_context:
          False (기본) → 변경 영역만 보냄 (diff + changed_text + 컨텍스트).
                        토큰 절감 — 큰 파일에서 90%+ 입력 감소 가능.
          True         → 옛/새 파일 본문 전체도 함께 포함.
                        변경 외 함수의 호출관계까지 풀 컨텍스트로 분석할 때 사용.
        """
        parts = []
        if cb_context:    parts.append(f"=== Codebeamer 컨텍스트 데이터 ===\n{cb_context}\n")  # ★ CB
        if code_info:     parts.append(f"=== 코드 정보 ===\n{code_info}\n")
        if changed_text:  parts.append(f"=== 함수별 변경점 ===\n{changed_text}\n")
        if diff_code:     parts.append(f"=== 변경점 (unified diff) ===\n{diff_code}\n")
        # ★ 파일 전체 본문은 옵션 ON 일 때만 포함 (입력 토큰 절감 목적)
        if include_full_context:
            if old_code:  parts.append(f"=== 수정 전 코드 ===\n{old_code}\n")
            if new_code:  parts.append(f"=== 수정 후 코드 ===\n{new_code}\n")
        if req_text:      parts.append(f"=== 요구사항 ===\n{req_text}\n")

        # ★ 리뷰 옵션 MD 내용 주입 — 체크된 옵션의 기준 문서를 검토 재료로 포함
        # sw_quality 는 cat1~cat6 stub 들이 본문에서 참조하는 카테고리 정의 문서 (항상 로드)
        _OPTION_LABELS = {
            "sw_quality": "SW 품질 결함 카테고리 기준",
            "cert_c":    "CERT-C 규칙 기준 (SEI CERT C Coding Standard 2016)",
            "misra_c":   "MISRA-C:2012 규칙 기준",
            "misra_c23": "MISRA-C:2023 규칙 기준",
            "req_diff":  "요구사항 DIFF 기준",
            # "extra1":    "추가 표준 기준",   # [EXTRA1 DISABLED]
            "past":      "과거차 이슈 목록",
            "ll":        "L&L 이슈 목록",
        }
        for key, content in (option_contents or {}).items():
            if content and content.strip():
                label = _OPTION_LABELS.get(key, f"{key} 기준 문서")
                parts.append(f"=== {label} ===\n{content}\n")

        return "\n".join(parts)

    def run(self):
        try:
            if anthropic is None:
                raise RuntimeError(
                    "anthropic 패키지가 설치되지 않았습니다.\n"
                    "pip install anthropic 을 실행해주세요.")

            client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY"))
            body = self._body(
                self.old_code, self.new_code, self.diff_code,
                self.code_info, self.req_text, self.changed_text,
                self.cb_context,                   # ★ CB 컨텍스트 전달
                self.option_contents,              # ★ 옵션 MD 내용 전달
                self.include_full_context)         # ★ 파일 전체 본문 포함 여부

            # ① 변경점 요약
            # 주의: claude-sonnet-4-6 은 assistant prefill 미지원 → temperature=0 만 사용

            # ★ 요약 프롬프트 요구사항 플레이스홀더 — req_text 제공 시에만 삽입
            if self.req_text:
                req_analysis_principle = (
                    "- 요구사항이 제공된 경우, 각 조건이 코드의 어느 위치"
                    "(파일명+함수명+라인번호)에 구현됐는지 매핑한다.\n"
                    "- 요구사항 조건에 해당하는 코드가 없으면 \"미구현\"으로 표기한다."
                )
                req_section = (
                    "\n---\n\n"
                    "### 2. 요구사항 ↔ 코드 매핑\n\n"
                    "요구사항의 각 조건이 코드의 어느 위치에 구현됐는지 아래 표 형식으로 매핑한다.\n"
                    "이 섹션은 반드시 출력한다. 생략 불가.\n\n"
                    "| 요구사항 조건 | 구현 위치 | 구현 여부 |\n"
                    "|---|---|---|\n"
                    "| 조건 설명 | `[파일명] 함수명()`, 라인 N | 구현 / 미구현 / 부분구현 |\n\n"
                    "### 3. 요구사항 충족 여부\n\n"
                    "요구사항 조건별 코드 충족 여부를 종합 요약한다.\n"
                    "이 섹션은 반드시 출력한다. 생략 불가.\n\n"
                    "| 번호 | 요구사항 조건 | 충족 | 비고 |\n"
                    "|---|---|---|---|\n"
                    "| 1 | 조건 | ✅ / ❌ / ⚠️ 부분 | 근거 또는 미구현 이유 |"
                )
            else:
                req_analysis_principle = ""
                req_section            = ""

            summary_system = _SYS_SUMMARY.format(
                req_analysis_principle=req_analysis_principle,
                req_section=req_section,
            )

            summary_text = ""
            summary_truncated = False
            with client.messages.stream(
                model="claude-sonnet-4-6", max_tokens=self.max_tokens,
                temperature=0,                          # ★ 결정성 확보 (재현 가능 출력)
                system=summary_system,
                messages=[{"role": "user", "content": body}]
            ) as stream:
                for chunk in stream.text_stream:
                    if self._cancel_req:
                        self.cancelled.emit(); return
                    summary_text += chunk
                # 스트림 완료 → 종료 사유 확인 (max_tokens 면 한도에서 잘림)
                final_msg = stream.get_final_message()
                summary_truncated = (final_msg.stop_reason == "max_tokens")
            if self._cancel_req:
                self.cancelled.emit(); return
            if summary_truncated:
                summary_text = self._truncation_warning(self.max_tokens) + summary_text
            self.summary_done.emit(summary_text, summary_truncated)

            # ② 취약점 분석
            # 변경점 요약 결과를 컨텍스트로 추가하여 분석 일관성 향상

            # ★ 기본: cat1~cat6 (단순/복합 20가지 유형) 항상 포함
            BASE_KEYS = ["cat1", "cat2", "cat3", "cat4", "cat5", "cat6"]
            base_cats = "\n".join(
                CAT_PROMPTS[k] for k in BASE_KEYS if k in CAT_PROMPTS)

            # ★ 추가: 체크된 코딩 표준 항목만 선택적으로 포함
            EXTRA_KEYS = ["cert_c", "misra_c", "misra_c23", "misra"]  # extra1 제거 [EXTRA1 DISABLED]
            extra_cats = "\n".join(
                CAT_PROMPTS[k] for k in EXTRA_KEYS
                if self.opts.get(k, False) and k in CAT_PROMPTS)

            cats = base_cats
            if extra_cats:
                cats += "\n\n=== 추가 코딩 표준 검사 ===\n" + extra_cats

            # ★ CB 과거 이슈 검사 지시문 — cb_context 가 있을 때만 추가
            cb_section = _CB_VULN_SECTION if self.cb_context else ""

            # ★ 규칙 위반 섹션 — cert_c / misra_c / misra_c23 중 하나라도 체크된 경우 추가
            _RULE_KEYS = ["cert_c", "misra_c", "misra_c23"]
            checked_standards = [
                {"cert_c": "CERT-C", "misra_c": "MISRA-C:2012", "misra_c23": "MISRA-C:2023"}.get(k, k)
                for k in _RULE_KEYS
                if self.opts.get(k, False) and self.option_contents.get(k, "").strip()
            ]
            rule_violation_section = (
                _RULE_VIOLATION_SECTION.format(
                    standards=", ".join(checked_standards))
                if checked_standards else ""
            )

            # ★ CB 연관 이슈 섹션 — 과거차/L&L/SWE1/SWE3 중 하나라도 로드 시 추가
            past_issue_section = _CB_ISSUES_SECTION if self.cb_context else ""

            # ★ SA(정적검증) 플레이스홀더 — 코딩 표준 체크 시에만 SA 관련 지시 삽입
            if checked_standards:
                sa_standards_principle = (
                    "1. 지정된 코딩 표준(아래 === 적용 코딩 표준 ===에 명시된 기준)만을 기반으로 "
                    "정적 분석 위반을 검출한다. 범위를 벗어난 임의 표준 적용 금지."
                )
                sa_crossref_rule = (
                    "7. 정적 분석 위반(CERT-C / MISRA)이 기능 결함(cat1~cat6) 항목과 동일 위치·"
                    "동일 근본 원인인 경우, 취약점 항목 표의 \"관련 정적 분석\" 컬럼에 SA 번호를 교차 기재한다.\n"
                    "   반대로 정적 분석 위반 항목에도 연관 취약점 번호(H-N/M-N/L-N)를 기재한다."
                )
                sa_summary_note = (
                    "*(H/M/L은 cat1~cat6 SW 품질 결함 기준. "
                    "CERT-C/MISRA 정적 분석 위반은 아래 별도 섹션 참조.)*"
                )
                sa_table_column     = "| 관련 정적 분석 | SA-N (해당 없으면 —) |"
                sa_selfcheck_crossref = (
                    "1. **Cross-reference 양방향 매핑 점검**:\n"
                    "   - cat1~cat6 취약점 항목 중 SA 위반과 연관된 항목에 \"관련 정적 분석\" 컬럼이 기재됐는가?\n"
                    "   - 정적 분석 위반 항목 중 취약점(H/M/L)과 연관된 항목에 해당 번호가 기재됐는가?"
                )
                sa_selfcheck_heading = ", 🔬 정적 분석 위반"
            else:
                sa_standards_principle = ""
                sa_crossref_rule       = ""
                sa_summary_note        = ""
                sa_table_column        = ""
                sa_selfcheck_crossref  = ""
                sa_selfcheck_heading   = ""

            # ★ 요구사항 플레이스홀더 (취약점 분석용) — req_text 제공 시에만 삽입
            req_principle = (
                "5. 요구사항이 제공된 경우, 변경 코드가 각 요구사항 조건을 충족하는지 검증하고 "
                "미충족 항목을 결함으로 보고한다."
            ) if self.req_text else ""

            vuln_body = body + f"\n=== [참고] 변경점 요약 분석 결과 ===\n{summary_text}\n"

            # ② 취약점 분석 (스트리밍 — 취소 플래그 지원)
            # 주의: claude-sonnet-4-6 은 assistant prefill 미지원 → temperature 만 사용
            # system prompt 와 user body 는 변수로 빼서 잘림 시 ContinueVulnWorker 가
            # 같은 컨텍스트로 이어 호출할 수 있게 함.
            vuln_system_prompt = _SYS_VULN_TMPL.format(
                cats=cats,
                rule_violation_section=rule_violation_section,
                past_issue_section=past_issue_section,
                sa_standards_principle=sa_standards_principle,
                sa_crossref_rule=sa_crossref_rule,
                sa_summary_note=sa_summary_note,
                sa_table_column=sa_table_column,
                sa_selfcheck_crossref=sa_selfcheck_crossref,
                sa_selfcheck_heading=sa_selfcheck_heading,
                req_principle=req_principle,
            ) + cb_section

            vuln_text = ""
            vuln_truncated = False
            with client.messages.stream(
                model="claude-sonnet-4-6", max_tokens=self.max_tokens,
                temperature=0.1,                        # ★ 결정성 우선 + 약간의 탐색 여지
                system=vuln_system_prompt,
                messages=[{"role": "user", "content": vuln_body}]
            ) as stream:
                for chunk in stream.text_stream:
                    if self._cancel_req:
                        self.cancelled.emit(); return
                    vuln_text += chunk
                # 스트림 완료 → 종료 사유 확인 (max_tokens 면 한도에서 잘림)
                final_msg = stream.get_final_message()
                vuln_truncated = (final_msg.stop_reason == "max_tokens")
            if self._cancel_req:
                self.cancelled.emit(); return
            # 이어서 분석 컨텍스트 저장 (컨트롤러가 잘림 시 읽음)
            self.last_vuln_system_prompt = vuln_system_prompt
            self.last_vuln_user_body     = vuln_body
            self.last_vuln_raw_text      = vuln_text   # 경고 prepend 전 원본
            if vuln_truncated:
                vuln_text = self._truncation_warning(self.max_tokens) + vuln_text
            self.vuln_done.emit(vuln_text, vuln_truncated)

        except Exception as e:
            self.error.emit(str(e))


# ══════════════════════════════════════════════════════════════
#  ContinueVulnWorker — 잘린 취약점 분석 이어서 호출
# ══════════════════════════════════════════════════════════════
class ContinueVulnWorker(QObject):
    """잘린 취약점 분석을 continuation prompt 방식으로 이어서 호출.

    구조: messages = [user(body), assistant(partial), user("이어서 작성해줘")]
    Claude Sonnet 4.6 은 assistant 로 끝나는 대화를 거부하므로(prefill 미지원),
    assistant turn 뒤에 user 지시 메시지를 추가해 "이어서 작성" 을 명시 요청한다.
    모델은 이전 assistant 출력을 컨텍스트로 보면서 새 user 지시에 응답 → 토큰 절약.

    원본 시스템 프롬프트와 user body 를 그대로 재사용 → 같은 분석 컨텍스트 유지.

    체이닝: 이어서 분석한 결과가 또 잘릴 수 있음. 컨트롤러가 last_raw_text 를
    읽어 다시 ContinueVulnWorker 를 띄우는 식으로 무한 체인 가능.
    """

    # 이어서 작성 지시 — 인사말/반복 없이 곧바로 본문을 이어가도록 강하게 명시
    _CONTINUE_INSTRUCTION = (
        "위 응답이 토큰 한도에서 잘렸습니다. 잘린 지점부터 이어서 계속 작성하세요.\n"
        "\n"
        "**반드시 준수:**\n"
        "- 인사말·안내 문구·메타 발언 없이 곧바로 본문을 이어 작성한다.\n"
        "- 이미 작성된 내용은 절대 반복하지 않는다 (잘린 마지막 단어/문장 직후부터 계속).\n"
        "- 마크다운 포맷·섹션 헤딩·번호 매김(예: H-2, M-1, SA-3, R-2)·표 구조를 그대로 유지한다.\n"
        "- 잘린 위치가 표 행 중간이면 그 행을 마저 완성한 뒤 다음 행으로 진행한다.\n"
        "- 잘린 위치가 코드블록 안이면 코드블록을 닫고 다음 섹션으로 진행한다.\n"
    )

    done      = pyqtSignal(str, bool)   # (display_text, was_truncated_again)
    error     = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, system_prompt: str, user_body: str,
                 partial_text: str, max_tokens: int):
        super().__init__()
        self.system_prompt = system_prompt
        self.user_body     = user_body
        self.partial_text  = partial_text   # 경고 미포함 원본 partial
        self.max_tokens    = max_tokens
        self._cancel_req   = False
        # 다음 chained continuation 을 위해 (partial + continuation) 원본 보관
        self.last_raw_text: str = ""

    def cancel(self):
        self._cancel_req = True

    def run(self):
        try:
            if anthropic is None:
                raise RuntimeError(
                    "anthropic 패키지가 설치되지 않았습니다.\n"
                    "pip install anthropic 을 실행해주세요.")

            client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY"))

            # 마지막 assistant turn 의 trailing whitespace 는 제거 (모델이 깔끔히 잇도록)
            prior_assistant = self.partial_text.rstrip()

            continuation_text = ""
            new_truncated = False
            with client.messages.stream(
                model="claude-sonnet-4-6", max_tokens=self.max_tokens,
                temperature=0.1,
                system=self.system_prompt,
                messages=[
                    {"role": "user",      "content": self.user_body},
                    {"role": "assistant", "content": prior_assistant},
                    {"role": "user",      "content": self._CONTINUE_INSTRUCTION},
                ]
            ) as stream:
                for chunk in stream.text_stream:
                    if self._cancel_req:
                        self.cancelled.emit(); return
                    continuation_text += chunk
                final_msg = stream.get_final_message()
                new_truncated = (final_msg.stop_reason == "max_tokens")

            if self._cancel_req:
                self.cancelled.emit(); return

            full_raw = prior_assistant + continuation_text
            self.last_raw_text = full_raw   # chained continuation 용

            display_text = full_raw
            if new_truncated:
                display_text = (
                    ReviewWorker._truncation_warning(self.max_tokens) + full_raw)
            self.done.emit(display_text, new_truncated)
        except Exception as e:
            self.error.emit(str(e))


# ══════════════════════════════════════════════════════════════
#  [대화형AI DISABLED] 대화형 AI 채팅 프롬프트
#  아래 블록 전체를 주석 해제하면 기능 복구 가능
# _SYS_CHAT = """\
# 너는 차량용 임베디드 SW 코드 리뷰 전문가다.
#
# === 역할 ===
# 개발자가 취약점 분석 결과에 대해 설명하거나 질문하면, 맥락을 반영해 응답하고
# 필요시 해당 취약점 항목을 업데이트한다.
#
# === 응답 형식 (반드시 이 태그 구조로만 출력) ===
#
# <reply>
# 개발자에게 전달할 답변 (2~5문장, 마크다운 사용 가능)
# </reply>
#
# <section_update>
# id: [H-1 형식의 항목 ID, 없으면 NONE]
# content:
# [업데이트된 항목 전체 마크다운. ### H-1. 제목 부터 다음 항목 --- 직전까지. 없으면 NONE]
# </section_update>
#
# <mod_log>
# [항목ID] | [원본 AI 판단 한 줄 요약] | [개발자 설명 한 줄 요약] | [AI 재평가 한 줄 요약]
# 없으면 NONE
# </mod_log>
#
# === 응답 지침 ===
# 1. 설계 의도 해명 시 (예: "이건 의도된 설계"):
#    - 해당 항목 ID를 특정하고 section_update로 내용을 재작성한다.
#    - 의도된 설계임을 반영해 심각도를 낮추거나 항목을 제거할 수 있다.
#    - mod_log에 변경 이력을 한 줄로 기록한다.
# 2. 일반 질문 시: reply만 작성, section_update와 mod_log는 NONE.
# 3. 여러 항목 언급 시: 가장 명확한 항목 하나만 업데이트한다.
# """


# ══════════════════════════════════════════════════════════════
#  [대화형AI DISABLED] 대화형 AI 채팅 워커
#  아래 블록 전체를 주석 해제하면 기능 복구 가능
# ══════════════════════════════════════════════════════════════
# class QaWorker(QObject):
#     answer_done = pyqtSignal(str)   # 구조화된 원문 응답 전달
#     error       = pyqtSignal(str)
#
#     def __init__(self, diff_code: str, vuln_analysis: str, question: str,
#                  history: list | None = None):
#         super().__init__()
#         self.diff_code     = diff_code
#         self.vuln_analysis = vuln_analysis
#         self.question      = question
#         self.history       = history or []   # [{"q": ..., "a": ...}, ...]
#
#     def run(self):
#         try:
#             if anthropic is None:
#                 raise RuntimeError(
#                     "anthropic 패키지가 설치되지 않았습니다.\n"
#                     "pip install anthropic 을 실행해주세요.")
#
#             client = anthropic.Anthropic(
#                 api_key=os.environ.get("ANTHROPIC_API_KEY"))
#
#             # 첫 번째 사용자 메시지에 diff + 분석 리포트를 포함
#             first_user = (
#                 f"=== 변경점 (unified diff) ===\n{self.diff_code}\n\n"
#                 f"=== 현재 취약점 분석 리포트 ===\n{self.vuln_analysis}"
#             )
#
#             # 대화 히스토리 구성
#             messages: list[dict] = []
#             if self.history:
#                 messages.append({
#                     "role": "user",
#                     "content": first_user + f"\n\n=== 개발자 메시지 ===\n{self.history[0]['q']}"
#                 })
#                 messages.append({"role": "assistant", "content": self.history[0]["a"]})
#                 for turn in self.history[1:]:
#                     messages.append({"role": "user",      "content": turn["q"]})
#                     messages.append({"role": "assistant", "content": turn["a"]})
#                 messages.append({"role": "user", "content": self.question})
#             else:
#                 messages.append({
#                     "role": "user",
#                     "content": first_user + f"\n\n=== 개발자 메시지 ===\n{self.question}"
#                 })
#
#             r = client.messages.create(
#                 model="claude-sonnet-4-6", max_tokens=6000,
#                 system=_SYS_CHAT,
#                 messages=messages)
#             self.answer_done.emit(r.content[0].text)
#
#         except Exception as e:
#             self.error.emit(str(e))
