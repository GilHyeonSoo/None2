# 채널 모델 정비 메모

## 목적

본 문서는 [`/Users/apple/Desktop/논문/scripts/simulation_env.py`](/Users/apple/Desktop/논문/scripts/simulation_env.py)의 공중 링크 모델을 `추상적 penalty 기반 모델`에서 `표준 문헌 참조형 LoS/NLoS 분리 모델`로 정비한 내용을 정리한다. 본 단계의 목표는 완전한 3GPP 표준 복제보다, 논문에서 설명 가능하고 재현 가능한 수준의 명시적 채널 가정을 제공하는 것이다.

## 반영 기준

- 3GPP TR 36.777 계열 UAV 연구에서 강조되는 `고도 증가에 따른 LoS 지배`, `다중 강한 이웃 셀 관측`, `간섭 증가` 특성을 반영한다.
- ITU-R P.1410-5의 `over-rooftop`, `LoS/NLoS 구분`, `반사 및 회절 구간` 개념을 도시 메트로폴리탄 추상화에 맞게 단순화한다.
- 실제 표준의 세부 계수를 그대로 복제하지 않고, 코드와 논문이 동시에 설명 가능한 범위에서 가정값을 공개한다.

## 코드 반영 내용

### 1. LoS 확률 함수 추가

- 함수: `self._aerial_los_probability()`
- 입력: 수평 거리, 고도
- 동작: 기체가 rooftop 높이보다 충분히 높을수록 LoS 확률을 크게 두고, 수평 거리가 길어질수록 점진적으로 감소시킨다.

### 2. LoS/NLoS 상태 캐시 추가

- 함수: `self._is_los_condition()`
- 목적: 같은 링크 tile에서 반복 호출될 때 LoS/NLoS 상태가 임의로 흔들리지 않도록 결정적 상태를 유지한다.
- 효과: 기존의 단순 랜덤성보다 channel condition의 공간적 일관성이 높아진다.

### 3. Shadowing 분리

- LoS shadowing 표준편차: `1.8 dB`
- NLoS shadowing 표준편차: `4.5 dB`
- 의미: 공중 LoS 링크는 변동이 작고, 차폐된 NLoS 링크는 변동성이 더 크다는 점을 반영한다.

### 4. Small-scale fading 분리

- LoS: `Rician-like fading`
- NLoS: `Rayleigh-like fading`
- 목적: LoS 지배 링크와 차폐 링크를 같은 fading 가정으로 처리하던 한계를 줄인다.

### 5. NLoS excess loss 추가

- NLoS에는 `18 dB` 기본 excess loss를 부여한다.
- 기체가 rooftop보다 낮을수록 추가 손실이 증가한다.
- 효과: 동일 거리라도 LoS/NLoS 상태 차이가 수신 전력에 명확히 반영된다.

### 6. Downtilt penalty 정교화

- 고도와 거리 조건에 따라 `3 dB`, `5 dB`, `7 dB` 수준으로 penalty를 다르게 부여한다.
- 장거리 상공 링크에는 추가 `1 dB` penalty를 둔다.
- 목적: 지상 중심 안테나 패턴의 side-lobe 열세를 더 현실적으로 반영한다.

## 현재 단계의 한계

- 이 모델은 `TR 36.777 inspired` 수준의 단순화 구현이며, 3GPP 표준 수식을 완전 재현한 것은 아니다.
- clutter class, street orientation, building block geometry, full 3D antenna pattern은 아직 반영하지 않는다.
- 이착륙 수직 전이 구간은 다음 단계에서 별도로 확장할 예정이다.

## 논문 반영 시 표현 기준

- `3GPP TR 36.777 및 ITU-R P.1410-5를 참조한 단순화 air-ground channel model`로 기술한다.
- `표준을 완전 복제하였다`고 쓰지 않고, `LoS/NLoS 분리, shadowing/fading 차등화, downtilt penalty 반영`을 핵심 기여로 서술한다.
- 실험의 현실성은 개선되었으나, 여전히 추상화 모델이라는 점을 한계 항목에서 명시한다.
