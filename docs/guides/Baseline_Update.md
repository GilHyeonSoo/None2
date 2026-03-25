# Baseline 강화 메모

## 목적

본 문서는 `reactive vs. proactive`의 이분 비교 구조를 보완하기 위해, [`/Users/apple/Desktop/논문/scripts/simulation_env.py`](/Users/apple/Desktop/논문/scripts/simulation_env.py)에 `a3_ttt` baseline을 추가한 내용을 정리한다. 이는 `Updata.md`가 지적한 `비교군 부족` 문제를 완화하기 위한 단계이다.

## 추가된 정책

### 1. `reactive`

- 가장 단순한 즉시 반응형 정책
- 현재 시점에서 더 좋은 셀이 보이면 즉시 전환
- 히스테리시스 외의 dwell time은 사용하지 않음

### 2. `a3_ttt`

- A3 이벤트와 Time-to-Trigger를 단순화한 중간 baseline
- `best SINR > serving SINR + a3_margin_db` 조건이 일정 시간 유지될 때만 전환
- 현재 구현 기본값:
  - `a3_margin_db = 2.0 dB`
  - `a3_ttt_s = 3.0 s`

### 3. `proactive`

- 궤적 기반 미래 위치/고도 예측과 precaching을 결합한 제안 정책
- 사전 예약과 준비가 완료된 경우 interruption을 줄이는 구조

## 의미

- 이제 비교는 `즉시 반응형` vs `고전적 A3+TTT형` vs `예측 기반 proactive`의 3단 구조가 된다.
- 따라서 논문에서 `단순 baseline만 이긴 것 아닌가`라는 비판을 줄일 수 있다.
- 특히 `a3_ttt`는 ping-pong 억제는 일부 가능하지만 precaching은 없기 때문에, proactive의 순수 예측/준비 이득을 더 분리해서 볼 수 있다.

## 현재 단계의 한계

- `a3_ttt`는 엄밀한 LTE/NR 이벤트 구현이 아니라, 논문 비교용 단순화 baseline이다.
- A3 offset, CIO, separate filtering window, neighbor ranking policy는 아직 세분화하지 않았다.
- ML 기반 baseline이나 NTN-assisted baseline은 후속 확장 대상이다.
