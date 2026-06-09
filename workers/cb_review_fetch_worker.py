"""cb_review_fetch_worker.py — ⑤ 정적 검증 / ⑦ 설계자 테스트 페이지 전용 fetch.

CB 트래커 안의 모든 이슈를 fetch + 각 이슈의:
  • 첨부 파일 존재 여부 (OK/NG 판단용)
  • 코멘트(리뷰 내용) 전체

를 가져와 페이지에 표시한다. 사용자가 파일을 직접 업로드하지 않고 CB 에
이미 올려둔 결과 + 리뷰 댓글만 확인하는 흐름.

Signals:
  progress(str)  : 상태 메시지
  done(dict)     : {
                    "tracker_id":    str,
                    "has_attachment": bool,   # 1개 이상 첨부 있으면 True
                    "total_attachments": int,
                    "items": [
                      {"id":..., "name":...,
                       "attachments": [...], "comments": [...]},
                      ...
                    ]
                  }
  error(str)     : 실패 사유
"""

from PyQt6.QtCore import QObject, pyqtSignal

from integrations.codebeamer.api import CbFetcher


class CbReviewFetchWorker(QObject):
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

            self.progress.emit("🔐  CB 로그인 확인 중...")
            self.fetcher._get_session()

            self.progress.emit(
                f"📥  트래커 #{self.tracker_id} 이슈 목록 조회 중...")
            items = self.fetcher.fetch_tracker_items(self.tracker_id) or []
            total = len(items)

            enriched: list[dict] = []
            total_atts = 0
            for i, it in enumerate(items, start=1):
                cid = str(it.get("id") or "").strip()
                if not cid:
                    continue
                name = it.get("name") or it.get("summary") or ""
                self.progress.emit(
                    f"📎  첨부/댓글 조회 [{i}/{total}] — #{cid}")
                atts = self.fetcher.fetch_item_attachments(cid)
                cmts = self.fetcher.fetch_item_comments(cid)
                total_atts += len(atts or [])
                enriched.append({
                    "id":          cid,
                    "name":        name,
                    "attachments": atts or [],
                    "comments":    cmts or [],
                })

            self.done.emit({
                "tracker_id":        self.tracker_id,
                "has_attachment":    total_atts > 0,
                "total_attachments": total_atts,
                "items":             enriched,
            })
        except Exception as e:
            self.error.emit(str(e))
