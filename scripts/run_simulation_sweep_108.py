import csv
from pathlib import Path

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
POLICIES = ("reactive", "proactive")
SEEDS = (7,)
RUN_DURATION_S = 1800.0
TRAFFIC_HOURS = 1.0


def main() -> None:
    run_rows = []
    flight_rows = []
    run_id = 0

    for seed in SEEDS:
        for phase in PHASES:
            for speed_name, speed_range in SPEED_PROFILES.items():
                for altitude_name, altitude_bands in ALTITUDE_PROFILES.items():
                    for density_name, spacing_km in BS_DENSITY_PROFILES.items():
                        for policy in POLICIES:
                            cfg = SimulationConfig(
                                phase=phase,
                                seed=seed,
                                speed_range_kmh=speed_range,
                                altitude_bands_m=altitude_bands,
                                bs_spacing_km=spacing_km,
                            )
                            sim = UAMHandoverSimulation(cfg)
                            generated = sim.spawn_reference_traffic(hours=TRAFFIC_HOURS)
                            summary = sim.run(duration_s=RUN_DURATION_S, policy=policy)
                            context = {
                                "run_id": run_id,
                                "seed": seed,
                                "phase": phase,
                                "speed_profile": speed_name,
                                "altitude_profile": altitude_name,
                                "bs_density_profile": density_name,
                                "bs_spacing_km": spacing_km,
                                "generated_flights": generated,
                                "run_duration_s": RUN_DURATION_S,
                            }
                            run_rows.append({**context, **summary})
                            flight_rows.extend(
                                sim.collect_flight_rows(policy=policy, context=context)
                            )
                            run_id += 1

    RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_output = RAW_RESULTS_DIR / "simulation_sweep_run_results.csv"
    flight_output = RAW_RESULTS_DIR / "simulation_sweep_flight_results.csv"

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
        "service_continuity_successes",
        "service_continuity_failures",
        "ping_pong_events",
        "control_latency_violations",
        "precache_hits",
        "mean_throughput_mbps",
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
        "service",
        "handover_count",
        "radio_handover_successes",
        "radio_handover_failures",
        "service_continuity_successes",
        "service_continuity_failures",
        "ping_pong_events",
        "precache_hits",
        "latency_violations",
        "mean_throughput_mbps",
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

    print(run_output.resolve())
    print(flight_output.resolve())
    print(f"run_rows={len(run_rows)} flight_rows={len(flight_rows)}")


if __name__ == "__main__":
    main()
