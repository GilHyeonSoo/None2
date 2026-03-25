# Seed 확대 실행 가이드

## 목적

본 가이드는 [`/Users/apple/Desktop/논문/scripts/run_simulation_sweep.py`](/Users/apple/Desktop/논문/scripts/run_simulation_sweep.py)를 이용하여 seed 2개 고정 구조를 해소하고, 사용자가 직접 30개 이상 독립 seed 실험을 수행할 수 있도록 정리한 문서이다. 본 단계에서는 실행 스크립트와 재현성 구조만 정비하며, 실제 대규모 시뮬레이션 실행은 사용자가 수행한다.

현재는 후속 개선 사항까지 반영한 최종 실행 안내가 [`/Users/apple/Desktop/논문/docs/guides/Final_Simulation_Execution_Guide.md`](/Users/apple/Desktop/논문/docs/guides/Final_Simulation_Execution_Guide.md)에 정리되어 있으므로, 실제 재실행 시에는 해당 문서를 우선 참고하는 편이 좋다.

## 변경 사항

- `--seed-spec` 인자를 통해 `1-30`, `7,11,13`, `1-10,21-30` 형태로 seed를 지정할 수 있다.
- `--output-prefix` 인자를 통해 결과 파일 충돌 없이 여러 배치를 별도로 저장할 수 있다.
- 실행 시 `manifest.json`이 함께 저장되어, 어떤 조건으로 돌렸는지 재현 가능하게 기록된다.
- phase, speed, altitude, density, policy도 부분 실행이 가능하여 사전 점검과 본실험을 분리할 수 있다.
- 정책 목록은 `reactive`, `a3_ttt`, `proactive`의 3개를 지원한다.

## 생성 파일

예를 들어 `--output-prefix seed30_full`로 실행하면 다음 파일이 저장된다.

- [`/Users/apple/Desktop/논문/results/raw/seed30_full_run_results.csv`](/Users/apple/Desktop/논문/results/raw/seed30_full_run_results.csv)
- [`/Users/apple/Desktop/논문/results/raw/seed30_full_flight_results.csv`](/Users/apple/Desktop/논문/results/raw/seed30_full_flight_results.csv)
- [`/Users/apple/Desktop/논문/results/raw/seed30_full_manifest.json`](/Users/apple/Desktop/논문/results/raw/seed30_full_manifest.json)

## 권장 실행 순서

### 1. 도움말 확인

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py --help
```

### 2. dry-run으로 조합 수 확인

아래 명령은 실제 시뮬레이션을 실행하지 않고, seed 수, 총 run 수, 저장 경로만 먼저 출력한다.

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py \
  --seed-spec 1-30 \
  --output-prefix seed30_full \
  --dry-run
```

### 3. 소규모 점검 실행

아래 명령은 코드와 파일 출력 구조를 확인하기 위한 최소 점검용이다.

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py \
  --seed-spec 7 \
  --phases introduction \
  --speed-profiles low \
  --altitude-profiles low \
  --bs-density-profiles sparse \
  --policies reactive,a3_ttt,proactive \
  --run-duration-s 600 \
  --output-prefix smoke_check
```

### 4. 논문용 권장 본실험

`Updata.md`의 지적을 반영하면, seed는 최소 30개 이상이 적절하다. 아래는 전체 조건을 유지하면서 30개 seed를 사용하는 기본 명령이다.

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py \
  --seed-spec 1-30 \
  --policies reactive,a3_ttt,proactive \
  --run-duration-s 1800 \
  --traffic-hours 1.0 \
  --output-prefix seed30_full
```

이 경우 총 run 수는 다음과 같다.

- `30 seeds × 3 phases × 3 speed × 3 altitude × 2 density × 3 policies = 4860 runs`

## 부분 실험 예시

### 성장기만 재실험

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py \
  --seed-spec 1-30 \
  --phases growth \
  --output-prefix seed30_growth_only
```

### proactive만 재실험

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py \
  --seed-spec 1-30 \
  --policies proactive \
  --output-prefix seed30_proactive_only
```

### sparse 조건만 재실험

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py \
  --seed-spec 1-30 \
  --bs-density-profiles sparse \
  --output-prefix seed30_sparse_only
```

## 재현성 관리 규칙

- 서로 다른 실험 배치는 반드시 다른 `output_prefix`를 사용한다.
- 분석 전에 어떤 CSV가 최신 논문용 결과인지 `manifest.json`으로 먼저 확인한다.
- 하나의 배치가 끝난 뒤에는 해당 prefix를 기준으로 분석 스크립트 입력 경로를 맞춰야 한다.
- 현재 분석 스크립트는 기본적으로 `simulation_sweep_*` 파일명을 기대하므로, 최종 논문용 배치를 사용할 때는 파일명을 맞추거나 후속 단계에서 분석 입력 인자를 같이 확장해야 한다.

## 주의사항

- 이 문서는 seed 확대 구조에 초점을 둔 중간 가이드이며, 최종 권장 절차는 `Final_Simulation_Execution_Guide.md`를 따른다.
- 분석 스크립트는 이제 `--run-csv`, `--flight-csv`를 지원하므로, output prefix를 자유롭게 사용해도 된다.
- 현재 문서는 구조 이해용 보조 문서로 보고, 실제 논문용 재실행은 최종 가이드 기준으로 수행하는 것이 바람직하다.
