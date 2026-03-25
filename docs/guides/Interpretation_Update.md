# 7단계 반영 메모: Failure 기준 및 결과 해석 정비

## 목적

본 문서는 [`/Users/apple/Desktop/논문/docs/guides/Updata.md`](/Users/apple/Desktop/논문/docs/guides/Updata.md)의 3, 4, 5, 7번 요구를 반영한 결과를 요약한다. 핵심 목표는 `핸드오버 실패 기준 통일`, `처리량 요구치 미달의 정면 분석`, `service continuity 3.86%의 보수적 해석`, `latency violation 효과 과장 제거`이다.

## 반영 내용

### 1. Radio failure 기준 명시화

- [`/Users/apple/Desktop/논문/scripts/simulation_env.py`](/Users/apple/Desktop/논문/scripts/simulation_env.py)에 `HandoverOutcome`와 `_evaluate_handover_outcome()`를 추가하였다.
- 이제 radio handover failure는 정책과 무관하게 `target throughput < handover_floor_mbps`일 때만 동일하게 판정된다.
- service continuity success는 `radio success`와 `interruption <= latency_budget_ms`를 동시에 만족해야만 성립한다.

### 2. Failure 사유 분해

- 향후 재실행 결과에는 다음 항목이 CSV에 함께 저장된다.
- `radio_failures_low_throughput`
- `service_failures_radio_only`
- `service_failures_latency_only`
- `service_failures_dual`
- 이를 통해 strict continuity 실패가 낮은 처리량 때문인지, interruption 초과 때문인지, 혹은 둘 다 때문인지 분리해 해석할 수 있다.

### 3. 처리량 요구치 미달 분석 강화

- 링크 샘플 단계에서 `throughput_gap_samples`, `demand_met_samples`, `demand_unmet_samples`를 추적하도록 수정하였다.
- run/flight 결과에는 `mean_throughput_gap_mbps`, `demand_satisfied_sample_pct`, `throughput_to_demand_pct`가 추가된다.
- 분석 스크립트는 [`/Users/apple/Desktop/논문/results/analysis/analysis_throughput_gap_breakdown.csv`](/Users/apple/Desktop/논문/results/analysis/analysis_throughput_gap_breakdown.csv)를 생성하여 정책별, 단계별, 조건별 요구 대역폭 충족 정도를 직접 보여준다.

### 4. 논문 서술 수위 조정

- [`/Users/apple/Desktop/논문/manuscript/drafts/UAM_Intro_Draft.txt`](/Users/apple/Desktop/논문/manuscript/drafts/UAM_Intro_Draft.txt)와 [`/Users/apple/Desktop/논문/manuscript/submission/UAM_Submission_Ready.txt`](/Users/apple/Desktop/논문/manuscript/submission/UAM_Submission_Ready.txt)의 초록, 4장, 5장을 보수적으로 수정하였다.
- `3.86%`는 strict continuity의 정량적 개선이지만 여전히 운항 수준에는 크게 못 미친다는 점을 명시하였다.
- `10.81/10.20 Mb/s`는 두 정책 모두 25 Mb/s 요구치를 충족하지 못한 결과로 해석하도록 바꾸었다.
- `p=0.0002`는 effect size `-0.0525`와 함께 읽어야 하며, latency violation 개선은 실질 효과가 작다고 서술하였다.

## 사용 시 주의

- 기존 CSV는 새 failure 세부 항목이 없으므로, 세부 원인 분석은 사용자가 재실행한 새 결과에서 가장 정확하게 가능하다.
- 현재 단계의 목적은 결과를 더 좋아 보이게 만드는 것이 아니라, 같은 수치를 더 엄격하고 일관된 기준으로 읽게 만드는 것이다.
