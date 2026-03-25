# 최종 실행 가이드

## 목적

본 문서는 [`/Users/apple/Desktop/논문/docs/guides/Updata.md`](/Users/apple/Desktop/논문/docs/guides/Updata.md)의 개선 사항이 반영된 현재 시뮬레이터를 사용자가 직접 재실행할 수 있도록 정리한 최종 가이드이다. 본 가이드는 대규모 시뮬레이션 실행, 분석 CSV 생성, 그리고 결과 해석 순서만 다루며, 실제 실행은 사용자가 수행한다.

## 현재 반영된 실험 구조

- 정책: `reactive`, `a3_ttt`, `proactive`
- phase: `introduction`, `growth`, `maturity`
- 속도: `low`, `medium`, `high`
- 고도: `low`, `mid`, `high`
- 기지국 밀도: `sparse`, `dense`
- 수직 전이 구간: `takeoff -> climb -> cruise -> descent -> landing`
- 추가 비용/경합 지표: `precache_backhaul_mb`, `reservation_collisions`, `control_slice_exhaustions`, `edge_cache_overflows`
- 추가 해석 지표: `mean_throughput_gap_mbps`, `throughput_to_demand_pct`, `demand_satisfied_sample_pct`, `service_failures_*`

## 1. 코드 문법 점검

```bash
python3 -m py_compile \
  /Users/apple/Desktop/논문/scripts/simulation_env.py \
  /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py \
  /Users/apple/Desktop/논문/scripts/analyze_simulation_csv.py
```

## 2. dry-run으로 총 run 수 확인

아래 명령은 실제 시뮬레이션을 수행하지 않고 조합 수와 출력 경로만 확인한다.

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py \
  --seed-spec 1-30 \
  --policies reactive,a3_ttt,proactive \
  --run-duration-s 1800 \
  --traffic-hours 1.0 \
  --output-prefix seed30_final \
  --dry-run
```

예상 조합 수:

- `30 seeds × 3 phases × 3 speed × 3 altitude × 2 density × 3 policies = 4860 runs`

## 3. 소규모 smoke run

전체 본실험 전에 최소 조건만 먼저 돌려서 출력 형식을 확인하는 것이 안전하다.

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py \
  --seed-spec 7 \
  --phases introduction \
  --speed-profiles low \
  --altitude-profiles low \
  --bs-density-profiles sparse \
  --policies reactive,a3_ttt,proactive \
  --run-duration-s 600 \
  --output-prefix smoke_check_stage8
```

## 4. 논문용 권장 본실험

아래 명령은 현재 개선 구조를 모두 유지한 상태에서 30개 seed로 전체 sweep를 수행하는 기본 예시이다.

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py \
  --seed-spec 1-30 \
  --policies reactive,a3_ttt,proactive \
  --run-duration-s 1800 \
  --traffic-hours 1.0 \
  --output-prefix seed30_final
```

생성 파일:

- [`/Users/apple/Desktop/논문/results/raw/seed30_final_run_results.csv`](/Users/apple/Desktop/논문/results/raw/seed30_final_run_results.csv)
- [`/Users/apple/Desktop/논문/results/raw/seed30_final_flight_results.csv`](/Users/apple/Desktop/논문/results/raw/seed30_final_flight_results.csv)
- [`/Users/apple/Desktop/논문/results/raw/seed30_final_manifest.json`](/Users/apple/Desktop/논문/results/raw/seed30_final_manifest.json)

## 5. 분석 CSV 생성

이제 분석 스크립트는 입력 CSV 경로를 직접 받을 수 있다. 따라서 `output_prefix`를 자유롭게 사용해도 된다.

```bash
python3 /Users/apple/Desktop/논문/scripts/analyze_simulation_csv.py \
  --run-csv /Users/apple/Desktop/논문/results/raw/seed30_final_run_results.csv \
  --flight-csv /Users/apple/Desktop/논문/results/raw/seed30_final_flight_results.csv
```

주요 생성 파일:

- [`/Users/apple/Desktop/논문/results/analysis/analysis_service_continuity_breakdown.csv`](/Users/apple/Desktop/논문/results/analysis/analysis_service_continuity_breakdown.csv)
- [`/Users/apple/Desktop/논문/results/analysis/analysis_handover_failure_rate.csv`](/Users/apple/Desktop/논문/results/analysis/analysis_handover_failure_rate.csv)
- [`/Users/apple/Desktop/논문/results/analysis/analysis_latency_violation_deep.csv`](/Users/apple/Desktop/논문/results/analysis/analysis_latency_violation_deep.csv)
- [`/Users/apple/Desktop/논문/results/analysis/analysis_throughput_gap_breakdown.csv`](/Users/apple/Desktop/논문/results/analysis/analysis_throughput_gap_breakdown.csv)
- [`/Users/apple/Desktop/논문/results/analysis/additional_condition_sweep_summary.csv`](/Users/apple/Desktop/논문/results/analysis/additional_condition_sweep_summary.csv)
- [`/Users/apple/Desktop/논문/results/analysis/additional_failure_analysis.csv`](/Users/apple/Desktop/논문/results/analysis/additional_failure_analysis.csv)

## 6. 결과 해석 우선순위

### 1차 확인

- `analysis_throughput_gap_breakdown.csv`
- `analysis_service_continuity_breakdown.csv`
- `analysis_handover_failure_rate.csv`

먼저 이 세 파일로 `25 Mb/s 요구 대역폭 충족 여부`, `strict continuity 절대 수준`, `radio failure 분포`를 본다. interruption이 줄더라도 throughput gap이 크면 안전 해법으로 해석하면 안 된다.

### 2차 확인

- `analysis_latency_violation_deep.csv`
- `additional_condition_sweep_summary.csv`

여기서는 `effect size`와 조건별 평균값을 같이 본다. p-value만 보고 latency 개선을 과장하면 안 되며, density, speed, altitude가 더 큰 원인인지 함께 확인해야 한다.

### 3차 확인

- `additional_failure_analysis.csv`
- `results/raw/*_flight_results.csv`

여기서는 `service_failures_radio_only`, `service_failures_latency_only`, `service_failures_dual`, `reservation_collisions`, `control_slice_exhaustions`, `edge_cache_overflows`를 본다. proactive의 비용과 실패 원인을 분리해 해석하는 단계이다.

## 7. 논문에 직접 반영할 때 주의할 점

- `3.86%`와 같은 strict continuity 수치는 개선 여부와 별개로 절대값 자체가 매우 낮을 수 있다.
- `mean_throughput_mbps`가 `25 Mb/s`에 크게 못 미치면, 제안 방식이 안전 운항 수준을 충족했다고 쓰면 안 된다.
- `p-value`가 작아도 `effect_size`가 매우 작으면 실질 효과는 제한적이라고 해석해야 한다.
- `a3_ttt`를 포함한 새 결과를 논문 본문에 반영하려면, 표와 그림도 세 정책 기준으로 다시 구성해야 한다.

## 8. 권장 보관 규칙

- 새로운 배치마다 `output_prefix`를 다르게 둔다.
- 최종 논문용 배치를 정했으면 해당 `manifest.json`을 함께 보관한다.
- 기존 결과를 덮어쓰고 싶지 않다면 `simulation_sweep` 대신 고유 prefix를 사용하고, 분석 단계에서 `--run-csv`, `--flight-csv`를 직접 넘긴다.
