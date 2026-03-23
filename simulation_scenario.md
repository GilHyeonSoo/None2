# UAM 핸드오버 시뮬레이션 시나리오 초안

## 1. 연구 목적
본 시뮬레이션은 도심 항공 모빌리티(UAM) 기체가 버티포트 간 항공로를 따라 이동하는 동안, 기존 반응형 핸드오버와 제안하는 선제적 핸드오버 및 엣지 프리캐싱 방식의 차이를 정량적으로 비교하기 위한 Python 기반 평가 환경이다. 평가지표는 핸드오버 횟수, 핑퐁 빈도, 전환 중단 시간, 제어 지연 위반 횟수, 평균 SINR, 평균 처리량으로 구성한다.

## 2. 문헌 기반 환경 설정값

### 2.1 단계별 네트워크 규모
- 수도권 UAM 네트워크는 도입기 4개, 성장기 8개, 성숙기 20개 버티포트로 확장된다.
- 단계별 참고 노선 수는 8, 14, 123개이다.
- 단계별 일일 수요는 29명, 4,536명, 113,179명으로 제시된다.
- 근거: [`/Users/apple/Desktop/논문/RelatedWorks/국내논문2.pdf`](/Users/apple/Desktop/논문/RelatedWorks/국내논문2.pdf)

위 결과를 바탕으로 시뮬레이터는 `introduction`, `growth`, `maturity`의 3개 단계를 제공하며, 각 단계에서 활성화되는 버티포트 수를 각각 4, 8, 20으로 설정한다.

### 2.2 노선 길이와 항공로 구성
- K-UAM 수도권 네트워크 연구는 성장기 확장 대상 구간을 시군구 기준 20∼50km 통행으로 설명한다.
- 상파울루 UAM 네트워크 연구는 초기 UAM 노선 길이를 7.41km에서 48.7km 범위로 제시한다.
- 상파울루 연구는 각 vertiport/airport를 네트워크에 연결할 때 two nearest neighbors와 Dijkstra 기반 shortest path를 사용한다.
- 근거: [`/Users/apple/Desktop/논문/RelatedWorks/국내논문2.pdf`](/Users/apple/Desktop/논문/RelatedWorks/국내논문2.pdf), [`/Users/apple/Desktop/논문/RelatedWorks/해외논문2.pdf`](/Users/apple/Desktop/논문/RelatedWorks/해외논문2.pdf)

이에 따라 시뮬레이터는 버티포트 그래프를 구성할 때 각 노드를 최근접 2개 노드와 연결하고, 실제 비행 경로는 Dijkstra 최단경로로 산출한다. 경로 길이는 7.41km 이상 48.7km 이하를 기본 범위로 두고, 특히 20km 이상 구간은 수도권 확장 수요를 반영하는 대표 평가 구간으로 간주한다.

### 2.3 운항량 기준
- 상파울루 연구는 초기 도입 단계의 기준 수요로 약 186 operations per day를 제시한다.
- 해당 연구는 이 수치가 현재 헬리콥터 운항량의 약 9.3% 수준이라고 설명한다.
- 근거: [`/Users/apple/Desktop/논문/RelatedWorks/해외논문2.pdf`](/Users/apple/Desktop/논문/RelatedWorks/해외논문2.pdf)

본 시뮬레이터는 직접적인 일일 운항 횟수 값이 제시된 자료가 상파울루 연구이므로, 기본 기준 운항량을 186회/일로 둔다. 이후 18시간 운항 창과 피크 시간 계수(`peak_hour_multiplier`)를 적용하여 1시간 단위의 스트레스 트래픽을 생성한다.

### 2.4 속도 및 서비스 요구사항
- NTN 리뷰 논문은 TS 22.261 기반 vehicular connectivity에서 UE 속도를 최대 250km/h로 제시한다.
- 같은 문헌은 airborne service 요구사항에서 Remote UAV controller through HD video에 대해 25Mb/s uplink, 100ms latency, 300kb/s downlink, 20ms latency를 제시한다.
- 실시간 비디오는 100ms, 1080p 비디오 스트리밍은 200ms 지연 조건을 사용한다.
- 근거: [`/Users/apple/Desktop/논문/RelatedWorks/해외논문1.pdf`](/Users/apple/Desktop/논문/RelatedWorks/해외논문1.pdf)

따라서 시뮬레이터는 UAM 속도 상한을 250km/h로 설정하고, 서비스 프로파일은 다음과 같이 둔다.

- `remote_uav_hd_control`: 요구 대역폭 25Mb/s, 핸드오버 지연 예산 20ms, 최소 연속성 유지 대역폭 300kb/s
- `real_time_video`: 100ms 지연 예산
- `video_streaming_1080p`: 9Mb/s, 200ms 지연 예산

### 2.5 네트워크 제어 절차 근거
- NTN 리뷰 논문은 UAV가 planned flight route information과 required QoS를 UTM/5G 시스템에 제공하고, 네트워크가 해당 경로에서 QoS 가능 여부를 사전 검토하는 절차를 설명한다.
- 같은 문헌은 mobility management와 network switching strategies를 핵심 연구 과제로 지적한다.
- 근거: [`/Users/apple/Desktop/논문/RelatedWorks/해외논문1.pdf`](/Users/apple/Desktop/논문/RelatedWorks/해외논문1.pdf)

본 시뮬레이션의 선제적 핸드오버 정책은 바로 이 절차를 단순화하여 반영한다. 즉, 비행 경로 사전 공유, 후보 셀 예약, TTL 기반 전환 준비, 프리캐싱 완료 후 전환을 한 흐름으로 구현한다.

## 3. 모델링 가정값
아래 값들은 관련 연구 PDF에 직접 수치가 제시되지 않았으므로, 핸드오버 실험을 위해 합리적인 범위에서 설정한 모델링 가정이다.

### 3.1 공간 크기
- `50km x 50km`
- 이유: 국내 논문의 20∼50km 수도권 통행 구간과 상파울루 논문의 최대 48.7km 노선을 한 장의 메트로폴리탄 맵 안에 수용하기 위해 정사각형 평가 공간으로 추상화하였다.

### 3.2 버티포트 좌표와 허브
- 20개 버티포트 중 2개는 공항형 허브로, 나머지는 서울·인천·경기권 노드로 배치하였다.
- 이유: 국내 논문은 20개 버티포트의 행정권역 분포를 제시하지만 세부 좌표는 제공하지 않으므로, 수도권 구조를 반영한 추상 좌표를 사용하였다.

### 3.3 기지국 배치
- 항공로를 따라 약 4km 간격으로 corridor base station을 배치하고, 버티포트 주변에는 이착륙 커버리지를 위한 station을 별도로 둔다.
- 이유: 관련 연구는 버티포트와 항공로는 제시하지만 지상 셀룰러 기지국 밀도는 명시하지 않는다. 따라서 20∼50km 구간에서 복수의 핸드오버 이벤트가 발생하도록 중첩 커버리지가 가능한 간격을 사용하였다.

### 3.4 고도 밴드
- `300m`, `450m`, `600m`
- 이유: 관련 논문은 air corridor와 airborne communication을 강조하지만 고도 수치를 고정하지 않는다. 시뮬레이터는 3차원성 반영을 위해 세 개의 대표 고도 밴드를 사용한다.

### 3.5 시간 해상도
- `0.5초`
- 이유: 초고속 이동체가 셀 경계를 빠르게 통과하는 상황을 추적하면서도 Python 단일 프로세스에서 반복 실험이 가능하도록 설정하였다.

### 3.6 전파 및 부하 모델
- 3.5GHz carrier, 43dBm 송신 출력, -104dBm noise floor를 사용한다.
- 기지국 하향 틸트에 따른 aerial penalty와 corridor load penalty를 별도로 둔다.
- 이유: 관련 논문은 상공 간섭과 downtilt 기반 열세를 논의하나 세부 PHY 파라미터를 고정하지 않으므로, 5G 중대역을 가정한 단순화 모델을 적용하였다.

## 4. Python 환경 구성
Python 환경은 [`/Users/apple/Desktop/논문/simulation_env.py`](/Users/apple/Desktop/논문/simulation_env.py)에 구현하였다. 핵심 구성은 다음과 같다.

### 4.1 네트워크 토폴로지
- `PhaseProfile`: 도입기, 성장기, 성숙기 규모를 관리한다.
- `Vertiport`: 허브 여부, 좌표, 권역 정보를 관리한다.
- `BaseStation`: 항공로 기반 셀과 동적 load factor를 관리한다.
- `shortest_path()`: vertiport graph 위에서 Dijkstra 경로를 계산한다.

### 4.2 항공기 모델
- `Flight`: origin, destination, waypoint, altitude, service profile, reserved target cell, precache time을 보관한다.
- 이동은 waypoint 기반 piecewise linear motion으로 계산한다.

### 4.3 핸드오버 정책
- `reactive`: 현재 시점의 SINR과 best cell만을 기준으로 전환한다.
- `proactive`: 미래 위치 예측, candidate target reservation, precache completion 여부를 함께 고려한다.

### 4.4 링크 평가
- 수신 전력은 3차원 거리 기반 FSPL과 aerial penalty를 사용한다.
- SINR은 주변 강한 간섭 셀을 포함해 계산한다.
- 처리량은 유효 SINR 기반 근사치로 산정한다.
- 지연은 기본 지연, load penalty, 저 SINR penalty를 합산해 계산한다.

## 5. 평가 시나리오 초안

### 5.1 기본 시나리오
- 단계: `introduction`
- 활성 버티포트: 4개
- 기준 운항량: 186회/일
- 실험 시간: 30분
- 정책 비교: `reactive` vs `proactive`

### 5.2 트래픽 생성
- 하루 18시간 운항을 가정한다.
- 1시간 피크 구간에서는 `peak_hour_multiplier=3.0`을 적용한다.
- OD는 허브 연계 편향을 가지며, 이는 상파울루 연구가 airport shuttle과 inter-airport transfer를 초기 핵심 수요로 본 점을 반영한 것이다.

### 5.3 핸드오버 절차
1. 비행 생성 시 origin-destination 경로를 계산한다.
2. 초기 serving cell을 선택한다.
3. 매 step마다 위치와 링크 품질을 갱신한다.
4. `reactive`는 현재 최적 셀로 즉시 전환한다.
5. `proactive`는 미래 8초 위치를 예측하고, 1초 선행 프리캐싱이 완료되면 전환한다.
6. 전환 후 interruption time, ping-pong 여부, 지연 위반 여부를 누적한다.

### 5.4 주요 지표
- 총 핸드오버 횟수
- 핸드오버 성공/실패 횟수
- 핑퐁 이벤트 수
- 총 interruption 시간
- 제어 지연 위반 횟수
- 평균 SINR
- 평균 처리량
- precache hit 수

## 6. 논문 본문에 기술할 수 있는 해석 포인트
- 국내 연구의 단계형 버티포트 수와 노선 수를 적용함으로써, 제안 환경은 수도권 UAM의 네트워크 확장 단계를 반영한다.
- NTN 리뷰에서 제시된 mobility management와 network switching 문제를 미시적 handover 정책 평가 문제로 구체화하였다.
- 상파울루 연구의 two nearest neighbors, Dijkstra, 186회/일 운항량을 도입함으로써 초기 상용화 수준의 corridor traffic을 모사하였다.
- 기지국 밀도, 고도 밴드, 피크 시 계수는 논문에 직접 제시되지 않았으므로 모델링 가정으로 명시해야 한다.
