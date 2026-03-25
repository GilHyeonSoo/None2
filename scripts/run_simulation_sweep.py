from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Sequence

from simulation_env import SimulationConfig, UAMHandoverSimulation
from paths import RAW_RESULTS_DIR


SPEED_PROFILES = {
    "low": (120.0, 140.0, 160.0),
    "medium": (150.0, 180.0, 210.0),
    "high": (180.0, 215.0, 250.0),
}

ALTITUDE_PROFILES = {
    "low": (300.0,),
    "mid": (450.0,),
    "high": (600.0,),
}

BS_DENSITY_PROFILES = {
    "sparse": 5.5,
    "dense": 3.0,
}

PHASES = ("introduction", "growth", "maturity")
POLICIES = ("reactive", "a3_ttt", "proactive")
DEFAULT_SEEDS = (7, 11)
DEFAULT_RUN_DURATION_S = 1800.0
DEFAULT_TRAFFIC_HOURS = 1.0


def _format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _parse_seed_spec(seed_spec: str) -> tuple[int, ...]:
    values: list[int] = []
    for raw_part in seed_spec.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text.strip())
            end = int(end_text.strip())
            if end < start:
                raise ValueError(f"Invalid seed range: {part}")
            values.extend(range(start, end + 1))
        else:
            values.append(int(part))
    if not values:
        raise ValueError("At least one seed must be provided.")
    return tuple(sorted(dict.fromkeys(values)))


def _parse_choice_list(raw_value: str, allowed: Sequence[str], label: str) -> tuple[str, ...]:
    if raw_value.strip().lower() == "all":
        return tuple(allowed)
    selected = tuple(part.strip() for part in raw_value.split(",") if part.strip())
    if not selected:
        raise ValueError(f"At least one {label} must be selected.")
    invalid = [value for value in selected if value not in allowed]
    if invalid:
        raise ValueError(f"Unsupported {label}: {invalid}. Allowed: {list(allowed)}")
    return selected


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the UAM handover sweep with configurable seeds and condition subsets. "
            "This script only prepares outputs; the user is expected to choose the final "
            "experiment scale and execute it directly."
        )
    )
    parser.add_argument(
        "--seed-spec",
        default="7,11",
        help="Comma-separated seeds and/or inclusive ranges, for example '7,11' or '1-30'.",
    )
    parser.add_argument(
        "--phases",
        default="all",
        help="Comma-separated phase names or 'all'. Allowed: introduction,growth,maturity",
    )
    parser.add_argument(
        "--speed-profiles",
        default="all",
        help="Comma-separated speed profiles or 'all'. Allowed: low,medium,high",
    )
    parser.add_argument(
        "--altitude-profiles",
        default="all",
        help="Comma-separated altitude profiles or 'all'. Allowed: low,mid,high",
    )
    parser.add_argument(
        "--bs-density-profiles",
        default="all",
        help="Comma-separated BS density profiles or 'all'. Allowed: sparse,dense",
    )
    parser.add_argument(
        "--policies",
        default="all",
        help="Comma-separated policies or 'all'. Allowed: reactive,a3_ttt,proactive",
    )
    parser.add_argument(
        "--run-duration-s",
        type=float,
        default=DEFAULT_RUN_DURATION_S,
        help=f"Simulation time per run in seconds. Default: {DEFAULT_RUN_DURATION_S}",
    )
    parser.add_argument(
        "--traffic-hours",
        type=float,
        default=DEFAULT_TRAFFIC_HOURS,
        help=f"Reference traffic generation horizon in hours. Default: {DEFAULT_TRAFFIC_HOURS}",
    )
    parser.add_argument(
        "--output-prefix",
        default="simulation_sweep",
        help=(
            "Prefix for generated files under results/raw. "
            "Creates '<prefix>_run_results.csv', '<prefix>_flight_results.csv', and '<prefix>_manifest.json'."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved sweep configuration and exit without running the simulation.",
    )
    return parser


def _resolve_outputs(output_prefix: str) -> tuple[Path, Path, Path]:
    RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_prefix = output_prefix.strip()
    if not safe_prefix:
        raise ValueError("output_prefix must not be empty.")
    return (
        RAW_RESULTS_DIR / f"{safe_prefix}_run_results.csv",
        RAW_RESULTS_DIR / f"{safe_prefix}_flight_results.csv",
        RAW_RESULTS_DIR / f"{safe_prefix}_manifest.json",
    )


def _write_manifest(
    manifest_path: Path,
    seeds: tuple[int, ...],
    phases: tuple[str, ...],
    speed_profiles: tuple[str, ...],
    altitude_profiles: tuple[str, ...],
    bs_density_profiles: tuple[str, ...],
    policies: tuple[str, ...],
    run_duration_s: float,
    traffic_hours: float,
    run_output: Path,
    flight_output: Path,
    total_runs: int,
) -> None:
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": str(Path(__file__).resolve()),
        "seed_spec": list(seeds),
        "phase_spec": list(phases),
        "speed_profile_spec": list(speed_profiles),
        "altitude_profile_spec": list(altitude_profiles),
        "bs_density_profile_spec": list(bs_density_profiles),
        "policy_spec": list(policies),
        "run_duration_s": run_duration_s,
        "traffic_hours": traffic_hours,
        "total_runs": total_runs,
        "run_output_csv": str(run_output.resolve()),
        "flight_output_csv": str(flight_output.resolve()),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[MANIFEST] {manifest_path.resolve()}", flush=True)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    seeds = _parse_seed_spec(args.seed_spec)
    phases = _parse_choice_list(args.phases, PHASES, "phase")
    speed_profiles = _parse_choice_list(args.speed_profiles, tuple(SPEED_PROFILES.keys()), "speed profile")
    altitude_profiles = _parse_choice_list(
        args.altitude_profiles,
        tuple(ALTITUDE_PROFILES.keys()),
        "altitude profile",
    )
    bs_density_profiles = _parse_choice_list(
        args.bs_density_profiles,
        tuple(BS_DENSITY_PROFILES.keys()),
        "BS density profile",
    )
    policies = _parse_choice_list(args.policies, POLICIES, "policy")
    run_duration_s = float(args.run_duration_s)
    traffic_hours = float(args.traffic_hours)

    run_output, flight_output, manifest_output = _resolve_outputs(args.output_prefix)

    run_rows = []
    flight_rows = []
    run_id = 0
    total_runs = (
        len(seeds)
        * len(phases)
        * len(speed_profiles)
        * len(altitude_profiles)
        * len(bs_density_profiles)
        * len(policies)
    )

    if args.dry_run:
        print("[DRY RUN] Resolved sweep configuration", flush=True)
        print(f"  seeds={list(seeds)}", flush=True)
        print(f"  phases={list(phases)}", flush=True)
        print(f"  speed_profiles={list(speed_profiles)}", flush=True)
        print(f"  altitude_profiles={list(altitude_profiles)}", flush=True)
        print(f"  bs_density_profiles={list(bs_density_profiles)}", flush=True)
        print(f"  policies={list(policies)}", flush=True)
        print(f"  run_duration_s={run_duration_s}", flush=True)
        print(f"  traffic_hours={traffic_hours}", flush=True)
        print(f"  total_runs={total_runs}", flush=True)
        print(f"  run_output={run_output.resolve()}", flush=True)
        print(f"  flight_output={flight_output.resolve()}", flush=True)
        print(f"  manifest_output={manifest_output.resolve()}", flush=True)
        return

    completed_runs = 0
    sweep_started_at = time.perf_counter()

    print(
        "[SWEEP] "
        f"starting total_runs={total_runs} "
        f"seeds={len(seeds)} "
        f"seed_values={list(seeds)} "
        f"run_duration_s={run_duration_s} "
        f"traffic_hours={traffic_hours} "
        f"output_prefix={args.output_prefix}",
        flush=True,
    )

    for seed in seeds:
        for phase in phases:
            for speed_name in speed_profiles:
                speed_range = SPEED_PROFILES[speed_name]
                for altitude_name in altitude_profiles:
                    altitude_bands = ALTITUDE_PROFILES[altitude_name]
                    for density_name in bs_density_profiles:
                        spacing_km = BS_DENSITY_PROFILES[density_name]
                        for policy in policies:
                            run_started_at = time.perf_counter()
                            progress_index = completed_runs + 1
                            progress_pct = (progress_index / total_runs) * 100.0
                            print(
                                "[START] "
                                f"{progress_index}/{total_runs} "
                                f"({progress_pct:5.1f}%) "
                                f"seed={seed} phase={phase} "
                                f"speed={speed_name} altitude={altitude_name} "
                                f"bs_density={density_name} policy={policy}",
                                flush=True,
                            )

                            cfg = SimulationConfig(
                                phase=phase,
                                seed=seed,
                                speed_range_kmh=speed_range,
                                altitude_bands_m=altitude_bands,
                                bs_spacing_km=spacing_km,
                            )
                            sim = UAMHandoverSimulation(cfg)
                            generated = sim.spawn_reference_traffic(hours=traffic_hours)
                            summary = sim.run(duration_s=run_duration_s, policy=policy)

                            context = {
                                "run_id": run_id,
                                "seed": seed,
                                "phase": phase,
                                "speed_profile": speed_name,
                                "altitude_profile": altitude_name,
                                "bs_density_profile": density_name,
                                "bs_spacing_km": spacing_km,
                                "generated_flights": generated,
                                "run_duration_s": run_duration_s,
                            }
                            run_rows.append({**context, **summary})
                            flight_rows.extend(sim.collect_flight_rows(policy=policy, context=context))

                            completed_runs += 1
                            run_elapsed = time.perf_counter() - run_started_at
                            total_elapsed = time.perf_counter() - sweep_started_at
                            average_per_run = total_elapsed / completed_runs
                            remaining_runs = total_runs - completed_runs
                            eta_seconds = average_per_run * remaining_runs
                            print(
                                "[DONE ] "
                                f"{completed_runs}/{total_runs} "
                                f"elapsed={_format_duration(run_elapsed)} "
                                f"total_elapsed={_format_duration(total_elapsed)} "
                                f"eta={_format_duration(eta_seconds)} "
                                f"generated_flights={generated} "
                                f"completed_flights={summary['completed_flights']} "
                                f"handovers={summary['total_handovers']} "
                                f"radio_success={summary['radio_handover_successes']} "
                                f"service_success={summary['service_continuity_successes']}",
                                flush=True,
                            )
                            run_id += 1

    run_fieldnames = [
        "run_id",
        "seed",
        "phase",
        "speed_profile",
        "altitude_profile",
        "bs_density_profile",
        "bs_spacing_km",
        "generated_flights",
        "run_duration_s",
        "policy",
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

    flight_fieldnames = [
        "run_id",
        "seed",
        "phase",
        "speed_profile",
        "altitude_profile",
        "bs_density_profile",
        "bs_spacing_km",
        "generated_flights",
        "run_duration_s",
        "policy",
        "flight_id",
        "origin",
        "destination",
        "route_length_km",
        "speed_kmh",
        "altitude_m",
        "cruise_altitude_m",
        "vertical_phase",
        "distance_to_destination_km",
        "service",
        "handover_count",
        "radio_handover_successes",
        "radio_handover_failures",
        "service_continuity_successes",
        "service_continuity_failures",
        "ping_pong_events",
        "precache_hits",
        "precache_requests",
        "precache_commits",
        "precache_backhaul_mb",
        "precache_ttl_expiries",
        "precache_reclaims",
        "reservation_collisions",
        "control_slice_exhaustions",
        "edge_cache_overflows",
        "radio_failures_low_throughput",
        "service_failures_radio_only",
        "service_failures_latency_only",
        "service_failures_dual",
        "latency_violations",
        "mean_throughput_mbps",
        "mean_throughput_gap_mbps",
        "throughput_to_demand_pct",
        "demand_satisfied_sample_pct",
        "mean_sinr_db",
        "total_interruption_ms",
        "completed",
    ]

    with run_output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=run_fieldnames)
        writer.writeheader()
        writer.writerows(run_rows)

    with flight_output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=flight_fieldnames)
        writer.writeheader()
        writer.writerows(flight_rows)

    _write_manifest(
        manifest_output,
        seeds=seeds,
        phases=phases,
        speed_profiles=speed_profiles,
        altitude_profiles=altitude_profiles,
        bs_density_profiles=bs_density_profiles,
        policies=policies,
        run_duration_s=run_duration_s,
        traffic_hours=traffic_hours,
        run_output=run_output,
        flight_output=flight_output,
        total_runs=total_runs,
    )

    total_elapsed = time.perf_counter() - sweep_started_at
    print(
        "[SAVE ] "
        f"run_csv={run_output.resolve()} "
        f"flight_csv={flight_output.resolve()} "
        f"total_elapsed={_format_duration(total_elapsed)}",
        flush=True,
    )
    print(run_output.resolve())
    print(flight_output.resolve())
    print(manifest_output.resolve())
    print(f"run_rows={len(run_rows)} flight_rows={len(flight_rows)}")


if __name__ == "__main__":
    main()
