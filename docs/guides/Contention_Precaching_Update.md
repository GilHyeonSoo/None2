# 동시 핸드오버 경합 및 프리캐싱 비용 반영 메모

## 목적

본 문서는 [`/Users/apple/Desktop/논문/scripts/simulation_env.py`](/Users/apple/Desktop/논문/scripts/simulation_env.py)에 `동시 handover contention`과 `precaching overhead`를 추가한 내용을 정리한다. 기존 구현은 proactive 준비가 비용 없이 성공하는 것처럼 보였으므로, 실제 망 운영에서 중요한 `예약 충돌`, `제어 자원 고갈`, `cache occupancy`, `TTL expiry`, `reclaim`을 계측하도록 수정하였다.

## 추가된 핵심 지표

### run-level summary

- `precache_requests`
- `precache_commits`
- `precache_backhaul_mb`
- `precache_ttl_expiries`
- `precache_reclaims`
- `reservation_collisions`
- `control_slice_exhaustions`
- `edge_cache_overflows`
- `peak_active_precache_entries`
- `peak_edge_cache_usage_mb`

### flight-level summary

- `precache_requests`
- `precache_commits`
- `precache_backhaul_mb`
- `precache_ttl_expiries`
- `precache_reclaims`
- `reservation_collisions`
- `control_slice_exhaustions`
- `edge_cache_overflows`

## 구현 원리

### 1. Precache entry 명시화

각 proactive 준비는 `PrecacheEntry`로 관리된다. entry는 target BS, cache size, reserved control slice, 생성 시점, ready 시점, expiry 시점을 가진다.

### 2. Control slice 경합

동일 target BS에 대해 이미 예약된 control slice 합과 신규 요청을 더했을 때 `reserved_control_slice_mbps`를 초과하면, 준비는 거부되고 다음 지표가 증가한다.

- `reservation_collisions`
- `control_slice_exhaustions`

### 3. Edge cache 용량 제한

BS별 edge cache 사용량이 `edge_cache_capacity_mb`를 초과하면 precache commit을 거부한다. 이 경우 `edge_cache_overflows`와 `reservation_collisions`를 함께 증가시켜, 단순 신호 품질 외의 자원 제약을 결과에 반영한다.

### 4. Backhaul 비용 추적

각 commit 시 추정 payload 크기를 `precache_backhaul_mb`에 누적한다. 이는 proactive 개선 효과가 추가 backhaul traffic을 대가로 한다는 점을 정량적으로 보이기 위한 최소 비용 지표이다.

### 5. TTL expiry와 reclaim

사용되지 않은 precache entry는 `precache_ttl_s`가 지나면 만료되며 `precache_ttl_expiries`로 기록된다. 성공적 handover 또는 예측 무효화 시에는 `precache_reclaims`로 회수된다.

## 현재 단계의 한계

- contention은 BS별 총량 자원 모델로 단순화되어 있으며, scheduler queue나 subframe-level MAC 경쟁까지 반영하지 않는다.
- backhaul cost는 payload volume 기반의 1차 근사치이며, 실제 transport latency와 routing cost는 포함하지 않는다.
- 그럼에도 이번 수정은 `비용 없는 precaching`이라는 가장 큰 구조적 약점을 제거하는 데 의미가 있다.
