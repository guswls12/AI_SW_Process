"""cb_bulk_upload_worker.py — 변경점 묶음 일괄 등록 워커.

여러 변경점을 한 번에 같은 트래커(같은 상위 이슈) 에 새 이슈로 순차 등록.
각 항목은 독립적으로 처리되며, 실패해도 다음 항목으로 진행.
"""

import os
import re
import datetime
import tempfile

from PyQt6.QtCore import QObject, pyqtSignal


class CbBulkUploadWorker(QObject):
    """변경점 N개 일괄 등록 워커.

    items: list of dict — 각 항목은 다음 키를 가짐:
        - idx:         int       (1-based 변경점 번호 — 진행 메시지용)
        - title:       str       (이슈 제목)
        - summary:     str       (CB 이슈 요약/제목 — 보통 title 그대로)
        - body_md:     str       (이슈 본문 — 프로젝트 헤더 + 변경점 마크다운)
        - attachments: list[str] (옵션 — 사용자 첨부 파일 경로 리스트)
    """
    progress = pyqtSignal(str)
    # 완료 시 dict: {'results': [{'idx','title','item_id','url'}, ...],
    #                'failures': [{'idx','title','error'}, ...]}
    done     = pyqtSignal(dict)
    # 치명적 에러 (로그인 실패 등) — 루프 시작 전 중단
    error    = pyqtSignal(str)

    def __init__(self, fetcher, tracker_id: str, items: list,
                 project_name: str = "AIreview",
                 attach_md: bool = False, attach_html: bool = False,
                 parent_item_id: str = "",
                 hzt_tracker_id: str = "",
                 main_is_hzt: bool = False):
        super().__init__()
        self.fetcher        = fetcher
        self.tracker_id     = str(tracker_id or "").strip()
        self.items          = items or []
        self.project_name   = (project_name or "AIreview").strip()
        self.attach_md      = bool(attach_md)
        self.attach_html    = bool(attach_html)
        self.parent_item_id = str(parent_item_id or "").strip()
        # 수평전개 동기 — 비어있지 않으면 각 변경점마다 추가 수평전개 이슈 생성
        self.hzt_tracker_id = str(hzt_tracker_id or "").strip()
        # 메인 트래커에 차종 필드가 있으면 자동 매핑 (없으면 minimal 폴백)
        self.main_is_hzt    = bool(main_is_hzt)

    def run(self):
        try:
            self.progress.emit("🔐  Codebeamer 로그인 중...")
            self.fetcher._get_session()
        except Exception as e:
            self.error.emit(str(e))
            return

        results: list[dict] = []
        failures: list[dict] = []
        total = len(self.items)
        for i, item in enumerate(self.items, start=1):
            idx     = item.get("idx", i)
            title   = item.get("title", "") or "untitled"
            summary = item.get("summary", title)
            body_md = item.get("body_md", "")

            self.progress.emit(
                f"📝  변경점 {i}/{total} 「{title}」 등록 중...")

            try:
                # 상위 이슈 링크를 본문 최상단에 prepend (있을 때만)
                if self.parent_item_id:
                    parent_url = (
                        f"{self.fetcher.base_url}/issue/{self.parent_item_id}")
                    parent_link_md = (
                        f"> 📎 **상위 항목**: "
                        f"[#{self.parent_item_id}]({parent_url})\n\n---\n\n"
                    )
                    body_with_parent = parent_link_md + body_md
                else:
                    body_with_parent = body_md

                # ── 사전 업로드: 이미지가 있고 상위 이슈가 지정됐으면 ─────
                # 새 이슈 생성 전에 상위 이슈에 이미지를 먼저 첨부해 절대 URL 을
                # 확보. 이 CB 는 PATCH/PUT 미지원이라 이슈 생성 후 본문 갱신이
                # 불가 → 생성 시점에 이미 <img src="absolute_url"> 를 박는 것이
                # 본문 인라인 표시의 사실상 유일한 방법.
                # CB sanitizer 는 same-domain 절대 URL <img> 는 통과시킴.
                pre_upload_map: dict = {}   # filename → att_id (parent 첨부)
                _IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
                if self.parent_item_id:
                    user_atts_for_pre = [
                        p for p in (item.get("attachments") or []) if p]
                    img_atts_for_pre = [
                        p for p in user_atts_for_pre
                        if os.path.exists(p)
                        and os.path.splitext(p)[1].lower() in _IMG_EXTS]
                    if img_atts_for_pre:
                        self.progress.emit(
                            f"⬆  변경점 {i}/{total} 본문 인라인용 사전 업로드 "
                            f"({len(img_atts_for_pre)}개 이미지 → 상위 "
                            f"#{self.parent_item_id})...")
                    for p in img_atts_for_pre:
                        fname = os.path.basename(p)
                        try:
                            resp = self.fetcher.add_attachment(
                                self.parent_item_id, p) or {}
                            att_id = (
                                str(resp.get("id") or
                                    resp.get("attachmentId") or
                                    resp.get("attachment_id") or "").strip())
                            if att_id:
                                pre_upload_map[fname] = att_id
                        except Exception as ae:
                            self.progress.emit(
                                f"⚠  변경점 {i}/{total} 사전 업로드 실패 "
                                f"({fname}): {str(ae)[:80]}")

                # 마크다운 → HTML 변환 (CB 본문은 HTML 로 보냄)
                try:
                    from view.ui_md import _md_to_html, _inline_styles_for_cb
                    description_html = _inline_styles_for_cb(
                        _md_to_html(body_with_parent))
                except Exception:
                    description_html = body_with_parent

                # 사전 업로드된 이미지가 있으면 본문 HTML 의 마커를 <img> 로
                # 미리 치환 → 새 이슈는 생성 시점부터 이미지 인라인 표시.
                if pre_upload_map:
                    from workers.cb_upload_worker import (
                        replace_image_markers_with_img)
                    description_html = replace_image_markers_with_img(
                        description_html, pre_upload_map,
                        self.fetcher.base_url)

                # ── 메인 이슈 먼저 생성 ───────────────────────────
                # main_is_hzt=True 면 메인 트래커가 곧 수평전개 트래커일 수 있어
                # create_hzt_item 으로 차종/JIRA_LINK/JIRA_URL 매핑 시도. 매핑이
                # 실패하면 minimal 폴백으로 본문만 들어간다 (손해 없음).
                if self.main_is_hzt:
                    from workers.cb_upload_worker import HZT_VEHICLE_FIELD_MAP
                    main_fv = {}
                    main_hzt_state = item.get("hzt_state") or {}
                    for ui_vehicle, cb_field in HZT_VEHICLE_FIELD_MAP.items():
                        raw = main_hzt_state.get(ui_vehicle, "미적용")
                        if isinstance(raw, bool):
                            raw = "적용" if raw else "미적용"
                        main_fv[cb_field] = str(raw)
                    # 발생시점/고객OPEN 등 추가 텍스트 필드 (빈 값은 스킵)
                    for cb_fname, raw_val in (
                            item.get("hzt_extra_fields") or {}).items():
                        sval = str(raw_val or "").strip()
                        if sval:
                            main_fv[cb_fname] = sval
                    resp = self.fetcher.create_hzt_item(
                        self.tracker_id, summary,
                        item.get("jira_link") or "", main_fv,
                        description=description_html,
                        description_format="Html",
                        parent_item_id=self.parent_item_id)
                else:
                    resp = self.fetcher.create_item(
                        self.tracker_id, summary, description_html,
                        description_format="Html",
                        parent_item_id=self.parent_item_id,
                        custom_fields=None)
                target_id = str(
                    resp.get("id") or resp.get("itemId") or "").strip()
                if not target_id:
                    raise RuntimeError(
                        f"이슈 ID 응답 누락: {str(resp)[:200]}")
                if self.main_is_hzt and resp.get("_hzt_minimal_only"):
                    self.progress.emit(
                        f"⚠  변경점 {i}/{total} 메인 이슈 #{target_id} 생성됐지만 "
                        f"차종 필드 매핑 실패")
                else:
                    self.progress.emit(
                        f"✓  변경점 {i}/{total} 메인 이슈 #{target_id} 생성 완료")

                # ── 수평전개 이슈 생성 + '연관 사양변경' = 메인 ID ──
                hzt_id_for_link = ""
                hzt_url = ""
                hzt_minimal = False
                hzt_state = item.get("hzt_state") or {}
                if self.hzt_tracker_id:
                    from workers.cb_upload_worker import HZT_VEHICLE_FIELD_MAP
                    field_values = {}
                    for ui_vehicle, cb_field in HZT_VEHICLE_FIELD_MAP.items():
                        raw = hzt_state.get(ui_vehicle, "미적용")
                        if isinstance(raw, bool):
                            raw = "적용" if raw else "미적용"
                        field_values[cb_field] = str(raw)
                    # ★ HZT '연관 사양변경' = 메인 ID
                    if target_id:
                        field_values["연관 사양변경"] = target_id
                    # ★ 추가 텍스트 필드 (발생시점/고객OPEN 등)
                    for cb_fname, raw_val in (
                            item.get("hzt_extra_fields") or {}).items():
                        sval = str(raw_val or "").strip()
                        if sval:
                            field_values[cb_fname] = sval
                    self.progress.emit(
                        f"📋  변경점 {i}/{total} 수평전개 이슈 생성 중 "
                        f"(연관 사양변경 = 메인 #{target_id})...")
                    try:
                        jira_link = (item.get("jira_link") or "").strip()
                        hzt_body  = (item.get("hzt_body")  or "")
                        hzt_resp = self.fetcher.create_hzt_item(
                            self.hzt_tracker_id, title, jira_link,
                            field_values, description=hzt_body)
                        hzt_id_for_link = str(
                            hzt_resp.get("id") or
                            hzt_resp.get("itemId") or "").strip()
                        if hzt_id_for_link:
                            hzt_url = (
                                f"{self.fetcher.base_url}/issue/"
                                f"{hzt_id_for_link}")
                            hzt_minimal = bool(
                                hzt_resp.get("_hzt_minimal_only"))
                            # '연관 사양변경' 필드 검증
                            related_ok_b = False
                            try:
                                hzt_chk = self.fetcher.fetch_item_detail(
                                    hzt_id_for_link)
                                for cf in (hzt_chk.get("customFields") or []):
                                    if (isinstance(cf, dict) and
                                            (cf.get("name") or "").strip()
                                            == "연관 사양변경"):
                                        vals = cf.get("values") or cf.get("value")
                                        related_ok_b = bool(vals)
                                        break
                            except Exception:
                                related_ok_b = None
                            if hzt_minimal:
                                self.progress.emit(
                                    f"⚠  변경점 {i}/{total} 수평전개 이슈 "
                                    f"#{hzt_id_for_link} 생성됐지만 차종 필드 "
                                    f"매핑 실패")
                            elif related_ok_b is True:
                                self.progress.emit(
                                    f"✓  변경점 {i}/{total} 수평전개 "
                                    f"#{hzt_id_for_link} '연관 사양변경' → "
                                    f"메인 #{target_id} 검증 완료")
                            elif related_ok_b is False:
                                self.progress.emit(
                                    f"⚠  변경점 {i}/{total} 수평전개 "
                                    f"#{hzt_id_for_link} 생성됐지만 "
                                    f"'연관 사양변경' 빈 상태 — 수동 연결 필요")
                            else:
                                self.progress.emit(
                                    f"ℹ  변경점 {i}/{total} 수평전개 "
                                    f"#{hzt_id_for_link} 생성됨 (검증 불가)")
                    except Exception as he:
                        self.progress.emit(
                            f"❌  변경점 {i}/{total} 수평전개 이슈 "
                            f"생성 실패 — 메인은 정상: {str(he)[:160]}")

                # MD/HTML 자동 첨부 — 비활성화 (사용자 요청). 본문 description
                # 에 동일 내용이 이미 들어가므로 백업 파일 불필요.

                # 사용자 첨부 파일 (항목별) + 이미지 인라인 코멘트
                user_atts = [p for p in (item.get("attachments") or []) if p]
                uploaded_images: list[dict] = []
                _IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
                for j, path in enumerate(user_atts, start=1):
                    if not os.path.exists(path):
                        self.progress.emit(
                            f"⚠  변경점 {i}/{total} 첨부 스킵 (파일 없음): "
                            f"{os.path.basename(path)}")
                        continue
                    fname = os.path.basename(path)
                    self.progress.emit(
                        f"📎  변경점 {i}/{total} 첨부 {j}/{len(user_atts)} "
                        f"({fname})...")
                    try:
                        resp = self.fetcher.add_attachment(target_id, path) or {}
                        if os.path.splitext(fname)[1].lower() in _IMG_EXTS:
                            att_id = (
                                str(resp.get("id") or resp.get("attachmentId") or
                                    resp.get("attachment_id") or "").strip())
                            uploaded_images.append({
                                "name": fname, "att_id": att_id})
                    except Exception as ae:
                        self.progress.emit(
                            f"⚠  변경점 {i}/{total} 첨부 실패 "
                            f"({fname}): {str(ae)[:120]}")

                # ── 본문 description 업데이트 시도 — 이미지 인라인 임베드 ──
                # 사전 업로드(parent)로 이미 본문에 <img> 가 들어간 경우에는 스킵.
                # 사전 업로드가 없었던 경우(parent 미지정 등)만 시도 — 대부분의
                # CB 인스턴스에서 PATCH/PUT 가 막혀 있어 실패할 가능성이 높지만
                # 일부 인스턴스에선 동작.
                inline_in_body = bool(pre_upload_map)
                if inline_in_body:
                    self.progress.emit(
                        f"✓  변경점 {i}/{total} 본문에 이미지 인라인 "
                        f"임베드 성공 (사전 업로드)")
                else:
                    image_map = {rec["name"]: rec["att_id"]
                                 for rec in uploaded_images if rec["att_id"]}
                    if image_map:
                        from workers.cb_upload_worker import (
                            replace_image_markers_with_img)
                        new_desc_html = replace_image_markers_with_img(
                            description_html, image_map,
                            self.fetcher.base_url)
                        if new_desc_html != description_html:
                            first_att = next(iter(image_map.values()))
                            verify_marker = (
                                f"attachments/{first_att}/content")
                            self.progress.emit(
                                f"✏  변경점 {i}/{total} 본문에 이미지 "
                                f"인라인 임베드 시도...")
                            try:
                                inline_in_body = (
                                    self.fetcher.try_update_description(
                                        target_id, new_desc_html,
                                        description_format="Html",
                                        verify_marker=verify_marker))
                            except Exception as ue:
                                self.progress.emit(
                                    f"⚠  변경점 {i}/{total} 본문 업데이트 "
                                    f"예외 (계속 진행): {str(ue)[:120]}")
                                inline_in_body = False
                            if inline_in_body:
                                self.progress.emit(
                                    f"✓  변경점 {i}/{total} 본문에 이미지 "
                                    f"인라인 임베드 성공 (사후 업데이트)")
                            else:
                                self.progress.emit(
                                    f"⚠  변경점 {i}/{total} 본문 업데이트 "
                                    f"미지원 — 댓글로 이미지 표시")

                # 이미지 인라인 코멘트 — HTML + 절대 URL, 폴백 wiki
                # 본문 업데이트가 성공하면 스킵 (이미 본문에 이미지가 있음)
                if uploaded_images and not inline_in_body:
                    self.progress.emit(
                        f"💬  변경점 {i}/{total} 이미지 코멘트 "
                        f"({len(uploaded_images)}개)...")
                    base_url = self.fetcher.base_url
                    html_parts = ['<p><b>📷 페이스트된 이미지</b></p>']
                    wiki_fallbacks: list[str] = []
                    for rec in uploaded_images:
                        name = rec["name"]; att_id = rec["att_id"]
                        if att_id:
                            # base_url 이 이미 .../cb 포함 → 여기서 /cb 추가 X.
                            # (이전 코드는 /cb/cb/ 중복으로 깨진 URL 생성).
                            url = f"{base_url}/api/v3/attachments/{att_id}/content"
                            html_parts.append(
                                f'<p><img src="{url}" alt="{name}" '
                                f'style="max-width:720px;'
                                f'border:1px solid #CBD5E1;'
                                f'border-radius:6px;" /></p>')
                        else:
                            wiki_fallbacks.append(name)
                    try:
                        self.fetcher.add_comment(
                            target_id, "\n".join(html_parts),
                            comment_format="Html")
                    except Exception as ce:
                        self.progress.emit(
                            f"⚠  변경점 {i}/{total} HTML 코멘트 실패: "
                            f"{str(ce)[:120]}")
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

                # 수평전개 이슈는 위에서 메인 생성 전에 이미 만들었음 (단계 0.5)

                results.append({
                    "idx":     idx,
                    "title":   title,
                    "item_id": target_id,
                    "url":     f"{self.fetcher.base_url}/issue/{target_id}",
                    "hzt_url": hzt_url,
                })
            except Exception as e:
                failures.append({
                    "idx":   idx,
                    "title": title,
                    "error": str(e),
                })
                self.progress.emit(
                    f"❌  변경점 {i}/{total} 「{title}」 실패: {str(e)[:100]}")

        self.done.emit({"results": results, "failures": failures})

