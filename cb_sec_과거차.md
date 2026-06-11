# Codebeamer 과거 이슈 컨텍스트
> 생성 일시: 2026-06-11 11:01:40

아래는 각 컴포넌트별 과거 이슈 목록입니다.
코드 리뷰 시 현재 변경점이 과거 이슈와 유사한 경우 경고해주세요.

## 🔧 PLBM 이슈

### [1020908] [PLBM_20][HKMCJGRLBM-179]특정 타이밍에 PDC CAN WakeUp 시 간헐적으로 PLBM WakeUp 미동작
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: 변경점 반영 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
  - **2차 기능분류**: Mode 전이 타이밍 오류
- **설명**: %%;font-style:normal;font-variant-ligatures:normal;font-variant-caps:normal;letter-spacing:normal;orphans:2;text-align:start;text-indent:0px;text-transform:none;widows:2;word-spacing:0px;-webkit-text-stroke-width:0px;white-space:normal;background-color:rgb(255, 255, 255);text-decoration-thickness:initial;text-decoration-style:initial;text-decoration-color:initial;display:inline !important;float:none;) %!__NX5__
문제점
[HKMCJGRLBM~-179] 특정 타이밍에 PDC CAN WakeUp 시 간헐적으로 PLBM WakeUp 미동작
원인
%%
1)%%ASW%!%%에서 %!%%BSW%!%%로 %!%%MCU %!%%슬립 요청 후 %!%%ASW%!%%는 종료%!%%.%!%!
%%
2)%%BSW%!%%에서 %!%%MCU %!%%슬립 처리 중%!%% CAN %!%%메시지를 수신%!%%. SBC%!%%에서 %!%%CAN_RX Pin%!%%을 %!%%High %!%%à%!%% Low%!%%로 변경하여 %!%%MCU%!%%에 알림%!%%.%!%!
%%
3)%%ASW%!%%가 종료된 상태라 %!%%CAN_Rx Pin%!%%이 %!%%Low%!%%인 걸 확인할 수 없어서%!%%~, CAN wakeup %!%%하지 않고 슬립에 진입%!%!
문제점 개선
%%
1)%%CAN %!%%네트워크 슬립 시 %!%%CAN Rx%!%%에 대한%!%% %!%%(text-decoration:underline;)%%ICU%!%!%%(text-decoration:underline;)%% 활성화 추가%!%!%%.%!%!
%%
2)%%BSW%!%%에서%!%% MCU %!%%슬립 처리 중 %!%%CAN %!%%메시지를 수신%!%%. %!%!
%%
3)%%SBC%!%%에서 %!%%CAN_RX Pin%!%%을 %!%%H %!%%à%!%% L%!%%로 변경하여 %!%%MCU%!%%에 알림%!%%.%!%!
%%
4)%%SBC%!%%로부터의 %!%%CAN Wakeup %!%%정보%!%% %!%%Pin%!%% %!%%H%!%%à%!%%L)%!%%를 %!%%ICU%!%%에서 감지%!%%.%!%!
%%
5)%%PLBM CAN Wakeup %!%%및 정상 동작%!%!
\\
\\
%%''*ICU(Input Capture Unit):''%! %% %! %%''CAN Rx H ''%! %%''à''%! %%'' L''%! %%'' 변화를 감지''%! %%''. ''%!\\
\\


%%;text-align:start;background-color:rgb(255, 255, 255);float:none;display:inline !important;)* 자료 첨부 : %![[HKMCJGRLBM-179] [NX5] 특정 타이밍에 PDC CAN WakeUp 시 간헐적으로 PLBM WakeUp 미동작 - Jira|https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-179?filter=allissues]

### [743762] 로직 예외 흐름 고려 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 1건

#### [630960] [PLBM_3] [TK1_SOP] SOC 90%이상, 저온(19.5도) or 고온(54.5도) 조건에서 충전 시 충전 과전류 발생
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: 로직 예외 흐름 고려 미흡
  - **SW Layer**: Application
  - **1차 기능분류**: A3. 데이터 처리
  - **2차 기능분류**: 연산 오류((사칙연산, 데이터 오류)
- **설명**: __TK1__
문제점
 [TK1_SOP] SOC 90~%이상~, 저온(19.5도) or 고온(54.5도) 조건에서 충전 시 충전 과전류 발생
원인
 1. DC/DC 컨버터 소자 특성 상 0.2A이하의 전류 제어가 되지 않음\\
~- PI제어를 통해 목표 전류에 도달하기 위해서 PWM값을 변경하는데~, 위의 소자 특성에 의한 목표치에 도달하지 못하면서 PWM값을 계속 증가시켜 Overflow(65535 ~-~-~> 0)로 인한\\
과전류 출력 (PWM값과 출력전류는 반비례)\\
~- PWM의 출력 범위는 0 32~,768(0~% 100~%)이다.
문제점 개선
 1. PI 제어 가능한 범위를 설정 (4000 32768) <~-~- 0A 30A에 해당하는 PWM 값 (첨부 참조)\\

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-9]

### [743760] 예외 입력/신호 처리 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 1건

#### [630966] [PLBM_6] [HKMCJGRLBM-15] [OEUK 적용 차종]SW 다운그레이드 방지 누락
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 예외 입력/신호 처리 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P8. 보안 (OTA/FBL/HSM)
  - **2차 기능분류**: CRC/무결성 검증 오류
- **설명**: 문제점
 [HKMCJGRLBM~-15] [OEUK 적용 차종] SW 다운그레이드 방지 누락
원인
 FBL 내 CRC 값이 ~'0~'으로 초기화되어 있어 SW 업데이트를 위한 버전 비교 시 유효한 값이 없다고 판단하여 업데이트 가능\\
\\
[!1774312289486.png#35a2e2fa323774aee8a465231ccad833!]\\
문제점 개선
 생산용 통합파일(.sre)에 CRC 값을 주입하여 해당 증상을 개선함(대책참조_그림2. 4.)\\
. HSM + FBL + APP SW 파일 ~>~> 생산용 배포파일\\
. 생산용 배포파일 기준으로~, CRC 값을 계산하여 강제로 .SRE 파일에 주입함\\
\\
\\
~- crc 값 주입\\
\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-15?filter=allopenissues]

### [743758] 임계값 설계 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 1건

#### [630964] [PLBM_5] [HKMCJGRLBM-14] [LX3_SOP] BAT_SOC_for_BLTN_CAM 101% 송출 현상 발생
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 임계값 설계 미흡
  - **SW Layer**: Application
  - **1차 기능분류**: A3. 데이터 처리
  - **2차 기능분류**: 연산 오류((사칙연산, 데이터 오류)
- **설명**: __LX3__
문제점
 [HKMCJGRLBM~-14] [LX3_SOP] BAT_SOC_for_BLTN_CAM 101~% 송출 현상 발생
원인
 1. 의도치 않은 표기값에 대한 Guard 처리 없음\\
2. BLTN SOC 할당량은 30Ah 연산 오류 X\\
~- 30Ah BLTN Max 할당량 : 28.8 * 0.7 * 0.66 = 13.305Ah\\
~- 20Ah BLTN Max 할당량 : 19.2 * 0.7 * 1 = 13.44Ah\\
\\
20Ah인 경우 BLTN_SOC = 13.44Ah/13.44Ah = 100~%~,\\
이 상태에서 $BC20 request를 통해 LBM_BAT_Capapcity를 30Ah로 변환할 경우는 아래의 수식을 통해서 BLTN_SOC가 계산 됨\\
13.44/13.305Ah = 101~%\\
따라서 위의 재현 상황에서 결과가 100~%가 아닌 101~%가 나오게 됨
문제점 개선
 1. BLTN_SOC가 100 초과한 값을 표기하지 않도록 Guard 처리

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-14]

### [743756] 환경 조건 고려 미흡
- **상태**: New
- **설명**: (없음)

### [743754] 상세 설계/검증 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 4건

#### [743756] 환경 조건 고려 미흡
- **상태**: New

#### [743758] 임계값 설계 미흡
- **상태**: New

- **하위 아이템**: 1건

#### [630964] [PLBM_5] [HKMCJGRLBM-14] [LX3_SOP] BAT_SOC_for_BLTN_CAM 101% 송출 현상 발생
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 임계값 설계 미흡
  - **SW Layer**: Application
  - **1차 기능분류**: A3. 데이터 처리
  - **2차 기능분류**: 연산 오류((사칙연산, 데이터 오류)
- **설명**: __LX3__
문제점
 [HKMCJGRLBM~-14] [LX3_SOP] BAT_SOC_for_BLTN_CAM 101~% 송출 현상 발생
원인
 1. 의도치 않은 표기값에 대한 Guard 처리 없음\\
2. BLTN SOC 할당량은 30Ah 연산 오류 X\\
~- 30Ah BLTN Max 할당량 : 28.8 * 0.7 * 0.66 = 13.305Ah\\
~- 20Ah BLTN Max 할당량 : 19.2 * 0.7 * 1 = 13.44Ah\\
\\
20Ah인 경우 BLTN_SOC = 13.44Ah/13.44Ah = 100~%~,\\
이 상태에서 $BC20 request를 통해 LBM_BAT_Capapcity를 30Ah로 변환할 경우는 아래의 수식을 통해서 BLTN_SOC가 계산 됨\\
13.44/13.305Ah = 101~%\\
따라서 위의 재현 상황에서 결과가 100~%가 아닌 101~%가 나오게 됨
문제점 개선
 1. BLTN_SOC가 100 초과한 값을 표기하지 않도록 Guard 처리

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-14]

#### [743760] 예외 입력/신호 처리 미흡
- **상태**: New

- **하위 아이템**: 1건

#### [630966] [PLBM_6] [HKMCJGRLBM-15] [OEUK 적용 차종]SW 다운그레이드 방지 누락
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 예외 입력/신호 처리 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P8. 보안 (OTA/FBL/HSM)
  - **2차 기능분류**: CRC/무결성 검증 오류
- **설명**: 문제점
 [HKMCJGRLBM~-15] [OEUK 적용 차종] SW 다운그레이드 방지 누락
원인
 FBL 내 CRC 값이 ~'0~'으로 초기화되어 있어 SW 업데이트를 위한 버전 비교 시 유효한 값이 없다고 판단하여 업데이트 가능\\
\\
[!1774312289486.png#35a2e2fa323774aee8a465231ccad833!]\\
문제점 개선
 생산용 통합파일(.sre)에 CRC 값을 주입하여 해당 증상을 개선함(대책참조_그림2. 4.)\\
. HSM + FBL + APP SW 파일 ~>~> 생산용 배포파일\\
. 생산용 배포파일 기준으로~, CRC 값을 계산하여 강제로 .SRE 파일에 주입함\\
\\
\\
~- crc 값 주입\\
\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-15?filter=allopenissues]

#### [743762] 로직 예외 흐름 고려 미흡
- **상태**: New

- **하위 아이템**: 1건

#### [630960] [PLBM_3] [TK1_SOP] SOC 90%이상, 저온(19.5도) or 고온(54.5도) 조건에서 충전 시 충전 과전류 발생
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: 로직 예외 흐름 고려 미흡
  - **SW Layer**: Application
  - **1차 기능분류**: A3. 데이터 처리
  - **2차 기능분류**: 연산 오류((사칙연산, 데이터 오류)
- **설명**: __TK1__
문제점
 [TK1_SOP] SOC 90~%이상~, 저온(19.5도) or 고온(54.5도) 조건에서 충전 시 충전 과전류 발생
원인
 1. DC/DC 컨버터 소자 특성 상 0.2A이하의 전류 제어가 되지 않음\\
~- PI제어를 통해 목표 전류에 도달하기 위해서 PWM값을 변경하는데~, 위의 소자 특성에 의한 목표치에 도달하지 못하면서 PWM값을 계속 증가시켜 Overflow(65535 ~-~-~> 0)로 인한\\
과전류 출력 (PWM값과 출력전류는 반비례)\\
~- PWM의 출력 범위는 0 32~,768(0~% 100~%)이다.
문제점 개선
 1. PI 제어 가능한 범위를 설정 (4000 32768) <~-~- 0A 30A에 해당하는 PWM 값 (첨부 참조)\\

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-9]

### [743752] 공유 자원 설계 오류
- **상태**: New
- **설명**: (없음)

### [743750] 응답 시간 설계 오류
- **상태**: New
- **설명**: (없음)

### [743748] 인터럽트 설계 오류
- **상태**: New
- **설명**: (없음)

### [743746] 동작 우선순위 설계 오류
- **상태**: New
- **설명**: (없음)

### [743744] 메모리 Task 설계 미흡
- **상태**: New
- **설명**: (없음)

### [743742] 아키텍처 설계/검증 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 5건

#### [743744] 메모리 Task 설계 미흡
- **상태**: New

#### [743746] 동작 우선순위 설계 오류
- **상태**: New

#### [743748] 인터럽트 설계 오류
- **상태**: New

#### [743750] 응답 시간 설계 오류
- **상태**: New

#### [743752] 공유 자원 설계 오류
- **상태**: New

### [743740] 시스템 에러 감지 미흡
- **상태**: New
- **설명**: (없음)

### [743738] 제어기간 연계 고려 미흡
- **상태**: New
- **설명**: (없음)

### [743736] 모듈간 연계 고려 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 1건

#### [630970] [PLBM_8] [HKMCJGRLBM-19] [CAN FD 2세대 차종] 리셋 기능 강건화 적용 건 - Jira
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 시스템 설계/검증 미흡
  - **3차 분류**: 모듈간 연계 고려 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P10. 시스템 서비스
  - **2차 기능분류**: ECU State 관리 오류
- **설명**: 문제점
 [HKMCJGRLBM~-19] [CAN FD 2세대 차종] 리셋 기능 강건화 적용 건 ~- Jira
원인
 리셋 수행 조건 만족 후 실제 리셋이 수행되지 못한 경우~, 플래그 값 초기화 처리 누락
문제점 개선
 실제 리셋 기능을 수행하지 못한 경우~, 리셋을 수행하기 위한 초기 조건으로 Normal Mode로 진입 시 해당 플래그 강제 초기화 처리.\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-19?filter=allopenissues]

### [743734] 시스템 Reset 로직 설계 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 1건

#### [630974] [PLBM_10] [HKMCJGRLBM-24] PDC Reset 요청에 의한 Reset Complete 이후 휴지 시간 없이 팩 SOC 즉시 Recal 됨
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 시스템 설계/검증 미흡
  - **3차 분류**: 시스템 Reset 로직 설계 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P7. 데이터 관리 (NVM/EEPROM/Flash)
  - **2차 기능분류**: 과거 데이터 오입 사용
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-24] PDC Reset 요청에 의한 Reset Complete 이후 휴지 시간 없이 팩 SOC 즉시 Recal 됨
원인
 DC reset 시 SOC recalibration이 수행 된 시간을 NVM에 저장 하지 않은 상태에서~, reset 이후 과거 시간 정보를 load하여 지난 휴지 시간이 경과 한 것으로 오인하여 SOC가 잘못 recal 됨.\\
검토 시에 PDC reset 뿐만 아니라 진단에 의한 Hard reset 시에도 NVM에 저장 되어야 함.
문제점 개선
 1. System Reset 요청시~, APP_RTC_Save_SocRecal_Pause_Done_Time()을 실행하여 SocRecal_Pause_Done_Time을 갱신함\\
~- System Reset 요청\\
. Programming Session 진입 / Reset기능 / 진단_Hard Reset / MCU_Sleep\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-24?filter=allopenissues]

### [743732] 시스템 설계/검증 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 4건

#### [743734] 시스템 Reset 로직 설계 미흡
- **상태**: New

- **하위 아이템**: 1건

#### [630974] [PLBM_10] [HKMCJGRLBM-24] PDC Reset 요청에 의한 Reset Complete 이후 휴지 시간 없이 팩 SOC 즉시 Recal 됨
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 시스템 설계/검증 미흡
  - **3차 분류**: 시스템 Reset 로직 설계 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P7. 데이터 관리 (NVM/EEPROM/Flash)
  - **2차 기능분류**: 과거 데이터 오입 사용
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-24] PDC Reset 요청에 의한 Reset Complete 이후 휴지 시간 없이 팩 SOC 즉시 Recal 됨
원인
 DC reset 시 SOC recalibration이 수행 된 시간을 NVM에 저장 하지 않은 상태에서~, reset 이후 과거 시간 정보를 load하여 지난 휴지 시간이 경과 한 것으로 오인하여 SOC가 잘못 recal 됨.\\
검토 시에 PDC reset 뿐만 아니라 진단에 의한 Hard reset 시에도 NVM에 저장 되어야 함.
문제점 개선
 1. System Reset 요청시~, APP_RTC_Save_SocRecal_Pause_Done_Time()을 실행하여 SocRecal_Pause_Done_Time을 갱신함\\
~- System Reset 요청\\
. Programming Session 진입 / Reset기능 / 진단_Hard Reset / MCU_Sleep\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-24?filter=allopenissues]

#### [743736] 모듈간 연계 고려 미흡
- **상태**: New

- **하위 아이템**: 1건

#### [630970] [PLBM_8] [HKMCJGRLBM-19] [CAN FD 2세대 차종] 리셋 기능 강건화 적용 건 - Jira
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 시스템 설계/검증 미흡
  - **3차 분류**: 모듈간 연계 고려 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P10. 시스템 서비스
  - **2차 기능분류**: ECU State 관리 오류
- **설명**: 문제점
 [HKMCJGRLBM~-19] [CAN FD 2세대 차종] 리셋 기능 강건화 적용 건 ~- Jira
원인
 리셋 수행 조건 만족 후 실제 리셋이 수행되지 못한 경우~, 플래그 값 초기화 처리 누락
문제점 개선
 실제 리셋 기능을 수행하지 못한 경우~, 리셋을 수행하기 위한 초기 조건으로 Normal Mode로 진입 시 해당 플래그 강제 초기화 처리.\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-19?filter=allopenissues]

#### [743738] 제어기간 연계 고려 미흡
- **상태**: New

#### [743740] 시스템 에러 감지 미흡
- **상태**: New

### [743730] 요구사양 미확인/오해석
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 5건

#### [630956] [PLBM_1] S32K31x MCU에서 Stack fault 로 인한 Reset, 스케줄링이상 동작 발생
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P10. 시스템 서비스
  - **2차 기능분류**: OS Task 스케줄링 오류
- **설명**: __NQ5__
문제점
 S32K31x MCU에서 Stack fault 로 인한 Reset~, 스케줄링이상 동작 발생
원인
 오토에버 수평전개 사항 (NML 패치)
문제점 개선
 1. OS 패치 적용(연관 모듈 : ECUM)\\
~- b_autosar_sys_EcuM_R40(Ver 3.1.4.0)\\
~- integration_EcuM(Ver 2.8.3.0_HF1)\\
~- b_autosar_sys_Os_cytxxx_R40(Ver 2.4.5.0_HF1)

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-10]

#### [630968] [PLBM_7] [HKMCJGRLBM-16] [NX5] HSM 보안 사양에 대한 상태 값을 RDBI 서비스에 추가 필요
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
  - **2차 기능분류**: 사양 해석 불일치
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-16] [NX5] HSM 보안 사양에 대한 상태 값을 RDBI 서비스에 추가 필요
원인
 진단 통신 서비스 활용 (상세는 ES95486~-02에서 "Annex. C Data Transmission Functional Unit Data Parameter Definitions 확인 필요~')\\
~- 사용 서비스: ReadDatabyIdentifier (22hex) service\\
~- 사용 DID: 0xF1C0 [ECUSecurityInformationDataIdentifier]
문제점 개선
 필수 확인 HSM 상태 값\\
~- Configuration Lock State : 설정 (Enabled)~, 미설정 (Disabled)\\
~- Secure Boot State : 설정 (Enabled)~, 미설정 (Disabled)\\
~- Secure Debug State : 설정 (Enabled)~, 미설정 (Disabled)~, 설정 이후 인증에 따른 임시해제\\
(DebugProtectionTempStop)~, Debug port 미사용 설정 (Debug Disable)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-16?filter=allopenissues]

#### [630972] [PLBM_9] [HKMCJGRLBM-20] [공통] PLBM MAX방전시 빌트인캠 할당량 실시간 미반영
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
  - **2차 기능분류**: 사양 해석 불일치
- **설명**: 문제점
 [HKMCJGRLBM~-20] [공통] PLBM MAX방전시 빌트인캠 할당량 실시간 미반영
원인
 1. 개발단계(PROTO~P1) 때~, 고객(HMC 김성태 책임)과 실차평가 후 Wrap~-up 회의 시 해당 방향으로 정해짐.\\
2. 양산 이후 고객 쪽에서 이슈가 발생하였고~, 검토 후 문제가 아니라고 회신함 (배강우 책임 통해서)\\
3. 이후 경쟁사와 동작이 다르다는 내용이 접수 됨 (어느쪽이 정답인지는 모르나~, 경쟁사 측 동작이 더 맞다고 생각되어 JIRA티켓 상신)
문제점 개선
 1. 맥스 방전 시 컨버터 방전 할당량 사용 후 빌트인캠 전력 할당량 사용 시 빌트인캠 SOC 실시간 갱신으로 설계\\
1~-1. (AS~-IS): 맥스 방전 시 빌트인캠 SOC를 실시간 갱신하지 않음 (빌트인캠 SOC는 빌트인캠 방전 시에만 갱신 됨)\\
1~-2. (TO~-BE): 맥스 방전 시 빌트인캠 SOC를 실시간 갱신하도록 변경 (맥스 방전 시에는 빌트인캠 방전량뿐만 아니라 컨버터 방전량까지 포함할 것)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-20?filter=allopenissues]

#### [630982] [PLBM_14] [HKMCJGRLBM-35] IPS Current 센싱 오류
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P5. 입력 처리 (ADC/GPIO/센싱)
  - **2차 기능분류**: 샘플링 주기 설정 오류
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-35] IPS Current 센싱 오류
원인
 기존 5ms Task 코드 변경(5ms ~-~> 10ms) 시 누락으로 IPS_Interface Task가 변경되지 않아 Sampling 주기 / Filtering Time 변경 필요
문제점 개선
 Sampling 주기(60ms) 에 맞게 코드 변경\\
~- Task 변경(5ms ~-~>10ms) / IPS_SEL_CYCLE_NUM 값 변경(10 ~-~>2)~, IPS_AVG_NUM(6 ~-~>12)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-35?filter=allopenissues]

#### [630992] [PLBM_19] [HKMCJGRLBM-52] Lin 진단 go-to-sleep 명령 시 즉시 진입 불가 현상 개선
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
  - **2차 기능분류**: Mode 전이 타이밍 오류
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-52] Lin 진단 go~-to~-sleep 명령 시 즉시 진입 불가 현상 개선
원인
 Lin 버스가 4초 이상 비활성화 시 Lin Slave Nodes는 최소 4초에서 10초 사이에 버스 Sleep Mode 진입 필요.\\
네트워크 내 모든 노드들은 동시에 Sleep 전환이 이루어져야 하므로~, 각 시스템별 Inactive Sleep 조건을 위한 시간이 있으며~, 미정의 시 4초(Default).\\
관련 사양 만족을 위해 4초 후 Sleep에 진입하나~, 진단의 경우 즉시 진입하는 것으로 수정 필요.\\
* ES90600~-00 Sleep Mode 사양 참고
문제점 개선
 Lin_Slave.c~, App_Lin_Interface.c~, App_Lin_Interface.h 수정\\
1. Lin_Busoff 함수 생성 및 UserCallout_GoToSleepDetection 함수 내 추가\\
진단 명령(Master)을 통한 Lin Inactive 진입 시 inactive 관련 변수 변경\\
g_LIN_INF_Var.Operation_Control_Inactive_Cnt = 550\\
g_LIN_INF_Var.LIN_INF_Mode_Operation_Control = 0\\
g_LIN_INF_Var.Bus_Inactive_Cnt = 400\\
g_LIN_INF_Var.LIN_INF_Mode = 0\\
~-~> 4초 후 Lin Inactive가 아닌 즉시 Lin Inactive되도록 수정 및 검증 완료

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-52?filter=allopenissues]

### [743728] 요구사양 분석/검증 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 1건

#### [743730] 요구사양 미확인/오해석
- **상태**: New

- **하위 아이템**: 5건

#### [630956] [PLBM_1] S32K31x MCU에서 Stack fault 로 인한 Reset, 스케줄링이상 동작 발생
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P10. 시스템 서비스
  - **2차 기능분류**: OS Task 스케줄링 오류
- **설명**: __NQ5__
문제점
 S32K31x MCU에서 Stack fault 로 인한 Reset~, 스케줄링이상 동작 발생
원인
 오토에버 수평전개 사항 (NML 패치)
문제점 개선
 1. OS 패치 적용(연관 모듈 : ECUM)\\
~- b_autosar_sys_EcuM_R40(Ver 3.1.4.0)\\
~- integration_EcuM(Ver 2.8.3.0_HF1)\\
~- b_autosar_sys_Os_cytxxx_R40(Ver 2.4.5.0_HF1)

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-10]

#### [630968] [PLBM_7] [HKMCJGRLBM-16] [NX5] HSM 보안 사양에 대한 상태 값을 RDBI 서비스에 추가 필요
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
  - **2차 기능분류**: 사양 해석 불일치
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-16] [NX5] HSM 보안 사양에 대한 상태 값을 RDBI 서비스에 추가 필요
원인
 진단 통신 서비스 활용 (상세는 ES95486~-02에서 "Annex. C Data Transmission Functional Unit Data Parameter Definitions 확인 필요~')\\
~- 사용 서비스: ReadDatabyIdentifier (22hex) service\\
~- 사용 DID: 0xF1C0 [ECUSecurityInformationDataIdentifier]
문제점 개선
 필수 확인 HSM 상태 값\\
~- Configuration Lock State : 설정 (Enabled)~, 미설정 (Disabled)\\
~- Secure Boot State : 설정 (Enabled)~, 미설정 (Disabled)\\
~- Secure Debug State : 설정 (Enabled)~, 미설정 (Disabled)~, 설정 이후 인증에 따른 임시해제\\
(DebugProtectionTempStop)~, Debug port 미사용 설정 (Debug Disable)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-16?filter=allopenissues]

#### [630972] [PLBM_9] [HKMCJGRLBM-20] [공통] PLBM MAX방전시 빌트인캠 할당량 실시간 미반영
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
  - **2차 기능분류**: 사양 해석 불일치
- **설명**: 문제점
 [HKMCJGRLBM~-20] [공통] PLBM MAX방전시 빌트인캠 할당량 실시간 미반영
원인
 1. 개발단계(PROTO~P1) 때~, 고객(HMC 김성태 책임)과 실차평가 후 Wrap~-up 회의 시 해당 방향으로 정해짐.\\
2. 양산 이후 고객 쪽에서 이슈가 발생하였고~, 검토 후 문제가 아니라고 회신함 (배강우 책임 통해서)\\
3. 이후 경쟁사와 동작이 다르다는 내용이 접수 됨 (어느쪽이 정답인지는 모르나~, 경쟁사 측 동작이 더 맞다고 생각되어 JIRA티켓 상신)
문제점 개선
 1. 맥스 방전 시 컨버터 방전 할당량 사용 후 빌트인캠 전력 할당량 사용 시 빌트인캠 SOC 실시간 갱신으로 설계\\
1~-1. (AS~-IS): 맥스 방전 시 빌트인캠 SOC를 실시간 갱신하지 않음 (빌트인캠 SOC는 빌트인캠 방전 시에만 갱신 됨)\\
1~-2. (TO~-BE): 맥스 방전 시 빌트인캠 SOC를 실시간 갱신하도록 변경 (맥스 방전 시에는 빌트인캠 방전량뿐만 아니라 컨버터 방전량까지 포함할 것)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-20?filter=allopenissues]

#### [630982] [PLBM_14] [HKMCJGRLBM-35] IPS Current 센싱 오류
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P5. 입력 처리 (ADC/GPIO/센싱)
  - **2차 기능분류**: 샘플링 주기 설정 오류
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-35] IPS Current 센싱 오류
원인
 기존 5ms Task 코드 변경(5ms ~-~> 10ms) 시 누락으로 IPS_Interface Task가 변경되지 않아 Sampling 주기 / Filtering Time 변경 필요
문제점 개선
 Sampling 주기(60ms) 에 맞게 코드 변경\\
~- Task 변경(5ms ~-~>10ms) / IPS_SEL_CYCLE_NUM 값 변경(10 ~-~>2)~, IPS_AVG_NUM(6 ~-~>12)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-35?filter=allopenissues]

#### [630992] [PLBM_19] [HKMCJGRLBM-52] Lin 진단 go-to-sleep 명령 시 즉시 진입 불가 현상 개선
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
  - **2차 기능분류**: Mode 전이 타이밍 오류
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-52] Lin 진단 go~-to~-sleep 명령 시 즉시 진입 불가 현상 개선
원인
 Lin 버스가 4초 이상 비활성화 시 Lin Slave Nodes는 최소 4초에서 10초 사이에 버스 Sleep Mode 진입 필요.\\
네트워크 내 모든 노드들은 동시에 Sleep 전환이 이루어져야 하므로~, 각 시스템별 Inactive Sleep 조건을 위한 시간이 있으며~, 미정의 시 4초(Default).\\
관련 사양 만족을 위해 4초 후 Sleep에 진입하나~, 진단의 경우 즉시 진입하는 것으로 수정 필요.\\
* ES90600~-00 Sleep Mode 사양 참고
문제점 개선
 Lin_Slave.c~, App_Lin_Interface.c~, App_Lin_Interface.h 수정\\
1. Lin_Busoff 함수 생성 및 UserCallout_GoToSleepDetection 함수 내 추가\\
진단 명령(Master)을 통한 Lin Inactive 진입 시 inactive 관련 변수 변경\\
g_LIN_INF_Var.Operation_Control_Inactive_Cnt = 550\\
g_LIN_INF_Var.LIN_INF_Mode_Operation_Control = 0\\
g_LIN_INF_Var.Bus_Inactive_Cnt = 400\\
g_LIN_INF_Var.LIN_INF_Mode = 0\\
~-~> 4초 후 Lin Inactive가 아닌 즉시 Lin Inactive되도록 수정 및 검증 완료

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-52?filter=allopenissues]

### [743726] 복합
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 4건

#### [743728] 요구사양 분석/검증 미흡
- **상태**: New

- **하위 아이템**: 1건

#### [743730] 요구사양 미확인/오해석
- **상태**: New

#### [743732] 시스템 설계/검증 미흡
- **상태**: New

- **하위 아이템**: 4건

#### [743734] 시스템 Reset 로직 설계 미흡
- **상태**: New

#### [743736] 모듈간 연계 고려 미흡
- **상태**: New

#### [743738] 제어기간 연계 고려 미흡
- **상태**: New

#### [743740] 시스템 에러 감지 미흡
- **상태**: New

#### [743742] 아키텍처 설계/검증 미흡
- **상태**: New

- **하위 아이템**: 5건

#### [743744] 메모리 Task 설계 미흡
- **상태**: New

#### [743746] 동작 우선순위 설계 오류
- **상태**: New

#### [743748] 인터럽트 설계 오류
- **상태**: New

#### [743750] 응답 시간 설계 오류
- **상태**: New

#### [743752] 공유 자원 설계 오류
- **상태**: New

#### [743754] 상세 설계/검증 미흡
- **상태**: New

- **하위 아이템**: 4건

#### [743756] 환경 조건 고려 미흡
- **상태**: New

#### [743758] 임계값 설계 미흡
- **상태**: New

#### [743760] 예외 입력/신호 처리 미흡
- **상태**: New

#### [743762] 로직 예외 흐름 고려 미흡
- **상태**: New

### [743724] 버전/코드 관리 미흡
- **상태**: New
- **설명**: (없음)

### [743722] SW 변경 영향도 분석 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 4건

#### [630958] [PLBM_2] [TK1_SOP] 미사용 메시지(0x159, LBM_FD_02_100ms)의 초깃값 송출이 dbc와 다르다
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P3. CAN (CAN/CAN FD/NM)
  - **2차 기능분류**: 메시지 조기값/Default 오류
- **설명**: __TK1__
문제점
 [TK1_SOP] 미사용 메시지(0x159~, LBM_FD_02_100ms)의 초깃값 송출이 dbc와 다름
원인
 CAN DB에 정의된 초깃값을 사용하지 않고~, 잘못된 값으로 초기화
문제점 개선
 CAN DB에 정의된 초깃값으로 초기화 (첨부 참조)\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-8]

#### [630976] [PLBM_11] [HKMCJGRLBM-25] [공통] HSM 보안 라이브러리 변경으로 인한 기양산차 OTA 불가
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P8. 보안 (OTA/FBL/HSM)
  - **2차 기능분류**: OTA 호환성 문제
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-25] [공통] HSM 보안 라이브러리 변경으로 인한 기양산차 OTA 불가
원인
 1. 신규차종 추가(BC4i)에 따른 HSM 발행 과정에서 보안라이브러리 “암호화 Key” 변경\\
1) 보안라이브러리(SLB~-231212~-0006) ~-~>신규 보안라이브러리(SLB~-250306~-0002)\\
2) 변경 시점 : 25년 3월\\
※ “암호화 Key” 용어는 추상적인 개념으로 명확한 용어로 사용이 아님을 참고 (문제현상에 대한 설명을 위한 용어)
문제점 개선
 1. 보안라이브러리(SLB~-250306~-0002) ~-~> 보안라이브러리(SLB~-231212~-0006)로 원복 필요\\
~-. 양산차종 OTA 업데이트 정상화\\
ㄴ 보안 라이브러리 원복 완료 (25.05.30)\\
ㄴ 배포 지연 양산 차종(TK1~, LX3) 배포 완 (25.06.05)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-25?filter=allopenissues]

#### [630978] [PLBM_12] [HKMCJGRLBM-26] [NX5] 정적수정 코드 버그, 진단_Read_DTC_Count&TimeStamp
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P7. 데이터 관리 (NVM/EEPROM/Flash)
  - **2차 기능분류**: 데이터 크기/타입 불일치
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-26] [NX5] 정적수정 코드 버그~, 진단_Read_DTC_Count&TimeStamp
원인
 실제 활용가능한 변수 크기와 선언된 변수 크기가 불일치
문제점 개선
 enum 타입의 명시적 캐스팅을 tU08 ~-~> tU16으로 수정.\\
~- 문제가 발생되는 코드에서 + 연산에 관련된 모든 데이터 형을 tU16으로 일치.\\
~- 정적 검증 코드 기반으로 모든 명시적 캐스팅에 대한 에러 재확인(~5/20)\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-26?filter=allissues]

#### [630988] [PLBM_17] [HKMCJGRLBM-47] [NQ6, SX3] MCU 전력 소모량 Available Power 반영
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Application
  - **1차 기능분류**: A1. 기능 로직
  - **2차 기능분류**: Available Power 계산
- **설명**: __NQ6~, SX3__
문제점
 [HKMCJGRLBM~-47] [NQ6~, SX3] MCU 전력 소모량 Available Power 반영
원인
 1. LBM에서 출력하는 신호(BLTN Available Power)에 MCU 전력 소모량 미반영\\
2. ACU 및 NCAP IPS에 의한 전력 소모량을 Normal Available Power와 BLTN Avail Power에 미 포함 하였음.
문제점 개선
 1. ACU 및 NCAP IPS 소모 전력을 Normal Available Power의 연산에 포함 (25~'08/28~, 장길남 책임~, 심정현 책임~, 정세봉 책임~, 호성모 선임 협의 완)\\
1) Parking current: (\~ Shunt 전류\~ ~- IPS(4ch~, 2ch) 전류) =~>\\
(\~ Shunt 전류\~ ~- BLTN 전류)로 연산 식 수정\\
2) BLTN 상태에 따른 전류 계산 방법 변경\\
~- BLTN ON 상태\\
① Normal Available Power ~- (\~ Shunt 전류\~ ~- BLTN 전류)\\
② BLTN Available Power ~- BLTN 전류\\
~- BLTN OFF 상태\\
① Normal Available Power ~- \~ Shunt 전류\~ \\
② BLTN Available Power 감소 없음\\
\\
2. Normal Available Power == 0일 때~, BLTN Available Power에도 PCB 전력 소모량을 반영하여 계산

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-47?filter=allopenissues]

### [743720] 변경점 반영 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 1건

#### [1020908] [PLBM_20][HKMCJGRLBM-179]특정 타이밍에 PDC CAN WakeUp 시 간헐적으로 PLBM WakeUp 미동작
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: 변경점 반영 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
  - **2차 기능분류**: Mode 전이 타이밍 오류
- **설명**: %%;font-style:normal;font-variant-ligatures:normal;font-variant-caps:normal;letter-spacing:normal;orphans:2;text-align:start;text-indent:0px;text-transform:none;widows:2;word-spacing:0px;-webkit-text-stroke-width:0px;white-space:normal;background-color:rgb(255, 255, 255);text-decoration-thickness:initial;text-decoration-style:initial;text-decoration-color:initial;display:inline !important;float:none;) %!__NX5__
문제점
[HKMCJGRLBM~-179] 특정 타이밍에 PDC CAN WakeUp 시 간헐적으로 PLBM WakeUp 미동작
원인
%%
1)%%ASW%!%%에서 %!%%BSW%!%%로 %!%%MCU %!%%슬립 요청 후 %!%%ASW%!%%는 종료%!%%.%!%!
%%
2)%%BSW%!%%에서 %!%%MCU %!%%슬립 처리 중%!%% CAN %!%%메시지를 수신%!%%. SBC%!%%에서 %!%%CAN_RX Pin%!%%을 %!%%High %!%%à%!%% Low%!%%로 변경하여 %!%%MCU%!%%에 알림%!%%.%!%!
%%
3)%%ASW%!%%가 종료된 상태라 %!%%CAN_Rx Pin%!%%이 %!%%Low%!%%인 걸 확인할 수 없어서%!%%~, CAN wakeup %!%%하지 않고 슬립에 진입%!%!
문제점 개선
%%
1)%%CAN %!%%네트워크 슬립 시 %!%%CAN Rx%!%%에 대한%!%% %!%%(text-decoration:underline;)%%ICU%!%!%%(text-decoration:underline;)%% 활성화 추가%!%!%%.%!%!
%%
2)%%BSW%!%%에서%!%% MCU %!%%슬립 처리 중 %!%%CAN %!%%메시지를 수신%!%%. %!%!
%%
3)%%SBC%!%%에서 %!%%CAN_RX Pin%!%%을 %!%%H %!%%à%!%% L%!%%로 변경하여 %!%%MCU%!%%에 알림%!%%.%!%!
%%
4)%%SBC%!%%로부터의 %!%%CAN Wakeup %!%%정보%!%% %!%%Pin%!%% %!%%H%!%%à%!%%L)%!%%를 %!%%ICU%!%%에서 감지%!%%.%!%!
%%
5)%%PLBM CAN Wakeup %!%%및 정상 동작%!%!
\\
\\
%%''*ICU(Input Capture Unit):''%! %% %! %%''CAN Rx H ''%! %%''à''%! %%'' L''%! %%'' 변화를 감지''%! %%''. ''%!\\
\\


%%;text-align:start;background-color:rgb(255, 255, 255);float:none;display:inline !important;)* 자료 첨부 : %![[HKMCJGRLBM-179] [NX5] 특정 타이밍에 PDC CAN WakeUp 시 간헐적으로 PLBM WakeUp 미동작 - Jira|https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-179?filter=allissues]

### [743718] 변경점 관리 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 3건

#### [743720] 변경점 반영 미흡
- **상태**: New

- **하위 아이템**: 1건

#### [1020908] [PLBM_20][HKMCJGRLBM-179]특정 타이밍에 PDC CAN WakeUp 시 간헐적으로 PLBM WakeUp 미동작
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: 변경점 반영 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
  - **2차 기능분류**: Mode 전이 타이밍 오류
- **설명**: %%;font-style:normal;font-variant-ligatures:normal;font-variant-caps:normal;letter-spacing:normal;orphans:2;text-align:start;text-indent:0px;text-transform:none;widows:2;word-spacing:0px;-webkit-text-stroke-width:0px;white-space:normal;background-color:rgb(255, 255, 255);text-decoration-thickness:initial;text-decoration-style:initial;text-decoration-color:initial;display:inline !important;float:none;) %!__NX5__
문제점
[HKMCJGRLBM~-179] 특정 타이밍에 PDC CAN WakeUp 시 간헐적으로 PLBM WakeUp 미동작
원인
%%
1)%%ASW%!%%에서 %!%%BSW%!%%로 %!%%MCU %!%%슬립 요청 후 %!%%ASW%!%%는 종료%!%%.%!%!
%%
2)%%BSW%!%%에서 %!%%MCU %!%%슬립 처리 중%!%% CAN %!%%메시지를 수신%!%%. SBC%!%%에서 %!%%CAN_RX Pin%!%%을 %!%%High %!%%à%!%% Low%!%%로 변경하여 %!%%MCU%!%%에 알림%!%%.%!%!
%%
3)%%ASW%!%%가 종료된 상태라 %!%%CAN_Rx Pin%!%%이 %!%%Low%!%%인 걸 확인할 수 없어서%!%%~, CAN wakeup %!%%하지 않고 슬립에 진입%!%!
문제점 개선
%%
1)%%CAN %!%%네트워크 슬립 시 %!%%CAN Rx%!%%에 대한%!%% %!%%(text-decoration:underline;)%%ICU%!%!%%(text-decoration:underline;)%% 활성화 추가%!%!%%.%!%!
%%
2)%%BSW%!%%에서%!%% MCU %!%%슬립 처리 중 %!%%CAN %!%%메시지를 수신%!%%. %!%!
%%
3)%%SBC%!%%에서 %!%%CAN_RX Pin%!%%을 %!%%H %!%%à%!%% L%!%%로 변경하여 %!%%MCU%!%%에 알림%!%%.%!%!
%%
4)%%SBC%!%%로부터의 %!%%CAN Wakeup %!%%정보%!%% %!%%Pin%!%% %!%%H%!%%à%!%%L)%!%%를 %!%%ICU%!%%에서 감지%!%%.%!%!
%%
5)%%PLBM CAN Wakeup %!%%및 정상 동작%!%!
\\
\\
%%''*ICU(Input Capture Unit):''%! %% %! %%''CAN Rx H ''%! %%''à''%! %%'' L''%! %%'' 변화를 감지''%! %%''. ''%!\\
\\


%%;text-align:start;background-color:rgb(255, 255, 255);float:none;display:inline !important;)* 자료 첨부 : %![[HKMCJGRLBM-179] [NX5] 특정 타이밍에 PDC CAN WakeUp 시 간헐적으로 PLBM WakeUp 미동작 - Jira|https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-179?filter=allissues]

#### [743722] SW 변경 영향도 분석 미흡
- **상태**: New

- **하위 아이템**: 4건

#### [630958] [PLBM_2] [TK1_SOP] 미사용 메시지(0x159, LBM_FD_02_100ms)의 초깃값 송출이 dbc와 다르다
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P3. CAN (CAN/CAN FD/NM)
  - **2차 기능분류**: 메시지 조기값/Default 오류
- **설명**: __TK1__
문제점
 [TK1_SOP] 미사용 메시지(0x159~, LBM_FD_02_100ms)의 초깃값 송출이 dbc와 다름
원인
 CAN DB에 정의된 초깃값을 사용하지 않고~, 잘못된 값으로 초기화
문제점 개선
 CAN DB에 정의된 초깃값으로 초기화 (첨부 참조)\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-8]

#### [630976] [PLBM_11] [HKMCJGRLBM-25] [공통] HSM 보안 라이브러리 변경으로 인한 기양산차 OTA 불가
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P8. 보안 (OTA/FBL/HSM)
  - **2차 기능분류**: OTA 호환성 문제
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-25] [공통] HSM 보안 라이브러리 변경으로 인한 기양산차 OTA 불가
원인
 1. 신규차종 추가(BC4i)에 따른 HSM 발행 과정에서 보안라이브러리 “암호화 Key” 변경\\
1) 보안라이브러리(SLB~-231212~-0006) ~-~>신규 보안라이브러리(SLB~-250306~-0002)\\
2) 변경 시점 : 25년 3월\\
※ “암호화 Key” 용어는 추상적인 개념으로 명확한 용어로 사용이 아님을 참고 (문제현상에 대한 설명을 위한 용어)
문제점 개선
 1. 보안라이브러리(SLB~-250306~-0002) ~-~> 보안라이브러리(SLB~-231212~-0006)로 원복 필요\\
~-. 양산차종 OTA 업데이트 정상화\\
ㄴ 보안 라이브러리 원복 완료 (25.05.30)\\
ㄴ 배포 지연 양산 차종(TK1~, LX3) 배포 완 (25.06.05)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-25?filter=allopenissues]

#### [630978] [PLBM_12] [HKMCJGRLBM-26] [NX5] 정적수정 코드 버그, 진단_Read_DTC_Count&TimeStamp
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P7. 데이터 관리 (NVM/EEPROM/Flash)
  - **2차 기능분류**: 데이터 크기/타입 불일치
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-26] [NX5] 정적수정 코드 버그~, 진단_Read_DTC_Count&TimeStamp
원인
 실제 활용가능한 변수 크기와 선언된 변수 크기가 불일치
문제점 개선
 enum 타입의 명시적 캐스팅을 tU08 ~-~> tU16으로 수정.\\
~- 문제가 발생되는 코드에서 + 연산에 관련된 모든 데이터 형을 tU16으로 일치.\\
~- 정적 검증 코드 기반으로 모든 명시적 캐스팅에 대한 에러 재확인(~5/20)\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-26?filter=allissues]

#### [630988] [PLBM_17] [HKMCJGRLBM-47] [NQ6, SX3] MCU 전력 소모량 Available Power 반영
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Application
  - **1차 기능분류**: A1. 기능 로직
  - **2차 기능분류**: Available Power 계산
- **설명**: __NQ6~, SX3__
문제점
 [HKMCJGRLBM~-47] [NQ6~, SX3] MCU 전력 소모량 Available Power 반영
원인
 1. LBM에서 출력하는 신호(BLTN Available Power)에 MCU 전력 소모량 미반영\\
2. ACU 및 NCAP IPS에 의한 전력 소모량을 Normal Available Power와 BLTN Avail Power에 미 포함 하였음.
문제점 개선
 1. ACU 및 NCAP IPS 소모 전력을 Normal Available Power의 연산에 포함 (25~'08/28~, 장길남 책임~, 심정현 책임~, 정세봉 책임~, 호성모 선임 협의 완)\\
1) Parking current: (\~ Shunt 전류\~ ~- IPS(4ch~, 2ch) 전류) =~>\\
(\~ Shunt 전류\~ ~- BLTN 전류)로 연산 식 수정\\
2) BLTN 상태에 따른 전류 계산 방법 변경\\
~- BLTN ON 상태\\
① Normal Available Power ~- (\~ Shunt 전류\~ ~- BLTN 전류)\\
② BLTN Available Power ~- BLTN 전류\\
~- BLTN OFF 상태\\
① Normal Available Power ~- \~ Shunt 전류\~ \\
② BLTN Available Power 감소 없음\\
\\
2. Normal Available Power == 0일 때~, BLTN Available Power에도 PCB 전력 소모량을 반영하여 계산

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-47?filter=allopenissues]

#### [743724] 버전/코드 관리 미흡
- **상태**: New

### [743716] 기능 누락
- **상태**: New
- **설명**: (없음)

### [743714] 파라미터 관리 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 1건

#### [630980] [PLBM_13] [HKMCJGRLBM-28] [NQ5]ES90700-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TDL016)
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 파라미터 관리 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P3. CAN (CAN/CAN FD/NM)
  - **2차 기능분류**: DLC/Length 불일치
- **설명**: __NQ5__
문제점
 [HKMCJGRLBM~-28] [NQ5] ES90700~-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TDL016)
원인
 오토에버 문의 결과 DLC 6의 메시지에 OE 반응하지 않는 것은 정상동작으로 확인됨.\\
ㄴ CanIf 모듈▶CanIfPrivateCfg 설정 내 DLC Check Option이 Enable한 경우\\
설정된 DLC 6 Byte)\\
20240105_STD_LOCAL_PDC_2021_HS_Local_NM_v23.08.01_Modify_DLC.윷

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-28?filter=allopenissues]

### [743712] 로직 구현 오류
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 4건

#### [630984] [PLBM_15] [HKMCJGRLBM-44] [NQ5 PE] EOL라인 SOC 255%으로 인한 공정 Fail
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Application
  - **1차 기능분류**: A3. 데이터 처리
  - **2차 기능분류**: 변수 초기화
- **설명**: __NQ5 PE__
문제점
 [HKMCJGRLBM~-44] [NQ5 PE] EOL라인 SOC 255~%으로 인한 공정 Fail
원인
 1. 초기 SW 다운로드 후 PoR 시~, EEPROM 저장 변수 및 SOC 내부 변수가 제대로 set되지 않음. (고품1~3 사진 참조)\\
2. PoR 시 SOC Recalibration 수행 조건((SOC ==255) && (OCV == 19.4))을 만족하지 않아 조건 확인 로직에 계속 머무르며 SOC 255~% 송출.\\
3. 로직 구조 상 PoR시 Recalibration 수행하지 않으면 SOC 값이 갱신되지 않음. (진단 명령 Recal 수행도 불가능)
문제점 개선
 아래의 1) 또는 2) 조건을 하나라도 만족하는 경우 SOC Recalibration 수행할 수 있도록 조건 추가\\
1) 정상 PoR 동작 시 ((SOC ==255) && (OCV == 19.4))\\
2) 진단 강제 Recal 명령 수신 시 && Pack 전압 정상 범위 이내(0~15V)\\
\\
~-~> 조건 확인 로직에 갇혀 탈출하지 못해 SOC 255~%를 지속 송출하며 동작 불가 현상이 발생할 경우~,\\
강제 구동 명령으로 Recalibration을 수행하고 SOC를 정상적으로 갱신하기 위함.\\
~-~> 추가적으로 센싱 팩 전압이 정상 범위인지 확인하여 단순 EEPROM 값 저장의 문제인 경우 정상 동작하도록 하고~,\\
BMIC 센싱의 문제인 경우 동작하지 않도록 함.

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-44?filter=allopenissues]

#### [630986] [PLBM_16] [HKMCJGRLBM-46] [NQ5]ES90700-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TNM127)
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
  - **2차 기능분류**: Wake-up 이벤트 누락 (CAN/LIN/ICU)
- **설명**: __NQ5__
문제점
 [HKMCJGRLBM~-46] [NQ5] ES90700~-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TNM127)
원인
 APP에서 Sleep 요청 시점과 MCU_Sleep 진입 시점~, 사이에서 CAN WakeUp 판단을 하지 못하는 것으로 판단됨
문제점 개선
 증상발생 구간에서 MCU_Sleep 에 진입하지 못하도록 “Event Wakeup” 를 확인 할 수 있도록 ICU를 활성화 함\\
첨부자료 250818_ES90700_10_FAIL건분석.pptx 참고

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-46?filter=allopenissues]

#### [630990] [PLBM_18] [HKMCJGRLBM-48] IO Control 강제 구동 시 Avapwr 계산로직 강건화 - Jira
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
  - **2차 기능분류**: 진단 경제구동 로직 오류 (IO Control/Recall)
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-48] IO Control 강제 구동 시 Avapwr 계산로직 강건화 ~- Jira
원인
 강제 구동 시 방전 허용량을 Recal이 되나 모드 진입/탈출을 반복하여 Recal이 됨\\
(AvaPwr_Mode = Normal / Checking 반복)\\
~- 충전 강제구동 후 강제구동 OFF 시 충전진입 Flag Clear 되지 않음
문제점 개선
 IO Control 강제 구동 시 Avapwr Mode 진입/탈출 조건 변경\\
수정 파일 : App_Charger.c\\
수정 부분 : App_Charger_Proc_AvaPwr_Normal()\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-48?filter=allopenissues]

#### [630962] [PLBM_4] [공통]진단_DTC Count&Time($BC09) – 충전시, Count +2 이슈 추가 개선
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
  - **2차 기능분류**: DTC Count/TimeStamp 불일치
- **설명**: 문제점
 [공통] 진단_DTC Count&Time($BC09) – 충전시~, Count +2 이슈 추가 개선
원인
 1. 충전모드 중에~, DTC 발생으로 충전 금지 ~-~> OperationCycle() 함수 실행 ~-~> DTC 발생시~, Count +2\\
~- 추가 설명 : OperationCycle() 함수 실행시~, DTC Status가 OFF 되는 현상으로 인한 증상 발생
문제점 개선
 ~- DemStatusBitStorageTestFailed : TRUE로 변경\\
 ㄴ 결과 : DTC 상태 ON에서 OperationCycle() 함수 실행으로 인한 DTC상태 OFF 가 발생되지 않음

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-11]

### [743710] 최초 구현 미흡
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 3건

#### [743712] 로직 구현 오류
- **상태**: New

- **하위 아이템**: 4건

#### [630984] [PLBM_15] [HKMCJGRLBM-44] [NQ5 PE] EOL라인 SOC 255%으로 인한 공정 Fail
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Application
  - **1차 기능분류**: A3. 데이터 처리
  - **2차 기능분류**: 변수 초기화
- **설명**: __NQ5 PE__
문제점
 [HKMCJGRLBM~-44] [NQ5 PE] EOL라인 SOC 255~%으로 인한 공정 Fail
원인
 1. 초기 SW 다운로드 후 PoR 시~, EEPROM 저장 변수 및 SOC 내부 변수가 제대로 set되지 않음. (고품1~3 사진 참조)\\
2. PoR 시 SOC Recalibration 수행 조건((SOC ==255) && (OCV == 19.4))을 만족하지 않아 조건 확인 로직에 계속 머무르며 SOC 255~% 송출.\\
3. 로직 구조 상 PoR시 Recalibration 수행하지 않으면 SOC 값이 갱신되지 않음. (진단 명령 Recal 수행도 불가능)
문제점 개선
 아래의 1) 또는 2) 조건을 하나라도 만족하는 경우 SOC Recalibration 수행할 수 있도록 조건 추가\\
1) 정상 PoR 동작 시 ((SOC ==255) && (OCV == 19.4))\\
2) 진단 강제 Recal 명령 수신 시 && Pack 전압 정상 범위 이내(0~15V)\\
\\
~-~> 조건 확인 로직에 갇혀 탈출하지 못해 SOC 255~%를 지속 송출하며 동작 불가 현상이 발생할 경우~,\\
강제 구동 명령으로 Recalibration을 수행하고 SOC를 정상적으로 갱신하기 위함.\\
~-~> 추가적으로 센싱 팩 전압이 정상 범위인지 확인하여 단순 EEPROM 값 저장의 문제인 경우 정상 동작하도록 하고~,\\
BMIC 센싱의 문제인 경우 동작하지 않도록 함.

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-44?filter=allopenissues]

#### [630986] [PLBM_16] [HKMCJGRLBM-46] [NQ5]ES90700-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TNM127)
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
  - **2차 기능분류**: Wake-up 이벤트 누락 (CAN/LIN/ICU)
- **설명**: __NQ5__
문제점
 [HKMCJGRLBM~-46] [NQ5] ES90700~-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TNM127)
원인
 APP에서 Sleep 요청 시점과 MCU_Sleep 진입 시점~, 사이에서 CAN WakeUp 판단을 하지 못하는 것으로 판단됨
문제점 개선
 증상발생 구간에서 MCU_Sleep 에 진입하지 못하도록 “Event Wakeup” 를 확인 할 수 있도록 ICU를 활성화 함\\
첨부자료 250818_ES90700_10_FAIL건분석.pptx 참고

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-46?filter=allopenissues]

#### [630990] [PLBM_18] [HKMCJGRLBM-48] IO Control 강제 구동 시 Avapwr 계산로직 강건화 - Jira
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
  - **2차 기능분류**: 진단 경제구동 로직 오류 (IO Control/Recall)
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-48] IO Control 강제 구동 시 Avapwr 계산로직 강건화 ~- Jira
원인
 강제 구동 시 방전 허용량을 Recal이 되나 모드 진입/탈출을 반복하여 Recal이 됨\\
(AvaPwr_Mode = Normal / Checking 반복)\\
~- 충전 강제구동 후 강제구동 OFF 시 충전진입 Flag Clear 되지 않음
문제점 개선
 IO Control 강제 구동 시 Avapwr Mode 진입/탈출 조건 변경\\
수정 파일 : App_Charger.c\\
수정 부분 : App_Charger_Proc_AvaPwr_Normal()\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-48?filter=allopenissues]

#### [630962] [PLBM_4] [공통]진단_DTC Count&Time($BC09) – 충전시, Count +2 이슈 추가 개선
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
  - **2차 기능분류**: DTC Count/TimeStamp 불일치
- **설명**: 문제점
 [공통] 진단_DTC Count&Time($BC09) – 충전시~, Count +2 이슈 추가 개선
원인
 1. 충전모드 중에~, DTC 발생으로 충전 금지 ~-~> OperationCycle() 함수 실행 ~-~> DTC 발생시~, Count +2\\
~- 추가 설명 : OperationCycle() 함수 실행시~, DTC Status가 OFF 되는 현상으로 인한 증상 발생
문제점 개선
 ~- DemStatusBitStorageTestFailed : TRUE로 변경\\
 ㄴ 결과 : DTC 상태 ON에서 OperationCycle() 함수 실행으로 인한 DTC상태 OFF 가 발생되지 않음

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-11]

#### [743714] 파라미터 관리 미흡
- **상태**: New

- **하위 아이템**: 1건

#### [630980] [PLBM_13] [HKMCJGRLBM-28] [NQ5]ES90700-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TDL016)
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 파라미터 관리 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P3. CAN (CAN/CAN FD/NM)
  - **2차 기능분류**: DLC/Length 불일치
- **설명**: __NQ5__
문제점
 [HKMCJGRLBM~-28] [NQ5] ES90700~-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TDL016)
원인
 오토에버 문의 결과 DLC 6의 메시지에 OE 반응하지 않는 것은 정상동작으로 확인됨.\\
ㄴ CanIf 모듈▶CanIfPrivateCfg 설정 내 DLC Check Option이 Enable한 경우\\
설정된 DLC 6 Byte)\\
20240105_STD_LOCAL_PDC_2021_HS_Local_NM_v23.08.01_Modify_DLC.윷

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-28?filter=allopenissues]

#### [743716] 기능 누락
- **상태**: New

### [743708] 단순
- **상태**: New
- **설명**: (없음)

- **하위 아이템**: 2건

#### [743710] 최초 구현 미흡
- **상태**: New

- **하위 아이템**: 3건

#### [743712] 로직 구현 오류
- **상태**: New

#### [743714] 파라미터 관리 미흡
- **상태**: New

#### [743716] 기능 누락
- **상태**: New

#### [743718] 변경점 관리 미흡
- **상태**: New

- **하위 아이템**: 3건

#### [743720] 변경점 반영 미흡
- **상태**: New

#### [743722] SW 변경 영향도 분석 미흡
- **상태**: New

#### [743724] 버전/코드 관리 미흡
- **상태**: New

### [630992] [PLBM_19] [HKMCJGRLBM-52] Lin 진단 go-to-sleep 명령 시 즉시 진입 불가 현상 개선
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
  - **2차 기능분류**: Mode 전이 타이밍 오류
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-52] Lin 진단 go~-to~-sleep 명령 시 즉시 진입 불가 현상 개선
원인
 Lin 버스가 4초 이상 비활성화 시 Lin Slave Nodes는 최소 4초에서 10초 사이에 버스 Sleep Mode 진입 필요.\\
네트워크 내 모든 노드들은 동시에 Sleep 전환이 이루어져야 하므로~, 각 시스템별 Inactive Sleep 조건을 위한 시간이 있으며~, 미정의 시 4초(Default).\\
관련 사양 만족을 위해 4초 후 Sleep에 진입하나~, 진단의 경우 즉시 진입하는 것으로 수정 필요.\\
* ES90600~-00 Sleep Mode 사양 참고
문제점 개선
 Lin_Slave.c~, App_Lin_Interface.c~, App_Lin_Interface.h 수정\\
1. Lin_Busoff 함수 생성 및 UserCallout_GoToSleepDetection 함수 내 추가\\
진단 명령(Master)을 통한 Lin Inactive 진입 시 inactive 관련 변수 변경\\
g_LIN_INF_Var.Operation_Control_Inactive_Cnt = 550\\
g_LIN_INF_Var.LIN_INF_Mode_Operation_Control = 0\\
g_LIN_INF_Var.Bus_Inactive_Cnt = 400\\
g_LIN_INF_Var.LIN_INF_Mode = 0\\
~-~> 4초 후 Lin Inactive가 아닌 즉시 Lin Inactive되도록 수정 및 검증 완료

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-52?filter=allopenissues]

### [630990] [PLBM_18] [HKMCJGRLBM-48] IO Control 강제 구동 시 Avapwr 계산로직 강건화 - Jira
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
  - **2차 기능분류**: 진단 경제구동 로직 오류 (IO Control/Recall)
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-48] IO Control 강제 구동 시 Avapwr 계산로직 강건화 ~- Jira
원인
 강제 구동 시 방전 허용량을 Recal이 되나 모드 진입/탈출을 반복하여 Recal이 됨\\
(AvaPwr_Mode = Normal / Checking 반복)\\
~- 충전 강제구동 후 강제구동 OFF 시 충전진입 Flag Clear 되지 않음
문제점 개선
 IO Control 강제 구동 시 Avapwr Mode 진입/탈출 조건 변경\\
수정 파일 : App_Charger.c\\
수정 부분 : App_Charger_Proc_AvaPwr_Normal()\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-48?filter=allopenissues]

### [630988] [PLBM_17] [HKMCJGRLBM-47] [NQ6, SX3] MCU 전력 소모량 Available Power 반영
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Application
  - **1차 기능분류**: A1. 기능 로직
  - **2차 기능분류**: Available Power 계산
- **설명**: __NQ6~, SX3__
문제점
 [HKMCJGRLBM~-47] [NQ6~, SX3] MCU 전력 소모량 Available Power 반영
원인
 1. LBM에서 출력하는 신호(BLTN Available Power)에 MCU 전력 소모량 미반영\\
2. ACU 및 NCAP IPS에 의한 전력 소모량을 Normal Available Power와 BLTN Avail Power에 미 포함 하였음.
문제점 개선
 1. ACU 및 NCAP IPS 소모 전력을 Normal Available Power의 연산에 포함 (25~'08/28~, 장길남 책임~, 심정현 책임~, 정세봉 책임~, 호성모 선임 협의 완)\\
1) Parking current: (\~ Shunt 전류\~ ~- IPS(4ch~, 2ch) 전류) =~>\\
(\~ Shunt 전류\~ ~- BLTN 전류)로 연산 식 수정\\
2) BLTN 상태에 따른 전류 계산 방법 변경\\
~- BLTN ON 상태\\
① Normal Available Power ~- (\~ Shunt 전류\~ ~- BLTN 전류)\\
② BLTN Available Power ~- BLTN 전류\\
~- BLTN OFF 상태\\
① Normal Available Power ~- \~ Shunt 전류\~ \\
② BLTN Available Power 감소 없음\\
\\
2. Normal Available Power == 0일 때~, BLTN Available Power에도 PCB 전력 소모량을 반영하여 계산

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-47?filter=allopenissues]

### [630986] [PLBM_16] [HKMCJGRLBM-46] [NQ5]ES90700-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TNM127)
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P1. Sleep/Wake-up/Power Mode
  - **2차 기능분류**: Wake-up 이벤트 누락 (CAN/LIN/ICU)
- **설명**: __NQ5__
문제점
 [HKMCJGRLBM~-46] [NQ5] ES90700~-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TNM127)
원인
 APP에서 Sleep 요청 시점과 MCU_Sleep 진입 시점~, 사이에서 CAN WakeUp 판단을 하지 못하는 것으로 판단됨
문제점 개선
 증상발생 구간에서 MCU_Sleep 에 진입하지 못하도록 “Event Wakeup” 를 확인 할 수 있도록 ICU를 활성화 함\\
첨부자료 250818_ES90700_10_FAIL건분석.pptx 참고

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-46?filter=allopenissues]

### [630984] [PLBM_15] [HKMCJGRLBM-44] [NQ5 PE] EOL라인 SOC 255%으로 인한 공정 Fail
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Application
  - **1차 기능분류**: A3. 데이터 처리
  - **2차 기능분류**: 변수 초기화
- **설명**: __NQ5 PE__
문제점
 [HKMCJGRLBM~-44] [NQ5 PE] EOL라인 SOC 255~%으로 인한 공정 Fail
원인
 1. 초기 SW 다운로드 후 PoR 시~, EEPROM 저장 변수 및 SOC 내부 변수가 제대로 set되지 않음. (고품1~3 사진 참조)\\
2. PoR 시 SOC Recalibration 수행 조건((SOC ==255) && (OCV == 19.4))을 만족하지 않아 조건 확인 로직에 계속 머무르며 SOC 255~% 송출.\\
3. 로직 구조 상 PoR시 Recalibration 수행하지 않으면 SOC 값이 갱신되지 않음. (진단 명령 Recal 수행도 불가능)
문제점 개선
 아래의 1) 또는 2) 조건을 하나라도 만족하는 경우 SOC Recalibration 수행할 수 있도록 조건 추가\\
1) 정상 PoR 동작 시 ((SOC ==255) && (OCV == 19.4))\\
2) 진단 강제 Recal 명령 수신 시 && Pack 전압 정상 범위 이내(0~15V)\\
\\
~-~> 조건 확인 로직에 갇혀 탈출하지 못해 SOC 255~%를 지속 송출하며 동작 불가 현상이 발생할 경우~,\\
강제 구동 명령으로 Recalibration을 수행하고 SOC를 정상적으로 갱신하기 위함.\\
~-~> 추가적으로 센싱 팩 전압이 정상 범위인지 확인하여 단순 EEPROM 값 저장의 문제인 경우 정상 동작하도록 하고~,\\
BMIC 센싱의 문제인 경우 동작하지 않도록 함.

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-44?filter=allopenissues]

### [630982] [PLBM_14] [HKMCJGRLBM-35] IPS Current 센싱 오류
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P5. 입력 처리 (ADC/GPIO/센싱)
  - **2차 기능분류**: 샘플링 주기 설정 오류
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-35] IPS Current 센싱 오류
원인
 기존 5ms Task 코드 변경(5ms ~-~> 10ms) 시 누락으로 IPS_Interface Task가 변경되지 않아 Sampling 주기 / Filtering Time 변경 필요
문제점 개선
 Sampling 주기(60ms) 에 맞게 코드 변경\\
~- Task 변경(5ms ~-~>10ms) / IPS_SEL_CYCLE_NUM 값 변경(10 ~-~>2)~, IPS_AVG_NUM(6 ~-~>12)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-35?filter=allopenissues]

### [630980] [PLBM_13] [HKMCJGRLBM-28] [NQ5]ES90700-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TDL016)
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 파라미터 관리 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P3. CAN (CAN/CAN FD/NM)
  - **2차 기능분류**: DLC/Length 불일치
- **설명**: __NQ5__
문제점
 [HKMCJGRLBM~-28] [NQ5] ES90700~-10(바디편의 도메인 고속 CAN 평가 사양서) 평가 FAIL 항목 분석 (TDL016)
원인
 오토에버 문의 결과 DLC 6의 메시지에 OE 반응하지 않는 것은 정상동작으로 확인됨.\\
ㄴ CanIf 모듈▶CanIfPrivateCfg 설정 내 DLC Check Option이 Enable한 경우\\
설정된 DLC 6 Byte)\\
20240105_STD_LOCAL_PDC_2021_HS_Local_NM_v23.08.01_Modify_DLC.윷

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-28?filter=allopenissues]

### [630978] [PLBM_12] [HKMCJGRLBM-26] [NX5] 정적수정 코드 버그, 진단_Read_DTC_Count&TimeStamp
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P7. 데이터 관리 (NVM/EEPROM/Flash)
  - **2차 기능분류**: 데이터 크기/타입 불일치
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-26] [NX5] 정적수정 코드 버그~, 진단_Read_DTC_Count&TimeStamp
원인
 실제 활용가능한 변수 크기와 선언된 변수 크기가 불일치
문제점 개선
 enum 타입의 명시적 캐스팅을 tU08 ~-~> tU16으로 수정.\\
~- 문제가 발생되는 코드에서 + 연산에 관련된 모든 데이터 형을 tU16으로 일치.\\
~- 정적 검증 코드 기반으로 모든 명시적 캐스팅에 대한 에러 재확인(~5/20)\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-26?filter=allissues]

### [630976] [PLBM_11] [HKMCJGRLBM-25] [공통] HSM 보안 라이브러리 변경으로 인한 기양산차 OTA 불가
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P8. 보안 (OTA/FBL/HSM)
  - **2차 기능분류**: OTA 호환성 문제
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-25] [공통] HSM 보안 라이브러리 변경으로 인한 기양산차 OTA 불가
원인
 1. 신규차종 추가(BC4i)에 따른 HSM 발행 과정에서 보안라이브러리 “암호화 Key” 변경\\
1) 보안라이브러리(SLB~-231212~-0006) ~-~>신규 보안라이브러리(SLB~-250306~-0002)\\
2) 변경 시점 : 25년 3월\\
※ “암호화 Key” 용어는 추상적인 개념으로 명확한 용어로 사용이 아님을 참고 (문제현상에 대한 설명을 위한 용어)
문제점 개선
 1. 보안라이브러리(SLB~-250306~-0002) ~-~> 보안라이브러리(SLB~-231212~-0006)로 원복 필요\\
~-. 양산차종 OTA 업데이트 정상화\\
ㄴ 보안 라이브러리 원복 완료 (25.05.30)\\
ㄴ 배포 지연 양산 차종(TK1~, LX3) 배포 완 (25.06.05)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-25?filter=allopenissues]

### [630974] [PLBM_10] [HKMCJGRLBM-24] PDC Reset 요청에 의한 Reset Complete 이후 휴지 시간 없이 팩 SOC 즉시 Recal 됨
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 시스템 설계/검증 미흡
  - **3차 분류**: 시스템 Reset 로직 설계 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P7. 데이터 관리 (NVM/EEPROM/Flash)
  - **2차 기능분류**: 과거 데이터 오입 사용
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-24] PDC Reset 요청에 의한 Reset Complete 이후 휴지 시간 없이 팩 SOC 즉시 Recal 됨
원인
 DC reset 시 SOC recalibration이 수행 된 시간을 NVM에 저장 하지 않은 상태에서~, reset 이후 과거 시간 정보를 load하여 지난 휴지 시간이 경과 한 것으로 오인하여 SOC가 잘못 recal 됨.\\
검토 시에 PDC reset 뿐만 아니라 진단에 의한 Hard reset 시에도 NVM에 저장 되어야 함.
문제점 개선
 1. System Reset 요청시~, APP_RTC_Save_SocRecal_Pause_Done_Time()을 실행하여 SocRecal_Pause_Done_Time을 갱신함\\
~- System Reset 요청\\
. Programming Session 진입 / Reset기능 / 진단_Hard Reset / MCU_Sleep\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-24?filter=allopenissues]

### [630972] [PLBM_9] [HKMCJGRLBM-20] [공통] PLBM MAX방전시 빌트인캠 할당량 실시간 미반영
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
  - **2차 기능분류**: 사양 해석 불일치
- **설명**: 문제점
 [HKMCJGRLBM~-20] [공통] PLBM MAX방전시 빌트인캠 할당량 실시간 미반영
원인
 1. 개발단계(PROTO~P1) 때~, 고객(HMC 김성태 책임)과 실차평가 후 Wrap~-up 회의 시 해당 방향으로 정해짐.\\
2. 양산 이후 고객 쪽에서 이슈가 발생하였고~, 검토 후 문제가 아니라고 회신함 (배강우 책임 통해서)\\
3. 이후 경쟁사와 동작이 다르다는 내용이 접수 됨 (어느쪽이 정답인지는 모르나~, 경쟁사 측 동작이 더 맞다고 생각되어 JIRA티켓 상신)
문제점 개선
 1. 맥스 방전 시 컨버터 방전 할당량 사용 후 빌트인캠 전력 할당량 사용 시 빌트인캠 SOC 실시간 갱신으로 설계\\
1~-1. (AS~-IS): 맥스 방전 시 빌트인캠 SOC를 실시간 갱신하지 않음 (빌트인캠 SOC는 빌트인캠 방전 시에만 갱신 됨)\\
1~-2. (TO~-BE): 맥스 방전 시 빌트인캠 SOC를 실시간 갱신하도록 변경 (맥스 방전 시에는 빌트인캠 방전량뿐만 아니라 컨버터 방전량까지 포함할 것)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-20?filter=allopenissues]

### [630970] [PLBM_8] [HKMCJGRLBM-19] [CAN FD 2세대 차종] 리셋 기능 강건화 적용 건 - Jira
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 시스템 설계/검증 미흡
  - **3차 분류**: 모듈간 연계 고려 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P10. 시스템 서비스
  - **2차 기능분류**: ECU State 관리 오류
- **설명**: 문제점
 [HKMCJGRLBM~-19] [CAN FD 2세대 차종] 리셋 기능 강건화 적용 건 ~- Jira
원인
 리셋 수행 조건 만족 후 실제 리셋이 수행되지 못한 경우~, 플래그 값 초기화 처리 누락
문제점 개선
 실제 리셋 기능을 수행하지 못한 경우~, 리셋을 수행하기 위한 초기 조건으로 Normal Mode로 진입 시 해당 플래그 강제 초기화 처리.\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-19?filter=allopenissues]

### [630968] [PLBM_7] [HKMCJGRLBM-16] [NX5] HSM 보안 사양에 대한 상태 값을 RDBI 서비스에 추가 필요
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 요구사양 분석/검증 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P9. Variant/사양/지역 분기
  - **2차 기능분류**: 사양 해석 불일치
- **설명**: __NX5__
문제점
 [HKMCJGRLBM~-16] [NX5] HSM 보안 사양에 대한 상태 값을 RDBI 서비스에 추가 필요
원인
 진단 통신 서비스 활용 (상세는 ES95486~-02에서 "Annex. C Data Transmission Functional Unit Data Parameter Definitions 확인 필요~')\\
~- 사용 서비스: ReadDatabyIdentifier (22hex) service\\
~- 사용 DID: 0xF1C0 [ECUSecurityInformationDataIdentifier]
문제점 개선
 필수 확인 HSM 상태 값\\
~- Configuration Lock State : 설정 (Enabled)~, 미설정 (Disabled)\\
~- Secure Boot State : 설정 (Enabled)~, 미설정 (Disabled)\\
~- Secure Debug State : 설정 (Enabled)~, 미설정 (Disabled)~, 설정 이후 인증에 따른 임시해제\\
(DebugProtectionTempStop)~, Debug port 미사용 설정 (Debug Disable)

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-16?filter=allopenissues]

### [630966] [PLBM_6] [HKMCJGRLBM-15] [OEUK 적용 차종]SW 다운그레이드 방지 누락
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 예외 입력/신호 처리 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P8. 보안 (OTA/FBL/HSM)
  - **2차 기능분류**: CRC/무결성 검증 오류
- **설명**: 문제점
 [HKMCJGRLBM~-15] [OEUK 적용 차종] SW 다운그레이드 방지 누락
원인
 FBL 내 CRC 값이 ~'0~'으로 초기화되어 있어 SW 업데이트를 위한 버전 비교 시 유효한 값이 없다고 판단하여 업데이트 가능\\
\\
[!1774312289486.png#35a2e2fa323774aee8a465231ccad833!]\\
문제점 개선
 생산용 통합파일(.sre)에 CRC 값을 주입하여 해당 증상을 개선함(대책참조_그림2. 4.)\\
. HSM + FBL + APP SW 파일 ~>~> 생산용 배포파일\\
. 생산용 배포파일 기준으로~, CRC 값을 계산하여 강제로 .SRE 파일에 주입함\\
\\
\\
~- crc 값 주입\\
\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/projects/HKMCJGRLBM/issues/HKMCJGRLBM-15?filter=allopenissues]

### [630964] [PLBM_5] [HKMCJGRLBM-14] [LX3_SOP] BAT_SOC_for_BLTN_CAM 101% 송출 현상 발생
- **상태**: New
- **필드**:
  - **1차 분류**: 복합
  - **2차 분류**: 상세 설계/검증 미흡
  - **3차 분류**: 임계값 설계 미흡
  - **SW Layer**: Application
  - **1차 기능분류**: A3. 데이터 처리
  - **2차 기능분류**: 연산 오류((사칙연산, 데이터 오류)
- **설명**: __LX3__
문제점
 [HKMCJGRLBM~-14] [LX3_SOP] BAT_SOC_for_BLTN_CAM 101~% 송출 현상 발생
원인
 1. 의도치 않은 표기값에 대한 Guard 처리 없음\\
2. BLTN SOC 할당량은 30Ah 연산 오류 X\\
~- 30Ah BLTN Max 할당량 : 28.8 * 0.7 * 0.66 = 13.305Ah\\
~- 20Ah BLTN Max 할당량 : 19.2 * 0.7 * 1 = 13.44Ah\\
\\
20Ah인 경우 BLTN_SOC = 13.44Ah/13.44Ah = 100~%~,\\
이 상태에서 $BC20 request를 통해 LBM_BAT_Capapcity를 30Ah로 변환할 경우는 아래의 수식을 통해서 BLTN_SOC가 계산 됨\\
13.44/13.305Ah = 101~%\\
따라서 위의 재현 상황에서 결과가 100~%가 아닌 101~%가 나오게 됨
문제점 개선
 1. BLTN_SOC가 100 초과한 값을 표기하지 않도록 Guard 처리

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-14]

### [630962] [PLBM_4] [공통]진단_DTC Count&Time($BC09) – 충전시, Count +2 이슈 추가 개선
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 최초 구현 미흡
  - **3차 분류**: 로직 구현 오류
  - **SW Layer**: Platform
  - **1차 기능분류**: P2. 진단 (UDS/DTC/IO Control)
  - **2차 기능분류**: DTC Count/TimeStamp 불일치
- **설명**: 문제점
 [공통] 진단_DTC Count&Time($BC09) – 충전시~, Count +2 이슈 추가 개선
원인
 1. 충전모드 중에~, DTC 발생으로 충전 금지 ~-~> OperationCycle() 함수 실행 ~-~> DTC 발생시~, Count +2\\
~- 추가 설명 : OperationCycle() 함수 실행시~, DTC Status가 OFF 되는 현상으로 인한 증상 발생
문제점 개선
 ~- DemStatusBitStorageTestFailed : TRUE로 변경\\
 ㄴ 결과 : DTC 상태 ON에서 OperationCycle() 함수 실행으로 인한 DTC상태 OFF 가 발생되지 않음

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-11]

### [630960] [PLBM_3] [TK1_SOP] SOC 90%이상, 저온(19.5도) or 고온(54.5도) 조건에서 충전 시 충전 과전류 발생
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: 로직 예외 흐름 고려 미흡
  - **SW Layer**: Application
  - **1차 기능분류**: A3. 데이터 처리
  - **2차 기능분류**: 연산 오류((사칙연산, 데이터 오류)
- **설명**: __TK1__
문제점
 [TK1_SOP] SOC 90~%이상~, 저온(19.5도) or 고온(54.5도) 조건에서 충전 시 충전 과전류 발생
원인
 1. DC/DC 컨버터 소자 특성 상 0.2A이하의 전류 제어가 되지 않음\\
~- PI제어를 통해 목표 전류에 도달하기 위해서 PWM값을 변경하는데~, 위의 소자 특성에 의한 목표치에 도달하지 못하면서 PWM값을 계속 증가시켜 Overflow(65535 ~-~-~> 0)로 인한\\
과전류 출력 (PWM값과 출력전류는 반비례)\\
~- PWM의 출력 범위는 0 32~,768(0~% 100~%)이다.
문제점 개선
 1. PI 제어 가능한 범위를 설정 (4000 32768) <~-~- 0A 30A에 해당하는 PWM 값 (첨부 참조)\\

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-9]

### [630958] [PLBM_2] [TK1_SOP] 미사용 메시지(0x159, LBM_FD_02_100ms)의 초깃값 송출이 dbc와 다르다
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: SW 변경 영향도 분석 미흡
  - **SW Layer**: Platform
  - **1차 기능분류**: P3. CAN (CAN/CAN FD/NM)
  - **2차 기능분류**: 메시지 조기값/Default 오류
- **설명**: __TK1__
문제점
 [TK1_SOP] 미사용 메시지(0x159~, LBM_FD_02_100ms)의 초깃값 송출이 dbc와 다름
원인
 CAN DB에 정의된 초깃값을 사용하지 않고~, 잘못된 값으로 초기화
문제점 개선
 CAN DB에 정의된 초깃값으로 초기화 (첨부 참조)\\
\\

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-8]

### [630956] [PLBM_1] S32K31x MCU에서 Stack fault 로 인한 Reset, 스케줄링이상 동작 발생
- **상태**: New
- **필드**:
  - **1차 분류**: 단순
  - **2차 분류**: 변경점 관리 미흡
  - **3차 분류**: 요구사양 미확인/오해석
  - **SW Layer**: Platform
  - **1차 기능분류**: P10. 시스템 서비스
  - **2차 기능분류**: OS Task 스케줄링 오류
- **설명**: __NQ5__
문제점
 S32K31x MCU에서 Stack fault 로 인한 Reset~, 스케줄링이상 동작 발생
원인
 오토에버 수평전개 사항 (NML 패치)
문제점 개선
 1. OS 패치 적용(연관 모듈 : ECUM)\\
~- b_autosar_sys_EcuM_R40(Ver 3.1.4.0)\\
~- integration_EcuM(Ver 2.8.3.0_HF1)\\
~- b_autosar_sys_Os_cytxxx_R40(Ver 2.4.5.0_HF1)

* 자료 첨부 : [https://sl-jira.slworld.com/browse/HKMCJGRLBM-10]
