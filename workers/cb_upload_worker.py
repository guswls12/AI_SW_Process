"""cb_upload_worker.py — Codebeamer 업로드 백그라운드 워커.

UI 스레드를 막지 않고:
  1) 트래커에 새 이슈 생성 (선택적으로 상위 이슈 하위로)
  2) 선택적으로 MD/HTML 파일을 첨부
하는 작업을 수행한다.

CbFetcher 의 create_item / add_attachment 를 호출.
"""

import os
import re
import html as _html
import datetime
import tempfile

from PyQt6.QtCore import QObject, pyqtSignal


# ══════════════════════════════════════════════════════════════
#  수평전개 차종 → CB 트래커 커스텀 필드명 매핑
# ══════════════════════════════════════════════════════════════
#  사양변경 페이지의 차종 컬럼 (VEHICLE_COLUMNS) 을 수평전개 트래커
#  (예: 과거차_수평전개, #8686086) 의 CB 필드명에 매핑.
#  값 ("미적용"/"적용"/"NA") 는 CB choice field 의 옵션 이름과 일치해야 함.
HZT_VEHICLE_FIELD_MAP = {
    "NQ5 PE":     "NQ5 PE",
    "MQ4i":       "MQ4i",
    "LX3":        "LX3",
    "JW":         "JW",
    "TK1":        "TK1",
    "LQ2":        "LQ2",
    "SP3":        "SP3",
    "KU FL":      "KU KL",     # ★ CB 트래커 측 필드명은 'KU KL'
    "SG2":        "SG2",
    "NX5(30Ah)":  "NX5_30Ah",
    "NX5(20Ah)":  "NX5_20Ah",
    "SX3":        "SX3",
    "Qy2i":       "Qy2i",
    "NQ6":        "NQ6",
}


def _save_hzt_debug_log(tracker_id: str, field_values: dict,
                        attempts: list, item_id: str = "") -> str:
    """HZT customFields 매핑이 minimal 폴백으로 빠졌을 때 진단 로그를 파일에
    저장한다. 반환값: 저장된 로그 파일 절대 경로 (실패 시 빈 문자열).
    사용자에게 보여줄 위치 안내용.
    """
    try:
        from integrations.codebeamer import _BASE
        log_path = os.path.join(_BASE, "hzt_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().isoformat(timespec="seconds")
            f.write(f"\n{'='*70}\n")
            f.write(f"[{ts}] HZT 차종 필드 매핑 실패 (minimal 폴백)\n")
            f.write(f"  트래커 ID  : {tracker_id}\n")
            if item_id:
                f.write(f"  생성된 이슈: #{item_id} (본문은 들어갔지만 필드는 비어있음)\n")
            f.write(f"  보내려한 필드:\n")
            for k, v in (field_values or {}).items():
                f.write(f"    - {k!s} = {v!s}\n")
            f.write(f"  시도된 payload 형식 (모두 거부됨):\n")
            for e in (attempts or []):
                f.write(f"    {e}\n")
            f.write(f"{'='*70}\n")
        return log_path
    except Exception:
        return ""


def build_hzt_description(data: dict) -> str:
    """변경점 dict 에서 수평전개 이슈 설명(description) 본문 텍스트 생성.

    포함:
      - 현상 / 분석 내용 / 대책 (입력된 것만)
      - JIRA 링크 (있으면 끝에)
    형식: 일반 텍스트 (CB 설명 필드는 PlainText 로 보냄 — 마크다운 미렌더).
    """
    sections = []
    for label, key in (("[현상]", "phenom"),
                       ("[분석 내용]", "analysis"),
                       ("[대책]", "action")):
        val = (data.get(key) or "").strip() if isinstance(data, dict) else ""
        if val:
            sections.append(f"{label}\n{val}")
    jira = (data.get("jira") or "").strip() if isinstance(data, dict) else ""
    if jira:
        sections.append(f"[JIRA]\n{jira}")
    return "\n\n".join(sections)


# ══════════════════════════════════════════════════════════════
#  공용 헬퍼 — HTML 본문의 이미지 마커를 <img> 절대 URL 로 치환
# ══════════════════════════════════════════════════════════════
def replace_image_markers_with_img(html: str, image_map: dict,
                                   base_url: str) -> str:
    """렌더된 HTML 본문 안의 이미지 마커
    (`<strong>📷 fname</strong> <em>(↓ 첨부/댓글 영역에 이미지 표시)</em>`)
    를 CB 절대 URL 의 `<img>` 태그 + 클릭 하이퍼링크로 치환.

    image_map : {filename: att_id} — 업로드 완료된 첨부의 매핑
    base_url  : CbFetcher.base_url (예: 'https://.../cb')

    **2중 안전망 구조**:
      - `<img src="absolute_url">` — sanitizer 가 통과시키면 이미지 인라인 표시
      - `<a href="absolute_url">📷 fname</a>` — sanitizer 가 <img> 를 제거해도
        클릭 가능한 텍스트 링크는 살아남아 새 창에서 이미지 보기 가능

    CB 인스턴스마다 body sanitizer 정책이 다르므로 (댓글은 <img> 통과시켜도
    본문은 차단하는 케이스 있음) 양쪽 모두 출력해 어느 한쪽은 살아남도록 한다.

    매칭 안 된 마커(att_id 미존재 등)는 원본 그대로 둔다 → 사용자는 첨부 영역
    에서 파일로 확인. 마커가 부분 일치라도 다른 파일과 충돌 방지를 위해
    파일명을 정규식 escape 후 정확히 매칭한다.
    """
    if not html or not image_map:
        return html
    out = html
    for fname, att_id in image_map.items():
        if not att_id or not fname:
            continue
        url = f"{base_url}/api/v3/attachments/{att_id}/content"
        # 두 가지 변형 — 메인 캡션 있는 마커, 또는 단독 마커
        pattern = (
            r'<strong>📷\s+' + re.escape(fname) + r'</strong>'
            r'(?:\s*<em>[^<]*</em>)?'
        )
        fname_esc = _html.escape(fname)
        # <img> + <a> 묶음 — <img> 차단돼도 <a> 링크는 남도록
        replacement = (
            f'<img src="{url}" alt="{fname_esc}" '
            f'style="max-width:720px;border:1px solid #CBD5E1;'
            f'border-radius:6px;display:block;margin:8px 0;" />'
            f'<br>'
            f'<a href="{url}" target="_blank" '
            f'style="color:#1D4ED8;text-decoration:underline;font-weight:600;">'
            f'📷 {fname_esc} — 클릭하여 새 창에서 열기'
            f'</a>'
        )
        out = re.sub(pattern, replacement, out)
    return out


class CbUploadWorker(QObject):
    """새 이슈 생성 + 첨부 업로드 워커."""
    progress = pyqtSignal(str)
    # 완료 시 dict: {'item_id': str, 'url': str}
    done     = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, fetcher, tracker_id: str,
                 summary: str, description_md: str, project_name: str,
                 attach_md: bool = True, attach_html: bool = True,
                 parent_item_id: str = "",
                 extra_attachments: list = None,
                 hzt_tracker_id: str = "",
                 hzt_state: dict = None,
                 hzt_title: str = "",
                 hzt_jira_link: str = "",
                 hzt_body: str = "",
                 hzt_extra_fields: dict = None,
                 main_is_hzt: bool = False):
        super().__init__()
        self.fetcher           = fetcher
        self.tracker_id        = str(tracker_id or "").strip()
        self.summary           = summary or "SW 배포 파이프라인"
        self.description_md    = description_md or ""
        self.project_name      = (project_name or "AIreview").strip()
        self.attach_md         = bool(attach_md)
        self.attach_html       = bool(attach_html)
        self.parent_item_id    = str(parent_item_id or "").strip()
        # 사용자 첨부 파일 — 이슈 생성 후 add_attachment 로 업로드
        self.extra_attachments = [p for p in (extra_attachments or []) if p]
        # 수평전개 동기 — hzt_tracker_id 가 있을 때만 추가 이슈 생성
        self.hzt_tracker_id    = str(hzt_tracker_id or "").strip()
        self.hzt_state         = dict(hzt_state or {})
        self.hzt_title         = (hzt_title or self.summary).strip()
        self.hzt_jira_link     = (hzt_jira_link or "").strip()
        self.hzt_body          = (hzt_body or "")
        # HZT 추가 텍스트 필드 — {CB_필드명: 값} dict (발생시점/고객OPEN 등)
        self.hzt_extra_fields  = dict(hzt_extra_fields or {})
        # 메인 트래커가 곧 수평전개 트래커인 모드 — 사양변경/수평전개 탭에서 True.
        # True 면 메인 생성 시 create_item 대신 create_hzt_item 을 호출해서
        # 차종/JIRA_LINK/JIRA_URL 필드까지 한 번에 매핑한다.
        self.main_is_hzt       = bool(main_is_hzt)

    def run(self):
        try:
            self.progress.emit("🔐  Codebeamer 로그인 중...")
            # 세션 미리 확보 (실패 시 RuntimeError 던짐)
            self.fetcher._get_session()

            # ── 상위 이슈 링크를 본문 최상단에 prepend (있을 때만) ──
            # CB API 가 PATCH/PUT 미지원 등으로 실제 parent 연결에 실패하더라도
            # 본문 상단의 텍스트 링크로 시각적 추적이 가능하도록 보장한다.
            body_md = self.description_md
            if self.parent_item_id:
                parent_url = f"{self.fetcher.base_url}/issue/{self.parent_item_id}"
                parent_link_md = (
                    f"> 📎 **상위 항목**: "
                    f"[#{self.parent_item_id}]({parent_url})\n\n---\n\n"
                )
                body_md = parent_link_md + body_md

            # ── 사전 업로드: 이미지가 있고 상위 이슈가 지정됐으면 ─────
            # 새 이슈 생성 전에 상위 이슈에 이미지를 먼저 첨부해 절대 URL 을
            # 확보. 이 CB 는 PATCH/PUT 미지원이라 이슈 생성 후 본문 갱신이
            # 불가 → 생성 시점에 이미 <img src="absolute_url"> 를 박는 것이
            # 본문 인라인 표시의 사실상 유일한 방법.
            pre_upload_map: dict = {}   # filename → att_id (parent 첨부)
            _IMG_EXTS_PRE = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
            if self.parent_item_id and self.extra_attachments:
                img_atts_for_pre = [
                    p for p in self.extra_attachments
                    if p and os.path.exists(p)
                    and os.path.splitext(p)[1].lower() in _IMG_EXTS_PRE]
                if img_atts_for_pre:
                    self.progress.emit(
                        f"⬆  본문 인라인용 사전 업로드 "
                        f"({len(img_atts_for_pre)}개 이미지 → 상위 "
                        f"#{self.parent_item_id})...")
                for p in img_atts_for_pre:
                    fname = os.path.basename(p)
                    try:
                        resp_pre = self.fetcher.add_attachment(
                            self.parent_item_id, p) or {}
                        att_id_pre = (
                            str(resp_pre.get("id") or
                                resp_pre.get("attachmentId") or
                                resp_pre.get("attachment_id") or "").strip())
                        if att_id_pre:
                            pre_upload_map[fname] = att_id_pre
                    except Exception as ae:
                        self.progress.emit(
                            f"⚠  사전 업로드 실패 ({fname}): {str(ae)[:80]}")

            # CB 본문은 HTML 로 보냄 — 마크다운 표/헤더가 깔끔하게 렌더링됨.
            # CB sanitizer 가 <style> 블록을 제거하므로 인라인 style 속성으로
            # 변환해서 시각 요소가 살아남도록 한다 (_inline_styles_for_cb).
            try:
                from view.ui_md import _md_to_html, _inline_styles_for_cb
                description_html = _inline_styles_for_cb(_md_to_html(body_md))
            except Exception:
                # 변환 실패 시 마크다운 원문을 그대로 보냄 (api 가 PlainText 로 폴백)
                description_html = body_md

            # 사전 업로드된 이미지가 있으면 본문 HTML 의 마커를 <img> 로
            # 미리 치환 → 새 이슈는 생성 시점부터 이미지 인라인 표시.
            if pre_upload_map:
                description_html = replace_image_markers_with_img(
                    description_html, pre_upload_map,
                    self.fetcher.base_url)

            # ── 1) 메인 이슈를 먼저 생성 ─────────────────────────
            # 흐름: 메인 → HZT 방향. CB 가 PATCH/PUT 미지원이라 사후 갱신 불가
            # → HZT 를 메인 이후에 만들면서 '연관 사양변경' 필드에 메인 ID 박음.
            # 메인 이슈 본문에는 수평전개 링크가 안 들어감 (반대방향이라 비움).
            if self.parent_item_id:
                self.progress.emit(
                    f"📝  메인 이슈 생성 중 (상위 #{self.parent_item_id})...")
            else:
                self.progress.emit("📝  메인 이슈 생성 중...")

            if self.main_is_hzt:
                # 사양변경/수평전개 탭 등록 — 메인 트래커가 곧 수평전개 트래커.
                # create_hzt_item 으로 차종 + JIRA_LINK/URL + 추가 필드까지
                # 한 번에 매핑. description 은 HTML 본문으로 송신.
                field_values = {}
                for ui_vehicle, cb_field in HZT_VEHICLE_FIELD_MAP.items():
                    raw = self.hzt_state.get(ui_vehicle, "미적용")
                    if isinstance(raw, bool):
                        raw = "적용" if raw else "미적용"
                    field_values[cb_field] = str(raw)
                # 추가 텍스트 필드 (발생시점/고객OPEN 등) — 빈 값은 스킵
                for cb_fname, raw_val in self.hzt_extra_fields.items():
                    sval = str(raw_val or "").strip()
                    if sval:
                        field_values[cb_fname] = sval
                resp = self.fetcher.create_hzt_item(
                    self.tracker_id, self.summary,
                    self.hzt_jira_link, field_values,
                    description=description_html,
                    description_format="Html",
                    parent_item_id=self.parent_item_id)
            else:
                resp = self.fetcher.create_item(
                    self.tracker_id, self.summary, description_html,
                    description_format="Html",
                    parent_item_id=self.parent_item_id,
                    custom_fields=None)
            target_id = str(resp.get("id") or resp.get("itemId") or "")
            if not target_id:
                raise RuntimeError(
                    f"이슈 ID 응답 누락: {str(resp)[:200]}")
            if self.main_is_hzt and resp.get("_hzt_minimal_only"):
                # 차종 필드 매핑이 안 됨 — 진단 로그 파일에 저장
                log_path = _save_hzt_debug_log(
                    self.tracker_id,
                    resp.get("_hzt_field_values") or {},
                    resp.get("_hzt_attempts") or [],
                    item_id=target_id)
                if log_path:
                    self.progress.emit(
                        f"⚠  메인 이슈 #{target_id} 생성됐지만 차종 매핑 실패 — "
                        f"진단 로그: {log_path}")
                else:
                    self.progress.emit(
                        f"⚠  메인 이슈 #{target_id} 생성됐지만 "
                        f"차종 필드 매핑 실패 (CB schema 불일치)")
            else:
                self.progress.emit(f"✓  메인 이슈 #{target_id} 생성 완료")

            # ── 1.5) 수평전개 이슈 생성 + '연관 사양변경' = 메인 ID ──
            # 메인 ID 가 확보됐으므로 HZT 생성 시점에 customField 로 박는다.
            hzt_id_for_link = ""
            hzt_url = ""
            hzt_minimal = False
            if self.hzt_tracker_id:
                field_values = {}
                for ui_vehicle, cb_field in HZT_VEHICLE_FIELD_MAP.items():
                    raw = self.hzt_state.get(ui_vehicle, "미적용")
                    if isinstance(raw, bool):
                        raw = "적용" if raw else "미적용"
                    field_values[cb_field] = str(raw)
                # ★ HZT 의 '연관 사양변경' 필드에 메인 이슈 ID 박기 (HZT → 메인)
                if target_id:
                    field_values["연관 사양변경"] = target_id
                # ★ 추가 텍스트 필드 (발생시점/고객OPEN 등) — 빈 값은 스킵
                for cb_fname, raw_val in self.hzt_extra_fields.items():
                    sval = str(raw_val or "").strip()
                    if sval:
                        field_values[cb_fname] = sval
                self.progress.emit(
                    f"📋  수평전개 트래커 #{self.hzt_tracker_id} 에 이슈 생성 중 "
                    f"(연관 사양변경 = 메인 #{target_id})...")
                try:
                    hzt_resp = self.fetcher.create_hzt_item(
                        self.hzt_tracker_id, self.hzt_title,
                        self.hzt_jira_link, field_values,
                        description=self.hzt_body)
                    hzt_id_for_link = str(
                        hzt_resp.get("id") or
                        hzt_resp.get("itemId") or "").strip()
                    if hzt_id_for_link:
                        hzt_url = (
                            f"{self.fetcher.base_url}/issue/{hzt_id_for_link}")
                        hzt_minimal = bool(hzt_resp.get("_hzt_minimal_only"))
                        # 생성 후 '연관 사양변경' 필드 검증
                        related_ok = False
                        try:
                            hzt_check = self.fetcher.fetch_item_detail(
                                hzt_id_for_link)
                            cfs_h = hzt_check.get("customFields") or []
                            for cf in cfs_h:
                                if (isinstance(cf, dict) and
                                        (cf.get("name") or "").strip()
                                        == "연관 사양변경"):
                                    vals_h = cf.get("values") or cf.get("value")
                                    if vals_h:
                                        related_ok = True
                                        import sys as _sys
                                        print(
                                            f"[VERIFY] HZT '연관 사양변경' "
                                            f"저장됨: {cf!r}",
                                            file=_sys.stderr, flush=True)
                                    break
                        except Exception:
                            related_ok = None
                        if hzt_minimal:
                            log_path = _save_hzt_debug_log(
                                self.hzt_tracker_id,
                                hzt_resp.get("_hzt_field_values") or field_values,
                                hzt_resp.get("_hzt_attempts") or [],
                                item_id=hzt_id_for_link)
                            if log_path:
                                self.progress.emit(
                                    f"⚠  수평전개 이슈 #{hzt_id_for_link} 생성됐지만 "
                                    f"차종 매핑 실패 — 진단 로그: {log_path}")
                            else:
                                self.progress.emit(
                                    f"⚠  수평전개 이슈 #{hzt_id_for_link} 생성됐지만 "
                                    f"차종 필드 매핑 실패")
                        elif related_ok is True:
                            self.progress.emit(
                                f"✓  수평전개 #{hzt_id_for_link} '연관 사양변경' "
                                f"→ 메인 #{target_id} 검증 완료 ({hzt_url})")
                        elif related_ok is False:
                            self.progress.emit(
                                f"⚠  수평전개 #{hzt_id_for_link} 생성됐지만 "
                                f"'연관 사양변경' 빈 상태 — 수동 연결 필요")
                        else:
                            self.progress.emit(
                                f"ℹ  수평전개 #{hzt_id_for_link} 생성됨 "
                                f"(연관 사양변경 검증 불가) ({hzt_url})")
                except Exception as he:
                    self.progress.emit(
                        f"❌  수평전개 이슈 생성 실패 — 메인은 정상: "
                        f"{str(he)[:200]}")

            if self.parent_item_id:
                if resp.get("parent_link_ok"):
                    self.progress.emit(
                        f"✓  상위 #{self.parent_item_id} CB 트리 연결됨")
                else:
                    self.progress.emit(
                        f"⚠  CB API 가 상위 연결 미지원 — 본문 상단의 "
                        f"링크로 대체 표시됩니다")

            # ── 2) MD/HTML 자동 첨부 — 비활성화 (사용자 요청) ─────
            # 본문 description 에 이미 동일 내용이 들어가므로 백업 파일 불필요.
            # 사용자가 직접 추가한 첨부 파일은 다음 블록에서 처리.

            # ── 3) 사용자 첨부 파일 ───────────────────────────
            # 실패해도 이슈 자체는 성공으로 처리 (메시지만 progress 로 emit)
            # 이미지 첨부의 경우 응답 JSON 에서 attachment ID 를 추출해 후속
            # 코멘트에서 절대 URL 로 인라인 표시.
            uploaded_images: list[dict] = []   # {'name','att_id'} 리스트
            _IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
            for i, path in enumerate(self.extra_attachments, start=1):
                if not path or not os.path.exists(path):
                    self.progress.emit(
                        f"⚠  첨부 스킵 (파일 없음): {os.path.basename(path or '')}")
                    continue
                fname = os.path.basename(path)
                self.progress.emit(
                    f"📎  사용자 첨부 {i}/{len(self.extra_attachments)} "
                    f"({fname})...")
                try:
                    resp = self.fetcher.add_attachment(target_id, path) or {}
                    if os.path.splitext(fname)[1].lower() in _IMG_EXTS:
                        # CB 응답에서 ID 추출 — 버전별 키 이름 차이 흡수
                        att_id = (
                            str(resp.get("id") or resp.get("attachmentId") or
                                resp.get("attachment_id") or "").strip())
                        uploaded_images.append({
                            "name": fname, "att_id": att_id})
                except Exception as ae:
                    self.progress.emit(
                        f"⚠  첨부 실패 ({fname}): {str(ae)[:120]}")

            # ── 3.5) 본문 description 업데이트 시도 — 이미지 인라인 임베드
            # 사전 업로드(parent)로 이미 본문에 <img> 가 들어간 경우에는 스킵.
            # 사전 업로드가 없었던 경우(parent 미지정 등)만 PATCH/PUT 시도 —
            # 대부분의 CB 인스턴스에선 막혀 있어 실패 가능성 높음 → 댓글 폴백.
            inline_in_body = bool(pre_upload_map)
            if inline_in_body:
                self.progress.emit(
                    "✓  본문에 이미지 인라인 임베드 성공 (사전 업로드)")
            else:
                image_map = {rec["name"]: rec["att_id"]
                             for rec in uploaded_images if rec["att_id"]}
                if image_map:
                    base = self.fetcher.base_url
                    new_desc_html = replace_image_markers_with_img(
                        description_html, image_map, base)
                    if new_desc_html != description_html:
                        first_att = next(iter(image_map.values()))
                        verify_marker = f"attachments/{first_att}/content"
                        self.progress.emit(
                            "✏  본문에 이미지 인라인 임베드 시도 중...")
                        try:
                            inline_in_body = (
                                self.fetcher.try_update_description(
                                    target_id, new_desc_html,
                                    description_format="Html",
                                    verify_marker=verify_marker))
                        except Exception as ue:
                            self.progress.emit(
                                f"⚠  본문 업데이트 예외 (계속 진행): "
                                f"{str(ue)[:120]}")
                            inline_in_body = False
                        if inline_in_body:
                            self.progress.emit(
                                "✓  본문에 이미지 인라인 임베드 성공 (사후)")
                        else:
                            self.progress.emit(
                                "⚠  본문 업데이트 미지원 — 댓글로 이미지 표시")

            # ── 4) 이미지 인라인 표시용 코멘트 (본문 업데이트 실패 시 폴백) ──
            # CB sanitizer 가 본문 <img src="data:..."> / 상대 경로 양쪽 모두
            # 차단해 본문 인라인 표시는 불가. 첨부 업로드 후 CB-native 절대
            # URL 로 HTML 코멘트를 보내면 sanitizer 가 같은 도메인 URL 은
            # 통과시킨다.
            # attachment ID 미응답 시엔 위키 폴백 (`!filename!`).
            if uploaded_images and not inline_in_body:
                self.progress.emit(
                    f"💬  이미지 코멘트 추가 중 ({len(uploaded_images)}개)...")
                base = self.fetcher.base_url
                # HTML 코멘트 우선 — ID 가 있는 항목만 절대 URL 임베드
                html_parts = ['<p><b>📷 페이스트된 이미지</b></p>']
                wiki_fallbacks: list[str] = []
                for rec in uploaded_images:
                    name = rec["name"]; att_id = rec["att_id"]
                    if att_id:
                        # v3 API content endpoint — base_url 이 이미 .../cb 를
                        # 포함하므로 여기서 /cb 를 추가로 붙이면 안 된다
                        # (이전 코드는 /cb/cb/ 중복으로 깨진 URL 생성).
                        url = f"{base}/api/v3/attachments/{att_id}/content"
                        html_parts.append(
                            f'<p><img src="{url}" alt="{name}" '
                            f'style="max-width:720px;border:1px solid #CBD5E1;'
                            f'border-radius:6px;" /></p>')
                    else:
                        wiki_fallbacks.append(name)
                html_body = "\n".join(html_parts)
                try:
                    self.fetcher.add_comment(
                        target_id, html_body, comment_format="Html")
                except Exception as ce:
                    self.progress.emit(
                        f"⚠  HTML 이미지 코멘트 실패: {str(ce)[:120]}")
                # ID 못 뽑은 항목은 위키 폴백으로 별도 코멘트
                if wiki_fallbacks:
                    wiki_lines = ["📷 페이스트된 이미지 (위키 폴백)", ""]
                    for name in wiki_fallbacks:
                        wiki_lines += [f"!{name}!", ""]
                    try:
                        self.fetcher.add_comment(
                            target_id, "\n".join(wiki_lines).rstrip(),
                            comment_format="Wiki")
                    except Exception:
                        pass

            # 수평전개 이슈는 이미 위에서 생성 + 메인에 링크됨 (단계 0.5)

            base = self.fetcher.base_url
            self.done.emit({
                "item_id": target_id,
                "url":     f"{base}/issue/{target_id}",
                "hzt_url": hzt_url,
            })
        except Exception as e:
            self.error.emit(str(e))

