"""cb_items_worker.py — 단순 트래커 이슈 목록 fetch 워커.

CbFetcher.fetch_tracker_items() 만 호출하는 가벼운 워커. 본문 (description)
은 가져오지 않으므로 ②③④/⑤⑥⑦ 페이지의 "이미 등록된 결과가 있는지" 확인용
으로 적합.

(전체 본문이 필요한 ① 페이지는 spec_fetch_worker.SpecFetchWorker 를 사용.)
"""

from PyQt6.QtCore import QObject, pyqtSignal

from integrations.codebeamer.api import CbFetcher


class CbItemsWorker(QObject):
    progress = pyqtSignal(str)
    done     = pyqtSignal(list)   # [{"id":..., "name":..., ...}, ...]
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
            self.progress.emit("🔐  CB 로그인 확인 중...")
            self.fetcher._get_session()
            self.progress.emit(
                f"📥  트래커 #{self.tracker_id} 이슈 목록 조회 중...")
            items = self.fetcher.fetch_tracker_items(self.tracker_id) or []
            self.done.emit(items)
        except Exception as e:
            self.error.emit(str(e))
