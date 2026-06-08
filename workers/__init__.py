"""workers — Qt QThread 기반 백그라운드 작업자.

  diff_worker.py    : 폴더 DIFF 추출 (폴더 스캔 + 파일별 변경점 분석,
                      진행률 시그널 emit) — Claude API 무관
  prompts_worker.py : Claude API 호출 워커 (ReviewWorker)
                      — 프롬프트 본문은 core.worker 에서 import
"""
