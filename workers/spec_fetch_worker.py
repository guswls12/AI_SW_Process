"""spec_fetch_worker.py — ① 사양 변경 페이지의 트래커 불러오기 워커.

CB 트래커에 등록된 모든 이슈를 가져와 각 이슈의 description 까지 fetch 한
다음, spec_md_parser.classify_items() 로 이슈 / 사양변경 / 수평전개 세
카테고리로 분류해 컨트롤러에 전달한다.

Signals:
  progress(str)  : 상태 메시지 ("로그인 / 트래커 조회 / 본문 다운로드 N/M")
  done(dict)     : {"issue": [parsed,...], "spec": [...], "hzt": [...], "other": [...]}
  error(str)     : 실패 사유
"""

from PyQt6.QtCore import QObject, pyqtSignal

from integrations.codebeamer.api import CbFetcher
from core.spec_md_parser import classify_items


class SpecFetchWorker(QObject):
    progress = pyqtSignal(str)
    done     = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, fetcher: CbFetcher, tracker_id: str):
        super().__init__()
        self.fetcher    = fetcher
        self.tracker_id = str(tracker_id or "").strip()

    def run(self):
        try:
            if not self.tracker_id:
                self.error.emit("트래커 ID 가 비어있습니다.")
                return

            # 1) 로그인 + 트래커 항목 목록
            self.progress.emit("🔐  CB 로그인 확인 중...")
            self.fetcher._get_session()

            self.progress.emit(
                f"📥  트래커 #{self.tracker_id} 항목 목록 조회...")
            items = self.fetcher.fetch_tracker_items(self.tracker_id) or []
            total = len(items)
            if total == 0:
                # 빈 트래커 — 그냥 빈 결과 반환
                self.done.emit({"issue": [], "spec": [], "hzt": [], "other": []})
                return

            # 2) 각 항목의 상세 (description) 조회
            enriched: list[dict] = []
            for i, it in enumerate(items, start=1):
                cid = str(it.get("id") or "").strip()
                if not cid:
                    continue
                self.progress.emit(
                    f"📄  본문 다운로드 [{i}/{total}] — #{cid}")
                detail = self.fetcher.fetch_item_detail(cid) or {}
                # detail 의 description / descriptionPlain 어느 쪽이든 사용
                desc = (detail.get("description")
                        or detail.get("descriptionPlain")
                        or it.get("description")
                        or "")
                enriched.append({
                    "id":          cid,
                    "name":        detail.get("name") or it.get("name") or "",
                    "description": desc,
                })

            # 3) 카테고리 분류 (이슈 / 사양변경 / 수평전개 / other)
            self.progress.emit("🗂  카테고리 분류 중...")
            classified = classify_items(enriched)
            self.done.emit(classified)
        except Exception as e:
            self.error.emit(str(e))
