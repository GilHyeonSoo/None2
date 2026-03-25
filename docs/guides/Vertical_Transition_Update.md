# 이착륙 수직 전이 구간 반영 메모

## 목적

본 문서는 [`/Users/apple/Desktop/논문/scripts/simulation_env.py`](/Users/apple/Desktop/논문/scripts/simulation_env.py)에 `0~300m 수직 전이 구간`을 추가한 이유와 구현 범위를 정리한다. 기존 모델은 `300m`, `450m`, `600m`의 순항 밴드만 다루었기 때문에, 실제 eVTOL 운항에서 가장 민감한 이륙 직후와 착륙 직전 링크 변화를 반영하지 못했다.

## 반영 내용

### 1. 비행 고도 구조 변경

- 기존: 비행 전체에서 `altitude_m`이 고정
- 변경: 각 비행은 `takeoff -> climb -> cruise -> descent -> landing` 구조를 가진다
- 순항 고도는 기존과 동일하게 `300m`, `450m`, `600m` 중 하나로 선택한다

### 2. 수직 전이 길이 추가

- `climb_distance_km`
- `descent_distance_km`
- `vertical_transition_trigger_km`

수직 전이 구간은 단순 시간 기반이 아니라, 기체 속도와 수직 속도를 함께 고려하여 산정한다. 따라서 고속 기체일수록 동일 고도까지 도달하는 동안 더 긴 수평 corridor를 사용하게 된다.

### 3. flight 상태 변수 추가

- `cruise_altitude_m`
- `vertical_phase`
- `total_distance_travelled_km`
- `distance_to_destination_km`

이 값들을 통해 현재 비행이 climb, cruise, descent 중 어느 구간에 있는지 추적할 수 있다.

### 4. proactive 예측 수정

기존 proactive는 미래 위치만 예측하고 현재 고도를 그대로 사용했다. 이번 수정 이후에는 미래 `x`, `y`뿐 아니라 미래 `altitude`도 함께 예측하여 타깃 셀을 평가한다. 이는 이착륙 전환 구간에서 후보 셀 품질이 급변할 수 있다는 점을 반영하기 위한 것이다.

### 5. CSV 출력 확장

flight 결과에는 다음 필드가 추가된다.

- `cruise_altitude_m`
- `vertical_phase`
- `distance_to_destination_km`

이 값들은 이후 `이착륙 구간에서의 failure/latency/interruptions`를 별도로 분석할 때 직접 사용할 수 있다.

## 현재 단계의 한계

- 아직 이착륙 전용 버티포트 빔 패턴이나 dedicated pad-side cell은 별도로 두지 않았다.
- 수직 속도는 대표값으로 단순화하였으며, 상승과 하강 프로파일의 세부 동역학은 반영하지 않았다.
- 이번 단계는 `수직 전이 구간을 아예 누락한 상태`를 해소하는 것이 목적이며, 세부 eVTOL 비행역학 모델 추가는 후속 확장 과제이다.
