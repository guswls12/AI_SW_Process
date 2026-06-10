## 🔧 ILCU 이슈

### [741622] 요구사항 미확인/오해석
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 1건

#### [615526] [ILCU_6] ME1 FOD 외 지역 USM QR코드 뜨는 문제
- **상태**: New
- **필드**:
  - **2차 기능분류**: 옵션 조건 누락
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사항 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: 문제점
 ME1 FOD 외 지역 USM QR코드 뜨는 문제
원인
 \\
문제점 개선
 ~- DWLOpt 시그널 출력 조건 변경\\
\\
▶ 변경 전) \\
DWL 옵션이 1인 경우~, DWLOpt == 1 또는 2 출력\\
\\
▶ 변경 후)\\
~- 국가 사양이 0~2이고~, DWL 옵션이 1인 경우~, DWLOpt == 1 또는 2 출력\\
~- 0~2를 제외한 나머지 국가 사양은 DWL 옵션과 무관하게 DWLOpt == 0으로 출력

### [741620] 변경점 반영 미흡
- **상태**: New
- **설명**: (없음)

### [741260] 환경 조건 고려 미흡
- **상태**: New
- **설명**: (없음)

### [741258] 임계값 설계 미흡
- **상태**: New
- **설명**: (없음)

### [741256] 예외 입력/신호 처리 미흡
- **상태**: New
- **설명**: (없음)

### [741254] 로직 예외 흐름 고려 미흡
- **상태**: New
- **설명**: (없음)

### [741252] 메모리 Task 설계 미흡
- **상태**: New
- **설명**: (없음)

### [741250] 동작 우선순위 설계 오류
- **상태**: New
- **설명**: (없음)

### [741248] 인터럽트 설계 오류
- **상태**: New
- **설명**: (없음)

### [741246] 응답 시간 설계 오류
- **상태**: New
- **설명**: (없음)

### [741244] 공유 자원 설계 오류
- **상태**: New
- **설명**: (없음)

### [741242] 시스템 에러 감지 미흡
- **상태**: New
- **설명**: (없음)

### [741240] 제어기간 연계 고려 미흡
- **상태**: New
- **설명**: (없음)

### [741238] 모듈간 연계 고려 미흡
- **상태**: New
- **설명**: (없음)

### [741236] 시스템 Reset 로직 설계 미흡
- **상태**: New
- **설명**: (없음)

### [741234] 요구사양 미확인/오해석
- **상태**: New
- **설명**: (없음)

### [741232] 버전/코드 관리 미흡
- **상태**: New
- **설명**: (없음)

### [741230] SW 변경 영향도 분석 미흡
- **상태**: New
- **설명**: (없음)

### [741228] 변겅점 반영 미흡
- **상태**: New
- **설명**: (없음)

### [741226] 기능 누락
- **상태**: New
- **설명**: (없음)

### [741224] 파라미터 관리 미흡
- **상태**: New
- **설명**: (없음)

### [741222] 로직 구현 오류
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 7건

#### [615528] [ILCU_7] HKMC EOL 에서 간헐적으로 PSTN 램프 LED DTC 발생
- **상태**: New
- **필드**:
  - **2차 기능분류**: DTC Set/Clear 조건 오류
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
- **설명**: __ME1a ILCU__
문제점
 __HKMC EOL 에서 간헐적으로 PSTN 램프 LED DTC 발생__\\
\\
\\
%%└ 비 법규 항목으로 경고등 및 램프%! %% %! %%소등 없음%! %%. 운전자 인지 불가%! %%)%!\\
\\
%%└ %! %%DTC%! %% 발생 후 차량%! %% %! %%시동 %! %%30%! %%회 %! %%On & Off %! %%시 과거고장 자동%! %% %! %%소거%!\\
원인
 __설계__\\
ㄴ Driver IC의 LED 상태 신호를 모니터링해서 LED 고장 여부 판단.\\
\\
~- 전류 변경 구간에서 Driver IC의 LED 상태신호가 고장으로 출력 (가성 고장)\\
~- 포지션램프 점/소등을 빠르게 반복 시 전류 변경 구간이 지속되어 DTC 발생\\
\\
)문제점 개선
~- 고장판단 시작 기준 변경 ( A ~-~> B [IC 안정화 시간 이후 고장 판단] )\\
ㄴ 전류 변경 구간(Fade In/Out)에서 고장판단 미수행(Side Effect 없음)\\
\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/EaU5pes9t-5Dum2TueDdBJEB0VwvGldh7uRNFy3vFWVbNA?e=etHImW]

#### [615532] [ILCU_9] PDC 리셋 중 FAIL 송출 뒤 COMPLETE 송출
- **상태**: New
- **필드**:
  - **2차 기능분류**: Reset 이후 상태 복원 오류 (Flag/Mode)
  - **1차 분류**: 복합
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
- **설명**: NH2__
문제점
 PDC 리셋 중 FAIL 송출 뒤 COMPLETE 송출
원인
 ~- 차량 입력 신호에서 CAN 신호 내 Fail 구간 존재함\\
~- PDC_ResetPreWrng 0일 때 PDC_ResetReq 1 로 인한 발생\\
~- Reset 조건 만족 후 1초 후애 동작하는 시컨스로 인해\\
~- 1초 대기 중에 Fail조건 구간에서 Fail 송출.\\
~- 이후 정상적으로 제어기 Reset 후에 Complete 신호 송출\\
~- PDC RESET의 의도는 RESET 명령 수신 시 즉시 리셋 되도록 수정\\
)문제점 개선
~- 리셋 지연 로직 유지\\
~- PDC Reset 설계 담당자 조진호 책임연구원(전자전력제어개발팀)과 회의 시~,\\
Fail이 발생하고 최종적으로 Complete가 수행되기 때문에 문제가 되지는 않는 부분이며 양산 중인 차종에 수정없어도 될 것 같다는 의견을 받음\\
\\
[확인 메일]\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/EfA1EZcAeR5NtTHTjYf3MD4BqGF_nmxoP8PgRaRLRAJwTQ?e=KzMYOR]

#### [615536] [ILCU_11] STEEL 사양에서 ECS사양으로 Variant Coding 시 Leveling Sensor Fault DTC 유지
- **상태**: New
- **필드**:
  - **2차 기능분류**: Variant Coding 미반영
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: __CE FL HL__
문제점
 STEEL 사양에서 ECS사양으로 Variant Coding 시 Leveling Sensor Fault DTC 유지
원인
 Leveling Sensor Fault DTC 발생\\
~- 최초 램프 납품시 STEEL 사양으로 코딩되어 있어 ECS 사양 차량에 조립시 Leveling Sensor Fault DTC 발생\\
\\
ECS 사양 Variant Coding 시 DTC 유지\\
~- ECS사양으로 변경 시 STEEL 사양의 FAULT를 클리어하는 로직이 없어 DTC 유지됨
문제점 개선
 ECS Variant Coding 시~, VLS 고장 정보 클리어하는 로직 추가\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/Ed8zlzQbrm1OsKa1CVhVEt4BAp-BZzZH5QAtpreMH5HRKQ?e=5LaTL8]

#### [615538] [ILCU_12] Default Session에서 OTA READY (RID 0300) 진단 명령 시 부정응답 발생
- **상태**: New
- **필드**:
  - **2차 기능분류**: 진단 세션 전이 오류
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
- **설명**: __CE FL__
문제점
 Default Session에서 OTA READY (RID 0300) 진단 명령 시 부정응답 발생
원인
 OTA READY (RID 0300) 의 루틴 권한 설정에 Default session 누락\\
)문제점 개선
OTA READY ( RID 0300 ) 의 루틴 권한 설정에 Default session 추가\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/EdzXucE39ytFgVFtjOQ5BDYBWmKoa6gu9LMmc7saOU6f7Q?e=A5oiuy]

#### [615540] [ILCU_13] 월컴 동작 시 LOW, PSTN미점등(STD사양)
- **상태**: New
- **필드**:
  - **2차 기능분류**: Variant Coding 미반영
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: 문제점
 월컴 동작 시 LOW~, PSTN미점등(STD사양)
원인
 ~- 시작차 대응 이슈로 DWL 미사양이여도 DWL 신호가 들어옴\\
▶ 웰컴 커멘드 신호로 인해 LOW~, PSTN REQ 신호가 무시됨.\\
▶ DWL 사양 적용 시 LOW~, PSTN REQ 신호 무시 사항이 반영됨\\
NX5 STD의 NONE DWL 사양으로 신호 무시 미 반영 필요.
문제점 개선
 베리언트의 DWL 사양을 보고 신호 처리 되도록 수정

#### [615542] [ILCU_14] Center PSTN 점등 중 TURN Active Off/ON 시 센터 포지션 밝기 달라지는 현상
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 로직 구현 오류
- **설명**: 문제점
 Center PSTN 점등 중 TURN Active Off/ON 시 센터 포지션 밝기 달라지는 현상
원인
 ~- 품평용 SW 긴급 대응 수정으로 인한 test 부족\\
~- PSTN 전류가 5~%~-~>10~%변경 요청에 의해 SW로직 일부 미 수정됨\\
▶ PSTN Req 시 Center PSTN Duty – 10~%출력\\
▶ DRL Req 시 Center PSTN Duty – 100~%출력\\
▶ Turn on 시 Ceneter PSTN Duty – 100~% 출력\\
으로 동작됨.
문제점 개선
 Center PSTN 제어 로직에 DRL/PSTN 신호 조건에만 동작되도록 수정\\
▶ Center PSTN 제어 모델의 기준 신호를 PSTN or DRL 보도록 수정

#### [615544] [ILCU_15] NAS 사양 Variant 입력 시 LED 미점등 발생(2572 버전)
- **상태**: New
- **필드**:
  - **2차 기능분류**: Variant Coding 미반영
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: 문제점
 NAS 사양 Variant 입력 시 LED 미점등 발생(2572 버전)
원인
 ~- 2572 버전 ECS 센서 로직 추가에 따라 NAS Variant 입력 시 LED 파라미터 리드 미수행\\
▶ 2572 버전 변경점 : 지역에 따른 LED 파라미터 리드\\
~-~> 지역에 따른 HLL 파라미터 리드 후 LED 파라미터 리드\\
▶ 지역확인 변수값이 HLL과 LED 로직에 동일하게 사용하고 NAS사양의 지역확인 변수값이 동일해서 HLL 파라미터 리드 후 LED 지역확인 스킵 ~-~> LED 파라미터 리드 미수행
문제점 개선
 ~- 지역 확인 변수 분리(HLL~, LED)\\
~- 재발 방지 방안 수립 필요

### [741220] 상세 설계/검증 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 4건

#### [741260] 환경 조건 고려 미흡
- **상태**: New

#### [741258] 임계값 설계 미흡
- **상태**: New

#### [741256] 예외 입력/신호 처리 미흡
- **상태**: New

#### [741254] 로직 예외 흐름 고려 미흡
- **상태**: New

### [741218] 아키텍처 설계/검증 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 5건

#### [741252] 메모리 Task 설계 미흡
- **상태**: New

#### [741250] 동작 우선순위 설계 오류
- **상태**: New

#### [741248] 인터럽트 설계 오류
- **상태**: New

#### [741246] 응답 시간 설계 오류
- **상태**: New

#### [741244] 공유 자원 설계 오류
- **상태**: New

### [741216] 시스템 설계/검증 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 4건

#### [741236] 시스템 Reset 로직 설계 미흡
- **상태**: New

#### [741238] 모듈간 연계 고려 미흡
- **상태**: New

#### [741240] 제어기간 연계 고려 미흡
- **상태**: New

#### [741242] 시스템 에러 감지 미흡
- **상태**: New

### [741214] 요구사항 분석/검증 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 2건

#### [741234] 요구사양 미확인/오해석
- **상태**: New

#### [741622] 요구사항 미확인/오해석
- **상태**: New

- **하위 아이템**: 1건

#### [615526] [ILCU_6] ME1 FOD 외 지역 USM QR코드 뜨는 문제
- **상태**: New
- **필드**:
  - **2차 기능분류**: 옵션 조건 누락
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사항 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: 문제점
 ME1 FOD 외 지역 USM QR코드 뜨는 문제
원인
 \\
문제점 개선
 ~- DWLOpt 시그널 출력 조건 변경\\
\\
▶ 변경 전) \\
DWL 옵션이 1인 경우~, DWLOpt == 1 또는 2 출력\\
\\
▶ 변경 후)\\
~- 국가 사양이 0~2이고~, DWL 옵션이 1인 경우~, DWLOpt == 1 또는 2 출력\\
~- 0~2를 제외한 나머지 국가 사양은 DWL 옵션과 무관하게 DWLOpt == 0으로 출력

### [741212] 변경점 관리 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 4건

#### [741228] 변겅점 반영 미흡
- **상태**: New

#### [741230] SW 변경 영향도 분석 미흡
- **상태**: New

#### [741232] 버전/코드 관리 미흡
- **상태**: New

#### [741620] 변경점 반영 미흡
- **상태**: New

### [741210] 최초 구현 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 3건

#### [741222] 로직 구현 오류
- **상태**: New

- **하위 아이템**: 7건

#### [615528] [ILCU_7] HKMC EOL 에서 간헐적으로 PSTN 램프 LED DTC 발생
- **상태**: New
- **필드**:
  - **2차 기능분류**: DTC Set/Clear 조건 오류
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
- **설명**: __ME1a ILCU__
문제점
 __HKMC EOL 에서 간헐적으로 PSTN 램프 LED DTC 발생__\\
\\
\\
%%└ 비 법규 항목으로 경고등 및 램프%! %% %! %%소등 없음%! %%. 운전자 인지 불가%! %%)%!\\
\\
%%└ %! %%DTC%! %% 발생 후 차량%! %% %! %%시동 %! %%30%! %%회 %! %%On & Off %! %%시 과거고장 자동%! %% %! %%소거%!\\
원인
 __설계__\\
ㄴ Driver IC의 LED 상태 신호를 모니터링해서 LED 고장 여부 판단.\\
\\
~- 전류 변경 구간에서 Driver IC의 LED 상태신호가 고장으로 출력 (가성 고장)\\
~- 포지션램프 점/소등을 빠르게 반복 시 전류 변경 구간이 지속되어 DTC 발생\\
\\
)문제점 개선
~- 고장판단 시작 기준 변경 ( A ~-~> B [IC 안정화 시간 이후 고장 판단] )\\
ㄴ 전류 변경 구간(Fade In/Out)에서 고장판단 미수행(Side Effect 없음)\\
\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/EaU5pes9t-5Dum2TueDdBJEB0VwvGldh7uRNFy3vFWVbNA?e=etHImW]

#### [615532] [ILCU_9] PDC 리셋 중 FAIL 송출 뒤 COMPLETE 송출
- **상태**: New
- **필드**:
  - **2차 기능분류**: Reset 이후 상태 복원 오류 (Flag/Mode)
  - **1차 분류**: 복합
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
- **설명**: NH2__
문제점
 PDC 리셋 중 FAIL 송출 뒤 COMPLETE 송출
원인
 ~- 차량 입력 신호에서 CAN 신호 내 Fail 구간 존재함\\
~- PDC_ResetPreWrng 0일 때 PDC_ResetReq 1 로 인한 발생\\
~- Reset 조건 만족 후 1초 후애 동작하는 시컨스로 인해\\
~- 1초 대기 중에 Fail조건 구간에서 Fail 송출.\\
~- 이후 정상적으로 제어기 Reset 후에 Complete 신호 송출\\
~- PDC RESET의 의도는 RESET 명령 수신 시 즉시 리셋 되도록 수정\\
)문제점 개선
~- 리셋 지연 로직 유지\\
~- PDC Reset 설계 담당자 조진호 책임연구원(전자전력제어개발팀)과 회의 시~,\\
Fail이 발생하고 최종적으로 Complete가 수행되기 때문에 문제가 되지는 않는 부분이며 양산 중인 차종에 수정없어도 될 것 같다는 의견을 받음\\
\\
[확인 메일]\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/EfA1EZcAeR5NtTHTjYf3MD4BqGF_nmxoP8PgRaRLRAJwTQ?e=KzMYOR]

#### [615536] [ILCU_11] STEEL 사양에서 ECS사양으로 Variant Coding 시 Leveling Sensor Fault DTC 유지
- **상태**: New
- **필드**:
  - **2차 기능분류**: Variant Coding 미반영
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: __CE FL HL__
문제점
 STEEL 사양에서 ECS사양으로 Variant Coding 시 Leveling Sensor Fault DTC 유지
원인
 Leveling Sensor Fault DTC 발생\\
~- 최초 램프 납품시 STEEL 사양으로 코딩되어 있어 ECS 사양 차량에 조립시 Leveling Sensor Fault DTC 발생\\
\\
ECS 사양 Variant Coding 시 DTC 유지\\
~- ECS사양으로 변경 시 STEEL 사양의 FAULT를 클리어하는 로직이 없어 DTC 유지됨
문제점 개선
 ECS Variant Coding 시~, VLS 고장 정보 클리어하는 로직 추가\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/Ed8zlzQbrm1OsKa1CVhVEt4BAp-BZzZH5QAtpreMH5HRKQ?e=5LaTL8]

#### [615538] [ILCU_12] Default Session에서 OTA READY (RID 0300) 진단 명령 시 부정응답 발생
- **상태**: New
- **필드**:
  - **2차 기능분류**: 진단 세션 전이 오류
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
- **설명**: __CE FL__
문제점
 Default Session에서 OTA READY (RID 0300) 진단 명령 시 부정응답 발생
원인
 OTA READY (RID 0300) 의 루틴 권한 설정에 Default session 누락\\
)문제점 개선
OTA READY ( RID 0300 ) 의 루틴 권한 설정에 Default session 추가\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/EdzXucE39ytFgVFtjOQ5BDYBWmKoa6gu9LMmc7saOU6f7Q?e=A5oiuy]

#### [615540] [ILCU_13] 월컴 동작 시 LOW, PSTN미점등(STD사양)
- **상태**: New
- **필드**:
  - **2차 기능분류**: Variant Coding 미반영
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: 문제점
 월컴 동작 시 LOW~, PSTN미점등(STD사양)
원인
 ~- 시작차 대응 이슈로 DWL 미사양이여도 DWL 신호가 들어옴\\
▶ 웰컴 커멘드 신호로 인해 LOW~, PSTN REQ 신호가 무시됨.\\
▶ DWL 사양 적용 시 LOW~, PSTN REQ 신호 무시 사항이 반영됨\\
NX5 STD의 NONE DWL 사양으로 신호 무시 미 반영 필요.
문제점 개선
 베리언트의 DWL 사양을 보고 신호 처리 되도록 수정

#### [615542] [ILCU_14] Center PSTN 점등 중 TURN Active Off/ON 시 센터 포지션 밝기 달라지는 현상
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 로직 구현 오류
- **설명**: 문제점
 Center PSTN 점등 중 TURN Active Off/ON 시 센터 포지션 밝기 달라지는 현상
원인
 ~- 품평용 SW 긴급 대응 수정으로 인한 test 부족\\
~- PSTN 전류가 5~%~-~>10~%변경 요청에 의해 SW로직 일부 미 수정됨\\
▶ PSTN Req 시 Center PSTN Duty – 10~%출력\\
▶ DRL Req 시 Center PSTN Duty – 100~%출력\\
▶ Turn on 시 Ceneter PSTN Duty – 100~% 출력\\
으로 동작됨.
문제점 개선
 Center PSTN 제어 로직에 DRL/PSTN 신호 조건에만 동작되도록 수정\\
▶ Center PSTN 제어 모델의 기준 신호를 PSTN or DRL 보도록 수정

#### [615544] [ILCU_15] NAS 사양 Variant 입력 시 LED 미점등 발생(2572 버전)
- **상태**: New
- **필드**:
  - **2차 기능분류**: Variant Coding 미반영
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: 문제점
 NAS 사양 Variant 입력 시 LED 미점등 발생(2572 버전)
원인
 ~- 2572 버전 ECS 센서 로직 추가에 따라 NAS Variant 입력 시 LED 파라미터 리드 미수행\\
▶ 2572 버전 변경점 : 지역에 따른 LED 파라미터 리드\\
~-~> 지역에 따른 HLL 파라미터 리드 후 LED 파라미터 리드\\
▶ 지역확인 변수값이 HLL과 LED 로직에 동일하게 사용하고 NAS사양의 지역확인 변수값이 동일해서 HLL 파라미터 리드 후 LED 지역확인 스킵 ~-~> LED 파라미터 리드 미수행
문제점 개선
 ~- 지역 확인 변수 분리(HLL~, LED)\\
~- 재발 방지 방안 수립 필요

#### [741224] 파라미터 관리 미흡
- **상태**: New

#### [741226] 기능 누락
- **상태**: New

### [741208] 단순
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 2건

#### [741210] 최초 구현 미흡
- **상태**: New

- **하위 아이템**: 3건

#### [741222] 로직 구현 오류
- **상태**: New

#### [741224] 파라미터 관리 미흡
- **상태**: New

#### [741226] 기능 누락
- **상태**: New

#### [741212] 변경점 관리 미흡
- **상태**: New

- **하위 아이템**: 4건

#### [741228] 변겅점 반영 미흡
- **상태**: New

#### [741230] SW 변경 영향도 분석 미흡
- **상태**: New

#### [741232] 버전/코드 관리 미흡
- **상태**: New

#### [741620] 변경점 반영 미흡
- **상태**: New

### [741206] 복합
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 4건

#### [741214] 요구사항 분석/검증 미흡
- **상태**: New

- **하위 아이템**: 2건

#### [741234] 요구사양 미확인/오해석
- **상태**: New

#### [741622] 요구사항 미확인/오해석
- **상태**: New

#### [741216] 시스템 설계/검증 미흡
- **상태**: New

- **하위 아이템**: 4건

#### [741236] 시스템 Reset 로직 설계 미흡
- **상태**: New

#### [741238] 모듈간 연계 고려 미흡
- **상태**: New

#### [741240] 제어기간 연계 고려 미흡
- **상태**: New

#### [741242] 시스템 에러 감지 미흡
- **상태**: New

#### [741218] 아키텍처 설계/검증 미흡
- **상태**: New

- **하위 아이템**: 5건

#### [741252] 메모리 Task 설계 미흡
- **상태**: New

#### [741250] 동작 우선순위 설계 오류
- **상태**: New

#### [741248] 인터럽트 설계 오류
- **상태**: New

#### [741246] 응답 시간 설계 오류
- **상태**: New

#### [741244] 공유 자원 설계 오류
- **상태**: New

#### [741220] 상세 설계/검증 미흡
- **상태**: New

- **하위 아이템**: 4건

#### [741260] 환경 조건 고려 미흡
- **상태**: New

#### [741258] 임계값 설계 미흡
- **상태**: New

#### [741256] 예외 입력/신호 처리 미흡
- **상태**: New

#### [741254] 로직 예외 흐름 고려 미흡
- **상태**: New

### [616202] [ILCU_1] EV Ready 상태에서 인증서 주입 후 Reset 명령 수신 시 NRC 22 송신
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 고객 요구사항 수정
  - **3차 분류**: 고객 요구사항 수정
- **설명**: 문제점
 EV Ready 상태에서 인증서 주입 후 Reset 명령 수신 시 NRC 22 송신\\
원인
 \\
~- IGN2 ON/OFF 조건에 따른 FV 활성화 : 무선(CCU) Type에 한함(고객 요구 사항)
\\
~- EV Ready 상태에서 Reset 명령어 수신 시 NRC 22 송신(고객/시스템 요구 사항)
\\
~- 유선 Type 인증서 주입 후 Reboot 요청 시(ILCU ~-~> 진단기)~, 진단기에서 Reset 명령
\\
~- 무선 Type 인증서 주입 시 Reboot 요청 X
\\
\\
문제점 개선
 매뉴얼 기입\\

### [615546] [ILCU_16] RXSWIN 길이값 오류
- **상태**: New
- **필드**:
  - **2차 기능분류**: DLC/Length 불일치
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 사양 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P3. CAN (CAN/CAN FD/NM)
- **설명**: __NH2 유럽 양산 차량__
문제점
 RXSWIN 정보 표출 이상\\
\\
)원인
~- 양산 버전에서 RXSWIN 값 길이 오류 발생\\
ㄴ RXSWIN 데이터 길이 오설정\\
)문제점 개선
~- 시스템팀 전달 문서 자동화\\
~- 값 검증 방안 추가 구축}]

* 자료 첨부 : [https://cloud.slworld.com/share/url/D/vh9w7h11hq8tjbmoycjp]

### [615544] [ILCU_15] NAS 사양 Variant 입력 시 LED 미점등 발생(2572 버전)
- **상태**: New
- **필드**:
  - **2차 기능분류**: Variant Coding 미반영
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: 문제점
 NAS 사양 Variant 입력 시 LED 미점등 발생(2572 버전)
원인
 ~- 2572 버전 ECS 센서 로직 추가에 따라 NAS Variant 입력 시 LED 파라미터 리드 미수행\\
▶ 2572 버전 변경점 : 지역에 따른 LED 파라미터 리드\\
~-~> 지역에 따른 HLL 파라미터 리드 후 LED 파라미터 리드\\
▶ 지역확인 변수값이 HLL과 LED 로직에 동일하게 사용하고 NAS사양의 지역확인 변수값이 동일해서 HLL 파라미터 리드 후 LED 지역확인 스킵 ~-~> LED 파라미터 리드 미수행
문제점 개선
 ~- 지역 확인 변수 분리(HLL~, LED)\\
~- 재발 방지 방안 수립 필요

### [615542] [ILCU_14] Center PSTN 점등 중 TURN Active Off/ON 시 센터 포지션 밝기 달라지는 현상
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 로직 구현 오류
- **설명**: 문제점
 Center PSTN 점등 중 TURN Active Off/ON 시 센터 포지션 밝기 달라지는 현상
원인
 ~- 품평용 SW 긴급 대응 수정으로 인한 test 부족\\
~- PSTN 전류가 5~%~-~>10~%변경 요청에 의해 SW로직 일부 미 수정됨\\
▶ PSTN Req 시 Center PSTN Duty – 10~%출력\\
▶ DRL Req 시 Center PSTN Duty – 100~%출력\\
▶ Turn on 시 Ceneter PSTN Duty – 100~% 출력\\
으로 동작됨.
문제점 개선
 Center PSTN 제어 로직에 DRL/PSTN 신호 조건에만 동작되도록 수정\\
▶ Center PSTN 제어 모델의 기준 신호를 PSTN or DRL 보도록 수정

### [615540] [ILCU_13] 월컴 동작 시 LOW, PSTN미점등(STD사양)
- **상태**: New
- **필드**:
  - **2차 기능분류**: Variant Coding 미반영
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: 문제점
 월컴 동작 시 LOW~, PSTN미점등(STD사양)
원인
 ~- 시작차 대응 이슈로 DWL 미사양이여도 DWL 신호가 들어옴\\
▶ 웰컴 커멘드 신호로 인해 LOW~, PSTN REQ 신호가 무시됨.\\
▶ DWL 사양 적용 시 LOW~, PSTN REQ 신호 무시 사항이 반영됨\\
NX5 STD의 NONE DWL 사양으로 신호 무시 미 반영 필요.
문제점 개선
 베리언트의 DWL 사양을 보고 신호 처리 되도록 수정

### [615538] [ILCU_12] Default Session에서 OTA READY (RID 0300) 진단 명령 시 부정응답 발생
- **상태**: New
- **필드**:
  - **2차 기능분류**: 진단 세션 전이 오류
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
- **설명**: __CE FL__
문제점
 Default Session에서 OTA READY (RID 0300) 진단 명령 시 부정응답 발생
원인
 OTA READY (RID 0300) 의 루틴 권한 설정에 Default session 누락\\
)문제점 개선
OTA READY ( RID 0300 ) 의 루틴 권한 설정에 Default session 추가\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/EdzXucE39ytFgVFtjOQ5BDYBWmKoa6gu9LMmc7saOU6f7Q?e=A5oiuy]

### [615536] [ILCU_11] STEEL 사양에서 ECS사양으로 Variant Coding 시 Leveling Sensor Fault DTC 유지
- **상태**: New
- **필드**:
  - **2차 기능분류**: Variant Coding 미반영
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: __CE FL HL__
문제점
 STEEL 사양에서 ECS사양으로 Variant Coding 시 Leveling Sensor Fault DTC 유지
원인
 Leveling Sensor Fault DTC 발생\\
~- 최초 램프 납품시 STEEL 사양으로 코딩되어 있어 ECS 사양 차량에 조립시 Leveling Sensor Fault DTC 발생\\
\\
ECS 사양 Variant Coding 시 DTC 유지\\
~- ECS사양으로 변경 시 STEEL 사양의 FAULT를 클리어하는 로직이 없어 DTC 유지됨
문제점 개선
 ECS Variant Coding 시~, VLS 고장 정보 클리어하는 로직 추가\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/Ed8zlzQbrm1OsKa1CVhVEt4BAp-BZzZH5QAtpreMH5HRKQ?e=5LaTL8]

### [615534] [ILCU_10] 유선 OTA 다운로드 시 HIGH 일부 LED 점등 발생
- **상태**: New
- **필드**:
  - **2차 기능분류**: 센싱 조기값 오류 (PoR)
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: GPIO 핀 설정 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P5. 입력 처리 (ADC/GPIO/센싱)
- **설명**: CE FL HL__
문제점
 유선 OTA 다운로드 시 HIGH BEAM 일부 LED 점등 발생
원인
 FBL 진입 시~, GPIO 설정이 잘못되어 있어 HIGH BUCK IC 의 PWM을 ON 으로 출력\\
\\
)문제점 개선
~- FBL 의 GPIO 설정 확인\\
\\

* 자료 링크 : [https://slworld365.sharepoint.com/:p:/s/SW726/EVMQEPDEweJPuG1tSf6eiVoBbz0u0xWOwAp62fn3oOMb-w?e=jd6BaK]

### [615532] [ILCU_9] PDC 리셋 중 FAIL 송출 뒤 COMPLETE 송출
- **상태**: New
- **필드**:
  - **2차 기능분류**: Reset 이후 상태 복원 오류 (Flag/Mode)
  - **1차 분류**: 복합
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
- **설명**: NH2__
문제점
 PDC 리셋 중 FAIL 송출 뒤 COMPLETE 송출
원인
 ~- 차량 입력 신호에서 CAN 신호 내 Fail 구간 존재함\\
~- PDC_ResetPreWrng 0일 때 PDC_ResetReq 1 로 인한 발생\\
~- Reset 조건 만족 후 1초 후애 동작하는 시컨스로 인해\\
~- 1초 대기 중에 Fail조건 구간에서 Fail 송출.\\
~- 이후 정상적으로 제어기 Reset 후에 Complete 신호 송출\\
~- PDC RESET의 의도는 RESET 명령 수신 시 즉시 리셋 되도록 수정\\
)문제점 개선
~- 리셋 지연 로직 유지\\
~- PDC Reset 설계 담당자 조진호 책임연구원(전자전력제어개발팀)과 회의 시~,\\
Fail이 발생하고 최종적으로 Complete가 수행되기 때문에 문제가 되지는 않는 부분이며 양산 중인 차종에 수정없어도 될 것 같다는 의견을 받음\\
\\
[확인 메일]\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/EfA1EZcAeR5NtTHTjYf3MD4BqGF_nmxoP8PgRaRLRAJwTQ?e=KzMYOR]

### [615530] [ILCU_8] ME1 캐나다 사양 FOD SUPER DELETE 인증서 주입 실패
- **상태**: New
- **필드**:
  - **2차 기능분류**: 신호/명령 정의 혼선
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 사양별 이원화 설계 고려 부족
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: ME1a 캐나다 사양__
문제점
 ME1 캐나다 사양 FOD SUPER DELETE Test 중~, 인증서 주입 실패\\
ㄴNRC 72 발생
원인
 HKMC서버 NAS 사양 TFV(0x13) 정보와 ILCU FoD모듈의 FFV (0x3F) 정보 불일치 (NRC 발생)\\
[!1774233563735.png#f350d40150ed254e6410f479dd1a15ba!]\\
문제점 개선
 HKMC서버 TFV 정보 수정 (TFV값 일원화)\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/EcFSsyc3lflEuM829zy2TtQBZEkWc88YX-vlz1eJjhI_Yw?e=ker4vg]

### [615528] [ILCU_7] HKMC EOL 에서 간헐적으로 PSTN 램프 LED DTC 발생
- **상태**: New
- **필드**:
  - **2차 기능분류**: DTC Set/Clear 조건 오류
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
- **설명**: __ME1a ILCU__
문제점
 __HKMC EOL 에서 간헐적으로 PSTN 램프 LED DTC 발생__\\
\\
\\
%%└ 비 법규 항목으로 경고등 및 램프%! %% %! %%소등 없음%! %%. 운전자 인지 불가%! %%)%!\\
\\
%%└ %! %%DTC%! %% 발생 후 차량%! %% %! %%시동 %! %%30%! %%회 %! %%On & Off %! %%시 과거고장 자동%! %% %! %%소거%!\\
원인
 __설계__\\
ㄴ Driver IC의 LED 상태 신호를 모니터링해서 LED 고장 여부 판단.\\
\\
~- 전류 변경 구간에서 Driver IC의 LED 상태신호가 고장으로 출력 (가성 고장)\\
~- 포지션램프 점/소등을 빠르게 반복 시 전류 변경 구간이 지속되어 DTC 발생\\
\\
)문제점 개선
~- 고장판단 시작 기준 변경 ( A ~-~> B [IC 안정화 시간 이후 고장 판단] )\\
ㄴ 전류 변경 구간(Fade In/Out)에서 고장판단 미수행(Side Effect 없음)\\
\\

* 자료 첨부 : [https://slworld365.sharepoint.com/:p:/s/SW726/EaU5pes9t-5Dum2TueDdBJEB0VwvGldh7uRNFy3vFWVbNA?e=etHImW]

### [615526] [ILCU_6] ME1 FOD 외 지역 USM QR코드 뜨는 문제
- **상태**: New
- **필드**:
  - **2차 기능분류**: 옵션 조건 누락
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사항 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: 문제점
 ME1 FOD 외 지역 USM QR코드 뜨는 문제
원인
 \\
문제점 개선
 ~- DWLOpt 시그널 출력 조건 변경\\
\\
▶ 변경 전) \\
DWL 옵션이 1인 경우~, DWLOpt == 1 또는 2 출력\\
\\
▶ 변경 후)\\
~- 국가 사양이 0~2이고~, DWL 옵션이 1인 경우~, DWLOpt == 1 또는 2 출력\\
~- 0~2를 제외한 나머지 국가 사양은 DWL 옵션과 무관하게 DWLOpt == 0으로 출력

### [615524] [ILCU_5] ME1 / ME1a 북미 라이팅 패턴 표출 오류
- **상태**: New
- **필드**:
  - **2차 기능분류**: 신호/명령 정의 혼선
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 파라미터 관리 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
- **설명**: 문제점
 ME1 / ME1a 북미 라이팅 패턴 표출 오류
원인
 북미 DWL / DEL 시나리오 명칭 오류\\
1) 디자인팀 ~-~> 외장설계팀 : A / C / E\\
2) 외장 설계팀(최재민 책임연구원~-MLV 외장설계2팀) ~-~> 에스엘 : A / B / E
문제점 개선
 \\

### [615522] [ILCU_4] LX3 ILCU 미슬립에 의한 배터리 방전 이슈
- **상태**: New
- **필드**:
  - **2차 기능분류**: OS Task 스케줄링 오류
  - **1차 분류**: 복합
  - **2차 분류**: 아키텍처 설계/검증 미흡
  - **3차 분류**: 인터럽트 설계 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P10. 시스템 서비스
- **설명**: 문제점
 LX3 ILCU 미슬립에 의한 배터리 방전 이슈
원인
 Task 멈춤 현상에 의한 미슬립
문제점 개선
 OS 패치

### [615520] [ILCU_3] 배터리 방전이슈로 인한 로그분석요청
- **상태**: New
- **필드**:
  - **2차 기능분류**: NRC 처리 오류
  - **1차 분류**: 복합
  - **2차 분류**: 시스템 설계/검증 미흡
  - **3차 분류**: Test 부족
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
- **설명**: 문제점
 배터리 방전이슈로 인한 로그분석요청
원인
 로그 분석 간 Non~-Sleep Data(ED90) Invaild Data 확인
문제점 개선
 ~- ED90 진단 서비스 관련하여~, 정해진 스펙 범위 이외에 대해서 0으로 초기화 적용\\
[ED90 적용 차종 수평 전개]\\
~- Test Case 추가

### [615518] [ILCU_2] 전원 조건과 무관하게 인증서 설치 시 간헐적으로 RID 411 수신 후 ILCU 응답 없음
- **상태**: New
- **필드**:
  - **2차 기능분류**: 송수신 조건 오류 (상태/모드별)
  - **1차 분류**: 복합
  - **2차 분류**: 시스템 설계/검증 미흡
  - **3차 분류**: Test 부족
  - **SW Layer**: Platform
  - **1차 기능분류**: P3. CAN (CAN/CAN FD/NM)
- **설명**: 문제점
 전원 조건과 무관하게 인증서 설치 시 간헐적으로 RID 411 수신 후 ILCU 응답 없음
원인
 ~- 유선 Type 인증서 주입 시~, 라우터에 통해 ILCU로 인증서 정보 전달~, 라우터 부하에 따라 ST MIN 설정 값보다 빠른 시간으로 수신 경우 Data 놓침 현상 발생에 의한 무응답\\
\\
~- 고객 사이버 보안 정책으로 협력사로 진단기 판매 불가\\
~- 고객 사이버 보안 정책으로 양산계 인증서 정보 수신 불가
문제점 개선
 ~- 진단 ID 설정 변경\\
▶ Full CAN ~-~> Basic CAN + FIFO\\
▶ Basic CAN + FIFO 설정 시~, 버퍼에 저장 됨에 따라 Data 놓침 현상 발생 X(오토에버 답변)\\
\\
~- CAN FD 적용 차종 ~- 진단 ID에 한해 Basic CAB 적용(+FIFO) 기 적용
