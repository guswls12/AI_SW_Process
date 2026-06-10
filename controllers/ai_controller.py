"""ai_controller.py — Claude AI 분석 흐름 + 결과 라우팅.

main.py 의 _on_ai, _on_summary, _on_vuln, _on_ai_stop, _on_ai_cancelled,
_on_error, _show_ai_confirm_dialog 를 한곳에 모은다.

DiffController 와 CbController 가 보유한 변경점 / CB 컨텍스트를 읽어
ReviewWorker 에 전달하고, 워커 결과를 result panel 에 라우팅한다.
"""

import os

from PyQt6.QtCore import QThread, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QCheckBox,
)

from config                 import C
from core                   import project_state
from core.worker            import BASE_CONTEXT_FILES, OPTION_MD_FILES
from workers.prompts_worker import ReviewWorker, ContinueVulnWorker
from integrations.codebeamer import _BASE as CB_BASE


class AiController:
    def __init__(self, main_window):
        self._mw = main_window
        self._thread = None
        self._worker = None
        # ★ 다이얼로그 슬라이더 마지막 선택값 — 세션 내에서 다음 호출 시 기본값으로 복원
        self._last_max_tokens = 16000
        # ★ "파일 전체 컨텍스트" 다이얼로그 체크박스 마지막 상태 (세션 내 기억)
        self._last_full_ctx = False
        # ★ 잘림 시 이어서 분석(continuation) 상태
        self._continue_thread = None
        self._continue_worker = None
        self._continuation_context: dict | None = None
        # ★ 직전 AI 호출의 변경 함수 ↔ 사양변경 매핑 — _on_summary 에서 요약 결과
        #   상단에 정적 표 형태로 prepend 하기 위해 보관 (AI 분석에는 미사용).
        self._last_user_mapping_md: str = ""

    # ──────────────────────────────────────────────────────────
    #  ① AI 분석 진입점 — _input.ai_clicked 시그널 슬롯
    # ──────────────────────────────────────────────────────────
    def on_ai(self, params: dict):
        mw = self._mw

        # ── ① 파일 선택 검증 (다이얼로그 띄우기 전) ─────────────
        # 매핑 다이얼로그에서 사용할 "체크된 파일" 셋 — 폴더 모드일 때만 설정.
        # 단일 파일 모드면 None (= 필터링 없음 / 모든 함수)
        checked_files: set | None = None

        if "file_pairs" not in params:
            if not mw._result.get_single_file_checked():
                mw._sb.showMessage("⚠  AI 분석할 파일을 체크해주세요."); return

        if "file_pairs" in params:
            checked_pairs = mw._result.get_checked_folder_pairs()
            if not checked_pairs:
                mw._sb.showMessage("⚠  AI 분석할 파일을 하나 이상 체크해주세요."); return
            # 체크된 파일만으로 old_code / new_code / diff_code / changed_text 재조합
            old_parts, new_parts, diff_parts, output_lines, _, _ = \
                mw._diff.build_folder_code_parts(checked_pairs, skip_unchanged=False)
            params = dict(params)
            params["old_code"]  = "\n".join(old_parts)
            params["new_code"]  = "\n".join(new_parts)
            params["diff_code"] = "\n".join(diff_parts)
            mw._diff.changed_text = "\n".join(output_lines) if output_lines else "변경 없음"
            # 매핑 다이얼로그가 체크된 파일의 함수만 보여주도록 rel_path 셋 저장
            checked_files = {p[0] for p in checked_pairs}

        # ── ①.5 변경 함수 ↔ 사양변경 매핑 다이얼로그 ─────────────
        # 선택된 사양변경이 1개 이상이고 변경 함수 정보가 있으면 사용자가
        # 매핑을 확정한 후 분석에 사용. 사양변경 0개면 스킵 (기존 흐름).
        try:
            spec_list = mw._result.extras_panel.get_spec_changes_list()
        except Exception:
            spec_list = []
        changed_funcs = list(getattr(mw._diff, "changed_funcs", None) or [])
        # 1) 폴더 모드면 사용자가 결과 패널에서 체크한 파일의 함수만 표시
        # 2) __global__ 항목은 매핑 대상 제외 (전역 변경은 모든 사양변경에 영향)
        mappable = []
        for cf in changed_funcs:
            if (cf.get("function") or "") == "__global__":
                continue
            if checked_files is not None and cf.get("file") not in checked_files:
                continue
            mappable.append(cf)
        if spec_list and mappable:
            from view.ui_dialog import SpecMappingDialog
            dlg = SpecMappingDialog(mw, mappable, spec_list)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                mw._sb.showMessage("⏸  매핑 취소 — 분석을 중단했습니다.")
                return
            mapping = dlg.mapping
            # 매핑 정보를 마크다운 표로 변환 후 code_info 앞에 prepend (취약점 분석용)
            mapping_md = self._build_mapping_md(mapping, spec_list)
            old_ci = params.get("code_info") or ""
            params["code_info"] = mapping_md + ("\n\n" + old_ci if old_ci else "")
            # ★ 매핑 결과를 project_state 에 저장 — ⑧ OPEN 항목 페이지에서
            #   변경점별 OK/NG 판정에 사용 (변경점에 매핑된 함수가 있으면 OK)
            self._persist_review_mapping(mapping, spec_list)
            # ★ 요약 결과 상단에 prepend 할 사용자 매핑 표 (참고용 정적 표시)
            self._last_user_mapping_md = self._build_user_mapping_display(
                mapping, spec_list)
        else:
            self._last_user_mapping_md = ""

        # ── ② 컨텍스트 로딩 (다이얼로그 띄우기 전 — 토큰 카운트용) ──
        include_opts = params.get("include_opts", {})
        params["req_text"] = mw._result.extras_panel.get_req_text()
        if not include_opts.get("req", True):
            params["req_text"] = ""
        # CB 섹션 선택적 로드
        cb_keys = [k for k in ("past",)   # ll/swe1/swe3 비활성화 [LL/SWE DISABLED]
                   if include_opts.get(k, True)]
        mw._cb.cb_context = mw._cb.load_sections(cb_keys)

        # ★ 분석 컨텍스트 MD 파일 로드
        #   1) BASE_CONTEXT_FILES : 항상 로드 (sw_quality 카테고리 정의 등 핵심 분석 기준)
        #   2) OPTION_MD_FILES    : opts 에서 체크된 옵션만 로드 (CERT-C / MISRA 등)
        opts = params.get("opts", {})
        option_contents: dict[str, str] = {}
        _UNIMPLEMENTED = set()  # extra1 비활성화됨 [EXTRA1 DISABLED]

        def _load_md_into(key: str, md_filename: str, *, optional: bool):
            """MD 파일을 읽어 option_contents[key] 에 저장. 누락/실패 시 상태바 안내."""
            md_path = os.path.join(CB_BASE, md_filename)
            if os.path.exists(md_path):
                try:
                    with open(md_path, "r", encoding="utf-8") as f:
                        option_contents[key] = f.read()
                except Exception as e:
                    mw._sb.showMessage(f"⚠️  {md_filename} 로드 실패: {e}")
            else:
                if key in _UNIMPLEMENTED:
                    mw._sb.showMessage(
                        f"⚠️  [{key}] 옵션은 아직 미구현 상태입니다 "
                        f"({md_filename} 파일 없음) — 해당 검사를 건너뜁니다.")
                elif not optional:
                    # 기본 컨텍스트가 없으면 분석 품질이 떨어지므로 더 강한 경고
                    mw._sb.showMessage(
                        f"⚠️  필수 컨텍스트 파일 누락: {md_filename} "
                        f"— [{key}] 기준 없이 분석을 진행합니다.")
                else:
                    mw._sb.showMessage(
                        f"⚠️  {md_filename} 파일을 찾을 수 없습니다 "
                        f"— [{key}] 검사를 건너뜁니다.")

        # 1) 기본 컨텍스트 — 무조건 로드
        for key, md_filename in BASE_CONTEXT_FILES.items():
            _load_md_into(key, md_filename, optional=False)

        # 2) 선택 옵션 — 체크된 항목만 로드
        for opt_key, md_filename in OPTION_MD_FILES.items():
            if not opts.get(opt_key, False):
                continue  # 체크 안 된 옵션은 스킵
            _load_md_into(opt_key, md_filename, optional=True)

        # ★ 파일 전체 컨텍스트 포함 — 다이얼로그 체크박스로 결정 (세션 마지막 값으로 초기화)
        full_ctx_init = self._last_full_ctx

        # ── 진단용: body 컴포넌트별 크기 출력 (stderr) ─────────
        # 좌측 패널 체크 상태에 따라 cb_context / option_contents 가 어떻게
        # 채워지는지 한 줄로 보여줘서 토큰 변동 원인을 추적할 수 있게 한다.
        import sys
        opt_summary = {k: len(v) for k, v in option_contents.items()}
        print(
            f"[BODY DEBUG] include_opts={include_opts}  "
            f"cb_context={len(mw._cb.cb_context):,}ch  "
            f"option_contents={opt_summary}  "
            f"req_text={len(params['req_text']):,}ch  "
            f"changed_text={len(mw._diff.changed_text or ''):,}ch  "
            f"old_code={len(params['old_code']):,}ch  "
            f"new_code={len(params['new_code']):,}ch  "
            f"diff_code={len(params['diff_code']):,}ch  "
            f"full_ctx_init={full_ctx_init}",
            file=sys.stderr, flush=True)

        # ── ③ 초기 body 빌드 + 입력 토큰 카운트 ────────────────
        def _build_body(full_ctx_flag: bool) -> str:
            """다이얼로그 체크박스 토글 시 동일 입력 컴포넌트로 body 재조립."""
            body = ReviewWorker._body(
                params["old_code"], params["new_code"], params["diff_code"],
                params["code_info"], params["req_text"],
                mw._diff.changed_text or "",
                mw._cb.cb_context,
                option_contents,
                full_ctx_flag,
            )
            print(
                f"[BODY DEBUG] full_ctx={full_ctx_flag} → body={len(body):,}ch",
                file=sys.stderr, flush=True)
            return body

        from PyQt6.QtWidgets import QApplication
        mw._sb.showMessage("⏱  입력 토큰 측정 중...")
        QApplication.processEvents()
        input_tokens, count_error = self._count_input_tokens(
            _build_body(full_ctx_init))
        if count_error:
            mw._sb.showMessage(f"⚠  토큰 측정 실패: {count_error}")
        else:
            mw._sb.showMessage("")

        # ── ④ 커스텀 확인 다이얼로그 (토큰 표시 + 슬라이더 + 전체 컨텍스트 체크) ──
        result = self._show_confirm_dialog(
            input_tokens=input_tokens, count_error=count_error,
            full_ctx_initial=full_ctx_init,
            recount_callback=lambda flag: self._count_input_tokens(
                _build_body(flag)),
        )
        if result is None:
            return
        max_tokens, full_ctx = result
        self._last_full_ctx = full_ctx

        # ── ⑤ 한도 검사 (이미 카운트된 값 재사용) ───────────────
        if not self._check_token_limit(input_tokens, max_tokens):
            mw._sb.showMessage("🚫  토큰 한도 위험으로 분석을 취소했습니다.")
            return

        # ── ⑥ 분석 시작 ────────────────────────────────────────
        mw._input.set_ai_running(True)
        mw._result.step_bar.advance(2)
        if "file_pairs" in params:
            mw._sb.showMessage(
                f"🤖  Claude AI 분석 중...  |  선택 파일 {len(checked_pairs)}개")
        else:
            mw._sb.showMessage("🤖  Claude AI가 변경점 요약 및 취약점 분석 중...")

        self._thread = QThread()
        self._worker = ReviewWorker(
            params["old_code"], params["new_code"], params["diff_code"],
            params["code_info"], params["req_text"], params["opts"],
            mw._diff.changed_text,    # ★ 보관해둔 변경점 텍스트 전달
            mw._cb.cb_context,        # ★ Codebeamer 컨텍스트 전달
            option_contents,          # ★ 리뷰 옵션 MD 내용 전달
            max_tokens,               # ★ 사용자 지정 응답 토큰 한도
            full_ctx)                 # ★ 파일 전체 본문 포함 여부
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.summary_done.connect(self._on_summary)
        self._worker.vuln_done.connect(self._on_vuln)
        self._worker.error.connect(self._on_error)
        self._worker.cancelled.connect(self._on_cancelled)   # ★ 중단 완료
        self._worker.vuln_done.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.cancelled.connect(self._thread.quit)    # ★
        # 스레드 종료 후 워커/스레드 객체 deleteLater — gc 타이밍 충돌 방지
        # (SweReviewController / SrsReviewV2Controller 와 동일 패턴)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    # ──────────────────────────────────────────────────────────
    #  ② 워커 결과 슬롯
    # ──────────────────────────────────────────────────────────
    def _on_summary(self, text: str, truncated: bool = False):
        # ★ 사용자가 분석 직전 확정한 변경점 ↔ 변경 함수 매핑 표를 요약 결과
        #    상단에 정적 prepend (AI 출력 아님, 참고용 표시)
        prefix = self._last_user_mapping_md or ""
        full_text = (prefix + "\n\n" + text) if prefix else text
        self._mw._result.set_summary(full_text)
        if truncated:
            self._mw._sb.showMessage(
                "⚠  변경점 요약이 토큰 한도에서 잘림 — 결과 상단 경고 참조. "
                "취약점 분석은 계속 진행합니다.")
        else:
            self._mw._sb.showMessage("✅  변경점 요약 완료 — 취약점 분석 중...")

    def _on_vuln(self, text: str, truncated: bool = False):
        mw = self._mw
        mw._result.set_vuln(text)
        mw._result.set_project_name(mw._input.get_project_name())  # ★ 저장 파일명용
        mw._input.set_ai_running(False)

        if truncated:
            mw._sb.showMessage(
                "⚠  분석이 토큰 한도에서 잘렸습니다 — 이어서 분석할 수 있습니다.")
            # 이어서 분석을 위한 컨텍스트 저장 (워커 속성에서 복사)
            if self._worker is not None:
                self._continuation_context = {
                    "system_prompt": self._worker.last_vuln_system_prompt,
                    "user_body":     self._worker.last_vuln_user_body,
                    "raw_text":      self._worker.last_vuln_raw_text,
                }
            # 결과 패널이 redraw 한 뒤 팝업 띄움 (즉시 exec_() 면 redraw 전 블록됨)
            QTimer.singleShot(150, self._prompt_continue)
            return

        mw._sb.showMessage(
            "✅  분석 완료!  탭을 전환하여 결과를 확인하고 저장하세요.")
        QTimer.singleShot(150, self._show_complete_dialog)

    # ──────────────────────────────────────────────────────────
    #  ③ 중단 / 에러 처리
    # ──────────────────────────────────────────────────────────
    def on_stop(self):
        """UI 스레드 — 분석 중단 버튼 클릭 시 확인 다이얼로그 후 워커 cancel 요청.
        continuation 진행 중이면 그쪽을, 아니면 본 분석 워커를 취소."""
        if not self._show_stop_confirm_dialog():
            return   # 사용자가 "계속 진행" 선택 → 중단하지 않음
        if (self._continue_thread is not None and
                self._continue_thread.isRunning() and
                self._continue_worker is not None):
            self._continue_worker.cancel()
        elif self._worker is not None:
            self._worker.cancel()
        self._mw._sb.showMessage("⏹  분석 중단 요청 중...")

    def _on_cancelled(self):
        """워커가 cancelled 시그널 emit → UI 정상 복귀."""
        self._mw._input.set_ai_running(False)
        self._mw._sb.showMessage("⏹  AI 분석이 중단되었습니다.")

    def _on_error(self, msg: str):
        self._mw._input.set_ai_running(False)
        # API 키 관련 오류일 때만 환경변수 안내 추가. 그 외 (코드 버그·네트워크·SDK 기타)
        # 는 원본 메시지만 표시 → 잘못된 진단으로 사용자 헷갈리게 하지 않음.
        msg_lower = msg.lower()
        _API_KEY_MARKERS = (
            "anthropic_api_key",   # 환경변수 부재 시 워커가 직접 던지는 메시지
            "authentication",      # anthropic.AuthenticationError
            "invalid x-api-key",   # API 응답 메시지
            "no api key",
            "401",                 # HTTP unauthorized
        )
        # ★ 입력 토큰 한도 초과 — 친절한 다이얼로그로 라우팅
        _TOKEN_LIMIT_MARKERS = (
            "prompt is too long",          # Anthropic API 메시지
            "context length",
            "context_length",
            "token count exceeds",
            "tokens exceed",
            "maximum context length",
            "exceeds the maximum",
        )
        if any(m in msg_lower for m in _TOKEN_LIMIT_MARKERS):
            from view.ui_dialog import TokenLimitDialog
            # 메시지에서 실측 토큰 수 추출 시도 (예: "X tokens > Y maximum")
            import re
            m_in = re.search(r'(\d{4,})\s*tokens?', msg_lower)
            actual_input = int(m_in.group(1)) if m_in else 0
            TokenLimitDialog(
                self._mw,
                input_tokens=actual_input,
                max_tokens=self._last_max_tokens,
                buffer=0,                     # 실제 거부 — 버퍼 의미 없음
                model_limit=200_000,
                title="API 거부: 입력 토큰 한도 초과",
            ).exec()
            self._mw._sb.showMessage(f"❌  토큰 한도 초과: {msg[:90]}")
            return

        if any(m in msg_lower for m in _API_KEY_MARKERS):
            err = (f"❌ 오류가 발생했습니다.\n\n{msg}\n\n"
                   "ANTHROPIC_API_KEY 환경변수를 확인해주세요.")
        else:
            err = f"❌ 오류가 발생했습니다.\n\n{msg}"
        self._mw._result.set_summary(err)
        self._mw._result.set_vuln(err)
        self._mw._sb.showMessage(f"❌  오류: {msg[:90]}")

    # ──────────────────────────────────────────────────────────
    #  ★ 입력 토큰 카운트 (Anthropic count_tokens API)
    # ──────────────────────────────────────────────────────────
    def _count_input_tokens(self, body: str) -> tuple[int | None, str | None]:
        """Anthropic count_tokens 로 입력 토큰을 측정한다.
        반환: (tokens, error_reason)
          (int,  None) → 측정 성공
          (None, str)  → 측정 실패 (사유 문자열 — 다이얼로그/상태바 표시용)
        """
        import sys, traceback
        try:
            import anthropic
        except ImportError:
            return None, "anthropic SDK 미설치"
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None, "ANTHROPIC_API_KEY 환경변수 없음"
        try:
            client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            return None, f"클라이언트 초기화 실패: {type(e).__name__}"

        # SDK 버전 체크 — count_tokens 는 비교적 최근(0.40+) 추가
        if not hasattr(client.messages, "count_tokens"):
            return None, "SDK 버전 오래됨 (count_tokens 미지원, pip install -U anthropic)"

        # 빈 body 방어
        if not body or not body.strip():
            return None, "입력 본문이 비어 있음 (DIFF 추출 필요)"

        try:
            resp = client.messages.count_tokens(
                model="claude-sonnet-4-6",
                messages=[{"role": "user", "content": body}],
            )
            tokens = int(getattr(resp, "input_tokens", 0))
            return tokens, None
        except Exception as e:
            # 콘솔(stderr)에 전체 트레이스 — 진단용
            traceback.print_exc(file=sys.stderr)
            raw_msg = str(e)
            msg_l = raw_msg.lower()

            # 흔한 에러 패턴을 한국어로 친절하게 분기
            if "credit balance" in msg_l or "billing" in msg_l or "credit" in msg_l:
                return None, ("💳  Anthropic 크레딧 부족 — "
                              "console.anthropic.com 에서 충전 필요 "
                              "(분석도 동일 사유로 실패합니다)")
            if "rate limit" in msg_l or "429" in msg_l or "too many requests" in msg_l:
                return None, "🚦  API rate limit 도달 — 잠시 후 재시도"
            if ("authentication" in msg_l or "invalid x-api-key" in msg_l
                    or "401" in msg_l or "unauthorized" in msg_l):
                return None, "🔑  API 키 인증 실패 — ANTHROPIC_API_KEY 확인"
            if "model" in msg_l and ("not found" in msg_l or "invalid" in msg_l):
                return None, "🤖  모델 식별 오류 — claude-sonnet-4-6 사용 불가"
            # 게이트웨이/서버 일시 장애 (HTML 본문이 자주 따라옴)
            if any(code in msg_l for code in ("502", "503", "504", "bad gateway",
                                              "service unavailable", "gateway time")):
                return None, ("🌐  Anthropic 서버 일시 장애 (5xx) — "
                              "잠시 후 재시도. 결제 미활성 계정에서도 자주 발생함")
            # 일반 fallback — HTML 본문이면 태그 제거 후 표시 (RichText 깨짐 방지)
            import re
            cleaned = re.sub(r"<[^>]+>", " ", raw_msg)       # HTML 태그 제거
            cleaned = re.sub(r"\s+", " ", cleaned).strip()    # 공백 정리
            return None, f"{type(e).__name__}: {cleaned[:120]}"

    # ──────────────────────────────────────────────────────────
    #  ★ 한도 검사 + 초과 시 경고 다이얼로그
    # ──────────────────────────────────────────────────────────
    def _check_token_limit(self, input_tokens: int | None,
                           max_tokens: int) -> bool:
        """input + max_tokens + 버퍼가 모델 한도를 넘는지 검사.
        넘으면 TokenLimitDialog 띄워 사용자에게 선택권 제공.
        반환:
          True  → 진행 OK (안전하거나, 사용자가 '그래도 진행' 선택)
          False → 사용자가 '취소' 선택 → 분석 중단
        input_tokens 가 None(측정 실패) 이면 관대하게 True 반환.
        """
        if input_tokens is None:
            return True   # 측정 실패 — 워커 단에서 실 에러 처리

        # 버퍼 20K = 시스템 프롬프트(_SYS_SUMMARY/_SYS_VULN_TMPL ~ 수천 토큰) +
        # vuln 호출에 추가되는 요약 결과(최대 max_tokens 만큼) 의 안전 마진
        MODEL_LIMIT = 200_000
        BUFFER      = 20_000
        projected   = input_tokens + max_tokens + BUFFER
        if projected <= MODEL_LIMIT:
            return True

        # 한도 초과 위험 — 사용자 확인
        from view.ui_dialog import TokenLimitDialog
        dlg = TokenLimitDialog(
            self._mw,
            input_tokens=input_tokens,
            max_tokens=max_tokens,
            buffer=BUFFER,
            model_limit=MODEL_LIMIT,
        )
        return dlg.exec() == QDialog.DialogCode.Accepted  # Accepted=그래도 진행

    # ──────────────────────────────────────────────────────────
    #  변경 함수 ↔ 사양변경 매핑 — project_state 영속화
    # ──────────────────────────────────────────────────────────
    def _persist_review_mapping(self, mapping: list, spec_changes: list) -> None:
        """SpecMappingDialog 확정 결과를 project_state 에 저장.

        저장 위치: state["review_mapping"] = {
            "spec_changes": [{"id":..., "name":...}, ...],   # 매핑 다이얼로그가 사용한 사양변경 리스트
            "func_map":     [{"file":..., "function":..., "spec_id":...}, ...],
        }
        ⑧ OPEN 항목 페이지가 변경점 OK/NG 판정 시 이 데이터를 읽음:
          · ① 사양변경 페이지 변경점의 title 과 spec_changes[i].name 을 substring 매칭
          · 매칭된 spec_id 에 함수 1개라도 있으면 OK, 없으면 NG
        """
        mw = self._mw
        proj = getattr(mw, "_project_name", "") or ""
        ver  = getattr(mw, "_project_version", "") or ""
        if not proj or not ver:
            return
        try:
            state = project_state.load_state(proj, ver)
            state["review_mapping"] = {
                "spec_changes": [
                    {"id": str(sc.get("id", "") or ""),
                     "name": str(sc.get("name", "") or "")}
                    for sc in (spec_changes or [])
                ],
                "func_map": [
                    {"file":     str(it.get("file", "") or ""),
                     "function": str(it.get("function", "") or ""),
                     "spec_id":  str(it.get("spec_id", "") or "")}
                    for it in (mapping or [])
                ],
            }
            project_state.save_state(proj, ver, state)
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────
    #  사용자 확정 매핑 — 요약 결과 상단 표시용 (AI 분석 무관)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _build_user_mapping_display(mapping: list, spec_changes: list) -> str:
        """SpecMappingDialog 확정 결과를 요약 패널 상단에 정적 표로 표시.
        AI 분석에는 영향 없음 — 사용자가 직전에 선택한 매핑을 그대로 보여주기만 함.
        """
        if not mapping:
            return ""
        spec_lookup = {sc.get("id", ""): sc.get("name", "")
                       for sc in (spec_changes or [])}
        lines = [
            "## 🔗 변경점 ↔ 변경 코드 매핑 (사용자 확정)",
            "",
            "> 분석 직전 매핑 다이얼로그에서 확정한 매핑입니다 — 참고용 정적 표시.",
            "",
            "| 파일 | 함수 | 매칭 사양변경 |",
            "|------|------|---------------|",
        ]
        for item in mapping:
            f   = item.get("file") or ""
            fn  = item.get("function") or ""
            sid = item.get("spec_id") or ""
            fn_disp = "(전역 영역)" if fn == "__global__" else f"`{fn}()`"
            if sid:
                name = spec_lookup.get(sid, "")
                spec_disp = f"**#{sid}** — {name}" if name else f"**#{sid}**"
            else:
                spec_disp = "_미매칭_"
            lines.append(f"| `{f}` | {fn_disp} | {spec_disp} |")
        lines.append("")
        lines.append("---")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    #  변경 함수 ↔ 사양변경 매핑 마크다운 빌더
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _build_mapping_md(mapping: list, spec_changes: list) -> str:
        """SpecMappingDialog 가 확정한 매핑을 마크다운 표로 변환.
        AI 가 이 매핑을 그대로 사용하여 사양변경별로 그룹화 분석하도록 user
        body 최상단에 prepend 한다. 시스템 프롬프트 (.md) 는 안 건드림.

        포맷:
          ### 변경 함수 ↔ 사양변경 확정 매핑 (사용자 지정)
          | 파일 | 함수 | 매칭 사양변경 |
          | ... | ... | ... |
        """
        if not mapping:
            return ""
        spec_lookup = {sc.get("id", ""): sc.get("name", "")
                       for sc in (spec_changes or [])}

        lines = [
            "### 변경 함수 ↔ 사양변경 확정 매핑 (사용자 지정)",
            "",
            "아래 표는 사용자가 다이얼로그에서 직접 확정한 매핑입니다. "
            "**이 매핑을 그대로 적용**하여 각 변경 함수의 분석 결과를 해당 "
            "사양변경 섹션에 배치해주세요. 한 변경 함수가 매핑된 사양변경과 "
            "다른 사양변경 섹션에 절대 들어가면 안 됩니다.",
            "",
            "| 파일 | 함수 | 매칭 사양변경 |",
            "|------|------|---------------|",
        ]
        for item in mapping:
            f  = item.get("file") or ""
            fn = item.get("function") or ""
            sid = item.get("spec_id") or ""
            fn_disp = "(전역 영역)" if fn == "__global__" else f"`{fn}()`"
            if sid:
                name = spec_lookup.get(sid, "")
                spec_disp = f"**#{sid}** — {name}" if name else f"**#{sid}**"
            else:
                spec_disp = "_미매칭_"
            lines.append(f"| `{f}` | {fn_disp} | {spec_disp} |")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    #  ④ 분석 시작 확인 다이얼로그
    # ──────────────────────────────────────────────────────────
    def _show_confirm_dialog(self, input_tokens: int | None = None,
                             count_error: str | None = None,
                             full_ctx_initial: bool = False,
                             recount_callback=None) -> "tuple[int, bool] | None":
        """AI 분석 시작 확인 커스텀 다이얼로그.

        Args:
          input_tokens     : 사전 측정된 입력 토큰 수 (라벨로 표시).
          count_error      : 측정 실패 시 사유 문자열.
          full_ctx_initial : "파일 전체 컨텍스트 포함" 체크박스의 초기 상태.
          recount_callback : 체크박스 토글 시 호출 (flag) → (tokens, error).
                             None 이면 토큰 라벨은 갱신 안 함.

        Returns:
          (max_tokens, full_ctx) 튜플 — 분석 시작
          None                    — 취소
        """
        mw = self._mw
        dlg = QDialog(mw)
        dlg.setWindowTitle("AI 분석 확인")
        dlg.setFixedSize(460, 460)
        dlg.setStyleSheet(
            f"QDialog {{ background:{C.BG_PANEL}; border:1px solid {C.BDR2}; }}"
        )

        vlay = QVBoxLayout(dlg)
        vlay.setContentsMargins(32, 24, 32, 22)
        vlay.setSpacing(0)

        # 아이콘 + 타이틀
        icon_lbl = QLabel("🤖")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 28))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background:transparent; border:none;")
        vlay.addWidget(icon_lbl)
        vlay.addSpacing(8)

        title = QLabel("AI 분석을 시작합니다")
        title.setFont(QFont(C.FUI, 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{C.T0}; background:transparent; border:none;")
        vlay.addWidget(title)
        vlay.addSpacing(6)

        desc = QLabel("Claude API 토큰이 사용됩니다.\n계속 진행하시겠습니까?")
        desc.setFont(QFont(C.FUI, 10))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"color:{C.T3}; background:transparent; border:none;")
        vlay.addWidget(desc)
        vlay.addSpacing(10)

        # ── 사전 측정된 입력 토큰 표시 ─────────────────────────
        # 토큰 라벨은 이후 체크박스 토글 시 갱신해야 하므로 styled 함수로 분리
        def _set_tok_label(tokens: int | None, err: str | None,
                           measuring: bool = False):
            """토큰 라벨 텍스트·색상을 상태(측정 중/성공/실패) 별로 설정."""
            if measuring:
                text = "📊  입력 토큰: <i>측정 중...</i>"
                color, bg, border = C.T3, "#EEF2F7", C.BDR
            elif tokens is not None:
                text = f"📊  입력 토큰: <b>{tokens:,}</b>"
                if tokens >= 1000:
                    text += f"  ({tokens / 1000:.1f}K)"
                color, bg, border = C.T1, "#EEF2F7", C.BDR
            else:
                # 측정 실패 — count_error 본문이 HTML(예: Cloudflare 502)을 포함할 수
                # 있어 RichText 로 그대로 넘기면 레이아웃이 깨짐 → 항상 escape.
                from html import escape as _html_escape
                text = "📊  입력 토큰: <i>측정 실패</i>"
                if err:
                    text += (f"<br><span style='font-size:9pt; color:{C.T3};'>"
                             f"{_html_escape(err)}</span>")
                color, bg, border = "#92400E", "#FEF6EC", "#F0D8A8"
            tok_lbl.setText(text)
            tok_lbl.setStyleSheet(
                f"color:{color}; background:{bg}; border:1px solid {border}; "
                f"border-radius:6px; padding:8px 12px;")

        tok_lbl = QLabel("")
        tok_lbl.setTextFormat(Qt.TextFormat.RichText)
        tok_lbl.setFont(QFont(C.FUI, 10))
        tok_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tok_lbl.setWordWrap(True)
        tok_lbl.setMinimumHeight(56)
        _set_tok_label(input_tokens, count_error)
        vlay.addWidget(tok_lbl)
        vlay.addSpacing(10)

        # ── 파일 전체 컨텍스트 체크박스 ────────────────────────
        full_ctx_chk = QCheckBox("  파일 전체 컨텍스트 포함  (토큰 사용량 많음)")
        full_ctx_chk.setChecked(bool(full_ctx_initial))
        full_ctx_chk.setCursor(Qt.CursorShape.PointingHandCursor)
        full_ctx_chk.setFont(QFont(C.FUI, 10, QFont.Weight.DemiBold))
        full_ctx_chk.setStyleSheet(
            f"QCheckBox {{ color:{C.T1}; background:transparent; spacing:8px; }}"
            f"QCheckBox::indicator {{ width:16px; height:16px; border-radius:3px;"
            f"  border:1px solid {C.BDR2}; background:{C.BG_INPUT}; }}"
            f"QCheckBox::indicator:checked {{ background:{C.BLUE}; "
            f"  border-color:{C.BLUE}; }}"
            f"QCheckBox::indicator:hover {{ border-color:{C.BLUE}; }}")
        vlay.addWidget(full_ctx_chk)

        full_ctx_hint = QLabel(
            "OFF: 변경된 함수만 분석 (절감)  ·  ON: 전체 파일 본문 포함")
        full_ctx_hint.setFont(QFont(C.FUI, 8))
        full_ctx_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        full_ctx_hint.setStyleSheet(
            f"color:{C.T3}; background:transparent; border:none; padding-top:2px;")
        vlay.addWidget(full_ctx_hint)
        vlay.addSpacing(12)

        # ── 체크박스 토글 → 입력 토큰 재카운트 ─────────────────
        def _on_full_ctx_toggled(state):
            if recount_callback is None:
                return
            # 라벨을 "측정 중..." 으로 잠시 바꾸고 이벤트 펌프
            _set_tok_label(None, None, measuring=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
            flag = (state == Qt.CheckState.Checked.value)
            tokens, err = recount_callback(flag)
            _set_tok_label(tokens, err)
        full_ctx_chk.stateChanged.connect(_on_full_ctx_toggled)

        # ── 최대 응답 토큰 슬라이더 ────────────────────────────
        # 범위: 4,000 ~ 64,000 (Sonnet 4.6 max output 64K)
        # 슬라이더는 1K 단위 정수로 다룸 → setValue(16) == 16,000 토큰
        token_row = QHBoxLayout()
        token_row.setSpacing(10)
        token_row.setContentsMargins(0, 0, 0, 0)

        token_lbl = QLabel("최대 응답 토큰")
        token_lbl.setFont(QFont(C.FUI, 9, QFont.Weight.DemiBold))
        token_lbl.setStyleSheet(
            f"color:{C.T1}; background:transparent; border:none;")
        token_lbl.setMinimumWidth(95)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(4, 64)
        slider.setValue(max(4, min(64, self._last_max_tokens // 1000)))
        slider.setSingleStep(1)
        slider.setPageStep(4)
        slider.setCursor(Qt.CursorShape.PointingHandCursor)
        # 프로그램 메인 BLUE 통일 (기존 #2563EB/#1D4ED8 진한 블루였음)
        slider.setStyleSheet(
            "QSlider::groove:horizontal {"
            "  background:#CBD5E1; height:6px; border-radius:3px; }"
            f"QSlider::sub-page:horizontal {{"
            f"  background:{C.BLUE}; height:6px; border-radius:3px; }}"
            f"QSlider::handle:horizontal {{"
            f"  background:{C.BLUE_DK}; border:2px solid #FFFFFF;"
            f"  width:14px; height:14px; margin:-5px 0; border-radius:9px; }}"
            f"QSlider::handle:horizontal:hover {{ background:{C.ACCENT_H}; }}"
        )

        value_lbl = QLabel(f"{slider.value() * 1000:,}")
        value_lbl.setFont(QFont(C.FCODE, 10, QFont.Weight.Bold))
        value_lbl.setMinimumWidth(58)
        value_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_lbl.setStyleSheet(
            f"color:{C.T0}; background:transparent; border:none;")

        slider.valueChanged.connect(
            lambda v, lbl=value_lbl: lbl.setText(f"{v * 1000:,}"))

        token_row.addWidget(token_lbl)
        token_row.addWidget(slider, 1)
        token_row.addWidget(value_lbl)
        vlay.addLayout(token_row)

        hint = QLabel(
            "출력 토큰을 설정하세요")
        hint.setFont(QFont(C.FUI, 8))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            f"color:{C.T3}; background:transparent; border:none;"
            "padding-top:4px;")
        vlay.addWidget(hint)
        vlay.addSpacing(16)

        # 버튼 행
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BG_CARD}; color:{C.T2};"
            f"  border:1px solid {C.BDR}; border-radius:8px;"
            f"  font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BG_HOVER}; color:{C.T0}; }}")
        cancel_btn.clicked.connect(dlg.reject)

        confirm_btn = QPushButton("✓  분석 시작")
        confirm_btn.setFixedHeight(38)
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:none; border-radius:8px;"
            f"  font-size:12px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:pressed {{ background:{C.BLUE_DK}; }}")
        confirm_btn.clicked.connect(dlg.accept)
        confirm_btn.setDefault(True)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        vlay.addLayout(btn_row)

        # 부모 창 중앙에 배치
        if mw.isVisible():
            geo = mw.geometry()
            dlg.move(
                geo.x() + (geo.width()  - dlg.width())  // 2,
                geo.y() + (geo.height() - dlg.height()) // 2,
            )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        chosen = slider.value() * 1000
        self._last_max_tokens = chosen   # 다음 호출 기본값으로 복원
        return chosen, bool(full_ctx_chk.isChecked())

    # ──────────────────────────────────────────────────────────
    #  ⑤ 잘림(truncation) 시 이어서 분석 흐름
    # ──────────────────────────────────────────────────────────
    def _prompt_continue(self):
        """잘림 감지 시 호출 — 토큰 재지정 다이얼로그 띄우고
        accept 면 ContinueVulnWorker 시작."""
        if not self._continuation_context:
            return
        new_max = self._show_truncation_dialog()
        if new_max is None:
            return
        self._start_continuation(new_max)

    def _show_truncation_dialog(self) -> int | None:
        """응답 한도 초과 시 토큰 재지정 다이얼로그.
        수락 시 새로운 max_tokens(int), 취소 시 None.
        이전 결과를 컨텍스트로 사용하므로 토큰 절약됨을 안내한다."""
        mw = self._mw
        dlg = QDialog(mw)
        dlg.setWindowTitle("응답 한도 초과 — 이어서 분석")
        dlg.setFixedSize(480, 380)
        dlg.setStyleSheet(
            f"QDialog {{ background:{C.BG_PANEL}; border:1px solid {C.BDR2}; }}")

        vlay = QVBoxLayout(dlg)
        vlay.setContentsMargins(32, 24, 32, 22)
        vlay.setSpacing(0)

        # 아이콘 + 타이틀
        icon_lbl = QLabel("⚠️")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 28))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background:transparent; border:none;")
        vlay.addWidget(icon_lbl)
        vlay.addSpacing(8)

        title = QLabel("응답이 토큰 한도에서 잘렸습니다")
        title.setFont(QFont(C.FUI, 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{C.T0}; background:transparent; border:none;")
        vlay.addWidget(title)
        vlay.addSpacing(8)

        desc = QLabel(
            f"이전 한도: <b>{self._last_max_tokens:,}</b> 토큰<br>"
            "토큰을 늘려 이어서 분석할 수 있습니다.<br>"
            "이전 결과를 컨텍스트로 사용해 토큰을 절약합니다.")
        desc.setFont(QFont(C.FUI, 9))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(
            f"color:{C.T2}; background:transparent; border:none;"
            "line-height:150%;")
        desc.setTextFormat(Qt.TextFormat.RichText)
        vlay.addWidget(desc)
        vlay.addSpacing(18)

        # 슬라이더 — 기본값은 이전 한도의 2배 (64K 캡)
        suggested_k = max(8, min(64, (self._last_max_tokens // 1000) * 2))
        token_row = QHBoxLayout()
        token_row.setSpacing(10)
        token_row.setContentsMargins(0, 0, 0, 0)

        token_lbl = QLabel("이어 분석 토큰")
        token_lbl.setFont(QFont(C.FUI, 9, QFont.Weight.DemiBold))
        token_lbl.setStyleSheet(
            f"color:{C.T1}; background:transparent; border:none;")
        token_lbl.setMinimumWidth(95)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(4, 64)
        slider.setValue(suggested_k)
        slider.setSingleStep(1)
        slider.setPageStep(4)
        slider.setCursor(Qt.CursorShape.PointingHandCursor)
        # 프로그램 메인 BLUE 통일 (기존 #2563EB/#1D4ED8 진한 블루였음)
        slider.setStyleSheet(
            "QSlider::groove:horizontal {"
            "  background:#CBD5E1; height:6px; border-radius:3px; }"
            f"QSlider::sub-page:horizontal {{"
            f"  background:{C.BLUE}; height:6px; border-radius:3px; }}"
            f"QSlider::handle:horizontal {{"
            f"  background:{C.BLUE_DK}; border:2px solid #FFFFFF;"
            f"  width:14px; height:14px; margin:-5px 0; border-radius:9px; }}"
            f"QSlider::handle:horizontal:hover {{ background:{C.ACCENT_H}; }}"
        )

        value_lbl = QLabel(f"{slider.value() * 1000:,}")
        value_lbl.setFont(QFont(C.FCODE, 10, QFont.Weight.Bold))
        value_lbl.setMinimumWidth(58)
        value_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_lbl.setStyleSheet(
            f"color:{C.T0}; background:transparent; border:none;")

        slider.valueChanged.connect(
            lambda v, lbl=value_lbl: lbl.setText(f"{v * 1000:,}"))

        token_row.addWidget(token_lbl)
        token_row.addWidget(slider, 1)
        token_row.addWidget(value_lbl)
        vlay.addLayout(token_row)

        hint = QLabel(
            "Claude 가 잘린 지점부터 이어 작성합니다")
        hint.setFont(QFont(C.FUI, 8))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            f"color:{C.T3}; background:transparent; border:none;"
            "padding-top:4px;")
        vlay.addWidget(hint)
        vlay.addSpacing(16)

        # 버튼
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BG_CARD}; color:{C.T2};"
            f"  border:1px solid {C.BDR}; border-radius:8px;"
            f"  font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BG_HOVER}; color:{C.T0}; }}")
        cancel_btn.clicked.connect(dlg.reject)

        confirm_btn = QPushButton("▶  이어서 분석")
        confirm_btn.setFixedHeight(38)
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:none; border-radius:8px;"
            f"  font-size:12px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:pressed {{ background:{C.BLUE_DK}; }}")
        confirm_btn.clicked.connect(dlg.accept)
        confirm_btn.setDefault(True)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        vlay.addLayout(btn_row)

        # 부모 창 중앙에 배치
        if mw.isVisible():
            geo = mw.geometry()
            dlg.move(
                geo.x() + (geo.width()  - dlg.width())  // 2,
                geo.y() + (geo.height() - dlg.height()) // 2,
            )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        chosen = slider.value() * 1000
        self._last_max_tokens = chosen
        return chosen

    def _start_continuation(self, max_tokens: int):
        """ContinueVulnWorker 를 새 QThread 에 띄워 이어서 분석 시작."""
        if not self._continuation_context:
            return
        ctx = self._continuation_context
        self._continue_thread = QThread()
        self._continue_worker = ContinueVulnWorker(
            ctx["system_prompt"],
            ctx["user_body"],
            ctx["raw_text"],
            max_tokens,
        )
        self._continue_worker.moveToThread(self._continue_thread)
        self._continue_thread.started.connect(self._continue_worker.run)
        self._continue_worker.done.connect(self._on_continue_done)
        self._continue_worker.error.connect(self._on_error)
        self._continue_worker.cancelled.connect(self._on_continue_cancelled)
        self._continue_worker.done.connect(self._continue_thread.quit)
        self._continue_worker.error.connect(self._continue_thread.quit)
        self._continue_worker.cancelled.connect(self._continue_thread.quit)
        # 스레드 종료 후 워커/스레드 객체 deleteLater — gc 타이밍 충돌 방지
        self._continue_thread.finished.connect(self._continue_worker.deleteLater)
        self._continue_thread.finished.connect(self._continue_thread.deleteLater)

        self._mw._input.set_ai_running(True)
        self._mw._sb.showMessage("🤖  이어서 분석 중...")
        self._continue_thread.start()

    def _on_continue_done(self, text: str, truncated: bool):
        """ContinueVulnWorker 완료 슬롯. 또 잘리면 컨텍스트 갱신 후 재팝업."""
        mw = self._mw
        mw._result.set_vuln(text)
        mw._input.set_ai_running(False)

        if truncated:
            mw._sb.showMessage(
                "⚠  이어서 분석한 결과도 한도에서 잘렸습니다 — 토큰을 더 늘려 재시도하세요.")
            # chained continuation 컨텍스트 갱신 (raw text 새로고침)
            if self._continue_worker is not None and self._continuation_context:
                self._continuation_context["raw_text"] = (
                    self._continue_worker.last_raw_text)
            QTimer.singleShot(150, self._prompt_continue)
            return

        mw._sb.showMessage(
            "✅  이어서 분석 완료!  탭을 전환하여 결과를 확인하고 저장하세요.")
        QTimer.singleShot(150, self._show_complete_dialog)

    def _on_continue_cancelled(self):
        """ContinueVulnWorker 취소 슬롯."""
        self._mw._input.set_ai_running(False)
        self._mw._sb.showMessage("⏹  이어서 분석이 중단되었습니다.")

    # ──────────────────────────────────────────────────────────
    #  ⑥ 분석 중단 확인 다이얼로그
    # ──────────────────────────────────────────────────────────
    def _show_complete_dialog(self):
        """AI 분석 완료 알림 다이얼로그. '확인하기' 클릭 시 변경점 요약 탭으로 이동."""
        mw = self._mw
        dlg = QDialog(mw)
        dlg.setWindowTitle("분석 완료")
        dlg.setFixedSize(400, 230)
        dlg.setStyleSheet(
            f"QDialog {{ background:{C.BG_PANEL}; border:1px solid {C.BDR2}; }}")

        vlay = QVBoxLayout(dlg)
        vlay.setContentsMargins(32, 26, 32, 22)
        vlay.setSpacing(0)

        # 아이콘
        icon_lbl = QLabel("✅")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 26))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background:transparent; border:none;")
        vlay.addWidget(icon_lbl)
        vlay.addSpacing(8)

        # 타이틀
        title = QLabel("AI 분석이 완료되었습니다")
        title.setFont(QFont(C.FUI, 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{C.T0}; background:transparent; border:none;")
        vlay.addWidget(title)
        vlay.addSpacing(6)

        # 설명
        desc = QLabel("변경점 요약과 취약점 분석 결과를\n확인하고 저장하세요.")
        desc.setFont(QFont(C.FUI, 9))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(
            f"color:{C.T3}; background:transparent; border:none;")
        vlay.addWidget(desc)
        vlay.addSpacing(20)

        # 버튼 행
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        close_btn = QPushButton("닫기")
        close_btn.setFixedHeight(38)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BG_CARD}; color:{C.T2};"
            f"  border:1px solid {C.BDR}; border-radius:8px;"
            f"  font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BG_HOVER}; color:{C.T0}; }}")
        close_btn.clicked.connect(dlg.reject)

        confirm_btn = QPushButton("확인하기")
        confirm_btn.setFixedHeight(38)
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BLUE}; color:#FFFFFF;"
            f"  border:none; border-radius:8px;"
            f"  font-size:12px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{C.ACCENT_H}; }}"
            f"QPushButton:pressed {{ background:{C.BLUE_DK}; }}")
        confirm_btn.setDefault(True)
        confirm_btn.clicked.connect(dlg.accept)

        btn_row.addWidget(close_btn)
        btn_row.addWidget(confirm_btn)
        vlay.addLayout(btn_row)

        # 부모 창 중앙 배치
        if mw.isVisible():
            geo = mw.geometry()
            dlg.move(
                geo.x() + (geo.width()  - dlg.width())  // 2,
                geo.y() + (geo.height() - dlg.height()) // 2,
            )

        if dlg.exec() == QDialog.DialogCode.Accepted:
            mw._result._switch("summary")

    def _show_stop_confirm_dialog(self) -> bool:
        """분석 중단 확인 다이얼로그. True 면 중단 진행, False 면 계속.
        기본 포커스는 "계속 진행" 으로 두어 실수 클릭으로 작업이 사라지는 것을 방지."""
        mw = self._mw
        dlg = QDialog(mw)
        dlg.setWindowTitle("분석 중단 확인")
        dlg.setFixedSize(400, 230)
        dlg.setStyleSheet(
            f"QDialog {{ background:{C.BG_PANEL}; border:1px solid {C.BDR2}; }}")

        vlay = QVBoxLayout(dlg)
        vlay.setContentsMargins(32, 26, 32, 22)
        vlay.setSpacing(0)

        # 아이콘
        icon_lbl = QLabel("⏹")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 26))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background:transparent; border:none;")
        vlay.addWidget(icon_lbl)
        vlay.addSpacing(8)

        # 타이틀
        title = QLabel("분석을 중단하시겠습니까?")
        title.setFont(QFont(C.FUI, 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{C.T0}; background:transparent; border:none;")
        vlay.addWidget(title)
        vlay.addSpacing(6)

        # 설명
        desc = QLabel("진행 중인 작업이 취소되며\n현재까지의 분석 결과가 손실됩니다.")
        desc.setFont(QFont(C.FUI, 9))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(
            f"color:{C.T3}; background:transparent; border:none;"
            "line-height:150%;")
        vlay.addWidget(desc)
        vlay.addSpacing(20)

        # 버튼 행
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        keep_btn = QPushButton("계속 진행")
        keep_btn.setFixedHeight(38)
        keep_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        keep_btn.setStyleSheet(
            f"QPushButton {{ background:{C.BG_CARD}; color:{C.T2};"
            f"  border:1px solid {C.BDR}; border-radius:8px;"
            f"  font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C.BG_HOVER}; color:{C.T0}; }}")
        keep_btn.clicked.connect(dlg.reject)
        keep_btn.setDefault(True)   # 안전한 옵션을 기본 포커스로

        stop_btn = QPushButton("⏹  분석 중단")
        stop_btn.setFixedHeight(38)
        stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stop_btn.setStyleSheet(
            "QPushButton { background:#DC2626; color:#FFFFFF;"
            "  border:none; border-radius:8px;"
            "  font-size:12px; font-weight:700; }"
            "QPushButton:hover { background:#B91C1C; }"
            "QPushButton:pressed { background:#991B1B; }")
        stop_btn.clicked.connect(dlg.accept)

        btn_row.addWidget(keep_btn)
        btn_row.addWidget(stop_btn)
        vlay.addLayout(btn_row)

        # 부모 창 중앙 배치
        if mw.isVisible():
            geo = mw.geometry()
            dlg.move(
                geo.x() + (geo.width()  - dlg.width())  // 2,
                geo.y() + (geo.height() - dlg.height()) // 2,
            )
        return dlg.exec() == QDialog.DialogCode.Accepted

    # ──────────────────────────────────────────────────────────
    #  ⑦ [대화형AI DISABLED] 대화형 Q&A 비활성화 블록
    #  복구 시: 아래 코멘트 해제 + self._sb / self._result 참조를
    #          self._mw._sb / self._mw._result 로 변경, QaWorker import 추가
    # ──────────────────────────────────────────────────────────
    # ★ [대화형AI DISABLED] 대화형 AI 채팅 ─────────────────────
    # 아래 메서드 3개(_on_qa_submit, _on_qa_answer, _on_qa_error)와
    # 정적 메서드 2개(_replace_vuln_section, _append_mod_log),
    # 요약 탭 채팅 메서드 3개(_on_summary_qa_submit, _on_summary_qa_answer, _on_summary_qa_error)
    # 를 주석 해제하면 기능 복구 가능
    #
    # def _on_qa_submit(self, question: str):
    #     if not self._last_vuln_text:
    #         return
    #     self._sb.showMessage("💬  AI가 분석 중...")
    #     self._qa_thread = QThread()
    #     self._qa_worker = QaWorker(
    #         self._last_diff_code,
    #         self._last_vuln_text,
    #         question,
    #         list(self._qa_history))
    #     self._qa_worker.moveToThread(self._qa_thread)
    #     self._qa_thread.started.connect(self._qa_worker.run)
    #     self._qa_worker.answer_done.connect(
    #         lambda ans, q=question: self._on_qa_answer(q, ans))
    #     self._qa_worker.error.connect(self._on_qa_error)
    #     self._qa_worker.answer_done.connect(self._qa_thread.quit)
    #     self._qa_worker.error.connect(self._qa_thread.quit)
    #     self._qa_thread.start()
    #
    # def _on_qa_answer(self, question: str, raw: str):
    #     import re
    #
    #     def _tag(text: str, tag: str) -> str:
    #         m = re.search(rf'<{tag}>(.*?)</{tag}>', text, re.DOTALL)
    #         return m.group(1).strip() if m else ""
    #
    #     reply   = _tag(raw, "reply") or raw
    #     sec_raw = _tag(raw, "section_update")
    #     log_raw = _tag(raw, "mod_log")
    #
    #     # 히스토리에는 reply만 저장
    #     self._qa_history.append({"q": question, "a": reply})
    #     self._result.add_qa_answer(question, reply)
    #
    #     updated = False
    #
    #     # ── 섹션 업데이트 ──────────────────────────────────────
    #     if sec_raw and sec_raw.upper() != "NONE":
    #         id_m = re.search(r'id:\s*([HML]-\d+)', sec_raw, re.IGNORECASE)
    #         # content: 이후 전체 텍스트를 섹션 내용으로 사용
    #         cont_m = re.search(r'content:\s*\n(.*)', sec_raw, re.DOTALL)
    #         if id_m and cont_m:
    #             sec_id  = id_m.group(1).strip()
    #             new_sec = cont_m.group(1).strip()
    #             self._last_vuln_text = self._replace_vuln_section(
    #                 self._last_vuln_text, sec_id, new_sec)
    #             updated = True
    #
    #     # ── 수정 이력 추가 ─────────────────────────────────────
    #     if log_raw and log_raw.upper() != "NONE":
    #         self._last_vuln_text = self._append_mod_log(
    #             self._last_vuln_text, log_raw.strip())
    #         updated = True
    #
    #     if updated:
    #         self._result.update_vuln_text(self._last_vuln_text)
    #
    #     self._sb.showMessage("✅  AI 답변 완료")
    #
    # @staticmethod
    # def _replace_vuln_section(full: str, sec_id: str, new_content: str) -> str:
    #     """취약점 분석 텍스트에서 특정 섹션(예: H-1)을 교체."""
    #     import re
    #     pattern = rf'(### {re.escape(sec_id)}\..+?)(?=\n### [HML]-\d+\.|\n## |\Z)'
    #     m = re.search(pattern, full, re.DOTALL)
    #     if m:
    #         return full[:m.start()] + new_content + full[m.end():]
    #     return full
    #
    # @staticmethod
    # def _append_mod_log(full: str, log_line: str) -> str:
    #     """리포트 맨 아래 수정 이력 섹션에 행 추가."""
    #     header = "\n\n---\n\n## 📋 분석 수정 이력\n\n| 항목 | 원본 AI 판단 | 개발자 설명 | AI 재평가 |\n|------|------------|------------|----------|\n"
    #     if "## 📋 분석 수정 이력" in full:
    #         return full + f"| {log_line} |\n"
    #     return full + header + f"| {log_line} |\n"
    #
    # def _on_qa_error(self, msg: str):
    #     self._result.add_qa_answer("(오류)", f"❌ 오류: {msg}")
    #     self._sb.showMessage(f"❌  채팅 오류: {msg[:90]}")
    #
    # # ★ 요약 탭 채팅 ──────────────────────────────────────────
    # def _on_summary_qa_submit(self, question: str):
    #     if not self._last_summary_text:
    #         return
    #     self._sb.showMessage("💬  AI가 분석 중...")
    #     self._qa_thread = QThread()
    #     self._qa_worker = QaWorker(
    #         self._last_diff_code,
    #         self._last_summary_text,    # 요약 텍스트를 컨텍스트로 사용
    #         question,
    #         list(self._sum_qa_history))
    #     self._qa_worker.moveToThread(self._qa_thread)
    #     self._qa_thread.started.connect(self._qa_worker.run)
    #     self._qa_worker.answer_done.connect(
    #         lambda ans, q=question: self._on_summary_qa_answer(q, ans))
    #     self._qa_worker.error.connect(self._on_summary_qa_error)
    #     self._qa_worker.answer_done.connect(self._qa_thread.quit)
    #     self._qa_worker.error.connect(self._qa_thread.quit)
    #     self._qa_thread.start()
    #
    # def _on_summary_qa_answer(self, question: str, raw: str):
    #     import re
    #
    #     def _tag(text, tag):
    #         m = re.search(rf'<{tag}>(.*?)</{tag}>', text, re.DOTALL)
    #         return m.group(1).strip() if m else ""
    #
    #     reply = _tag(raw, "reply") or raw
    #     self._sum_qa_history.append({"q": question, "a": reply})
    #     self._result.add_summary_qa_answer(question, reply)
    #     self._sb.showMessage("✅  AI 답변 완료")
    #
    # def _on_summary_qa_error(self, msg: str):
    #     self._result.add_summary_qa_answer("(오류)", f"❌ 오류: {msg}")
    #     self._sb.showMessage(f"❌  채팅 오류: {msg[:90]}")

