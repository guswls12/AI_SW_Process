"""api.py — Codebeamer REST API 클라이언트 (CbFetcher).

세션 로그인(폼) → REST API 호출 (조회/생성/코멘트/첨부) → md 생성.
Qt 의존 없음 — 순수 requests 기반.
"""

import os
import datetime

try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    requests = None

from .config import CB_MD_FILE
from .text import _clean_text


# ══════════════════════════════════════════════════════════════
#  CbFetcher — 세션 로그인 + REST API 호출 + md 생성
# ══════════════════════════════════════════════════════════════
class CbFetcher:
    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self._session = None

    # ── 세션 로그인 ───────────────────────────────────────────
    def _get_session(self):
        if requests is None:
            raise RuntimeError(
                "requests 패키지가 없습니다.\n"
                "터미널에서: pip install requests")
        if self._session is not None:
            return self._session

        session = requests.Session()
        session.verify  = False
        session.headers.update({"Accept": "application/json"})

        # 폼 로그인 — 세션 쿠키(JSESSIONID) 확보
        # Basic Auth 는 이 CB 인스턴스에서 허용되지 않으므로 세션 쿠키 방식만 사용
        try:
            resp = session.post(
                f"{self.base_url}/login.spr",
                data={"user": self.username, "password": self.password,
                      "targetURL": ""},
                timeout=8,
                allow_redirects=True,
            )
            # login.spr 로 돌아오면 로그인 실패 (permissionDenied 는 웹 UI 권한 문제로 API 와 무관)
            if "login.spr" in resp.url:
                raise RuntimeError(
                    "로그인 실패 — 아이디/비밀번호를 확인해주세요.")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"서버 연결 실패: {e}")

        self._session = session
        return session

    # ── 내부 GET ──────────────────────────────────────────────
    def _get(self, endpoint: str, params: dict = None):
        session = self._get_session()
        # v3 API → legacy REST API 순으로 시도
        endpoints = [endpoint]
        if endpoint.startswith("/api/v3/trackers/") and endpoint.endswith("/items"):
            tid = endpoint.split("/")[4]
            endpoints += [f"/rest/tracker/{tid}/items",
                          f"/rest/trackers/{tid}/items"]

        last_resp = None
        for ep in endpoints:
            try:
                resp = session.get(
                    f"{self.base_url}{ep}",
                    params=params or {},
                    timeout=8,
                )
                last_resp = resp
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 401:
                    break   # 인증 오류는 더 시도해도 의미 없음
                # 404/403/500 등 → 다음 엔드포인트 시도
            except Exception:
                continue
        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError("서버에서 데이터를 가져올 수 없습니다.")

    # ── 내부 POST (application/json) ─────────────────────────
    def _post_json(self, endpoint: str, payload: dict, timeout: int = 30) -> dict:
        """JSON POST 헬퍼. 200/201 응답을 dict 로 반환, 그 외엔 RuntimeError.
        에러 메시지에 HTTP 상태코드 + 응답 본문 일부를 포함시켜 디버깅 도움."""
        return self._request_json("POST", endpoint, payload, timeout)

    # ── 내부 generic JSON 요청 (POST/PUT/PATCH) ──────────────
    def _request_json(self, method: str, endpoint: str, payload: dict,
                      timeout: int = 30) -> dict:
        """JSON 본문 요청 헬퍼 — method 에 따라 POST/PUT/PATCH 선택.
        2xx 응답을 dict 로 반환, 그 외엔 HTTP 상태코드 + 본문 일부 포함 RuntimeError."""
        session = self._get_session()
        method_u = method.upper()
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json"}
        try:
            if method_u == "POST":
                resp = session.post(url, json=payload, headers=headers, timeout=timeout)
            elif method_u == "PUT":
                resp = session.put(url, json=payload, headers=headers, timeout=timeout)
            elif method_u == "PATCH":
                resp = session.patch(url, json=payload, headers=headers, timeout=timeout)
            else:
                raise RuntimeError(f"지원하지 않는 메서드: {method}")
        except Exception as e:
            raise RuntimeError(f"네트워크 오류: {e}")
        if 200 <= resp.status_code < 300:
            try:
                return resp.json()
            except Exception:
                return {}
        body = (resp.text or "")[:300].replace("\n", " ")
        raise RuntimeError(f"HTTP {resp.status_code} — {body}")

    # ── 새 이슈 생성 ──────────────────────────────────────────
    def create_item(self, tracker_id: str, summary: str, description: str,
                    description_format: str = "Html",
                    parent_item_id: str = "",
                    custom_fields: list = None) -> dict:
        """트래커에 새 이슈 생성. 반환 dict 에 'id' 포함.
        description_format: 'Html' (기본, 본문이 HTML 인 경우) / 'PlainText' / 'Wiki'.
        parent_item_id   : 비어있지 않으면 **생성 시점에** 상위 항목과 함께 만든다.
                           (CB 웹 UI 가 /tracker/{tid}/create?parent_id={pid} 패턴을
                            쓰므로 동일하게 query/payload 변형들을 우선 시도하고,
                            모두 실패할 때만 생성 후 set_parent 폴백을 탄다.
                            이 CB 인스턴스는 PATCH/PUT 미지원이라 set_parent 폴백은
                            대부분 실패하므로 생성 시점 연결이 사실상 유일한 길.)
        custom_fields    : CB v3 형식의 customFields 배열을 그대로 payload 에 포함.
                           (예: [{"name": "수평전개", "values": [{"id": 123}]}])
                           생성 시점에 박지 않으면 PATCH/PUT 미지원이라 사후 채울 길이
                           거의 없으므로, 호출 측에서 미리 준비해서 전달한다.
        지정 포맷이 거부되면 점진적으로 폴백:
          1) 지정 포맷 → 2) PlainText → 3) descriptionFormat 필드 제거
        custom_fields 가 거부되면 한 번 더 빼고 재시도 (linking 실패해도 본문은 살림).
        """
        import sys
        tid = str(tracker_id).strip()
        if not tid:
            raise RuntimeError("트래커 ID가 비어있습니다.")
        base_endpoint = f"/api/v3/trackers/{tid}/items"
        base_payload = {"name": summary, "description": description}
        if custom_fields:
            base_payload["customFields"] = custom_fields

        # 시도할 포맷 순서 — 지정 포맷 우선, 이후 안전한 PlainText, 마지막은 필드 생략
        fmt_chain = []
        if description_format:
            fmt_chain.append(description_format)
        if "PlainText" not in fmt_chain:
            fmt_chain.append("PlainText")
        fmt_chain.append(None)  # descriptionFormat 필드 제거

        pid = str(parent_item_id or "").strip()
        pid_v = None
        if pid:
            try:
                pid_v = int(pid)
            except ValueError:
                pid_v = pid

        # ── 생성 전략 빌드 ────────────────────────────────────
        # 부모가 있으면: 웹 UI 와 동일한 query 변형을 최우선, 다음 payload 변형.
        # 부모가 없으면: 단순 base_endpoint 한 번만.
        # 각 항목 = (endpoint, extra_payload, has_parent)
        if pid:
            strategies = [
                # query parameter 변형 (CB 웹 UI 가 ?parent_id= 사용)
                (f"{base_endpoint}?parent_id={pid}",      None, True),
                (f"{base_endpoint}?parentItemId={pid}",   None, True),
                (f"{base_endpoint}?parentId={pid}",       None, True),
                # payload 변형 (일부 CB 버전 지원)
                (base_endpoint, {"parent": {"id": pid_v}},                True),
                (base_endpoint, {"parentItemId": pid_v},                  True),
                (base_endpoint, {"parent": pid_v},                        True),
            ]
        else:
            strategies = [(base_endpoint, None, False)]

        # ── 생성 시도 (첫 성공에서 멈춤 — 중복 이슈 방지) ─────
        last_err = None
        created = None
        used_strategy_has_parent = False
        for s_idx, (ep, extra, has_parent) in enumerate(strategies, 1):
            for fmt in fmt_chain:
                payload = dict(base_payload)
                if extra:
                    payload.update(extra)
                if fmt is not None:
                    payload["descriptionFormat"] = fmt
                try:
                    print(
                        f"[CREATE-ITEM {s_idx}/{len(strategies)}] POST {ep} "
                        f"fmt={fmt} extra={extra}",
                        file=sys.stderr, flush=True)
                    created = self._post_json(ep, payload)
                    used_strategy_has_parent = has_parent
                    break
                except RuntimeError as e:
                    last_err = e
                    print(f"  → ✗ {e}", file=sys.stderr, flush=True)
                    if "HTTP 400" not in str(e):
                        # 400 외 에러 (404/500 등) 는 이 전략 자체가 무효 → 다음 전략으로
                        break
            if created is not None:
                print(
                    f"  ✓ 생성됨 (전략 {s_idx}, has_parent={has_parent}): "
                    f"id={created.get('id') or created.get('itemId')}",
                    file=sys.stderr, flush=True)
                break

        # ── 폴백 1: customFields type 에러면 다른 후보 클래스명으로 자동 재시도 ──
        # 'Class cannot be resolved by type: X' 에러는 CB 가 type 값을 모른다는 뜻.
        # _resolve_field_payload 의 추정 클래스가 틀린 경우, 다른 흔한 CB v3
        # reference value 클래스명으로 바꿔서 재시도.
        if (created is None and custom_fields and last_err
                and "Class cannot be resolved by type" in str(last_err)):
            import re as _re
            # 마지막 에러에서 거부된 클래스명 추출
            m = _re.search(
                r"Class cannot be resolved by type:\s*([A-Za-z0-9_]+)",
                str(last_err))
            failed_class = m.group(1) if m else ""
            # 흔한 CB v3 value 클래스명 후보 — 첫 성공에서 멈춤
            # reference → text → URL 순으로 시도 (마지막은 ID/URL 을 텍스트로
            # 저장이라도 되게 — 빈 상태보단 나음)
            REF_TYPE_CANDIDATES = [
                # 참조 계열
                ("TrackerItemReferenceFieldValue",  "ref"),
                ("TrackerReferenceFieldValue",      "ref"),
                ("ItemReferenceFieldValue",         "ref"),
                ("ReferenceFieldValue",             "ref"),
                ("TableFieldValue",                 "ref"),
                ("ChoiceFieldValue",                "ref"),
                # 텍스트/URL 폴백 — 참조가 모두 거부되면 ID/URL 을 문자열로
                ("UrlFieldValue",                   "url"),
                ("WikiTextFieldValue",              "wiki"),
                ("TextFieldValue",                  "text"),
            ]
            base_url_for_link = self.base_url
            tried_classes = [failed_class] if failed_class else []
            for cand, kind in REF_TYPE_CANDIDATES:
                if cand in tried_classes:
                    continue
                # customFields 의 type 값을 cand 로 치환 (값 모양도 kind 에 맞춰 조정)
                swapped_cfs = []
                for cf in custom_fields:
                    if not isinstance(cf, dict):
                        swapped_cfs.append(cf); continue
                    new_cf = dict(cf)
                    if (new_cf.get("type") == failed_class
                            or (failed_class and failed_class in
                                str(new_cf.get("type") or ""))):
                        new_cf["type"] = cand
                        # text/url/wiki 계열은 값 모양도 바꿔야 함
                        if kind in ("text", "wiki", "url"):
                            # values 에서 id 추출 후 URL 문자열로
                            existing_vals = new_cf.get("values") or []
                            extracted_id = ""
                            if existing_vals and isinstance(existing_vals[0], dict):
                                extracted_id = str(
                                    existing_vals[0].get("id") or "")
                            if not extracted_id:
                                extracted_id = str(new_cf.get("value") or "")
                            link_url = (
                                f"{base_url_for_link}/issue/{extracted_id}"
                                if extracted_id else "")
                            # 'values' 제거하고 value 에 문자열
                            new_cf.pop("values", None)
                            if kind == "wiki" and extracted_id:
                                new_cf["value"] = f"[#{extracted_id}]({link_url})"
                            else:
                                new_cf["value"] = link_url or extracted_id
                    swapped_cfs.append(new_cf)
                base_payload_swap = dict(base_payload)
                base_payload_swap["customFields"] = swapped_cfs
                print(
                    f"[CREATE-ITEM] type 재시도: "
                    f"{failed_class!r} → {cand!r} (kind={kind})",
                    file=sys.stderr, flush=True)
                tried_classes.append(cand)
                for s_idx, (ep, extra, has_parent) in enumerate(strategies, 1):
                    payload = dict(base_payload_swap)
                    if extra:
                        payload.update(extra)
                    payload["descriptionFormat"] = description_format or "Html"
                    try:
                        created = self._post_json(ep, payload)
                        used_strategy_has_parent = has_parent
                        # 폴백 종류를 응답에 표시 (워커가 사용자에 안내)
                        created["_cf_value_kind"] = kind
                        created["_cf_value_class"] = cand
                        print(
                            f"  ✓ type={cand!r} (kind={kind}) 으로 생성 성공: "
                            f"id={created.get('id') or created.get('itemId')}",
                            file=sys.stderr, flush=True)
                        break
                    except RuntimeError as e:
                        last_err = e
                        if "Class cannot be resolved" in str(e):
                            m2 = _re.search(
                                r"Class cannot be resolved by type:\s*([A-Za-z0-9_]+)",
                                str(e))
                            if m2 and m2.group(1) not in tried_classes:
                                tried_classes.append(m2.group(1))
                            break
                        # 그 외 400 에러면 같은 cand 다른 strategy 로 계속
                        if "HTTP 400" not in str(e):
                            break
                if created is not None:
                    break

        # ── 폴백 2: customFields 자체를 빼고 재시도 (linking 포기) ──
        if created is None and custom_fields:
            print(
                "[CREATE-ITEM] customFields 포함 시도 모두 실패 — "
                "customFields 제거 후 재시도",
                file=sys.stderr, flush=True)
            base_payload_no_cf = {k: v for k, v in base_payload.items()
                                  if k != "customFields"}
            for s_idx, (ep, extra, has_parent) in enumerate(strategies, 1):
                for fmt in fmt_chain:
                    payload = dict(base_payload_no_cf)
                    if extra:
                        payload.update(extra)
                    if fmt is not None:
                        payload["descriptionFormat"] = fmt
                    try:
                        created = self._post_json(ep, payload)
                        used_strategy_has_parent = has_parent
                        created["custom_fields_dropped"] = True
                        print(
                            f"  ✓ customFields 제거 폴백 성공: "
                            f"id={created.get('id') or created.get('itemId')}",
                            file=sys.stderr, flush=True)
                        break
                    except RuntimeError as e:
                        last_err = e
                        if "HTTP 400" not in str(e):
                            break
                if created is not None:
                    break

        if created is None:
            raise last_err  # 모든 전략·포맷 실패

        # ── 상위 연결 검증 / set_parent 폴백 ──────────────────
        if pid:
            new_id = str(created.get("id") or created.get("itemId") or "")
            parent_set = False
            if used_strategy_has_parent and new_id:
                # 생성 시점에 부모 전달했으면 실제로 붙었는지 검증
                # (CB 가 알 수 없는 query/필드를 silent 무시할 수 있음)
                parent_set = self._check_parent_set(new_id, pid_v)
                if parent_set:
                    print(
                        f"  ✓ 상위 #{pid} 생성 시점 연결 확인됨",
                        file=sys.stderr, flush=True)
                else:
                    print(
                        f"  ⚠ 생성됐지만 상위 #{pid} 미적용 — set_parent 폴백 시도",
                        file=sys.stderr, flush=True)

            if not parent_set and new_id:
                # 폴백: 생성 후 set_parent (대부분 PATCH/PUT 미지원으로 실패할 것)
                try:
                    self.set_parent(new_id, pid)
                    parent_set = True
                except Exception as e:
                    print(
                        f"[CREATE-ITEM] 상위 #{pid} set_parent 폴백 실패 (계속 진행): {e}",
                        file=sys.stderr, flush=True)
                    created["parent_link_error"] = str(e)[:200]

            created["parent_link_ok"] = parent_set
        return created

    # ── 상위 항목 적용 검증 ───────────────────────────────────
    def _check_parent_set(self, item_id: str, expected_parent) -> bool:
        """fetch_item_detail 로 가져와서 parent/subjects/ancestors 중 하나라도
        expected_parent 와 일치하면 True. 어떤 필드를 쓰는지는 CB 버전마다 다름."""
        import sys
        try:
            detail = self.fetch_item_detail(str(item_id))
            pf = detail.get("parent")
            pf_id = pf.get("id") if isinstance(pf, dict) else None
            if pf_id is None and isinstance(detail.get("subjects"), list):
                subs = detail["subjects"]
                if subs and isinstance(subs[0], dict):
                    pf_id = subs[0].get("id")
            if pf_id is None and isinstance(detail.get("ancestors"), list):
                anc = detail["ancestors"]
                if anc and isinstance(anc[0], dict):
                    pf_id = anc[0].get("id")
            return str(pf_id) == str(expected_parent)
        except Exception as ve:
            print(f"  → verify 실패(무시): {ve}",
                  file=sys.stderr, flush=True)
            return False

    # ── 이슈에 상위 항목 설정 ─────────────────────────────────
    def set_parent(self, item_id: str, parent_id: str) -> dict:
        """기존 이슈에 상위 항목을 설정한다. CB 버전마다 schema/허용 메서드가
        달라 여러 (방법, 엔드포인트, payload) 조합을 순차 시도하며, 각 시도
        후 fetch_item_detail 로 실제 적용 여부를 검증한다.
        모든 시도의 결과는 stderr 에 로깅됨.

        이 CB 인스턴스는 PATCH/PUT 미지원이라 POST 위주의 변형을 우선 배치.
        """
        import sys
        iid = str(item_id).strip()
        pid = str(parent_id).strip()
        if not iid or not pid:
            raise RuntimeError("이슈 ID 또는 상위 ID가 비어있습니다.")
        try:
            pid_v = int(pid)
        except ValueError:
            pid_v = pid

        # 검증 헬퍼 — 시도 후 실제로 parent 가 붙었는지 확인
        def _verify_parent_set() -> bool:
            try:
                detail = self.fetch_item_detail(iid)
                pf = detail.get("parent")
                pf_id = pf.get("id") if isinstance(pf, dict) else None
                if pf_id is None and isinstance(detail.get("subjects"), list):
                    subs = detail["subjects"]
                    if subs and isinstance(subs[0], dict):
                        pf_id = subs[0].get("id")
                if pf_id is None and isinstance(detail.get("ancestors"), list):
                    anc = detail["ancestors"]
                    if anc and isinstance(anc[0], dict):
                        pf_id = anc[0].get("id")
                print(
                    f"  → verify: parent={pf}, subjects/ancestors={pf_id}",
                    file=sys.stderr, flush=True)
                return str(pf_id) == str(pid_v)
            except Exception as ve:
                print(f"  → verify 실패(무시): {ve}",
                      file=sys.stderr, flush=True)
                return False

        # JSON POST 변형들 (이 CB 는 PATCH/PUT 미지원이라 POST 위주)
        json_attempts = [
            # CB v3 워크플로우 오퍼레이션 (필드 갱신을 자기-전이로 수행)
            ("POST", f"/api/v3/items/{iid}/workflowOperation",
             {"fieldValues": [{"fieldId": -3,
                               "type": "TrackerItemReferenceFieldValue",
                               "values": [{"id": pid_v,
                                           "type": "TrackerItemReference"}]}]}),
            ("POST", f"/api/v3/items/{iid}/workflowOperations",
             {"fieldValues": [{"fieldId": -3,
                               "type": "TrackerItemReferenceFieldValue",
                               "values": [{"id": pid_v,
                                           "type": "TrackerItemReference"}]}]}),
            # 일부 CB 는 POST 를 PATCH 로 처리
            ("POST", f"/api/v3/items/{iid}",
             {"parent": {"id": pid_v}}),
            ("POST", f"/api/v3/items/{iid}",
             {"subjects": [{"id": pid_v}]}),
            ("POST", f"/api/v3/items/{iid}",
             {"fieldValues": [{"fieldId": -3,
                               "type": "TrackerItemReferenceFieldValue",
                               "values": [{"id": pid_v,
                                           "type": "TrackerItemReference"}]}]}),
            # upstream relation 엔드포인트
            ("POST", f"/api/v3/items/{iid}/upstreamReferences",
             {"item": {"id": pid_v}}),
            ("POST", f"/api/v3/items/{iid}/upstreamReferences",
             {"id": pid_v}),
        ]
        for idx, (method, ep, payload) in enumerate(json_attempts, 1):
            print(
                f"[SET-PARENT JSON {idx}/{len(json_attempts)}] {method} {ep} "
                f"payload={payload}",
                file=sys.stderr, flush=True)
            try:
                resp = self._request_json(method, ep, payload)
                print(f"  → 2xx: {str(resp)[:160]}",
                      file=sys.stderr, flush=True)
                if _verify_parent_set():
                    print(f"  ✓ 상위 #{pid_v} 연결 확인됨!",
                          file=sys.stderr, flush=True)
                    return resp
            except RuntimeError as e:
                print(f"  → ✗ {e}", file=sys.stderr, flush=True)
                err_str = str(e)
                if not any(c in err_str for c in
                           ("HTTP 400", "HTTP 404", "HTTP 405", "HTTP 422", "HTTP 500")):
                    raise

        # 폼 인코딩 legacy REST 변형 (구버전 CB 호환)
        form_attempts = [
            # 가장 일반적인 legacy quick edit
            ("/rest/itemQuickEdit", {"id": iid, "parent": pid_v}),
            ("/rest/itemQuickEdit", {"itemId": iid, "parentId": pid_v}),
            # alternative paths some CBs use
            ("/rest/item/edit",     {"id": iid, "parent": pid_v}),
        ]
        session = self._get_session()
        for idx, (ep, form) in enumerate(form_attempts, 1):
            print(
                f"[SET-PARENT FORM {idx}/{len(form_attempts)}] POST {ep} "
                f"form={form}",
                file=sys.stderr, flush=True)
            try:
                r = session.post(
                    f"{self.base_url}{ep}",
                    data=form,
                    headers={"Accept": "application/json"},
                    timeout=30,
                )
                print(
                    f"  → HTTP {r.status_code} "
                    f"body={(r.text or '')[:160].replace(chr(10), ' ')}",
                    file=sys.stderr, flush=True)
                if 200 <= r.status_code < 300:
                    if _verify_parent_set():
                        print(f"  ✓ 상위 #{pid_v} 연결 확인됨!",
                              file=sys.stderr, flush=True)
                        return {}
            except Exception as e:
                print(f"  → ✗ {e}", file=sys.stderr, flush=True)

        # 모든 시도 실패
        raise RuntimeError(
            f"상위 항목 설정 실패 — 이 CB 인스턴스는 PATCH/PUT 미지원이고 "
            f"시도한 POST/폼 변형 모두 적용 안 됨. CB 관리자에게 v3 API "
            f"PATCH 지원 또는 legacy /rest/itemQuickEdit 활성화 요청 필요.")

    # ── 트래커 필드 schema 조회 (캐시됨) ────────────────────────
    def fetch_tracker_fields(self, tracker_id: str) -> list:
        """트래커의 필드 정의 목록 조회. CB v3 / legacy 엔드포인트 순차 시도.
        반환: [{id, name, type, options?, ...}, ...]
        세션 동안 캐시되어 반복 호출은 캐시 사용.
        """
        tid = str(tracker_id or "").strip()
        if not tid:
            return []
        # 캐시 확인 (세션 단위)
        if not hasattr(self, "_tracker_fields_cache"):
            self._tracker_fields_cache: dict = {}
        if tid in self._tracker_fields_cache:
            return self._tracker_fields_cache[tid]

        endpoints = [
            f"/api/v3/trackers/{tid}/fields",
            f"/api/v3/trackers/{tid}/schema",
            f"/rest/tracker/{tid}/schema",
        ]
        import sys
        fields: list = []
        for ep in endpoints:
            try:
                data = self._get(ep)
                if isinstance(data, list):
                    fields = data; break
                if isinstance(data, dict):
                    for key in ("fields", "schema", "data", "trackerItemFields"):
                        v = data.get(key)
                        if isinstance(v, list):
                            fields = v; break
                    if fields:
                        break
            except Exception as e:
                print(f"[FIELD-SCHEMA] {ep} 조회 실패: {str(e)[:80]}",
                      file=sys.stderr, flush=True)
                continue

        # 옵션이 필드 안에 임베드 안 됐을 경우, 각 필드별로 옵션 조회 시도
        for f in fields:
            if not isinstance(f, dict):
                continue
            ftype = (f.get("type") or f.get("typeName") or "").lower()
            if ("choice" in ftype or "option" in ftype) and not f.get("options"):
                fid = f.get("id") or f.get("fieldId")
                if fid:
                    try:
                        opts_resp = self._get(
                            f"/api/v3/trackers/{tid}/fields/{fid}/options")
                        if isinstance(opts_resp, list):
                            f["options"] = opts_resp
                        elif isinstance(opts_resp, dict):
                            for k in ("options", "values", "items"):
                                if isinstance(opts_resp.get(k), list):
                                    f["options"] = opts_resp[k]
                                    break
                    except Exception:
                        pass

        self._tracker_fields_cache[tid] = fields
        print(f"[FIELD-SCHEMA] 트래커 #{tid} 필드 {len(fields)}개 캐시",
              file=sys.stderr, flush=True)
        # 상위 몇 개 std 필드 + 모든 custom 필드(id >= 1000) type 출력
        std_shown = 0
        for f in fields:
            if not isinstance(f, dict):
                continue
            fid = f.get('id')
            ftype = f.get('type') or f.get('typeName')
            is_custom = isinstance(fid, int) and fid >= 1000
            if is_custom:
                print(
                    f"  · [cf] id={fid} name={f.get('name')!r} "
                    f"type={ftype!r}",
                    file=sys.stderr, flush=True)
            elif std_shown < 3:
                print(
                    f"  · [std] id={fid} name={f.get('name')!r} "
                    f"type={ftype!r}",
                    file=sys.stderr, flush=True)
                std_shown += 1
        return fields

    # ── 개별 필드의 상세 정의 조회 ───────────────────────────────
    def fetch_field_detail(self, tracker_id: str, field_id) -> dict:
        """단일 필드의 상세 schema 조회. 트래커 fields 리스트는 'FieldReference'
        wrapper 만 주고 실제 type 을 가리는 경우가 있어, 개별 endpoint 로 정확한
        type 을 얻기 위함.
        세션 단위 캐시.
        """
        import sys
        tid = str(tracker_id or "").strip()
        fid = str(field_id).strip() if field_id is not None else ""
        if not (tid and fid):
            return {}
        if not hasattr(self, "_field_detail_cache"):
            self._field_detail_cache: dict = {}
        ck = (tid, fid)
        if ck in self._field_detail_cache:
            return self._field_detail_cache[ck]
        endpoints = [
            f"/api/v3/trackers/{tid}/fields/{fid}",
            f"/rest/tracker/{tid}/fields/{fid}",
        ]
        detail: dict = {}
        for ep in endpoints:
            try:
                data = self._get(ep)
                if isinstance(data, dict) and data:
                    detail = data
                    break
            except Exception:
                continue
        self._field_detail_cache[ck] = detail
        if detail:
            print(
                f"[FIELD-DETAIL] tracker #{tid} field #{fid}: "
                f"type={detail.get('type')!r} "
                f"typeName={detail.get('typeName')!r} "
                f"valueModel={detail.get('valueModel')!r}",
                file=sys.stderr, flush=True)
        return detail

    # ── 트래커의 기존 이슈들을 검색해 customFields 통합 template 구축 ──
    def fetch_first_item_detail(self, tracker_id: str) -> dict:
        """하위 호환 — 첫 이슈만 반환. _build_unified_template 권장."""
        items = self._fetch_template_items(tracker_id, max_items=1)
        return items[0] if items else {}

    def _fetch_template_items(self, tracker_id: str,
                              max_items: int = 20) -> list:
        """트래커에서 최대 max_items 개의 이슈 detail 을 가져온다.
        세션 단위 캐시."""
        import sys
        tid = str(tracker_id or "").strip()
        if not tid:
            return []
        if not hasattr(self, "_template_items_cache"):
            self._template_items_cache: dict = {}
        cache_key = (tid, max_items)
        if cache_key in self._template_items_cache:
            return self._template_items_cache[cache_key]

        details = []
        try:
            list_resp = self._get(
                f"/api/v3/trackers/{tid}/items",
                params={"page": 1, "pageSize": max_items})
            item_refs = []
            if isinstance(list_resp, dict):
                for k in ("itemRefs", "items", "data"):
                    v = list_resp.get(k)
                    if isinstance(v, list):
                        item_refs = v
                        break
            elif isinstance(list_resp, list):
                item_refs = list_resp
            for ref in item_refs[:max_items]:
                iid = ref.get("id") or ref.get("itemId")
                if not iid:
                    continue
                try:
                    d = self.fetch_item_detail(iid)
                    if d:
                        details.append(d)
                except Exception:
                    continue
        except Exception as e:
            print(f"[TEMPLATE] 이슈 목록 fetch 실패: {str(e)[:120]}",
                  file=sys.stderr, flush=True)

        self._template_items_cache[cache_key] = details
        print(
            f"[TEMPLATE] 트래커 #{tid}: {len(details)}개 이슈 detail 캐시",
            file=sys.stderr, flush=True)
        return details

    def _build_unified_field_map(self, tracker_id: str) -> dict:
        """트래커의 여러 이슈를 훑어 각 customField 이름별로 값이 채워진
        대표 entry 를 수집. 반환: {field_name: customField_entry_dict}.

        한 이슈에 모든 필드가 채워져있지 않으니 여러 이슈를 merge 한다.
        """
        import sys
        tid = str(tracker_id or "").strip()
        if not tid:
            return {}
        if not hasattr(self, "_unified_field_cache"):
            self._unified_field_cache: dict = {}
        if tid in self._unified_field_cache:
            return self._unified_field_cache[tid]

        items = self._fetch_template_items(tid, max_items=20)
        merged: dict = {}
        for d in items:
            cfs = d.get("customFields") or []
            for cf in cfs:
                if not isinstance(cf, dict):
                    continue
                nm = (cf.get("name") or "").strip()
                if not nm:
                    continue
                value = cf.get("value")
                values = cf.get("values")
                has_val = bool(value) or (isinstance(values, list) and values)
                if nm in merged:
                    # 이미 있는데 현재 게 더 채워져 있으면 교체
                    cur = merged[nm]
                    cur_has = bool(cur.get("value")) or (
                        isinstance(cur.get("values"), list) and cur.get("values"))
                    if has_val and not cur_has:
                        merged[nm] = cf
                else:
                    merged[nm] = cf
        self._unified_field_cache[tid] = merged
        print(
            f"[TEMPLATE] 트래커 #{tid} 통합 필드 맵: {len(merged)}개 "
            f"({len(items)}개 이슈 merge)",
            file=sys.stderr, flush=True)
        # 디버그 — reference 계열 필드만 미리 로깅
        for nm, entry in merged.items():
            etype = (entry.get("type") or "").lower()
            if "reference" in etype or "item" in etype:
                print(
                    f"  · '{nm}' template: {entry!r}",
                    file=sys.stderr, flush=True)
        return merged

    def _build_payload_from_template(self, tracker_id: str,
                                     name_value_map: dict) -> list:
        """여러 기존 이슈를 훑어 각 필드의 정확한 customFields 형식을 학습 후
        값만 새 값으로 교체해 payload 구성. 가장 신뢰도 높은 방식.

        반환 빈 리스트: 매칭 필드가 단 하나도 없을 때.
        """
        import sys
        tid = str(tracker_id or "").strip()

        # 트래커 schema 의 옵션 정보 (option name → option id 매핑)
        schema_fields = self.fetch_tracker_fields(tid)
        opts_by_field_id: dict = {}  # fieldId → {option_name: option_id}
        for sf in schema_fields:
            if not isinstance(sf, dict):
                continue
            sfid = sf.get("id") or sf.get("fieldId")
            options = sf.get("options") or []
            opt_map = {}
            for o in options:
                if isinstance(o, dict):
                    nm = (o.get("name") or "").strip()
                    oid = o.get("id")
                    if nm and oid is not None:
                        opt_map[nm] = oid
            if sfid is not None and opt_map:
                opts_by_field_id[sfid] = opt_map

        # 여러 이슈를 merge 한 통합 필드맵 사용 (한 이슈에 모든 필드가 채워져
        # 있지 않으므로 다수 이슈를 합쳐 누락 필드 확보)
        by_name = self._build_unified_field_map(tid)

        result = []
        for fname, fvalue in (name_value_map or {}).items():
            if fvalue is None:
                continue
            sval = str(fvalue).strip()
            if not sval:
                continue
            tmpl = by_name.get(fname.strip())
            if not tmpl:
                # template 에 없으면 schema 기반 resolve 로 폴백
                # (예: 어느 기존 이슈도 채우지 않은 reference 필드)
                try:
                    fallback = self._resolve_field_payload(
                        tid, {fname: fvalue})
                    if fallback:
                        result.extend(fallback)
                        print(
                            f"[TEMPLATE] '{fname}' template 없음 — "
                            f"schema 기반 폴백 추가",
                            file=sys.stderr, flush=True)
                        continue
                except Exception as e:
                    print(
                        f"[TEMPLATE] '{fname}' schema 폴백 예외: "
                        f"{str(e)[:80]}",
                        file=sys.stderr, flush=True)
                print(f"[TEMPLATE] 필드 '{fname}' template/schema 모두 없음 — 스킵",
                      file=sys.stderr, flush=True)
                continue
            new_entry = dict(tmpl)
            # 기존 'values' 의 구조를 학습해 같은 형식으로 새 값을 채움
            existing_values = tmpl.get("values")
            entry_type = (tmpl.get("type") or "").lower()
            fid = tmpl.get("fieldId") or tmpl.get("id")

            # Choice 계열 — 옵션 ID 매칭
            if "choice" in entry_type or "option" in entry_type:
                opt_map = opts_by_field_id.get(fid, {})
                opt_id = opt_map.get(sval)
                if opt_id is not None:
                    # 기존 values 의 한 항목 구조를 복사해 ID/name 만 교체
                    if isinstance(existing_values, list) and existing_values:
                        proto = dict(existing_values[0]) if isinstance(
                            existing_values[0], dict) else {}
                    else:
                        proto = {}
                    proto["id"]   = opt_id
                    proto["name"] = sval
                    new_entry["values"] = [proto]
                else:
                    # TrackerItemChoiceField (예: '연관 사양변경') — schema 가
                    # 옵션을 enumerate 하지 않음. 값이 정수 ID 이면 기존 values
                    # 구조를 복제해 트래커 항목 참조로 매핑.
                    try:
                        rid = int(sval)
                    except ValueError:
                        rid = None
                    is_tracker_ref = False
                    if isinstance(existing_values, list) and existing_values:
                        proto_sample = existing_values[0] if isinstance(
                            existing_values[0], dict) else {}
                        # 기존 항목의 type 이 TrackerItemReference 면 TrackerItem
                        # ChoiceField 확정 — 정수 ID 로 새 참조 박음
                        ev_type = (proto_sample.get("type") or "").lower()
                        if "trackeritemreference" in ev_type:
                            is_tracker_ref = True
                    if rid is not None and (is_tracker_ref or not opt_map):
                        # 옵션 맵이 비어있고 값이 정수 — TrackerItemChoiceField
                        # 로 간주 (schema fallback 으로 처리하도록 폴백)
                        try:
                            fallback = self._resolve_field_payload(
                                tid, {fname: fvalue})
                            if fallback:
                                result.extend(fallback)
                                print(
                                    f"[TEMPLATE] '{fname}' TrackerItemRef "
                                    f"감지 — schema 폴백 사용 (rid={rid})",
                                    file=sys.stderr, flush=True)
                                continue
                        except Exception as e:
                            print(
                                f"[TEMPLATE] '{fname}' schema 폴백 예외: "
                                f"{str(e)[:80]}",
                                file=sys.stderr, flush=True)
                    print(
                        f"[TEMPLATE] '{fname}' choice 옵션 '{sval}' 미매칭 "
                        f"(옵션: {list(opt_map.keys())[:5]}) — 스킵",
                        file=sys.stderr, flush=True)
                    continue
            elif "reference" in entry_type or "trackeritemreference" in entry_type:
                # 참조 필드 — 정수 ID 기대
                try:
                    rid = int(sval)
                except ValueError:
                    print(f"[TEMPLATE] '{fname}' reference 값이 ID 아님 — 스킵",
                          file=sys.stderr, flush=True)
                    continue
                if isinstance(existing_values, list) and existing_values:
                    proto = dict(existing_values[0]) if isinstance(
                        existing_values[0], dict) else {}
                else:
                    proto = {}
                proto["id"] = rid
                new_entry["values"] = [proto]
            else:
                # 텍스트/기타 — 'value' 필드 교체
                if "values" in new_entry:
                    new_entry["values"] = [sval] if isinstance(
                        existing_values, list) and existing_values and not isinstance(
                        existing_values[0], dict) else [{"value": sval}]
                else:
                    new_entry["value"] = sval
            result.append(new_entry)
            print(f"[TEMPLATE] '{fname}' → {new_entry!r}",
                  file=sys.stderr, flush=True)
        return result

    def _resolve_field_payload(self, tracker_id: str,
                               name_value_map: dict) -> list:
        """{필드이름: 값} 을 CB v3 customFields 배열로 변환.

        schema 조회로 fieldId 와 option ID 를 정확히 매칭한다. 매칭 실패하면
        이름 기반 항목으로 폴백 (CB 가 이름으로도 받을 수 있음).
        """
        import sys
        fields = self.fetch_tracker_fields(tracker_id)
        by_name = {}
        for f in fields:
            if not isinstance(f, dict):
                continue
            nm = (f.get("name") or "").strip()
            if nm:
                by_name[nm] = f

        # 헬퍼: schema 의 필드 type → 값 클래스명 추론 (<FieldType>Value 패턴)
        def _value_class_for(field_type: str) -> str:
            ft = (field_type or "").strip()
            if not ft:
                return "TextFieldValue"
            # FieldReference 는 wrapper 일 뿐 — 실제 type 모르므로 안전 폴백
            if ft.lower() == "fieldreference":
                return "TextFieldValue"
            if ft.endswith("Value"):
                return ft   # 이미 Value suffix
            if ft.endswith("Field"):
                return ft + "Value"
            return ft + "FieldValue"

        result = []
        for fname, fvalue in (name_value_map or {}).items():
            if fvalue is None:
                continue
            sval = str(fvalue).strip()
            if not sval:
                continue
            fdef = by_name.get(fname.strip())
            if not fdef:
                # 필드명이 schema 에 없음 — TextFieldValue 추정으로 폴백
                result.append({
                    "name": fname,
                    "type": "TextFieldValue",
                    "value": sval,
                })
                print(f"[FIELD-RESOLVE] '{fname}' schema 없음 — text 폴백",
                      file=sys.stderr, flush=True)
                continue
            fid   = fdef.get("id") or fdef.get("fieldId")
            ftype = (fdef.get("type") or fdef.get("typeName") or "").strip()
            value_model = ""
            # 'FieldReference' 만 받은 경우 개별 필드 detail 로 실제 type 시도
            if fid is not None:
                fdetail = self.fetch_field_detail(tracker_id, fid)
                if isinstance(fdetail, dict):
                    deeper = (fdetail.get("type") or
                              fdetail.get("typeName") or "").strip()
                    if deeper and deeper.lower() != "fieldreference":
                        ftype = deeper
                    value_model = (fdetail.get("valueModel") or "").strip()
            ftype_l = ftype.lower()

            # ─── valueModel 우선 ───
            # CB v3 가 'ChoiceFieldValue<TrackerItemReference>' 같이 generic
            # 으로 알려주면 그게 가장 정확한 정보. 외부 클래스 + 내부 참조 타입
            # 으로 분해해 정확한 페이로드 구성.
            import re as _re_p
            mvm = _re_p.match(r'^([A-Za-z_]\w*)\s*<\s*([A-Za-z_]\w*)\s*>',
                              value_model)
            if mvm:
                outer_class = mvm.group(1)
                inner_ref   = mvm.group(2)
                print(
                    f"[FIELD-RESOLVE] '{fname}' fid={fid} "
                    f"valueModel={value_model!r} → outer={outer_class!r} "
                    f"inner={inner_ref!r}",
                    file=sys.stderr, flush=True)
                try:
                    rid = int(sval)
                    # template 항목에 있는 sharedFieldNames 도 포함 (CB v3 가
                    # 일부 필드는 이게 없으면 silent ignore 함).
                    # 참조 값에는 tracker 정보도 함께 보냄 — 일부 CB 버전이
                    # 명시적 tracker 식별을 요구.
                    inner_value = {"id": rid, "type": inner_ref}
                    result.append({
                        "fieldId":          fid,
                        "name":             fname,
                        "type":             outer_class,
                        "sharedFieldNames": [],
                        "values":           [inner_value],
                    })
                    continue
                except ValueError:
                    # sval 이 ID 가 아님 → 텍스트로 폴백 처리
                    pass

            value_class = _value_class_for(ftype)
            print(
                f"[FIELD-RESOLVE] '{fname}' fid={fid} schemaType={ftype!r} "
                f"valueModel={value_model!r} → valueClass={value_class!r}",
                file=sys.stderr, flush=True)

            # 옵션 ID 매칭 (choice 필드)
            if ("choice" in ftype_l or "option" in ftype_l):
                options = fdef.get("options") or []
                opt_by_name = {}
                for o in options:
                    if isinstance(o, dict):
                        on = (o.get("name") or "").strip()
                        oid = o.get("id")
                        if on and oid is not None:
                            opt_by_name[on] = oid
                opt_id = opt_by_name.get(sval)
                if opt_id is not None:
                    result.append({
                        "fieldId": fid,
                        "name":    fname,
                        "type":    value_class,
                        "values":  [{"id": opt_id, "name": sval}],
                    })
                else:
                    result.append({
                        "fieldId": fid,
                        "name":    fname,
                        "type":    value_class,
                        "values":  [{"name": sval}],
                    })
            elif ("reference" in ftype_l or
                  ("item" in ftype_l and "field" in ftype_l)):
                # 참조 필드 — 정수 ID 기대
                try:
                    rid = int(sval)
                    result.append({
                        "fieldId": fid,
                        "name":    fname,
                        "type":    value_class,
                        "values":  [{"id": rid}],
                    })
                except ValueError:
                    result.append({
                        "fieldId": fid,
                        "name":    fname,
                        "type":    "TextFieldValue",
                        "value":   sval,
                    })
            else:
                # 텍스트/기타 — TextFieldValue / WikiTextFieldValue 추정
                # CB Jackson 은 type 누락하면 에러 → 항상 type 포함
                if "wiki" in ftype_l:
                    result.append({
                        "fieldId": fid,
                        "name":    fname,
                        "type":    value_class or "WikiTextFieldValue",
                        "value":   sval,
                    })
                else:
                    result.append({
                        "fieldId": fid,
                        "name":    fname,
                        "type":    value_class or "TextFieldValue",
                        "value":   sval,
                    })
        return result

    # ── 기존 이슈의 특정 커스텀 필드만 사후 갱신 ─────────────
    def try_set_custom_field(self, item_id: str,
                             custom_field_entry: dict) -> bool:
        """기존 이슈의 한 customField 만 PATCH/PUT/POST 로 갱신 시도.

        custom_field_entry: CB v3 형식의 단일 customFields entry dict
            (예: {"fieldId": 99, "type": "...", "values": [...]})

        여러 (method, endpoint) 변형을 순차 시도하고 첫 성공 시 True.
        모두 실패하면 False (호출 측이 폴백 가능).
        """
        import sys
        iid = str(item_id or "").strip()
        if not iid or not custom_field_entry:
            return False

        payload_partial = {"customFields": [custom_field_entry]}
        fid = custom_field_entry.get("fieldId")

        strategies = [
            ("PATCH", f"/api/v3/items/{iid}",            payload_partial),
            ("PUT",   f"/api/v3/items/{iid}",            payload_partial),
            ("POST",  f"/api/v3/items/{iid}/fields",     [custom_field_entry]),
            ("PATCH", f"/api/v3/items/{iid}/fields",     [custom_field_entry]),
        ]
        if fid is not None:
            strategies.append(
                ("PUT",  f"/api/v3/items/{iid}/fields/{fid}",
                 custom_field_entry))
            strategies.append(
                ("PATCH", f"/api/v3/items/{iid}/fields/{fid}",
                 custom_field_entry))

        for method, ep, payload in strategies:
            try:
                print(f"[SET-FIELD {method}] {ep}",
                      file=sys.stderr, flush=True)
                self._request_json(method, ep, payload)
                print(f"  ✓ {method} {ep} 성공",
                      file=sys.stderr, flush=True)
                # 검증 — fetch 해서 실제 들어갔는지 확인
                try:
                    detail = self.fetch_item_detail(iid)
                    cfs = detail.get("customFields") or []
                    for e in cfs:
                        if (isinstance(e, dict)
                                and (e.get("fieldId") == fid
                                     or e.get("name") == custom_field_entry.get("name"))):
                            vals = e.get("values") or []
                            if vals:
                                return True
                except Exception:
                    return True   # 응답 2xx 라 일단 성공 간주
            except RuntimeError as e:
                err_snip = str(e)[:160]
                print(f"  ✗ {err_snip}", file=sys.stderr, flush=True)
                continue
        return False

    # ── 수평전개(차종 적용여부) 전용 이슈 생성 ────────────────
    def create_hzt_item(self, tracker_id: str, title: str,
                        jira_link: str,
                        vehicle_field_values: dict,
                        description: str = "",
                        description_format: str = "PlainText",
                        parent_item_id: str = "") -> dict:
        """수평전개 트래커에 차종별 적용여부 매핑된 이슈 생성.

        vehicle_field_values: {field_name_in_cb: value_string} dict
            (예: {"NQ5 PE": "적용", "MQ4i": "미적용", "NX5_30Ah": "NA", ...})
        description_format : 본문 포맷 — "PlainText" / "Html" / "Wiki".
                             기본 PlainText (수평전개 동기 흐름은 평문 본문 사용).
                             사양변경/수평전개 탭에서 메인 등록 시는 "Html".
        parent_item_id     : 비어있지 않으면 생성 payload 에 parentId 포함.
                             (create_item 의 6가지 전략까진 안 쓰고 단순히 payload
                              에 'parentId' 키를 넣어 첫 성공에 의존 — HZT 흐름은
                              CB UI 자동연결을 못 받으므로 best-effort.)

        CB v3 API 가 트래커마다 field schema 가 달라 payload 형식이 다양함.
        4가지 customFields 형식을 순차 시도하고 첫 성공 응답을 반환.
        모두 실패하면 마지막 에러를 던진다.
        """
        import sys
        tid = str(tracker_id).strip()
        if not tid:
            raise RuntimeError("수평전개 트래커 ID가 비어있습니다.")
        endpoint = f"/api/v3/trackers/{tid}/items"

        base_payload = {"name": title, "description": description or ""}
        # parent_item_id 가 있으면 payload 에 부모 연결 키 추가 (best-effort)
        pid_str = str(parent_item_id or "").strip()
        if pid_str:
            # CB v3 표준 키 — 일부 트래커는 이 키를 받아 생성 시점에 연결됨
            base_payload["parentId"] = pid_str
        # JIRA_LINK / JIRA_URL 필드 — 수평전개 트래커의 커스텀 필드.
        # ★ 중요: JIRA_URL 은 UrlField — http(s):// 로 시작하는 URL 만 허용.
        #   유효하지 않은 값을 박으면 CB 가 "JIRA_URL must be wiki link or URL"
        #   로 전체 payload 를 거부 → 차종 필드 매핑까지 모두 실패한다.
        #   따라서 URL 형식 검증 후 분기:
        #     · http(s):// 시작 → JIRA_LINK(wiki) + JIRA_URL 모두 채움
        #     · 그 외 (자유 텍스트, JIRA 키만, 짧은 메모 등) → JIRA_LINK 에 평문
        #       그대로 넣고 JIRA_URL 은 비워둠 (CB UrlField 검증 회피)
        extra_fields = dict(vehicle_field_values or {})
        js = (jira_link or "").strip()
        if js:
            import re as _re_jira
            is_url = bool(_re_jira.match(r'^https?://', js))
            if is_url:
                # URL 에서 JIRA 티켓 키 (예: HKMCJGRLBM-45) 추출 → 라벨로 사용.
                jira_key_m = _re_jira.search(
                    r'/(?:browse|issues)/([A-Za-z]+[-_]\d+)', js)
                jira_label = jira_key_m.group(1) if jira_key_m else "JIRA 링크"
                extra_fields.setdefault(
                    "JIRA_LINK", f"[{jira_label}|{js}]")
                extra_fields.setdefault("JIRA_URL", js)
            else:
                # URL 아님 — JIRA_LINK 에만 평문으로 (WikiTextField 는 자유 텍스트 OK).
                # JIRA_URL 은 채우지 않음 (UrlField 검증 실패 방지).
                extra_fields.setdefault("JIRA_LINK", js)

        _df = description_format or "PlainText"

        def _make_payload_format_template():
            # 기존 이슈의 customFields 형식을 복제해 값만 교체 — 가장 신뢰도 높음.
            tpl = self._build_payload_from_template(tid, extra_fields)
            if not tpl:
                return None
            return {
                **base_payload,
                "descriptionFormat": _df,
                "customFields": tpl,
            }

        def _make_payload_format_schema():
            # 트래커 schema 조회 → fieldId + option ID 로 정확한 payload 구성.
            resolved = self._resolve_field_payload(tid, extra_fields)
            if not resolved:
                return None
            return {
                **base_payload,
                "descriptionFormat": _df,
                "customFields": resolved,
            }

        def _make_payload_format_a():
            # CB v3 표준 — choice field, name 기반
            return {
                **base_payload,
                "descriptionFormat": _df,
                "customFields": [
                    {"name": k, "type": "ChoiceFieldValue",
                     "values": [{"name": str(v)}]}
                    for k, v in extra_fields.items()
                ],
            }

        def _make_payload_format_b():
            # 간소 형식 — value 단일
            return {
                **base_payload,
                "descriptionFormat": _df,
                "customFields": [
                    {"name": k, "value": str(v)}
                    for k, v in extra_fields.items()
                ],
            }

        def _make_payload_format_c():
            # fieldValues 키 사용
            return {
                **base_payload,
                "descriptionFormat": _df,
                "fieldValues": [
                    {"name": k, "value": str(v)}
                    for k, v in extra_fields.items()
                ],
            }

        def _make_payload_format_d():
            # 평탄 형식 — 필드명을 키로 직접
            payload = {**base_payload, "descriptionFormat": _df}
            for k, v in extra_fields.items():
                payload[k] = str(v)
            return payload

        def _make_payload_minimal():
            # 마지막 폴백 — 커스텀 필드 없이 name + description 만.
            # CB 가 필수 커스텀 필드 누락으로 모든 형식을 거부할 때, 최소한
            # 빈 이슈라도 생성해 사용자가 트래커 연결 자체는 확인 가능하게 함.
            return {**base_payload, "descriptionFormat": _df}

        attempts = [
            ("template(existing-item-clone)",  _make_payload_format_template()),
            ("schema(fieldId+optionId)",       _make_payload_format_schema()),
            ("customFields(ChoiceFieldValue)", _make_payload_format_a()),
            ("customFields(value)",            _make_payload_format_b()),
            ("fieldValues",                    _make_payload_format_c()),
            ("flat",                           _make_payload_format_d()),
            ("minimal(no-customFields)",       _make_payload_minimal()),
        ]
        # template/schema 형식이 None (조회 실패) 이면 해당 항목 제거
        attempts = [(lbl, p) for lbl, p in attempts if p is not None]

        all_errs: list[str] = []
        for label, payload in attempts:
            try:
                print(f"[HZT-CREATE] try '{label}' on {endpoint}",
                      file=sys.stderr, flush=True)
                resp = self._post_json(endpoint, payload)
                # 응답에서 ID 확보 — 없으면 다음 형식
                new_id = str(resp.get("id") or resp.get("itemId") or "").strip()
                if new_id:
                    print(
                        f"[HZT-CREATE] ✓ '{label}' 성공 (id={new_id})",
                        file=sys.stderr, flush=True)
                    if label == "minimal(no-customFields)":
                        # 최소 페이로드로 성공했다는 건 커스텀 필드 매핑이
                        # 트래커 schema 와 안 맞았다는 뜻 → 사용자가 CB 에서
                        # 차종 필드를 수동 채워야 함. 응답에 flag + 진단 추가.
                        resp["_hzt_minimal_only"] = True
                        resp["_hzt_attempts"] = list(all_errs)
                        # 사용자가 실제 어떤 필드를 보내려 했는지도 진단에 포함
                        resp["_hzt_field_values"] = dict(extra_fields)
                    return resp
            except RuntimeError as e:
                err_snip = str(e)[:200]
                all_errs.append(f"[{label}] {err_snip}")
                print(f"[HZT-CREATE] ✗ '{label}': {err_snip}",
                      file=sys.stderr, flush=True)
                continue

        # 모든 시도 실패 — 모든 에러 메시지 묶어서 보고
        combined = " | ".join(all_errs)[:400]
        raise RuntimeError(
            f"수평전개 이슈 생성 실패 — 모든 시도 거부됨: {combined}")

    # ── 기존 이슈의 description(본문) 업데이트 시도 ──────────
    def try_update_description(self, item_id: str, description: str,
                               description_format: str = "Html",
                               verify_marker: str = "") -> bool:
        """기존 이슈의 본문을 갱신 시도. CB 버전마다 PATCH/PUT 지원 여부와 스키마가
        다르므로 여러 (method, endpoint, payload) 변형을 순차 시도하고, 매 시도
        후 fetch_item_detail 로 description 에 verify_marker 가 들어갔는지 검증.

        성공한 경우 True, 모든 시도 실패 시 False (예외 던지지 않음 — 호출 측이
        실패해도 무난히 폴백할 수 있도록).

        verify_marker: 본문에 들어갔는지 확인할 짧고 유일한 문자열. 비어있으면
                       2xx 응답만으로 성공 간주 (덜 안전).
        """
        import sys
        iid = str(item_id).strip()
        if not iid:
            return False

        # 시도할 (method, endpoint, payload) 조합 — v3 표준 → legacy 순
        strategies = [
            # (1) v3 field 단위 PATCH — 가장 안전한 부분 갱신 (다른 필드 보존)
            ("PATCH", f"/api/v3/items/{iid}/fields", {
                "fieldValues": [
                    {"fieldId": "description", "value": description},
                    {"fieldId": "descriptionFormat", "value": description_format},
                ]
            }),
            ("PATCH", f"/api/v3/items/{iid}/fields", {
                "fieldValues": [
                    {"name": "description", "value": description},
                    {"name": "descriptionFormat", "value": description_format},
                ]
            }),
            # (2) v3 전체 PATCH — description 만 보내고 나머지는 유지 기대
            ("PATCH", f"/api/v3/items/{iid}", {
                "description":       description,
                "descriptionFormat": description_format,
            }),
            # (3) v3 PUT — 일부 CB 버전에서 부분 업데이트로 동작
            ("PUT", f"/api/v3/items/{iid}", {
                "description":       description,
                "descriptionFormat": description_format,
            }),
            # (4) legacy quick-edit (구버전 CB 호환)
            ("POST", f"/rest/itemQuickEdit", {
                "id":          iid,
                "description": description,
                "descriptionFormat": description_format,
            }),
        ]

        for s_idx, (method, ep, payload) in enumerate(strategies, 1):
            try:
                print(
                    f"[UPDATE-DESC {s_idx}/{len(strategies)}] "
                    f"{method} {ep}",
                    file=sys.stderr, flush=True)
                self._request_json(method, ep, payload)
            except RuntimeError as e:
                # 4xx/5xx 등 — 다음 전략 시도
                print(f"  → ✗ {e}", file=sys.stderr, flush=True)
                continue

            # 2xx 응답 → 실제로 들어갔는지 검증
            if verify_marker:
                try:
                    detail = self.fetch_item_detail(iid)
                    current = (detail.get("description") or "")
                    if verify_marker in current:
                        print(f"  ✓ 검증 성공 (marker found)",
                              file=sys.stderr, flush=True)
                        return True
                    else:
                        print(
                            f"  ✗ 응답 2xx but marker 미발견 — "
                            f"실제 적용 안 됨, 다음 전략",
                            file=sys.stderr, flush=True)
                        continue
                except Exception as ve:
                    # 검증 실패 — 2xx 응답이라 일단 성공 간주
                    print(f"  ? 검증 실패 (계속 진행, 성공 간주): {ve}",
                          file=sys.stderr, flush=True)
                    return True
            else:
                # marker 없으면 2xx 만으로 성공
                return True

        print(f"[UPDATE-DESC] 모든 전략 실패 — 본문 갱신 불가",
              file=sys.stderr, flush=True)
        return False

    # ── 기존 이슈에 코멘트 추가 ───────────────────────────────
    def add_comment(self, item_id: str, comment_text: str,
                    comment_format: str = "Html") -> dict:
        """기존 이슈에 코멘트(설명) 추가.
        comment_format: 'Html' (기본) / 'PlainText' / 'Wiki'.
        포맷·스키마가 거부되면 다음 순으로 폴백:
          1) {comment, format=지정값} → 2) {comment, format=PlainText}
          → 3) {comment} (format 생략) → 4) {description} (구버전 스키마)
        """
        iid = str(item_id).strip()
        if not iid:
            raise RuntimeError("이슈 ID가 비어있습니다.")
        endpoint = f"/api/v3/items/{iid}/comments"

        attempts = []
        if comment_format:
            attempts.append({"comment": comment_text, "format": comment_format})
        if comment_format != "PlainText":
            attempts.append({"comment": comment_text, "format": "PlainText"})
        attempts.append({"comment": comment_text})
        attempts.append({"description": comment_text})  # 구버전 스키마

        last_err = None
        for payload in attempts:
            try:
                return self._post_json(endpoint, payload)
            except RuntimeError as e:
                last_err = e
                if "HTTP 400" not in str(e):
                    raise
        raise last_err

    # ── 첨부 파일 업로드 ──────────────────────────────────────
    def add_attachment(self, item_id: str, file_path: str,
                       display_name: str = None) -> dict:
        """기존 이슈에 파일 첨부 (multipart/form-data).
        CB 버전마다 엔드포인트/필드명이 달라서 여러 조합을 시도한다.
        모두 실패하면 각 시도의 응답 상태/본문을 묶어 RuntimeError 로 던진다."""
        iid = str(item_id).strip()
        if not iid:
            raise RuntimeError("이슈 ID가 비어있습니다.")
        if not os.path.exists(file_path):
            raise RuntimeError(f"파일을 찾을 수 없습니다: {file_path}")
        fname = display_name or os.path.basename(file_path)
        session = self._get_session()

        # (endpoint, multipart_field_name) 조합 — v3 → legacy 순으로 시도
        candidates = [
            (f"/api/v3/items/{iid}/attachments", "attachments"),  # v3 표준
            (f"/api/v3/items/{iid}/attachments", "file"),          # v3 대체 필드명
            (f"/rest/item/{iid}/attachments",    "attachment"),    # legacy
            (f"/rest/item/{iid}/attachments",    "attachments"),   # legacy 복수형
            (f"/rest/item/{iid}/attachments",    "file"),          # legacy 'file' 필드
            (f"/rest/items/{iid}/attachments",   "file"),          # 일부 버전
        ]

        import sys
        attempts = []  # (ep, field, status, body)
        for ep, field in candidates:
            try:
                with open(file_path, "rb") as f:
                    files = {field: (fname, f, "application/octet-stream")}
                    resp = session.post(
                        f"{self.base_url}{ep}",
                        files=files,
                        timeout=60,
                    )
            except Exception as e:
                msg = f"[CB-ATTACH] {fname} → {ep} [field={field}] 네트워크오류: {e}"
                print(msg, file=sys.stderr, flush=True)
                attempts.append((ep, field, 0, f"네트워크 오류: {e}"))
                continue
            body_snip = (resp.text or "")[:200].replace("\n", " ").strip()
            print(
                f"[CB-ATTACH] {fname} → {ep} [field={field}] "
                f"HTTP {resp.status_code} body={body_snip[:120]}",
                file=sys.stderr, flush=True)
            if resp.status_code in (200, 201):
                try:
                    return resp.json()
                except Exception:
                    return {}
            attempts.append((ep, field, resp.status_code, body_snip))

        # 모든 시도 실패 — 진단용 상세 메시지 구성
        lines = [f"첨부 실패 — {len(attempts)}개 엔드포인트 시도 모두 실패:"]
        for ep, field, status, body in attempts:
            lines.append(f"  • {ep} [field={field}] → HTTP {status}: {body[:120]}")
        raise RuntimeError("\n".join(lines))

    # ── 연결 테스트 ───────────────────────────────────────────
    def test_connection(self) -> str:
        """폼 로그인(세션 쿠키)으로 자격증명을 검증하고 API 접근을 확인한다."""
        if requests is None:
            raise RuntimeError(
                "requests 패키지가 없습니다.\n터미널에서: pip install requests")

        probe = requests.Session()
        probe.verify  = False
        probe.headers.update({"Accept": "application/json"})

        # ① 폼 로그인
        try:
            resp = probe.post(
                f"{self.base_url}/login.spr",
                data={"user": self.username, "password": self.password,
                      "targetURL": ""},
                timeout=8,
                allow_redirects=True,
            )
            if "login.spr" in resp.url:
                raise RuntimeError(
                    "로그인 실패 — 아이디/비밀번호를 확인해주세요.")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"서버 연결 실패: {e}")

        # ② API 접근 확인
        for ep in ["/api/v3/projects", "/rest/projects"]:
            try:
                resp = probe.get(
                    f"{self.base_url}{ep}",
                    timeout=8,
                    allow_redirects=True,
                )
                if resp.status_code == 200:
                    # 인증 성공 → probe 세션을 그대로 self._session에 저장
                    self._session = probe
                    return "연결 성공 ✓"
                if resp.status_code == 401:
                    raise RuntimeError(
                        "로그인 실패 — 아이디/비밀번호를 확인해주세요.")
                if resp.status_code == 403:
                    raise RuntimeError(
                        "로그인은 됐지만 REST API 접근 권한이 없습니다.\n"
                        "CB 관리자에게 'Rest / Remote API - Access' 권한 부여를 요청하세요.")
            except RuntimeError:
                raise
            except Exception:
                continue

        raise RuntimeError("서버에 연결할 수 없습니다. URL을 다시 확인해주세요.")

    # ── 트래커 이름으로 ID 자동 탐색 ─────────────────────────
    def find_tracker_id(self, name: str) -> str:
        """트래커 약어(예: ILCU)나 키명으로 tracker ID를 검색한다."""
        name_upper = name.strip().upper()

        # v3 API: 전체 트래커 검색
        for ep, key in [
            ("/api/v3/trackers",          "trackers"),
            ("/api/v3/trackers",          None),
        ]:
            try:
                data = self._get(ep, {"page": 1, "pageSize": 500})
                items = data if isinstance(data, list) else data.get(key or "trackers", [])
                for t in items:
                    abbr = (t.get("keyName") or t.get("abbreviation") or
                            t.get("mnemonicId") or "").upper()
                    tname = (t.get("name") or "").upper()
                    if name_upper in (abbr, tname) or name_upper in tname:
                        return str(t.get("id", ""))
            except Exception:
                pass

        # REST API (구버전 호환)
        try:
            data = self._get("/rest/trackers", {"page": 1, "pageSize": 500})
            items = data if isinstance(data, list) else data.get("trackers", [])
            for t in items:
                abbr  = (t.get("keyName") or t.get("abbreviation") or "").upper()
                tname = (t.get("name") or "").upper()
                if name_upper in (abbr, tname) or name_upper in tname:
                    return str(t.get("id", ""))
        except Exception:
            pass

        return ""

    # ── Tracker 아이템 목록 조회 ──────────────────────────────
    @staticmethod
    def _normalize_items(raw) -> list[dict]:
        """CB 엔드포인트 응답 다양성 흡수: 정수/문자열 ID 도 {'id': ...} dict 로 래핑."""
        if not isinstance(raw, list):
            return []
        out = []
        for x in raw:
            if isinstance(x, dict):
                out.append(x)
            elif isinstance(x, (int, str)):
                out.append({"id": x})
            # 그 외 타입은 무시
        return out

    def fetch_tracker_items(self, tracker_id: str) -> list[dict]:
        all_items: list[dict] = []
        page = 1
        while True:
            data = self._get(
                f"/api/v3/trackers/{tracker_id}/items",
                {"page": page, "pageSize": 100},
            )
            if isinstance(data, list):
                chunk_raw = data
            elif isinstance(data, dict):
                chunk_raw = (data.get("itemRefs")
                             or data.get("items")
                             or data.get("trackerItems")
                             or [])
            else:
                break
            chunk = self._normalize_items(chunk_raw)
            if not chunk:
                break
            all_items.extend(chunk)
            total = (data.get("total", len(chunk))
                     if isinstance(data, dict) else len(chunk))
            if len(all_items) >= total:
                break
            page += 1
        return all_items

    # ── 아이템 상세 조회 ──────────────────────────────────────
    def fetch_item_detail(self, item_id) -> dict:
        try:
            return self._get(f"/api/v3/items/{item_id}")
        except Exception:
            return {}

    # ── 아이템 하위(child) 목록 조회 ──────────────────────────
    def fetch_item_children(self, item_id) -> list[dict]:
        """
        특정 아이템의 하위(child) 아이템 목록을 조회.
        Codebeamer 계층 구조에서 대분류 → 세부 과거차 티켓을 따라가기 위함.
        여러 엔드포인트를 순서대로 시도한다.
        """
        endpoints = [
            f"/api/v3/items/{item_id}/children",
            f"/rest/item/{item_id}/children",
        ]
        for ep in endpoints:
            try:
                data = self._get(ep)
                if isinstance(data, list):
                    items = self._normalize_items(data)
                    if items:
                        return items
                elif isinstance(data, dict):
                    raw = (data.get("children")
                           or data.get("itemRefs")
                           or data.get("items")
                           or data.get("trackerItems")
                           or [])
                    items = self._normalize_items(raw)
                    if items:
                        return items
            except Exception:
                continue
        return []

    # ── MD 생성 ───────────────────────────────────────────────
    def generate_md(self,
                    tracker_map: dict,     # {"ILCU": "12345", "LDM": "23456", ...}
                    output_path: str = None,
                    progress_cb        = None) -> str:
        output_path = output_path or CB_MD_FILE
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines: list[str] = [
            "# Codebeamer 과거 이슈 컨텍스트",
            f"> 생성 일시: {ts}",
            "",
            "아래는 각 컴포넌트별 과거 이슈 목록입니다.",
            "코드 리뷰 시 현재 변경점이 과거 이슈와 유사한 경우 경고해주세요.",
            "",
        ]

        total = sum(1 for v in tracker_map.values() if v.strip())
        done  = 0

        # ── 한 아이템을 MD 블록으로 직렬화 (재귀 헬퍼) ─────────
        #   indent_level: 0 = 최상위(### [id]), 1+ = 하위 티켓(#### [id])
        #   max_depth   : 하위 아이템을 따라갈 최대 계층 (runaway 방지)
        def _render_item(ref, indent_level: int = 0,
                         max_depth: int = 2) -> list[str]:
            # ── 타입 방어: 일부 CB 엔드포인트는 dict 대신 정수(ID) 만 반환 ──
            # 예: {"children": [741622, 741620, ...]} 또는 그냥 [741622, ...]
            # → id 만 가진 최소 dict 로 감싸서 이후 로직을 통과시킴.
            if isinstance(ref, (int, str)):
                ref = {"id": ref}
            elif not isinstance(ref, dict):
                return []

            item_id = ref.get("id") or ref.get("itemId") or ""
            name    = ref.get("name", f"Item {item_id}")

            detail: dict = {}
            if item_id:
                detail = self.fetch_item_detail(item_id)

            desc = _clean_text(
                detail.get("description", ref.get("description", "")))

            # ── 커스텀 필드: 값이 있는 모든 필드 포함 ──────────
            #   이전에는 '문제점/원인/개선' 키워드 매칭 필드만 포함했으나,
            #   실제 Codebeamer 트래커마다 필드명이 다양해 누락이 많았음.
            #   → 상태/ID/이름 제외 모든 non-empty 필드를 기록한다.
            custom_lines = []
            status = ""
            for cf in (detail.get("customFields") or []):
                # customFields 엔트리가 dict 가 아니면 스킵 (예: 원시 값)
                if not isinstance(cf, dict):
                    continue
                fid = cf.get("fieldId")
                cf_name = (fid.get("name", "") if isinstance(fid, dict) else "") \
                          or cf.get("name", "")
                cf_val  = cf.get("value", "") or cf.get("values", "")
                if not cf_name:
                    continue
                cf_name_l = cf_name.lower()
                # 상태 필드는 별도 캡처
                if not status and ("status" in cf_name_l or "상태" in cf_name_l):
                    if isinstance(cf_val, dict):
                        status = cf_val.get("name", "") or str(cf_val)
                    elif isinstance(cf_val, list) and cf_val:
                        v0 = cf_val[0]
                        status = v0.get("name", str(v0)) if isinstance(v0, dict) else str(v0)
                    else:
                        status = str(cf_val)
                    continue
                if not cf_val:
                    continue
                # 리스트/딕셔너리 값 평탄화
                if isinstance(cf_val, list):
                    flat = [v.get("name", str(v)) if isinstance(v, dict) else str(v)
                            for v in cf_val]
                    cf_val_str = ", ".join(x for x in flat if x)
                elif isinstance(cf_val, dict):
                    cf_val_str = cf_val.get("name", "") or str(cf_val)
                else:
                    cf_val_str = str(cf_val)
                cleaned = _clean_text(cf_val_str)
                if cleaned:
                    custom_lines.append(f"  - **{cf_name}**: {cleaned[:500]}")

            if not status:
                raw = detail.get("status", "")
                status = (raw.get("name", "") if isinstance(raw, dict)
                          else str(raw)) or "미지정"

            header_hash = "###" if indent_level == 0 else "####"
            out = [f"{header_hash} [{item_id}] {name}",
                   f"- **상태**: {status}"]
            if custom_lines:
                out.append("- **필드**:")
                out.extend(custom_lines)
            if desc and desc.strip() not in (name.strip(), "--"):
                out.append(f"- **설명**: {desc[:2000]}")
            elif not custom_lines and indent_level == 0:
                out.append("- **설명**: (없음)")
            out.append("")

            # ── 하위(child) 아이템 재귀 조회 ───────────────────
            if item_id and indent_level < max_depth:
                try:
                    children = self.fetch_item_children(item_id)
                except Exception:
                    children = []
                if children:
                    out.append(f"- **하위 아이템**: {len(children)}건")
                    out.append("")
                    for c_ref in children[:50]:    # 안전장치: 자식 최대 50개
                        out.extend(_render_item(
                            c_ref, indent_level + 1, max_depth))
            return out

        for tracker_name, tracker_id in tracker_map.items():
            if not tracker_id.strip():
                continue
            done += 1
            pct = int(10 + 80 * done / total)
            if progress_cb:
                progress_cb(f"{tracker_name} 이슈 조회 중... ({done}/{total})", pct)

            lines += [f"## 🔧 {tracker_name} 이슈", ""]
            try:
                refs = self.fetch_tracker_items(tracker_id.strip())
                if not refs:
                    lines += ["_(항목 없음)_", ""]; continue

                for i, ref in enumerate(refs):
                    lines += _render_item(ref, indent_level=0, max_depth=2)

            except Exception as e:
                lines += [f"> ⚠️ 조회 실패: {e}", ""]

        if progress_cb:
            progress_cb("파일 저장 중...", 95)

        md_text = "\n".join(lines)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_text)

        if progress_cb:
            progress_cb("완료!", 100)
        return md_text
