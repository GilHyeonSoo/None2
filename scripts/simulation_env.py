"""
UAM handover simulation environment.

Literature-backed defaults used in this module:
1. Jeong & Son (2025), "A Study of Designing Networks for Urban Air Mobility
   in Seoul Metropolitan Area"
   - Vertiport phase scale: 4 / 8 / 20 vertiports
   - Route scale: 8 / 14 / 123 routes
   - High-demand trip distance: 20-50 km
2. Park et al. (2025), "A Comprehensive Review on Non-terrestrial Network
   Technologies in 3GPP Standards"
   - Vehicular connectivity speed up to 250 km/h (TS 22.261)
   - Remote UAV controller through HD video:
     25 Mb/s uplink with 100 ms latency, 300 kb/s downlink with 20 ms latency
   - Pre-flight route sharing and network-assisted flight support are relevant
     design primitives for mobility management and switching
3. Carvalho et al. (2025 preprint), "Data-Driven Framework for Urban Air
   Mobility Planning..."
   - Initial demand reference: about 186 operations/day
   - Initial UAM routes: about 7.41 km to 48.7 km
   - Each vertiport/airport is attached to the route network using the two
     nearest neighbors, and Dijkstra is used for shortest-path routing
4. Channel-model references used for the air-ground link abstraction:
   - 3GPP TR 36.777 / 3GPP UAV study items: aerial UEs above rooftops are
     often LoS-dominant and may observe multiple strong neighbor cells,
     which increases interference and motivates height-aware mobility logic.
   - ITU-R P.1410-5: rooftop transition, LoS/NLoS separation, reflected and
     diffracted propagation regions, and building-wall reflection loss
     guidance are used as references for a simplified metropolitan model.

Values not explicitly provided by the papers are marked in comments as
"modeling assumption".
"""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import math
import random
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class PhaseProfile:
    name: str
    vertiports: int
    reference_routes: int
    reference_daily_passengers: int


PHASE_PROFILES: Dict[str, PhaseProfile] = {
    "introduction": PhaseProfile(
        name="introduction",
        vertiports=4,
        reference_routes=8,
        reference_daily_passengers=29,
    ),
    "growth": PhaseProfile(
        name="growth",
        vertiports=8,
        reference_routes=14,
        reference_daily_passengers=4536,
    ),
    "maturity": PhaseProfile(
        name="maturity",
        vertiports=20,
        reference_routes=123,
        reference_daily_passengers=113179,
    ),
}


@dataclass(frozen=True)
class ServiceProfile:
    name: str
    demand_mbps: float
    handover_floor_mbps: float
    latency_budget_ms: float
    description: str


SERVICE_PROFILES: Dict[str, ServiceProfile] = {
    "remote_uav_hd_control": ServiceProfile(
        name="remote_uav_hd_control",
        demand_mbps=25.0,
        handover_floor_mbps=0.3,
        latency_budget_ms=20.0,
        description=(
            "TS 22.125 airborne service reference: remote UAV controller "
            "through HD video requires 25 Mb/s uplink and 20 ms downlink "
            "latency target for control feedback."
        ),
    ),
    "real_time_video": ServiceProfile(
        name="real_time_video",
        demand_mbps=4.0,
        handover_floor_mbps=0.1,
        latency_budget_ms=100.0,
        description=(
            "Airborne real-time video tolerates 100 ms latency in the NTN "
            "review; this profile is used as a moderate user-plane service."
        ),
    ),
    "video_streaming_1080p": ServiceProfile(
        name="video_streaming_1080p",
        demand_mbps=9.0,
        handover_floor_mbps=1.0,
        latency_budget_ms=200.0,
        description=(
            "Video streaming at 1080p is associated with about 9 Mb/s and "
            "200 ms latency in the NTN review."
        ),
    ),
}


@dataclass
class SimulationConfig:
    phase: str = "introduction"
    seed: int = 7
    area_size_km: float = 50.0
    time_step_s: float = 0.5
    service_window_hours: float = 18.0
    reference_initial_operations_per_day: int = 186
    peak_hour_multiplier: float = 3.0
    neighbor_degree: int = 2
    route_min_km: float = 7.41
    route_max_km: float = 48.7
    planning_route_min_km: float = 20.0
    planning_route_max_km: float = 50.0
    speed_range_kmh: Tuple[float, float, float] = (120.0, 180.0, 250.0)
    altitude_bands_m: Tuple[float, ...] = (300.0, 450.0, 600.0)
    carrier_freq_ghz: float = 3.5
    tx_power_dbm: float = 43.0
    noise_floor_dbm: float = -104.0
    handover_margin_db: float = 2.5
    min_operational_sinr_db: float = 3.0
    handover_hysteresis_s: float = 2.0
    a3_ttt_s: float = 3.0
    a3_margin_db: float = 2.0
    proactive_trigger_window_s: float = 8.0
    precache_lead_time_s: float = 1.0
    precache_ttl_s: float = 12.0
    precache_control_reservation_mbps: float = 1.0
    edge_cache_capacity_mb: float = 96.0
    ping_pong_window_s: float = 15.0
    bs_spacing_km: float = 4.0
    bs_height_m: float = 30.0
    bs_capacity_mbps: float = 200.0
    reserved_control_slice_mbps: float = 5.0
    hub_route_bias: float = 0.7
    shadowing_tile_km: float = 0.5
    rooftop_height_m: float = 30.0
    los_shadowing_std_db: float = 1.8
    nlos_shadowing_std_db: float = 4.5
    nlos_excess_loss_db: float = 18.0
    rician_k_db: float = 8.0
    takeoff_transition_altitude_m: float = 300.0
    takeoff_vertical_rate_mps: float = 6.0
    landing_vertical_rate_mps: float = 5.0
    vertical_transition_trigger_km: float = 3.0

    def __post_init__(self) -> None:
        if self.phase not in PHASE_PROFILES:
            raise ValueError(f"Unsupported phase: {self.phase}")

    @property
    def phase_profile(self) -> PhaseProfile:
        return PHASE_PROFILES[self.phase]


@dataclass(frozen=True)
class Vertiport:
    vid: int
    name: str
    x_km: float
    y_km: float
    is_hub: bool
    cluster: str


@dataclass
class BaseStation:
    bid: int
    x_km: float
    y_km: float
    height_m: float
    attached_edge: Optional[Tuple[int, int]]
    connected_flights: set = field(default_factory=set)

    @property
    def load_factor(self) -> float:
        # Modeling assumption:
        # The reviewed papers do not specify per-cell capacity for UAM.
        # We normalize the dynamic load by assuming that six simultaneous
        # active UAM sessions already create a high-load corridor cell.
        return min(1.0, len(self.connected_flights) / 6.0)


@dataclass
class Flight:
    fid: int
    origin: int
    destination: int
    waypoints: List[Tuple[float, float]]
    route_length_km: float
    speed_kmh: float
    cruise_altitude_m: float
    altitude_m: float
    service: ServiceProfile
    current_bs: Optional[int] = None
    segment_index: int = 0
    segment_progress_km: float = 0.0
    x_km: float = 0.0
    y_km: float = 0.0
    active: bool = True
    reserved_target_bs: Optional[int] = None
    precache_ready_at_s: float = math.inf
    last_handover_time_s: float = -math.inf
    a3_candidate_bs: Optional[int] = None
    a3_candidate_since_s: float = math.inf
    handover_history: List[Tuple[float, int]] = field(default_factory=list)
    handover_count: int = 0
    interruption_ms_total: float = 0.0
    latency_violations: int = 0
    radio_handover_successes: int = 0
    radio_handover_failures: int = 0
    service_continuity_successes: int = 0
    service_continuity_failures: int = 0
    ping_pong_events: int = 0
    precache_hits: int = 0
    precache_requests: int = 0
    precache_commits: int = 0
    precache_backhaul_mb: float = 0.0
    precache_ttl_expiries: int = 0
    precache_reclaims: int = 0
    reservation_collisions: int = 0
    control_slice_exhaustions: int = 0
    edge_cache_overflows: int = 0
    radio_failures_low_throughput: int = 0
    service_failures_radio_only: int = 0
    service_failures_latency_only: int = 0
    service_failures_dual: int = 0
    throughput_samples: List[float] = field(default_factory=list)
    throughput_gap_samples: List[float] = field(default_factory=list)
    sinr_samples: List[float] = field(default_factory=list)
    demand_met_samples: int = 0
    demand_unmet_samples: int = 0
    vertical_phase: str = "climb"
    climb_distance_km: float = 0.0
    descent_distance_km: float = 0.0
    takeoff_altitude_m: float = 0.0
    total_distance_travelled_km: float = 0.0
    distance_to_destination_km: float = 0.0

    def remaining_distance_km(self) -> float:
        if not self.active:
            return 0.0
        remaining = 0.0
        current = (self.x_km, self.y_km)
        next_wp = self.waypoints[self.segment_index + 1]
        remaining += _distance_km(current, next_wp)
        for idx in range(self.segment_index + 1, len(self.waypoints) - 1):
            remaining += _distance_km(self.waypoints[idx], self.waypoints[idx + 1])
        return remaining


def _distance_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass
class PrecacheEntry:
    flight_id: int
    target_bs: int
    cache_size_mb: float
    reserved_control_mbps: float
    created_at_s: float
    ready_at_s: float
    expire_at_s: float


@dataclass(frozen=True)
class HandoverOutcome:
    observed_throughput_mbps: float
    required_floor_mbps: float
    interruption_ms: float
    latency_budget_ms: float
    meets_handover_floor: bool
    meets_latency_budget: bool

    @property
    def radio_success(self) -> bool:
        return self.meets_handover_floor

    @property
    def service_success(self) -> bool:
        return self.meets_handover_floor and self.meets_latency_budget

    @property
    def service_failure_radio_only(self) -> bool:
        return (not self.meets_handover_floor) and self.meets_latency_budget

    @property
    def service_failure_latency_only(self) -> bool:
        return self.meets_handover_floor and (not self.meets_latency_budget)

    @property
    def service_failure_dual(self) -> bool:
        return (not self.meets_handover_floor) and (not self.meets_latency_budget)


class UAMHandoverSimulation:
    def __init__(self, config: SimulationConfig):
        self.cfg = config
        self.random = random.Random(config.seed)
        self.np_rng = np.random.default_rng(config.seed)
        self.current_time_s = 0.0
        self.metrics = {
            "handover_attempts": 0,
            "radio_handover_successes": 0,
            "radio_handover_failures": 0,
            "radio_failures_low_throughput": 0,
            "service_continuity_successes": 0,
            "service_continuity_failures": 0,
            "service_failures_radio_only": 0,
            "service_failures_latency_only": 0,
            "service_failures_dual": 0,
            "ping_pong_events": 0,
            "control_latency_violations": 0,
            "precache_hits": 0,
            "precache_requests": 0,
            "precache_commits": 0,
            "precache_backhaul_mb": 0.0,
            "precache_ttl_expiries": 0,
            "precache_reclaims": 0,
            "reservation_collisions": 0,
            "control_slice_exhaustions": 0,
            "edge_cache_overflows": 0,
            "peak_active_precache_entries": 0,
            "peak_edge_cache_usage_mb": 0.0,
            "throughput_demand_met_samples": 0,
            "throughput_demand_unmet_samples": 0,
        }
        self._measurement_cache: Dict[Tuple[float, float, float], Tuple[int, Dict[int, Dict[str, float]]]] = {}
        self._shadowing_cache: Dict[Tuple[int, int, int, int, int], float] = {}
        self._channel_state_cache: Dict[Tuple[int, int, int, int], bool] = {}
        self._precache_entries: Dict[int, PrecacheEntry] = {}

        self.vertiports = self._build_reference_vertiports()
        self.active_vertiport_ids = self._active_vertiport_ids()
        self.route_graph = self._build_route_graph()
        self.base_stations = self._place_base_stations()
        self.flights: Dict[int, Flight] = {}
        self._next_flight_id = 0

    def _build_reference_vertiports(self) -> List[Vertiport]:
        # Modeling assumption:
        # The Seoul study gives the 7/2/11 regional split but not exact
        # coordinates. We create a 50 x 50 km metropolitan abstraction that
        # preserves two airport-like hubs and clustered urban nodes.
        coords = [
            (4.0, 24.0, "IncheonHub", True, "Incheon"),
            (12.0, 26.0, "GimpoHub", True, "Seoul"),
            (20.0, 25.0, "Yeouido", False, "Seoul"),
            (27.0, 25.0, "Jamsil", False, "Seoul"),
            (30.0, 21.0, "Gangnam", False, "Seoul"),
            (32.0, 17.0, "Pangyo", False, "Gyeonggi"),
            (29.0, 10.0, "Suwon", False, "Gyeonggi"),
            (37.0, 28.0, "Hanam", False, "Gyeonggi"),
            (18.0, 33.0, "Goyang", False, "Gyeonggi"),
            (6.0, 14.0, "Songdo", False, "Incheon"),
            (15.0, 22.0, "Bucheon", False, "Gyeonggi"),
            (34.0, 18.0, "Seongnam", False, "Gyeonggi"),
            (24.0, 15.0, "Anyang", False, "Gyeonggi"),
            (28.0, 37.0, "Uijeongbu", False, "Gyeonggi"),
            (39.0, 13.0, "Yongin", False, "Gyeonggi"),
            (10.0, 30.0, "GimpoCity", False, "Gyeonggi"),
            (41.0, 31.0, "Namyangju", False, "Gyeonggi"),
            (45.0, 18.0, "Icheon", False, "Gyeonggi"),
            (35.0, 5.0, "Pyeongtaek", False, "Gyeonggi"),
            (18.0, 8.0, "Ansan", False, "Gyeonggi"),
        ]
        vertiports = []
        for idx, (x_km, y_km, name, is_hub, cluster) in enumerate(coords):
            vertiports.append(
                Vertiport(
                    vid=idx,
                    name=name,
                    x_km=x_km,
                    y_km=y_km,
                    is_hub=is_hub,
                    cluster=cluster,
                )
            )
        return vertiports

    def _active_vertiport_ids(self) -> List[int]:
        profile = self.cfg.phase_profile
        if profile.vertiports == 4:
            return [0, 1, 2, 3]
        if profile.vertiports == 8:
            return [0, 1, 2, 3, 4, 5, 6, 7]
        return list(range(profile.vertiports))

    def _build_route_graph(self) -> Dict[int, Dict[int, float]]:
        active = [self.vertiports[idx] for idx in self.active_vertiport_ids]
        graph: Dict[int, Dict[int, float]] = {v.vid: {} for v in active}
        hubs = [v for v in active if v.is_hub]

        for vertiport in active:
            neighbors = sorted(
                (other for other in active if other.vid != vertiport.vid),
                key=lambda other: _distance_km(
                    (vertiport.x_km, vertiport.y_km), (other.x_km, other.y_km)
                ),
            )
            for other in neighbors[: self.cfg.neighbor_degree]:
                self._add_edge(graph, vertiport.vid, other.vid)

            if hubs and not vertiport.is_hub:
                nearest_hub = min(
                    hubs,
                    key=lambda hub: _distance_km(
                        (vertiport.x_km, vertiport.y_km), (hub.x_km, hub.y_km)
                    ),
                )
                self._add_edge(graph, vertiport.vid, nearest_hub.vid)

        if len(hubs) >= 2:
            self._add_edge(graph, hubs[0].vid, hubs[1].vid)

        return graph

    def _add_edge(self, graph: Dict[int, Dict[int, float]], a: int, b: int) -> None:
        va = self.vertiports[a]
        vb = self.vertiports[b]
        dist = _distance_km((va.x_km, va.y_km), (vb.x_km, vb.y_km))
        graph[a][b] = dist
        graph[b][a] = dist

    def _place_base_stations(self) -> Dict[int, BaseStation]:
        base_stations: Dict[int, BaseStation] = {}
        next_bid = 0
        unique_edges = set()
        for src, neighbors in self.route_graph.items():
            for dst in neighbors:
                unique_edges.add(tuple(sorted((src, dst))))

        # One station near every active vertiport for takeoff/landing coverage.
        for vid in self.active_vertiport_ids:
            v = self.vertiports[vid]
            offset = 0.8 if v.is_hub else 0.5
            bs = BaseStation(
                bid=next_bid,
                x_km=min(self.cfg.area_size_km, v.x_km + offset),
                y_km=min(self.cfg.area_size_km, v.y_km + offset),
                height_m=self.cfg.bs_height_m,
                attached_edge=None,
            )
            base_stations[next_bid] = bs
            next_bid += 1

        # Modeling assumption:
        # Corridor stations are placed every 4 km to force multiple handover
        # opportunities along 20-50 km routes while keeping overlap.
        for edge in sorted(unique_edges):
            a = self.vertiports[edge[0]]
            b = self.vertiports[edge[1]]
            dist = _distance_km((a.x_km, a.y_km), (b.x_km, b.y_km))
            segments = max(1, int(dist / self.cfg.bs_spacing_km))
            dx = b.x_km - a.x_km
            dy = b.y_km - a.y_km
            length = math.hypot(dx, dy)
            perp_x = 0.0 if length == 0 else -dy / length
            perp_y = 0.0 if length == 0 else dx / length
            for step in range(1, segments):
                t = step / segments
                jitter = 0.4 if step % 2 == 0 else -0.4
                x_km = a.x_km + dx * t + perp_x * jitter
                y_km = a.y_km + dy * t + perp_y * jitter
                base_stations[next_bid] = BaseStation(
                    bid=next_bid,
                    x_km=max(0.0, min(self.cfg.area_size_km, x_km)),
                    y_km=max(0.0, min(self.cfg.area_size_km, y_km)),
                    height_m=self.cfg.bs_height_m,
                    attached_edge=edge,
                )
                next_bid += 1

        return base_stations

    def shortest_path(self, origin: int, destination: int) -> List[int]:
        queue: List[Tuple[float, int]] = [(0.0, origin)]
        prev: Dict[int, Optional[int]] = {origin: None}
        dist: Dict[int, float] = {origin: 0.0}

        while queue:
            cur_dist, node = heapq.heappop(queue)
            if node == destination:
                break
            if cur_dist > dist[node]:
                continue
            for neighbor, weight in self.route_graph[node].items():
                new_dist = cur_dist + weight
                if neighbor not in dist or new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    prev[neighbor] = node
                    heapq.heappush(queue, (new_dist, neighbor))

        if destination not in prev:
            raise RuntimeError("No path found between the selected vertiports.")

        path = []
        node: Optional[int] = destination
        while node is not None:
            path.append(node)
            node = prev[node]
        return list(reversed(path))

    def spawn_reference_traffic(
        self,
        hours: float = 1.0,
        traffic_multiplier: Optional[float] = None,
    ) -> int:
        multiplier = (
            self.cfg.peak_hour_multiplier
            if traffic_multiplier is None
            else traffic_multiplier
        )
        expected_ops = (
            self.cfg.reference_initial_operations_per_day
            * (hours / self.cfg.service_window_hours)
            * multiplier
        )
        num_flights = max(1, int(round(expected_ops)))
        for _ in range(num_flights):
            self.spawn_flight()
        return num_flights

    def spawn_flight(
        self,
        origin: Optional[int] = None,
        destination: Optional[int] = None,
        service_name: str = "remote_uav_hd_control",
    ) -> int:
        if service_name not in SERVICE_PROFILES:
            raise ValueError(f"Unsupported service profile: {service_name}")

        if origin is None or destination is None:
            origin, destination = self._sample_od_pair()

        route_nodes = self.shortest_path(origin, destination)
        waypoints = [
            (self.vertiports[node].x_km, self.vertiports[node].y_km)
            for node in route_nodes
        ]
        route_length_km = sum(
            _distance_km(waypoints[idx], waypoints[idx + 1])
            for idx in range(len(waypoints) - 1)
        )
        speed_kmh = self.random.triangular(*self.cfg.speed_range_kmh)
        altitude_m = self.random.choice(self.cfg.altitude_bands_m)
        climb_distance_km = max(
            self.cfg.vertical_transition_trigger_km,
            speed_kmh * (self.cfg.takeoff_transition_altitude_m / max(self.cfg.takeoff_vertical_rate_mps, 1e-6)) / 3600.0,
        )
        descent_distance_km = max(
            self.cfg.vertical_transition_trigger_km,
            speed_kmh * (self.cfg.takeoff_transition_altitude_m / max(self.cfg.landing_vertical_rate_mps, 1e-6)) / 3600.0,
        )

        flight = Flight(
            fid=self._next_flight_id,
            origin=origin,
            destination=destination,
            waypoints=waypoints,
            route_length_km=route_length_km,
            speed_kmh=speed_kmh,
            cruise_altitude_m=altitude_m,
            altitude_m=altitude_m,
            service=SERVICE_PROFILES[service_name],
            x_km=waypoints[0][0],
            y_km=waypoints[0][1],
            climb_distance_km=min(route_length_km / 2.0, climb_distance_km),
            descent_distance_km=min(route_length_km / 2.0, descent_distance_km),
            takeoff_altitude_m=0.0,
            distance_to_destination_km=route_length_km,
        )
        flight.altitude_m = flight.takeoff_altitude_m
        flight.vertical_phase = "climb"

        initial_bs, _ = self._best_bs_for_position(
            flight.x_km,
            flight.y_km,
            flight.altitude_m,
        )
        flight.current_bs = initial_bs
        self.flights[flight.fid] = flight
        self._next_flight_id += 1
        return flight.fid

    def _sample_od_pair(self) -> Tuple[int, int]:
        active = self.active_vertiport_ids
        hubs = [vid for vid in active if self.vertiports[vid].is_hub]

        if self.random.random() < self.cfg.hub_route_bias and hubs:
            if self.random.random() < 0.15 and len(hubs) >= 2:
                origin, destination = hubs[0], hubs[1]
            else:
                hub = self.random.choice(hubs)
                other_candidates = [vid for vid in active if vid != hub]
                origin, destination = hub, self.random.choice(other_candidates)
                if self.random.random() < 0.5:
                    origin, destination = destination, origin
        else:
            origin, destination = self.random.sample(active, 2)

        route_nodes = self.shortest_path(origin, destination)
        waypoints = [
            (self.vertiports[node].x_km, self.vertiports[node].y_km)
            for node in route_nodes
        ]
        route_length_km = sum(
            _distance_km(waypoints[idx], waypoints[idx + 1])
            for idx in range(len(waypoints) - 1)
        )
        if route_length_km > self.cfg.route_max_km:
            return self._sample_od_pair()
        return origin, destination

    def step(self, policy: str = "reactive") -> None:
        if policy not in {"reactive", "a3_ttt", "proactive"}:
            raise ValueError(f"Unsupported policy: {policy}")

        self.current_time_s += self.cfg.time_step_s
        self._expire_precache_entries()
        self._refresh_bs_loads()
        self._measurement_cache.clear()

        for flight in self.flights.values():
            if not flight.active:
                continue

            self._advance_flight(flight, self.cfg.time_step_s)
            if not flight.active:
                self._detach_flight_from_bs(flight)
                self._reclaim_precache_entry(flight.fid)
                continue

            if policy == "reactive":
                self._reactive_handover(flight)
            elif policy == "a3_ttt":
                self._a3_ttt_handover(flight)
            else:
                self._proactive_handover(flight)

            self._sample_link_quality(flight)

        self._recompute_precache_peaks()

    def run(self, duration_s: float, policy: str = "reactive") -> Dict[str, float]:
        steps = int(duration_s / self.cfg.time_step_s)
        for _ in range(steps):
            self.step(policy=policy)
        return self.summarize(policy=policy)

    def summarize(self, policy: str) -> Dict[str, float]:
        throughput_samples = []
        throughput_gap_samples = []
        sinr_samples = []
        interruption_ms = 0.0
        completed = 0
        total_handovers = 0
        demand_met_samples = 0
        demand_total_samples = 0

        for flight in self.flights.values():
            throughput_samples.extend(flight.throughput_samples)
            throughput_gap_samples.extend(flight.throughput_gap_samples)
            sinr_samples.extend(flight.sinr_samples)
            interruption_ms += flight.interruption_ms_total
            total_handovers += flight.handover_count
            demand_met_samples += flight.demand_met_samples
            demand_total_samples += flight.demand_met_samples + flight.demand_unmet_samples
            if not flight.active:
                completed += 1

        mean_throughput = (
            float(np.mean(throughput_samples)) if throughput_samples else 0.0
        )
        mean_throughput_gap = (
            float(np.mean(throughput_gap_samples)) if throughput_gap_samples else 0.0
        )
        mean_sinr = float(np.mean(sinr_samples)) if sinr_samples else 0.0
        demand_satisfied_sample_pct = (
            (demand_met_samples / demand_total_samples) * 100.0
            if demand_total_samples
            else 0.0
        )

        return {
            "policy": policy,
            "phase": self.cfg.phase,
            "completed_flights": completed,
            "total_flights": len(self.flights),
            "total_handovers": total_handovers,
            "handover_attempts": self.metrics["handover_attempts"],
            "radio_handover_successes": self.metrics["radio_handover_successes"],
            "radio_handover_failures": self.metrics["radio_handover_failures"],
            "radio_failures_low_throughput": self.metrics["radio_failures_low_throughput"],
            "service_continuity_successes": self.metrics["service_continuity_successes"],
            "service_continuity_failures": self.metrics["service_continuity_failures"],
            "service_failures_radio_only": self.metrics["service_failures_radio_only"],
            "service_failures_latency_only": self.metrics["service_failures_latency_only"],
            "service_failures_dual": self.metrics["service_failures_dual"],
            "ping_pong_events": self.metrics["ping_pong_events"],
            "control_latency_violations": self.metrics["control_latency_violations"],
            "precache_hits": self.metrics["precache_hits"],
            "precache_requests": self.metrics["precache_requests"],
            "precache_commits": self.metrics["precache_commits"],
            "precache_backhaul_mb": round(float(self.metrics["precache_backhaul_mb"]), 2),
            "precache_ttl_expiries": self.metrics["precache_ttl_expiries"],
            "precache_reclaims": self.metrics["precache_reclaims"],
            "reservation_collisions": self.metrics["reservation_collisions"],
            "control_slice_exhaustions": self.metrics["control_slice_exhaustions"],
            "edge_cache_overflows": self.metrics["edge_cache_overflows"],
            "peak_active_precache_entries": self.metrics["peak_active_precache_entries"],
            "peak_edge_cache_usage_mb": round(float(self.metrics["peak_edge_cache_usage_mb"]), 2),
            "mean_throughput_mbps": round(mean_throughput, 2),
            "mean_throughput_gap_mbps": round(mean_throughput_gap, 2),
            "demand_satisfied_sample_pct": round(demand_satisfied_sample_pct, 2),
            "mean_sinr_db": round(mean_sinr, 2),
            "total_interruption_ms": round(interruption_ms, 2),
        }

    def _advance_flight(self, flight: Flight, delta_s: float) -> None:
        move_km = flight.speed_kmh * (delta_s / 3600.0)
        while move_km > 0 and flight.active:
            start = (flight.x_km, flight.y_km)
            end = flight.waypoints[flight.segment_index + 1]
            remaining_segment_km = _distance_km(start, end)
            if move_km < remaining_segment_km:
                ratio = move_km / max(remaining_segment_km, 1e-9)
                flight.x_km = start[0] + (end[0] - start[0]) * ratio
                flight.y_km = start[1] + (end[1] - start[1]) * ratio
                flight.total_distance_travelled_km += move_km
                move_km = 0.0
            else:
                flight.x_km, flight.y_km = end
                move_km -= remaining_segment_km
                flight.total_distance_travelled_km += remaining_segment_km
                flight.segment_index += 1
                if flight.segment_index >= len(flight.waypoints) - 1:
                    flight.active = False

        flight.distance_to_destination_km = max(
            0.0,
            flight.route_length_km - flight.total_distance_travelled_km,
        )
        self._update_flight_altitude(flight)

    def _update_flight_altitude(self, flight: Flight) -> None:
        if not flight.active:
            flight.altitude_m = 0.0
            flight.vertical_phase = "landed"
            return

        if flight.total_distance_travelled_km < flight.climb_distance_km:
            climb_ratio = flight.total_distance_travelled_km / max(flight.climb_distance_km, 1e-9)
            flight.altitude_m = (
                flight.takeoff_altitude_m
                + (flight.cruise_altitude_m - flight.takeoff_altitude_m) * climb_ratio
            )
            flight.vertical_phase = "climb"
            return

        if flight.distance_to_destination_km <= flight.descent_distance_km:
            descent_ratio = flight.distance_to_destination_km / max(flight.descent_distance_km, 1e-9)
            flight.altitude_m = max(
                flight.takeoff_altitude_m,
                flight.cruise_altitude_m * descent_ratio,
            )
            flight.vertical_phase = "descent"
            return

        flight.altitude_m = flight.cruise_altitude_m
        flight.vertical_phase = "cruise"

    def _refresh_bs_loads(self) -> None:
        for bs in self.base_stations.values():
            bs.connected_flights.clear()
        for flight in self.flights.values():
            if flight.active and flight.current_bs is not None:
                self.base_stations[flight.current_bs].connected_flights.add(flight.fid)

    def _recompute_precache_peaks(self) -> None:
        active_entries = len(self._precache_entries)
        total_cache_mb = sum(entry.cache_size_mb for entry in self._precache_entries.values())
        self.metrics["peak_active_precache_entries"] = max(
            self.metrics["peak_active_precache_entries"],
            active_entries,
        )
        self.metrics["peak_edge_cache_usage_mb"] = max(
            self.metrics["peak_edge_cache_usage_mb"],
            total_cache_mb,
        )

    def _expire_precache_entries(self) -> None:
        expired_flights = [
            flight_id
            for flight_id, entry in self._precache_entries.items()
            if entry.expire_at_s <= self.current_time_s
        ]
        for flight_id in expired_flights:
            flight = self.flights.get(flight_id)
            if flight is not None:
                flight.precache_ttl_expiries += 1
            self.metrics["precache_ttl_expiries"] += 1
            self._reclaim_precache_entry(flight_id)

    def _reclaim_precache_entry(self, flight_id: int) -> None:
        entry = self._precache_entries.pop(flight_id, None)
        if entry is None:
            return
        self.metrics["precache_reclaims"] += 1
        flight = self.flights.get(flight_id)
        if flight is not None:
            flight.precache_reclaims += 1

    def _reserved_control_usage_mbps(self, target_bs: int) -> float:
        return sum(
            entry.reserved_control_mbps
            for entry in self._precache_entries.values()
            if entry.target_bs == target_bs
        )

    def _cache_usage_mb(self, target_bs: int) -> float:
        return sum(
            entry.cache_size_mb
            for entry in self._precache_entries.values()
            if entry.target_bs == target_bs
        )

    def _estimate_precache_payload_mb(self, flight: Flight) -> float:
        payload_window_s = min(self.cfg.precache_ttl_s, 8.0)
        capped_rate_mbps = min(flight.service.demand_mbps, 12.0)
        return max(0.5, capped_rate_mbps * payload_window_s / 8.0)

    def _prepare_precache(self, flight: Flight, target_bs: int) -> bool:
        if flight.fid in self._precache_entries:
            existing_entry = self._precache_entries[flight.fid]
            if existing_entry.target_bs == target_bs:
                flight.reserved_target_bs = target_bs
                flight.precache_ready_at_s = existing_entry.ready_at_s
                return True
            self._reclaim_precache_entry(flight.fid)

        flight.precache_requests += 1
        self.metrics["precache_requests"] += 1

        reserved_control_mbps = min(
            self.cfg.reserved_control_slice_mbps,
            max(self.cfg.precache_control_reservation_mbps, flight.service.handover_floor_mbps),
        )
        if (
            self._reserved_control_usage_mbps(target_bs) + reserved_control_mbps
            > self.cfg.reserved_control_slice_mbps
        ):
            self.metrics["reservation_collisions"] += 1
            self.metrics["control_slice_exhaustions"] += 1
            flight.reservation_collisions += 1
            flight.control_slice_exhaustions += 1
            flight.reserved_target_bs = None
            flight.precache_ready_at_s = math.inf
            return False

        cache_size_mb = self._estimate_precache_payload_mb(flight)
        if self._cache_usage_mb(target_bs) + cache_size_mb > self.cfg.edge_cache_capacity_mb:
            self.metrics["edge_cache_overflows"] += 1
            self.metrics["reservation_collisions"] += 1
            flight.edge_cache_overflows += 1
            flight.reservation_collisions += 1
            flight.reserved_target_bs = None
            flight.precache_ready_at_s = math.inf
            return False

        entry = PrecacheEntry(
            flight_id=flight.fid,
            target_bs=target_bs,
            cache_size_mb=cache_size_mb,
            reserved_control_mbps=reserved_control_mbps,
            created_at_s=self.current_time_s,
            ready_at_s=self.current_time_s + self.cfg.precache_lead_time_s,
            expire_at_s=self.current_time_s + self.cfg.precache_ttl_s,
        )
        self._precache_entries[flight.fid] = entry
        self.metrics["precache_commits"] += 1
        self.metrics["precache_backhaul_mb"] += cache_size_mb
        flight.precache_commits += 1
        flight.precache_backhaul_mb += cache_size_mb
        flight.reserved_target_bs = target_bs
        flight.precache_ready_at_s = entry.ready_at_s
        self._recompute_precache_peaks()
        return True

    def _best_bs_for_position(
        self,
        x_km: float,
        y_km: float,
        altitude_m: float,
    ) -> Tuple[int, Dict[int, Dict[str, float]]]:
        cache_key = (round(x_km, 3), round(y_km, 3), round(altitude_m, 1))
        if cache_key in self._measurement_cache:
            return self._measurement_cache[cache_key]

        measurements: Dict[int, Dict[str, float]] = {}
        for bid, bs in self.base_stations.items():
            signal_dbm = self._received_power_dbm(x_km, y_km, altitude_m, bs)
            interference_mw = 0.0
            for other_bid, other_bs in self.base_stations.items():
                if other_bid == bid:
                    continue
                other_signal = self._received_power_dbm(x_km, y_km, altitude_m, other_bs)
                if other_signal > signal_dbm - 8.0:
                    interference_mw += 10 ** (other_signal / 10.0)

            noise_mw = 10 ** (self.cfg.noise_floor_dbm / 10.0)
            signal_mw = 10 ** (signal_dbm / 10.0)
            sinr_linear = signal_mw / max(noise_mw + interference_mw, 1e-12)
            sinr_db = 10.0 * math.log10(max(sinr_linear, 1e-12))
            load_penalty = 8.0 * self.base_stations[bid].load_factor
            effective_sinr_db = sinr_db - load_penalty
            throughput_mbps = min(
                50.0,
                max(0.1, 10.0 * math.log2(1.0 + max(10 ** (effective_sinr_db / 10.0), 0.0))),
            )
            latency_ms = (
                8.0
                + 12.0 * self.base_stations[bid].load_factor
                + max(0.0, 6.0 - effective_sinr_db) * 2.5
            )
            measurements[bid] = {
                "signal_dbm": signal_dbm,
                "sinr_db": effective_sinr_db,
                "throughput_mbps": throughput_mbps,
                "latency_ms": latency_ms,
                "los_probability": self._aerial_los_probability(
                    _distance_km((x_km, y_km), (bs.x_km, bs.y_km)) * 1000.0,
                    altitude_m,
                ),
                "is_los": 1.0 if self._is_los_condition(x_km, y_km, altitude_m, bs) else 0.0,
            }

        best_bid = max(measurements, key=lambda bid: measurements[bid]["sinr_db"])
        result = (best_bid, measurements)
        self._measurement_cache[cache_key] = result
        return result

    def _received_power_dbm(
        self,
        x_km: float,
        y_km: float,
        altitude_m: float,
        bs: BaseStation,
    ) -> float:
        horizontal_m = _distance_km((x_km, y_km), (bs.x_km, bs.y_km)) * 1000.0
        vertical_m = max(1.0, altitude_m - bs.height_m)
        dist_m = math.sqrt(horizontal_m ** 2 + vertical_m ** 2)
        dist_km = max(dist_m / 1000.0, 0.001)

        fspl_db = 32.44 + 20.0 * math.log10(dist_km) + 20.0 * math.log10(
            self.cfg.carrier_freq_ghz * 1000.0
        )

        is_los = self._is_los_condition(x_km, y_km, altitude_m, bs)
        downtilt_penalty_db = self._downtilt_penalty_db(horizontal_m, altitude_m)
        excess_loss_db = self._excess_loss_db(altitude_m, is_los)
        shadowing_db = self._shadowing_db(x_km, y_km, altitude_m, bs, is_los)
        fading_db = self._small_scale_fading_db(x_km, y_km, altitude_m, bs, is_los)
        return (
            self.cfg.tx_power_dbm
            - fspl_db
            - downtilt_penalty_db
            - excess_loss_db
            + shadowing_db
            + fading_db
        )

    def _mix_seed(self, *values: int) -> int:
        mixed = self.cfg.seed * 1000003
        for idx, value in enumerate(values, start=1):
            mixed = (mixed * 9176 + value * (131071 + idx * 104729)) & 0xFFFFFFFF
        return mixed

    def _channel_tile_key(
        self,
        x_km: float,
        y_km: float,
        altitude_m: float,
    ) -> Tuple[int, int, int]:
        tile = self.cfg.shadowing_tile_km
        tile_x = int(x_km / tile)
        tile_y = int(y_km / tile)
        altitude_bucket = int(altitude_m / 50.0)
        return tile_x, tile_y, altitude_bucket

    def _aerial_los_probability(self, horizontal_m: float, altitude_m: float) -> float:
        # TR 36.777 and the 3GPP UAV work emphasize that aerial UEs above
        # rooftops are frequently LoS-dominant and observe multiple strong
        # neighbors. ITU-R P.1410-5 also separates LoS, reflected-wave
        # dominant, and diffracted-wave dominant regions around rooftops.
        rooftop_delta_m = altitude_m - self.cfg.rooftop_height_m
        if rooftop_delta_m >= 250.0:
            base_probability = 0.98
        elif rooftop_delta_m >= 100.0:
            base_probability = 0.93
        elif rooftop_delta_m >= 0.0:
            base_probability = 0.83
        else:
            base_probability = 0.65

        distance_penalty = min(0.28, horizontal_m / 5000.0 * 0.28)
        below_rooftop_penalty = 0.10 if altitude_m < self.cfg.rooftop_height_m else 0.0
        probability = base_probability - distance_penalty - below_rooftop_penalty
        return max(0.20, min(0.98, probability))

    def _is_los_condition(
        self,
        x_km: float,
        y_km: float,
        altitude_m: float,
        bs: BaseStation,
    ) -> bool:
        tile_x, tile_y, altitude_bucket = self._channel_tile_key(x_km, y_km, altitude_m)
        state_key = (bs.bid, tile_x, tile_y, altitude_bucket)
        if state_key not in self._channel_state_cache:
            horizontal_m = _distance_km((x_km, y_km), (bs.x_km, bs.y_km)) * 1000.0
            los_probability = self._aerial_los_probability(horizontal_m, altitude_m)
            rng = random.Random(self._mix_seed(bs.bid, tile_x, tile_y, altitude_bucket, 17))
            self._channel_state_cache[state_key] = rng.random() < los_probability
        return self._channel_state_cache[state_key]

    def _downtilt_penalty_db(self, horizontal_m: float, altitude_m: float) -> float:
        if altitude_m < self.cfg.rooftop_height_m + 50.0:
            penalty_db = 3.0
        elif altitude_m < self.cfg.rooftop_height_m + 200.0:
            penalty_db = 5.0
        else:
            penalty_db = 7.0
        if horizontal_m >= 3000.0:
            penalty_db += 1.0
        return penalty_db

    def _excess_loss_db(self, altitude_m: float, is_los: bool) -> float:
        if is_los:
            return 0.0
        shadow_depth_m = max(0.0, self.cfg.rooftop_height_m - altitude_m)
        return self.cfg.nlos_excess_loss_db + 0.03 * shadow_depth_m

    def _shadowing_db(
        self,
        x_km: float,
        y_km: float,
        altitude_m: float,
        bs: BaseStation,
        is_los: bool,
    ) -> float:
        tile_x, tile_y, altitude_bucket = self._channel_tile_key(x_km, y_km, altitude_m)
        shadow_key = (bs.bid, tile_x, tile_y, altitude_bucket, int(is_los))
        if shadow_key not in self._shadowing_cache:
            sigma_db = (
                self.cfg.los_shadowing_std_db
                if is_los
                else self.cfg.nlos_shadowing_std_db
            )
            mixed_seed = self._mix_seed(bs.bid, tile_x, tile_y, altitude_bucket, int(is_los), 29)
            self._shadowing_cache[shadow_key] = random.Random(mixed_seed).gauss(0.0, sigma_db)
        return self._shadowing_cache[shadow_key]

    def _small_scale_fading_db(
        self,
        x_km: float,
        y_km: float,
        altitude_m: float,
        bs: BaseStation,
        is_los: bool,
    ) -> float:
        tile_x, tile_y, altitude_bucket = self._channel_tile_key(x_km, y_km, altitude_m)
        time_slot = int(self.current_time_s / max(self.cfg.time_step_s, 1e-9))
        rng = random.Random(
            self._mix_seed(bs.bid, tile_x, tile_y, altitude_bucket, time_slot, int(is_los), 43)
        )

        if is_los:
            k_linear = 10.0 ** (self.cfg.rician_k_db / 10.0)
            scatter_scale = math.sqrt(1.0 / (2.0 * (k_linear + 1.0)))
            los_component = math.sqrt(k_linear / (k_linear + 1.0))
            i_value = los_component + scatter_scale * rng.gauss(0.0, 1.0)
            q_value = scatter_scale * rng.gauss(0.0, 1.0)
            amplitude = math.sqrt(i_value * i_value + q_value * q_value)
        else:
            i_value = rng.gauss(0.0, 1.0 / math.sqrt(2.0))
            q_value = rng.gauss(0.0, 1.0 / math.sqrt(2.0))
            amplitude = math.sqrt(i_value * i_value + q_value * q_value)

        fading_db = 20.0 * math.log10(max(amplitude, 1e-6))
        return max(-12.0, min(6.0, fading_db))

    def _detach_flight_from_bs(self, flight: Flight) -> None:
        if flight.current_bs is not None:
            self.base_stations[flight.current_bs].connected_flights.discard(flight.fid)

    def _reactive_handover(self, flight: Flight) -> None:
        if (
            self.current_time_s - flight.last_handover_time_s
            < self.cfg.handover_hysteresis_s
        ):
            return

        best_bs, measurements = self._best_bs_for_position(
            flight.x_km, flight.y_km, flight.altitude_m
        )
        current = measurements[flight.current_bs]
        best = measurements[best_bs]

        need_switch = (
            best_bs != flight.current_bs
            and (
                current["sinr_db"] < self.cfg.min_operational_sinr_db
                or best["sinr_db"] > current["sinr_db"] + self.cfg.handover_margin_db
            )
        )

        if need_switch:
            interruption_ms = 60.0 + max(0.0, 5.0 - best["sinr_db"]) * 5.0
            self._execute_handover(
                flight,
                target_bs=best_bs,
                interruption_ms=interruption_ms,
                target_metrics=best,
                precache_hit=False,
            )

    def _a3_ttt_handover(self, flight: Flight) -> None:
        if (
            self.current_time_s - flight.last_handover_time_s
            < self.cfg.handover_hysteresis_s
        ):
            return

        best_bs, measurements = self._best_bs_for_position(
            flight.x_km, flight.y_km, flight.altitude_m
        )
        current = measurements[flight.current_bs]
        best = measurements[best_bs]

        a3_condition = (
            best_bs != flight.current_bs
            and best["sinr_db"] > current["sinr_db"] + self.cfg.a3_margin_db
        )

        if a3_condition:
            if flight.a3_candidate_bs != best_bs:
                flight.a3_candidate_bs = best_bs
                flight.a3_candidate_since_s = self.current_time_s
                return

            dwell_time = self.current_time_s - flight.a3_candidate_since_s
            if dwell_time >= self.cfg.a3_ttt_s or current["sinr_db"] < self.cfg.min_operational_sinr_db:
                interruption_ms = 42.0 + max(0.0, 4.5 - best["sinr_db"]) * 4.0
                self._execute_handover(
                    flight,
                    target_bs=best_bs,
                    interruption_ms=interruption_ms,
                    target_metrics=best,
                    precache_hit=False,
                )
                flight.a3_candidate_bs = None
                flight.a3_candidate_since_s = math.inf
            return

        flight.a3_candidate_bs = None
        flight.a3_candidate_since_s = math.inf

    def _proactive_handover(self, flight: Flight) -> None:
        if (
            self.current_time_s - flight.last_handover_time_s
            < self.cfg.handover_hysteresis_s
        ):
            return

        best_now_bs, now_measurements = self._best_bs_for_position(
            flight.x_km, flight.y_km, flight.altitude_m
        )
        current_metrics = now_measurements[flight.current_bs]

        future_pos = self._predict_future_position(
            flight,
            self.cfg.proactive_trigger_window_s,
        )
        best_future_bs, future_measurements = self._best_bs_for_position(
            future_pos[0], future_pos[1], future_pos[2]
        )
        future_current = future_measurements.get(
            flight.current_bs,
            {"sinr_db": -math.inf, "latency_ms": math.inf},
        )
        future_best = future_measurements[best_future_bs]

        should_prepare = (
            best_future_bs != flight.current_bs
            and future_best["sinr_db"]
            > future_current["sinr_db"] + self.cfg.handover_margin_db
        )

        if should_prepare:
            self._prepare_precache(flight, best_future_bs)
        elif flight.reserved_target_bs is not None:
            self._reclaim_precache_entry(flight.fid)
            flight.reserved_target_bs = None
            flight.precache_ready_at_s = math.inf

        if flight.reserved_target_bs is None:
            return

        prepared_metrics = now_measurements.get(flight.reserved_target_bs)
        if prepared_metrics is None:
            return

        prepared_ready = self.current_time_s >= flight.precache_ready_at_s
        should_switch = (
            current_metrics["sinr_db"] < self.cfg.min_operational_sinr_db + 1.0
            or (
                prepared_metrics["sinr_db"]
                > current_metrics["sinr_db"] + self.cfg.handover_margin_db
                and prepared_ready
            )
        )

        if should_switch:
            interruption_ms = 12.0 if prepared_ready else 35.0
            self._execute_handover(
                flight,
                target_bs=flight.reserved_target_bs,
                interruption_ms=interruption_ms,
                target_metrics=prepared_metrics,
                precache_hit=prepared_ready,
            )
            flight.reserved_target_bs = None
            flight.precache_ready_at_s = math.inf
            flight.a3_candidate_bs = None
            flight.a3_candidate_since_s = math.inf

    def _evaluate_handover_outcome(
        self,
        flight: Flight,
        interruption_ms: float,
        target_metrics: Dict[str, float],
    ) -> HandoverOutcome:
        observed_throughput_mbps = float(target_metrics["throughput_mbps"])
        required_floor_mbps = float(flight.service.handover_floor_mbps)
        latency_budget_ms = float(flight.service.latency_budget_ms)
        meets_handover_floor = observed_throughput_mbps >= required_floor_mbps
        meets_latency_budget = interruption_ms <= latency_budget_ms
        return HandoverOutcome(
            observed_throughput_mbps=observed_throughput_mbps,
            required_floor_mbps=required_floor_mbps,
            interruption_ms=interruption_ms,
            latency_budget_ms=latency_budget_ms,
            meets_handover_floor=meets_handover_floor,
            meets_latency_budget=meets_latency_budget,
        )

    def _execute_handover(
        self,
        flight: Flight,
        target_bs: int,
        interruption_ms: float,
        target_metrics: Dict[str, float],
        precache_hit: bool,
    ) -> None:
        if target_bs == flight.current_bs:
            return

        self.metrics["handover_attempts"] += 1
        flight.handover_count += 1
        flight.interruption_ms_total += interruption_ms

        if precache_hit:
            self.metrics["precache_hits"] += 1

        outcome = self._evaluate_handover_outcome(
            flight=flight,
            interruption_ms=interruption_ms,
            target_metrics=target_metrics,
        )

        if outcome.radio_success:
            self.metrics["radio_handover_successes"] += 1
            flight.radio_handover_successes += 1
        else:
            self.metrics["radio_handover_failures"] += 1
            self.metrics["radio_failures_low_throughput"] += 1
            flight.radio_handover_failures += 1
            flight.radio_failures_low_throughput += 1

        if outcome.service_success:
            self.metrics["service_continuity_successes"] += 1
            flight.service_continuity_successes += 1
        else:
            self.metrics["service_continuity_failures"] += 1
            flight.service_continuity_failures += 1
            self.metrics["control_latency_violations"] += 1
            flight.latency_violations += 1
            if outcome.service_failure_radio_only:
                self.metrics["service_failures_radio_only"] += 1
                flight.service_failures_radio_only += 1
            elif outcome.service_failure_latency_only:
                self.metrics["service_failures_latency_only"] += 1
                flight.service_failures_latency_only += 1
            elif outcome.service_failure_dual:
                self.metrics["service_failures_dual"] += 1
                flight.service_failures_dual += 1

        if flight.handover_history:
            prev_time_s, prev_bs = flight.handover_history[-1]
            if (
                prev_bs == target_bs
                and self.current_time_s - prev_time_s <= self.cfg.ping_pong_window_s
            ):
                self.metrics["ping_pong_events"] += 1
                flight.ping_pong_events += 1

        flight.handover_history.append((self.current_time_s, flight.current_bs))
        flight.current_bs = target_bs
        flight.last_handover_time_s = self.current_time_s
        if precache_hit:
            flight.precache_hits += 1
            self._reclaim_precache_entry(flight.fid)

    def _predict_future_position(
        self,
        flight: Flight,
        horizon_s: float,
    ) -> Tuple[float, float, float]:
        temp_segment = flight.segment_index
        temp_x = flight.x_km
        temp_y = flight.y_km
        move_km = flight.speed_kmh * (horizon_s / 3600.0)
        temp_distance = flight.total_distance_travelled_km

        while move_km > 0 and temp_segment < len(flight.waypoints) - 1:
            start = (temp_x, temp_y)
            end = flight.waypoints[temp_segment + 1]
            remaining_segment_km = _distance_km(start, end)
            if move_km < remaining_segment_km:
                ratio = move_km / max(remaining_segment_km, 1e-9)
                temp_x = start[0] + (end[0] - start[0]) * ratio
                temp_y = start[1] + (end[1] - start[1]) * ratio
                temp_distance += move_km
                break
            temp_x, temp_y = end
            move_km -= remaining_segment_km
            temp_distance += remaining_segment_km
            temp_segment += 1

        remaining_distance = max(0.0, flight.route_length_km - temp_distance)
        if temp_distance < flight.climb_distance_km:
            climb_ratio = temp_distance / max(flight.climb_distance_km, 1e-9)
            temp_altitude = (
                flight.takeoff_altitude_m
                + (flight.cruise_altitude_m - flight.takeoff_altitude_m) * climb_ratio
            )
        elif remaining_distance <= flight.descent_distance_km:
            descent_ratio = remaining_distance / max(flight.descent_distance_km, 1e-9)
            temp_altitude = max(flight.takeoff_altitude_m, flight.cruise_altitude_m * descent_ratio)
        else:
            temp_altitude = flight.cruise_altitude_m

        return temp_x, temp_y, temp_altitude

    def _sample_link_quality(self, flight: Flight) -> None:
        _, measurements = self._best_bs_for_position(
            flight.x_km, flight.y_km, flight.altitude_m
        )
        current_metrics = measurements[flight.current_bs]
        offered_throughput = current_metrics["throughput_mbps"]
        effective_throughput = min(
            offered_throughput, flight.service.demand_mbps
        )
        throughput_gap = max(0.0, flight.service.demand_mbps - offered_throughput)
        flight.throughput_samples.append(effective_throughput)
        flight.throughput_gap_samples.append(throughput_gap)
        flight.sinr_samples.append(current_metrics["sinr_db"])
        if offered_throughput >= flight.service.demand_mbps:
            self.metrics["throughput_demand_met_samples"] += 1
            flight.demand_met_samples += 1
        else:
            self.metrics["throughput_demand_unmet_samples"] += 1
            flight.demand_unmet_samples += 1
        if current_metrics["latency_ms"] > flight.service.latency_budget_ms:
            self.metrics["control_latency_violations"] += 1
            flight.latency_violations += 1

    def collect_flight_rows(self, policy: str, context: Dict[str, object]) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        for flight in self.flights.values():
            mean_throughput = (
                float(np.mean(flight.throughput_samples)) if flight.throughput_samples else 0.0
            )
            mean_throughput_gap = (
                float(np.mean(flight.throughput_gap_samples))
                if flight.throughput_gap_samples
                else 0.0
            )
            demand_sample_total = flight.demand_met_samples + flight.demand_unmet_samples
            demand_satisfied_sample_pct = (
                (flight.demand_met_samples / demand_sample_total) * 100.0
                if demand_sample_total
                else 0.0
            )
            mean_sinr = (
                float(np.mean(flight.sinr_samples)) if flight.sinr_samples else 0.0
            )
            row = {
                **context,
                "policy": policy,
                "flight_id": flight.fid,
                "origin": self.vertiports[flight.origin].name,
                "destination": self.vertiports[flight.destination].name,
                "route_length_km": round(flight.route_length_km, 2),
                "speed_kmh": round(flight.speed_kmh, 2),
                "altitude_m": round(flight.altitude_m, 1),
                "cruise_altitude_m": round(flight.cruise_altitude_m, 1),
                "vertical_phase": flight.vertical_phase,
                "distance_to_destination_km": round(flight.distance_to_destination_km, 3),
                "service": flight.service.name,
                "handover_count": flight.handover_count,
                "radio_handover_successes": flight.radio_handover_successes,
                "radio_handover_failures": flight.radio_handover_failures,
                "service_continuity_successes": flight.service_continuity_successes,
                "service_continuity_failures": flight.service_continuity_failures,
                "ping_pong_events": flight.ping_pong_events,
                "precache_hits": flight.precache_hits,
                "precache_requests": flight.precache_requests,
                "precache_commits": flight.precache_commits,
                "precache_backhaul_mb": round(flight.precache_backhaul_mb, 2),
                "precache_ttl_expiries": flight.precache_ttl_expiries,
                "precache_reclaims": flight.precache_reclaims,
                "reservation_collisions": flight.reservation_collisions,
                "control_slice_exhaustions": flight.control_slice_exhaustions,
                "edge_cache_overflows": flight.edge_cache_overflows,
                "radio_failures_low_throughput": flight.radio_failures_low_throughput,
                "service_failures_radio_only": flight.service_failures_radio_only,
                "service_failures_latency_only": flight.service_failures_latency_only,
                "service_failures_dual": flight.service_failures_dual,
                "latency_violations": flight.latency_violations,
                "mean_throughput_mbps": round(mean_throughput, 2),
                "mean_throughput_gap_mbps": round(mean_throughput_gap, 2),
                "throughput_to_demand_pct": round(
                    (mean_throughput / flight.service.demand_mbps) * 100.0,
                    2,
                ),
                "demand_satisfied_sample_pct": round(demand_satisfied_sample_pct, 2),
                "mean_sinr_db": round(mean_sinr, 2),
                "total_interruption_ms": round(flight.interruption_ms_total, 2),
                "completed": int(not flight.active),
            }
            rows.append(row)
        return rows


def format_summary(summary: Dict[str, float]) -> str:
    ordered_keys = [
        "policy",
        "phase",
        "completed_flights",
        "total_flights",
        "total_handovers",
        "handover_attempts",
        "radio_handover_successes",
        "radio_handover_failures",
        "radio_failures_low_throughput",
        "service_continuity_successes",
        "service_continuity_failures",
        "service_failures_radio_only",
        "service_failures_latency_only",
        "service_failures_dual",
        "ping_pong_events",
        "control_latency_violations",
        "precache_hits",
        "precache_requests",
        "precache_commits",
        "precache_backhaul_mb",
        "precache_ttl_expiries",
        "precache_reclaims",
        "reservation_collisions",
        "control_slice_exhaustions",
        "edge_cache_overflows",
        "peak_active_precache_entries",
        "peak_edge_cache_usage_mb",
        "mean_throughput_mbps",
        "mean_throughput_gap_mbps",
        "demand_satisfied_sample_pct",
        "mean_sinr_db",
        "total_interruption_ms",
    ]
    return "\n".join(f"{key}: {summary[key]}" for key in ordered_keys)


if __name__ == "__main__":
    duration_s = 1800.0
    for policy in ("reactive", "proactive"):
        sim = UAMHandoverSimulation(SimulationConfig(phase="introduction", seed=7))
        generated = sim.spawn_reference_traffic(hours=1.0)
        summary = sim.run(duration_s=duration_s, policy=policy)
        print(f"\n--- {policy.upper()} policy ({generated} flights) ---")
        print(format_summary(summary))
