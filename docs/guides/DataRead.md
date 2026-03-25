```
당신은 UAM(도심 항공 모빌리티) 네트워크 시뮬레이션 전문가이자 데이터 분석가입니다.

나는 두 가지 핸드오버 정책을 비교하는 시뮬레이션 스윕 실험을 완료했습니다:
- reactive  : 기존 방식 (전통적인 A3 이벤트 기반 핸드오버) — Baseline
- proactive : 제안 알고리즘

시뮬레이션 결과는 두 개의 CSV 파일에 저장되어 있습니다:
- simulation_sweep_run_results.csv    → 실행(run) 단위 집계 통계
- simulation_sweep_flight_results.csv → 비행(flight) 단위 세부 기록

---

## 역할 분담 (반드시 숙지할 것)

- 시뮬레이션 실행 및 새로운 데이터 생성 → 내가 직접 수행한다
- 코드 작성, 기존 CSV 분석, 추가 데이터 추출 → 당신이 수행한다

따라서 당신은:
1. 절대로 가상 데이터나 합성 데이터를 생성하지 말 것
2. 새로운 시뮬레이션 실행 코드를 작성하지 말 것
3. 오직 이미 제공된 CSV 파일에서 데이터를 분석하고 추출하는 코드만 작성할 것
4. 추가 시뮬레이션이 필요한 경우, 실행하지 말고
   "이 분석을 위해 추가로 필요한 시뮬레이션 조건"을 명확히 정리하여
   내가 직접 돌릴 수 있도록 안내할 것

---

## TASK 1: 아래 3가지 문제점을 분석하고 수정하라

---

### 문제 ①: Service Continuity Success Rate가 지나치게 낮음

현재 결과: reactive = 0.0%, proactive = 3.9%
전체 비행 수 대비 service_continuity_successes 수가 지나치게 낮게 집계되고 있음.

다음을 수행하라:

1. 원본 데이터에서 아래 비율을 계산하라:
   - service_continuity_successes / total_flights 비율을
     정책(reactive / proactive)별, 단계(introduction / growth / maturity)별로 계산

2. 성공률이 낮은 원인을 분석하라:
   - 한 비행이 "service_continuity_success = 1"로 집계되기 위해
     동시에 충족해야 하는 조건이 무엇인지 데이터에서 파악
   - 기준이 지나치게 엄격한 것은 아닌지 확인
     (예: 단절 0회 AND 핑퐁 0회 AND 지연 임계값 이하를 동시 만족해야 하는 경우)

3. 세분화된 서브 지표를 계산하여 저장하라:
   - 서브 지표 A: "단절 0 비율"      = total_interruption_ms == 0 인 비행 비율 (%)
   - 서브 지표 B: "핑퐁 0 비율"      = ping_pong_events == 0 인 비행 비율 (%)
   - 서브 지표 C: "지연 위반 0 비율" = latency_violations == 0 인 비행 비율 (%)
   - 서브 지표 D: "완전 성공 비율"   = 위 A, B, C를 모두 만족하는 비행 비율 (%)
   - 위 4가지 서브 지표를 정책별, 단계별로 계산하라
   - 결과를 저장: analysis_service_continuity_breakdown.csv

4. 만약 이 분석을 위해 추가 시뮬레이션 데이터가 필요하다면:
   - 시뮬레이션을 직접 실행하지 말 것
   - 내가 돌릴 수 있도록 필요한 추가 조건(파라미터, 실험 설정)을
     명확하게 정리하여 출력할 것

---

### 문제 ②: Latency Violations(지연 위반)이 두 정책 간 거의 동일함

현재 결과: Per-Flight Latency Violations 박스 플롯에서
reactive와 proactive의 분포가 거의 차이가 없음.

다음을 수행하라:

1. 정책별 latency_violations의 기술 통계를 계산하라:
   - 평균, 중앙값, 표준편차, 최솟값, 최댓값

2. 통계적 유의성 검정을 실시하라:
   - Mann-Whitney U 검정을 수행하여 두 정책 간 차이가
     통계적으로 유의미한지 확인 (유의 수준 p < 0.05)
   - p-value와 효과 크기(effect size)를 출력하라

3. 상관관계 분석을 수행하라:
   - latency_violations와 아래 변수들 간의 상관계수를 계산하라:
     bs_spacing_km, altitude_m, speed_kmh, service_handover_count
   - reactive와 proactive 각각 따로 계산하라
   - 목적: 지연 위반이 핸드오버 정책보다 채널 환경(고도, 속도, 기지국 간격)에
     더 크게 영향받는다는 사실을 수치로 증명하기 위함

4. 결과를 저장: analysis_latency_violation_deep.csv

5. 만약 이 분석을 위해 추가 시뮬레이션 데이터가 필요하다면:
   - 시뮬레이션을 직접 실행하지 말 것
   - 내가 돌릴 수 있도록 필요한 추가 조건을 명확하게 정리하여 출력할 것

---

### 문제 ③: Proactive에서도 Radio Handover Failure가 여전히 존재함

현재 결과: proactive 일부 비행에서 radio_handover_failures > 0 이 확인됨.

다음을 수행하라:

1. 전체 핸드오버 실패율을 계산하라:
   - reactive  실패율 = sum(radio_handover_failures) / sum(handover_attempts) × 100
   - proactive 실패율 = sum(radio_handover_failures) / sum(handover_attempts) × 100

2. 아래 조건별로 실패율을 세분화하여 계산하라:
   - 단계별       : introduction / growth / maturity
   - 속도 조건별  : low / medium / high
   - 고도 조건별  : low / mid / high
   - 기지국 밀도별: sparse / dense

3. Proactive 정책에서 실패율이 가장 높은 비행 상위 10개를 추출하라:
   - 기준: radio_handover_failures / service_handover_count 비율이 높은 순
   - 해당 비행의 origin, destination, speed_kmh, altitude_m, bs_density_profile 포함

4. 결과를 저장: analysis_handover_failure_rate.csv

5. 만약 이 분석을 위해 추가 시뮬레이션 데이터가 필요하다면:
   - 시뮬레이션을 직접 실행하지 말 것
   - 내가 돌릴 수 있도록 필요한 추가 조건을 명확하게 정리하여 출력할 것

---

## TASK 2: 논문 작성에 필요한 추가 데이터를 기존 CSV에서 추출하여 생성하라

아래 분석들은 논문 성능 평가 섹션에 반드시 필요하지만
아직 데이터가 별도로 추출되지 않은 항목들이다.
기존 CSV 파일을 기반으로 아래 파일들을 생성하라.

추가 시뮬레이션이 필요한 항목이 있다면:
- 직접 실행하지 말 것
- 시뮬레이션 실행은 내가 직접 수행할 것이므로
  필요한 실험 조건(파라미터, 반복 횟수, 변경할 설정값 등)을
  구체적이고 명확하게 정리하여 별도로 출력할 것

---

### 추가 데이터 1: 조건별 성능 스윕 요약
저장 파일명: additional_condition_sweep_summary.csv

필요한 컬럼:
  phase, speed_profile, altitude_profile, bs_density_profile, policy,
  mean_handovers, mean_ping_pong, mean_interruption_s, mean_latency_violations,
  service_success_rate_pct, mean_throughput_mbps, mean_sinr_db, sample_size

집계 방법:
  - 위 조건 컬럼들 + policy 기준으로 그룹화
  - 각 지표의 평균값 계산
  - sample_size = 해당 그룹의 비행 수

목적:
  논문의 히트맵 및 다중 조건 막대 그래프 작성에 활용

---

### 추가 데이터 2: 단계 진행별 성능 추이
저장 파일명: additional_phase_progression.csv

필요한 컬럼:
  phase, policy, run_index (각 단계 내 순차 번호),
  total_interruption_ms, total_handovers, ping_pong_events,
  service_success_rate_pct

목적:
  introduction → growth → maturity 단계로 갈수록
  성능이 어떻게 변화하는지를 보여주는 추이 그래프 작성에 활용
  (논문의 시나리오 섹션 및 성능 평가 섹션 연계)

만약 추가 시뮬레이션이 필요하다면:
  - 실행하지 말고 필요한 조건을 정리하여 출력할 것
  - 시뮬레이션 실행은 내가 직접 수행할 것임

---

### 추가 데이터 3: 경로별(Route) 성능 비교
저장 파일명: additional_route_performance.csv

필요한 컬럼:
  origin, destination, policy,
  mean_handovers, mean_interruption_ms, mean_latency_violations,
  mean_throughput_mbps, mean_sinr_db, flight_count

집계 방법:
  - origin + destination + policy 기준으로 그룹화
  - 각 지표의 평균값 계산
  - flight_count = 해당 경로의 비행 수

목적:
  어떤 UAM 경로에서 proactive 핸드오버의 효과가 가장 크게 나타나는지 분석
  (논문에서 특정 경로를 사례로 설명할 때 활용)

---

### 추가 데이터 4: 실패 케이스 심층 분석
저장 파일명: additional_failure_analysis.csv

아래 조건 중 하나라도 해당하는 모든 비행을 추출하라:
  - radio_handover_failures > 0
  - service_continuity_failures > 0
  - total_interruption_ms > 5000

원본 컬럼 전체를 포함하고, 아래 파생 컬럼을 추가하라:
  - handover_failure_rate = radio_handover_failures / service_handover_count
    (service_handover_count > 0 인 경우에만, 나머지는 0)
  - is_high_speed    = 1 (speed_kmh > 180인 경우), 그 외 0
  - is_high_altitude = 1 (altitude_m >= 600인 경우), 그 외 0
  - is_dense         = 1 (bs_density_profile == 'dense'인 경우), 그 외 0

목적:
  논문에서 실패 케이스 및 한계점(Limitation) 섹션 작성 시 근거 데이터로 활용

만약 추가 시뮬레이션이 필요하다면:
  - 실행하지 말고 필요한 조건을 정리하여 출력할 것
  - 시뮬레이션 실행은 내가 직접 수행할 것임

---

## 출력 요구사항

- 모든 CSV 파일은 깔끔한 헤더(snake_case 컬럼명)로 저장할 것
- TASK 1의 각 분석 결과 핵심 수치를 터미널에 출력할 것
- 통계 검정(Mann-Whitney U)의 p-value와 효과 크기를 반드시 출력할 것
- TASK 2의 각 파일 저장 후 행 수(row count)와 컬럼 구성을 출력할 것
- 데이터 처리는 pandas를 사용할 것
- 입력 CSV 파일은 현재 작업 디렉토리에 있음
- 출력 파일도 현재 작업 디렉토리에 저장할 것
- 추가 시뮬레이션이 필요한 경우, 코드 실행 마지막에
  아래 형식으로 정리하여 출력할 것:

  =============================================
  [추가 시뮬레이션 필요 항목]
  분석 항목  : (어떤 분석을 위한 시뮬레이션인지)
  필요 조건  : (변경해야 할 파라미터 및 설정값)
  반복 횟수  : (몇 회 실행이 필요한지)
  저장 파일명: (결과를 어떤 파일명으로 저장해야 하는지)
  비고       : (기타 주의사항)
  =============================================

## 주의사항 (반드시 준수)

- 절대로 가상 데이터나 합성 데이터를 생성하지 말 것
- 새로운 시뮬레이션 실행 코드를 작성하지 말 것
- 모든 출력은 반드시 제공된 CSV 파일에서 파생된 값이어야 함
- 추가 시뮬레이션이 필요한 경우 직접 실행하지 말고
  내가 돌릴 수 있도록 필요한 조건만 정리하여 출력할 것
- 컬럼명이 모호한 경우, 문맥에서 추론하고 코드 주석으로 가정 사항을 명시할 것
```

***

## 실행 후 생성되는 파일 목록

| 파일명 | 용도 |
|---|---|
| `analysis_service_continuity_breakdown.csv` | 문제 ① 해결 — 서브 지표 세분화 |
| `analysis_latency_violation_deep.csv` | 문제 ② 해결 — 지연 상관관계 분석 |
| `analysis_handover_failure_rate.csv` | 문제 ③ 해결 — 실패율 조건별 분석 |
| `additional_condition_sweep_summary.csv` | 논문 히트맵·막대 그래프용 |
| `additional_phase_progression.csv` | 단계별 성능 추이 그래프용 |
| `additional_route_performance.csv` | 경로별 효과 비교용 |
| `additional_failure_analysis.csv` | 실패 케이스·한계점 섹션용 |

***

## 추가 시뮬레이션이 필요할 때 Codex가 출력하는 형식 예시

Codex가 기존 데이터만으로 분석이 불가능한 항목을 발견하면 아래처럼 출력합니다. 이 내용을 그대로 확인하고 시뮬레이션을 직접 돌리면 됩니다:

```
=============================================
[추가 시뮬레이션 필요 항목]
분석 항목  : Latency Violation 상관관계 심화 분석
필요 조건  : bs_spacing_km 범위를 1.0 ~ 8.0km로 세분화
             (현재 데이터는 3.0km, 5.5km 두 값만 존재)
반복 횟수  : 조건당 최소 10회 반복 (seed 변경)
저장 파일명: simulation_sweep_latency_extended.csv
비고       : 기존 파일과 동일한 컬럼 구조로 저장할 것
=============================================
```

***
