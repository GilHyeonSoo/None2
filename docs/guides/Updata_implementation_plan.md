# Updata 반영 계획서

## 목적

본 문서는 [`/Users/apple/Desktop/논문/docs/guides/Updata.md`](/Users/apple/Desktop/논문/docs/guides/Updata.md)의 10개 개선 요구를 현재 코드 및 논문 상태와 대조하여, 누락 없이 단계적으로 반영하기 위한 작업 기준 문서이다. 사용자가 직접 시뮬레이션을 실행할 예정이므로, 본 계획은 `코드 반영`, `문서 수정`, `실행 가이드 작성`을 우선 대상으로 하며, 실제 대규모 재실험은 포함하지 않는다.

## 작업 분할

1. 개선 체크리스트와 현재 코드/문서의 차이점 정리
2. seed 수 확대가 가능하도록 실행 구조와 가이드 정비
3. 표준 채널 모델 명시 및 구현 파라미터 정비
4. 이착륙 수직 전이 구간 시나리오 추가
5. 비교 baseline 강화
6. 동시 핸드오버 경합과 프리캐싱 비용 지표 추가
7. failure 기준, throughput 해석, service continuity 해석 정비
8. 최종 실행 가이드와 항목별 코멘트 보고서 작성

## 항목별 현재 상태와 반영 방향

### 1. Seed 수 확대

- 현재 상태: [`/Users/apple/Desktop/논문/scripts/run_simulation_sweep.py`](/Users/apple/Desktop/논문/scripts/run_simulation_sweep.py)는 `SEEDS = (7, 11)`로 고정되어 있다.
- 문제점: 통계적 신뢰성 검증이 어려우며, 신뢰구간 산출을 위한 반복성이 부족하다.
- 반영 방향: seed 목록을 외부에서 쉽게 바꿀 수 있도록 구조를 정리하고, 최소 30개 이상 seed 실행 가이드를 별도로 제공한다.
- 비고: 사용자가 직접 재실행할 예정이므로, 이번 작업에서는 실행 스크립트와 가이드만 정비한다.

### 2. 표준 채널 모델 명시 및 적용

- 현재 상태: [`/Users/apple/Desktop/논문/scripts/simulation_env.py`](/Users/apple/Desktop/논문/scripts/simulation_env.py)는 단순 거리 기반 FSPL, aerial penalty, load penalty 중심의 추상화 모델을 사용한다.
- 문제점: 3GPP TR 36.777 또는 ITU-R 계열 공중 채널 모델을 명시적으로 설명하지 않아 현실성이 약하다.
- 반영 방향: 논문과 코드에 `TR 36.777 inspired` 채널 가정을 분명히 쓰고, LOS/NLOS, shadowing, altitude-dependent penalty, fading 가정을 구조적으로 분리한다.
- 비고: 완전한 표준 복제보다, 근거가 명시된 단순화 모델로 정리하는 것이 현 코드와의 정합성이 높다.

### 3. 처리량 요구치 미달 분석

- 현재 상태: 논문은 proactive의 처리량 손실을 부차적으로만 기술하고 있으며, 25 Mb/s 요구 대비 실제 달성 수준의 괴리를 정면으로 분석하지 않는다.
- 문제점: 현재 평균 처리량은 reactive 10.81 Mb/s, proactive 10.20 Mb/s로 요구치 대비 현저히 낮다.
- 반영 방향: 기지국 밀도, 고도, 속도 조건별로 처리량 충족률과 평균 처리량을 추가 분석하도록 코드와 문서를 보강한다.
- 비고: 이는 성능 개선 주장보다 시스템 한계 분석에 더 가까우므로, 결과 서술 어조를 보수적으로 수정해야 한다.

### 4. Service Continuity 과장 해석 수정

- 현재 상태: [`/Users/apple/Desktop/논문/manuscript/drafts/UAM_Intro_Draft.txt`](/Users/apple/Desktop/논문/manuscript/drafts/UAM_Intro_Draft.txt)는 3.86%를 개선 효과로 서술하지만, 안전 기준과의 큰 격차를 충분히 강조하지 않는다.
- 문제점: C2 수준 안전성 관점에서 3.86%는 개선이라기보다 엄격 기준 미달로 해석하는 것이 타당하다.
- 반영 방향: strict continuity metric의 의미와 한계를 분리해서 기술하고, `정량적 개선은 있으나 운항 안전 기준에는 크게 못 미친다`는 해석으로 문장을 수정한다.
- 비고: 논문 표현 수위 조정이 핵심이며, 결과 수치를 인위적으로 포장하지 않는다.

### 5. Latency violation 효과 과장 방지

- 현재 상태: 논문은 p-value를 제시하면서도 effect size가 매우 작다는 점을 충분히 비중 있게 서술하지 않는다.
- 문제점: 표본 수가 크기 때문에 통계적 유의성만으로 실효성을 주장하기 어렵다.
- 반영 방향: latency violation은 `작은 개선`, `실질 효과 제한적`, `환경 변수 영향 우세`라는 방향으로 해석 문구를 재작성한다.
- 비고: 관련 표와 본문에서 `통계적으로 유의`보다 `효과 크기 미미`를 더 강조해야 한다.

### 6. 비교 baseline 강화

- 현재 상태: 초기 버전은 `reactive`와 `proactive` 두 정책만 비교하였다.
- 문제점: reactive baseline이 너무 단순하여 기여도 해석이 약하다.
- 반영 방향: `A3 + TTT tuned reactive`에 해당하는 중간 baseline `a3_ttt`를 추가하고, 사용자가 세 정책을 함께 돌릴 수 있도록 실행 구조와 문서를 정비한다.
- 비고: ML 기반 baseline까지 한 번에 넣기보다, 먼저 해석 가능한 고전적 baseline을 추가하는 편이 현실적이다.

### 7. Radio handover failure 정의 통일

- 현재 상태: reactive는 0건, proactive는 552건으로 집계되지만, 두 정책이 정확히 같은 failure 판정 경로를 따르는지 코드상 명시가 약하다.
- 문제점: 결과 해석에 대해 `측정 기준이 다른 것 아닌가`라는 의문이 남는다.
- 반영 방향: radio failure 판정을 단일 함수로 묶고, 두 정책이 동일한 기준을 거친다는 점을 코드와 문서 모두에서 명시한다.
- 비고: 이는 결과 수치 자체보다 방법론적 신뢰성 확보를 위한 수정이다.

### 8. 이착륙 수직 전이 구간 추가

- 현재 상태: 현재 고도 모델은 300 m, 450 m, 600 m의 수평 밴드 위주이다.
- 문제점: 0~300 m의 climb/descent 구간이 빠져 있어 실제 eVTOL 운항에서 가장 민감한 통신 전환 상황을 반영하지 못한다.
- 반영 방향: flight에 수직 전이 segment를 추가하고, 이착륙 인접 구간에서 안테나 penalty와 serving-cell 변화가 다르게 작동하도록 구조를 보강한다.
- 비고: 이는 실험 설계의 현실성 개선에서 가장 중요한 구조 변경 중 하나이다.

### 9. 다중 기체 동시 핸드오버 경합 추가

- 현재 상태: 다수 기체가 같은 셀에 연결되면 load factor는 증가하지만, 동시 핸드오버 요청 간 예약 충돌과 제어 자원 경합은 직접 모델링되지 않는다.
- 문제점: 성숙기 dense traffic에서 proactive 예약 방식의 한계가 과소평가될 수 있다.
- 반영 방향: 동시 handover queue, reservation collision, control slice exhaustion 같은 지표를 추가한다.
- 비고: 이 항목은 결과 해석뿐 아니라 precaching cost 측정과도 연결된다.

### 10. 프리캐싱 비용 정량화

- 현재 상태: 프리캐싱은 효과 지표로만 간접 반영되고, backhaul cost와 cache occupancy는 추적되지 않는다.
- 문제점: 비용 없는 개선으로 보이기 때문에 논문 주장 균형이 무너진다.
- 반영 방향: precache bytes, active cache entries, ttl expiry count, cache reclaim count 등을 metric으로 추가한다.
- 비고: 최종 논문에서는 `효과-비용 교환관계`를 반드시 함께 기술해야 한다.

## 현재 논문 문서의 우선 수정 포인트

- 초록과 결론에서 service continuity 3.86%를 지나치게 긍정적으로 표현한 문장을 축소해야 한다.
- 성능 평가 장에서 throughput 부족과 latency effect size의 한계를 별도 문단으로 드러내야 한다.
- 이착륙 구간, 강화 baseline, 동시 handover contention, precaching cost는 현재 논문 초안에 거의 반영되어 있지 않으므로 후속 단계에서 시나리오 및 실험 설계 설명을 확장해야 한다.

## 이번 단계 산출물

- 본 계획서 작성 완료
- 다음 단계에서 seed 구조와 실행 가이드부터 우선 반영

## 진행 현황 메모

- 1단계 완료: 체크리스트와 차이점 정리
- 2단계 완료: seed 확장 실행 구조 및 가이드 반영
- 3단계 완료: 표준 문헌 기반 채널 모델 명시 및 단순화 적용
- 4단계 완료: 이착륙 수직 전이 구간 추가
- 5단계 완료: `a3_ttt` baseline 추가
- 6단계 완료: 동시 핸드오버 경합 및 프리캐싱 비용 지표 추가
- 7단계 완료: failure 기준 통일, throughput/service continuity/latency 해석 정비
- 관련 메모: [`/Users/apple/Desktop/논문/docs/guides/Interpretation_Update.md`](/Users/apple/Desktop/논문/docs/guides/Interpretation_Update.md)
- 다음 단계: 최종 실행 가이드와 항목별 코멘트 보고서 작성
