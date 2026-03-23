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
    proactive_trigger_window_s: float = 8.0
    precache_lead_time_s: float = 1.0
    ping_pong_window_s: float = 15.0
    bs_spacing_km: float = 4.0
    bs_height_m: float = 30.0
    bs_capacity_mbps: float = 200.0
    reserved_control_slice_mbps: float = 5.0
    hub_route_bias: float = 0.7
    shadowing_tile_km: float = 0.5

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
    throughput_samples: List[float] = field(default_factory=list)
    sinr_samples: List[float] = field(default_factory=list)

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
            "service_continuity_successes": 0,
            "service_continuity_failures": 0,
            "ping_pong_events": 0,
            "control_latency_violations": 0,
            "precache_hits": 0,
        }
        self._measurement_cache: Dict[Tuple[float, float, float], Tuple[int, Dict[int, Dict[str, float]]]] = {}
        self._shadowing_cache: Dict[Tuple[int, int, int], float] = {}

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

        flight = Flight(
            fid=self._next_flight_id,
            origin=origin,
            destination=destination,
            waypoints=waypoints,
            route_length_km=route_length_km,
            speed_kmh=speed_kmh,
            altitude_m=altitude_m,
            service=SERVICE_PROFILES[service_name],
            x_km=waypoints[0][0],
            y_km=waypoints[0][1],
        )

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
        if policy not in {"reactive", "proactive"}:
            raise ValueError(f"Unsupported policy: {policy}")

        self.current_time_s += self.cfg.time_step_s
        self._refresh_bs_loads()
        self._measurement_cache.clear()

        for flight in self.flights.values():
            if not flight.active:
                continue

            self._advance_flight(flight, self.cfg.time_step_s)
            if not flight.active:
                self._detach_flight_from_bs(flight)
                continue

            if policy == "reactive":
                self._reactive_handover(flight)
            else:
                self._proactive_handover(flight)

            self._sample_link_quality(flight)

    def run(self, duration_s: float, policy: str = "reactive") -> Dict[str, float]:
        steps = int(duration_s / self.cfg.time_step_s)
        for _ in range(steps):
            self.step(policy=policy)
        return self.summarize(policy=policy)

    def summarize(self, policy: str) -> Dict[str, float]:
        throughput_samples = []
        sinr_samples = []
        interruption_ms = 0.0
        completed = 0
        total_handovers = 0

        for flight in self.flights.values():
            throughput_samples.extend(flight.throughput_samples)
            sinr_samples.extend(flight.sinr_samples)
            interruption_ms += flight.interruption_ms_total
            total_handovers += flight.handover_count
            if not flight.active:
                completed += 1

        mean_throughput = (
            float(np.mean(throughput_samples)) if throughput_samples else 0.0
        )
        mean_sinr = float(np.mean(sinr_samples)) if sinr_samples else 0.0

        return {
            "policy": policy,
            "phase": self.cfg.phase,
            "completed_flights": completed,
            "total_flights": len(self.flights),
            "total_handovers": total_handovers,
            "handover_attempts": self.metrics["handover_attempts"],
            "radio_handover_successes": self.metrics["radio_handover_successes"],
            "radio_handover_failures": self.metrics["radio_handover_failures"],
            "service_continuity_successes": self.metrics["service_continuity_successes"],
            "service_continuity_failures": self.metrics["service_continuity_failures"],
            "ping_pong_events": self.metrics["ping_pong_events"],
            "control_latency_violations": self.metrics["control_latency_violations"],
            "precache_hits": self.metrics["precache_hits"],
            "mean_throughput_mbps": round(mean_throughput, 2),
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
                move_km = 0.0
            else:
                flight.x_km, flight.y_km = end
                move_km -= remaining_segment_km
                flight.segment_index += 1
                if flight.segment_index >= len(flight.waypoints) - 1:
                    flight.active = False

    def _refresh_bs_loads(self) -> None:
        for bs in self.base_stations.values():
            bs.connected_flights.clear()
        for flight in self.flights.values():
            if flight.active and flight.current_bs is not None:
                self.base_stations[flight.current_bs].connected_flights.add(flight.fid)

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

        # Modeling assumption:
        # Aerial UEs are penalized because terrestrial BSs are downtilted.
        downtilt_penalty_db = 6.0 if altitude_m >= 450.0 else 4.0
        tile = self.cfg.shadowing_tile_km
        tile_x = int(x_km / tile)
        tile_y = int(y_km / tile)
        shadow_key = (bs.bid, tile_x, tile_y)
        if shadow_key not in self._shadowing_cache:
            mixed_seed = (
                self.cfg.seed * 1000003
                + bs.bid * 9176
                + tile_x * 131071
                + tile_y * 524287
            ) & 0xFFFFFFFF
            self._shadowing_cache[shadow_key] = random.Random(mixed_seed).gauss(0.0, 2.0)
        shadowing_db = self._shadowing_cache[shadow_key]
        return self.cfg.tx_power_dbm - fspl_db - downtilt_penalty_db + shadowing_db

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
            future_pos[0], future_pos[1], flight.altitude_m
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
            if flight.reserved_target_bs is None:
                flight.reserved_target_bs = best_future_bs
                flight.precache_ready_at_s = (
                    self.current_time_s + self.cfg.precache_lead_time_s
                )
            elif (
                flight.reserved_target_bs != best_future_bs
                and self.current_time_s >= flight.precache_ready_at_s
            ):
                flight.reserved_target_bs = best_future_bs
                flight.precache_ready_at_s = (
                    self.current_time_s + self.cfg.precache_lead_time_s
                )

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

        latency_budget_ms = flight.service.latency_budget_ms
        radio_success = (
            target_metrics["throughput_mbps"] >= flight.service.handover_floor_mbps
        )
        service_success = radio_success and interruption_ms <= latency_budget_ms

        if radio_success:
            self.metrics["radio_handover_successes"] += 1
            flight.radio_handover_successes += 1
        else:
            self.metrics["radio_handover_failures"] += 1
            flight.radio_handover_failures += 1

        if service_success:
            self.metrics["service_continuity_successes"] += 1
            flight.service_continuity_successes += 1
        else:
            self.metrics["service_continuity_failures"] += 1
            flight.service_continuity_failures += 1
            self.metrics["control_latency_violations"] += 1
            flight.latency_violations += 1

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

    def _predict_future_position(
        self,
        flight: Flight,
        horizon_s: float,
    ) -> Tuple[float, float]:
        temp_segment = flight.segment_index
        temp_x = flight.x_km
        temp_y = flight.y_km
        move_km = flight.speed_kmh * (horizon_s / 3600.0)

        while move_km > 0 and temp_segment < len(flight.waypoints) - 1:
            start = (temp_x, temp_y)
            end = flight.waypoints[temp_segment + 1]
            remaining_segment_km = _distance_km(start, end)
            if move_km < remaining_segment_km:
                ratio = move_km / max(remaining_segment_km, 1e-9)
                temp_x = start[0] + (end[0] - start[0]) * ratio
                temp_y = start[1] + (end[1] - start[1]) * ratio
                break
            temp_x, temp_y = end
            move_km -= remaining_segment_km
            temp_segment += 1

        return temp_x, temp_y

    def _sample_link_quality(self, flight: Flight) -> None:
        _, measurements = self._best_bs_for_position(
            flight.x_km, flight.y_km, flight.altitude_m
        )
        current_metrics = measurements[flight.current_bs]
        effective_throughput = min(
            current_metrics["throughput_mbps"], flight.service.demand_mbps
        )
        flight.throughput_samples.append(effective_throughput)
        flight.sinr_samples.append(current_metrics["sinr_db"])
        if current_metrics["latency_ms"] > flight.service.latency_budget_ms:
            self.metrics["control_latency_violations"] += 1
            flight.latency_violations += 1

    def collect_flight_rows(self, policy: str, context: Dict[str, object]) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        for flight in self.flights.values():
            mean_throughput = (
                float(np.mean(flight.throughput_samples)) if flight.throughput_samples else 0.0
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
                "service": flight.service.name,
                "handover_count": flight.handover_count,
                "radio_handover_successes": flight.radio_handover_successes,
                "radio_handover_failures": flight.radio_handover_failures,
                "service_continuity_successes": flight.service_continuity_successes,
                "service_continuity_failures": flight.service_continuity_failures,
                "ping_pong_events": flight.ping_pong_events,
                "precache_hits": flight.precache_hits,
                "latency_violations": flight.latency_violations,
                "mean_throughput_mbps": round(mean_throughput, 2),
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
        "service_continuity_successes",
        "service_continuity_failures",
        "ping_pong_events",
        "control_latency_violations",
        "precache_hits",
        "mean_throughput_mbps",
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
