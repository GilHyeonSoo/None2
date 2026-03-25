from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr
from paths import ANALYSIS_RESULTS_DIR, RAW_RESULTS_DIR

RUN_CSV = RAW_RESULTS_DIR / "simulation_sweep_run_results.csv"
FLIGHT_CSV = RAW_RESULTS_DIR / "simulation_sweep_flight_results.csv"


def _save_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[saved] {path.name} rows={len(df)} columns={list(df.columns)}")


def _pct(numerator: pd.Series | float, denominator: pd.Series | float) -> pd.Series | float:
    if isinstance(denominator, pd.Series):
        return np.where(denominator != 0, (numerator / denominator) * 100.0, 0.0)
    return (numerator / denominator) * 100.0 if denominator else 0.0


def _format_table(df: pd.DataFrame, float_cols: Iterable[str] | None = None) -> str:
    if float_cols:
        formatters = {col: "{:.4f}".format for col in float_cols if col in df.columns}
        return df.to_string(index=False, formatters=formatters)
    return df.to_string(index=False)


def load_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    run_df = pd.read_csv(RUN_CSV)
    flight_df = pd.read_csv(FLIGHT_CSV)

    # Assumption:
    # DataRead.md asks for service_handover_count, but the source CSV stores the
    # same notion as handover_count. We add an explicit alias for analysis.
    flight_df["service_handover_count"] = flight_df["handover_count"]
    run_df["service_success_rate_pct"] = _pct(
        run_df["service_continuity_successes"], run_df["handover_attempts"]
    )
    run_df["run_index"] = (
        run_df.sort_values(["phase", "policy", "run_id"])
        .groupby(["phase", "policy"])
        .cumcount()
        .add(1)
        .sort_index()
    )

    flight_df["zero_interruption"] = (flight_df["total_interruption_ms"] == 0).astype(int)
    flight_df["zero_ping_pong"] = (flight_df["ping_pong_events"] == 0).astype(int)
    flight_df["zero_latency_violations"] = (flight_df["latency_violations"] == 0).astype(int)
    flight_df["complete_success"] = (
        (flight_df["zero_interruption"] == 1)
        & (flight_df["zero_ping_pong"] == 1)
        & (flight_df["zero_latency_violations"] == 1)
    ).astype(int)

    return run_df, flight_df


def analyze_service_continuity(
    run_df: pd.DataFrame,
    flight_df: pd.DataFrame,
) -> pd.DataFrame:
    run_group = (
        run_df.groupby(["policy", "phase"], as_index=False)
        .agg(
            total_flights=("total_flights", "sum"),
            handover_attempts=("handover_attempts", "sum"),
            service_continuity_successes=("service_continuity_successes", "sum"),
            service_continuity_failures=("service_continuity_failures", "sum"),
        )
    )
    run_group["service_success_per_total_flights_pct"] = _pct(
        run_group["service_continuity_successes"],
        run_group["total_flights"],
    )
    run_group["service_success_per_handover_pct"] = _pct(
        run_group["service_continuity_successes"],
        run_group["handover_attempts"],
    )

    flight_group = (
        flight_df.groupby(["policy", "phase"], as_index=False)
        .agg(
            flight_count=("flight_id", "size"),
            flights_with_any_service_success=("service_continuity_successes", lambda s: int((s > 0).sum())),
            flights_with_zero_service_failures=("service_continuity_failures", lambda s: int((s == 0).sum())),
            zero_interruption_flights=("zero_interruption", "sum"),
            zero_ping_pong_flights=("zero_ping_pong", "sum"),
            zero_latency_violation_flights=("zero_latency_violations", "sum"),
            complete_success_flights=("complete_success", "sum"),
        )
    )
    for target, numerator in [
        ("flights_with_any_service_success_pct", "flights_with_any_service_success"),
        ("flights_with_zero_service_failures_pct", "flights_with_zero_service_failures"),
        ("zero_interruption_pct", "zero_interruption_flights"),
        ("zero_ping_pong_pct", "zero_ping_pong_flights"),
        ("zero_latency_violation_pct", "zero_latency_violation_flights"),
        ("complete_success_pct", "complete_success_flights"),
    ]:
        flight_group[target] = _pct(flight_group[numerator], flight_group["flight_count"])

    output = run_group.merge(flight_group, on=["policy", "phase"], how="left")
    output = output[
        [
            "policy",
            "phase",
            "total_flights",
            "handover_attempts",
            "service_continuity_successes",
            "service_continuity_failures",
            "service_success_per_total_flights_pct",
            "service_success_per_handover_pct",
            "flights_with_any_service_success_pct",
            "flights_with_zero_service_failures_pct",
            "zero_interruption_pct",
            "zero_ping_pong_pct",
            "zero_latency_violation_pct",
            "complete_success_pct",
        ]
    ].sort_values(["policy", "phase"])

    print("\n[TASK 1-1] service_continuity_successes / total_flights")
    print(_format_table(output[["policy", "phase", "service_success_per_total_flights_pct", "service_success_per_handover_pct"]], ["service_success_per_total_flights_pct", "service_success_per_handover_pct"]))

    equality_service = bool(
        (
            flight_df["service_handover_count"]
            == flight_df["service_continuity_successes"] + flight_df["service_continuity_failures"]
        ).all()
    )
    print("\n[TASK 1-2] 서비스 연속성 저조 원인 진단")
    print(f"- all_rows(service_handover_count == service_successes + service_failures): {equality_service}")
    print("- interpretation: service_continuity_successes는 비행 단위 binary가 아니라 핸드오버 이벤트 성공 횟수입니다.")
    print("- zero_interruption_pct와 zero_latency_violation_pct가 모든 정책/단계에서 0%이면, 완전 성공 조건은 현재 데이터에서 사실상 성립하지 않습니다.")
    print(_format_table(
        output[
            [
                "policy",
                "phase",
                "flights_with_any_service_success_pct",
                "flights_with_zero_service_failures_pct",
                "zero_interruption_pct",
                "zero_ping_pong_pct",
                "zero_latency_violation_pct",
                "complete_success_pct",
            ]
        ],
        [
            "flights_with_any_service_success_pct",
            "flights_with_zero_service_failures_pct",
            "zero_interruption_pct",
            "zero_ping_pong_pct",
            "zero_latency_violation_pct",
            "complete_success_pct",
        ],
    ))
    return output


def analyze_latency_violations(flight_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []

    descriptive = (
        flight_df.groupby("policy")["latency_violations"]
        .agg(["mean", "median", "std", "min", "max", "count"])
        .reset_index()
    )
    for _, row in descriptive.iterrows():
        for stat in ["mean", "median", "std", "min", "max", "count"]:
            records.append(
                {
                    "analysis_section": "descriptive",
                    "policy": row["policy"],
                    "variable": "latency_violations",
                    "statistic": stat,
                    "value": float(row[stat]),
                    "p_value": np.nan,
                    "effect_size": np.nan,
                    "n": int(row["count"]),
                }
            )

    proactive = flight_df.loc[flight_df["policy"] == "proactive", "latency_violations"]
    reactive = flight_df.loc[flight_df["policy"] == "reactive", "latency_violations"]
    u_stat, p_value = mannwhitneyu(proactive, reactive, alternative="two-sided")
    rank_biserial = (2.0 * u_stat / (len(proactive) * len(reactive))) - 1.0
    records.append(
        {
            "analysis_section": "mann_whitney_u",
            "policy": "proactive_vs_reactive",
            "variable": "latency_violations",
            "statistic": "two_sided_u_test",
            "value": float(u_stat),
            "p_value": float(p_value),
            "effect_size": float(rank_biserial),
            "n": int(len(proactive) + len(reactive)),
        }
    )

    for policy, group in flight_df.groupby("policy"):
        for variable in ["bs_spacing_km", "altitude_m", "speed_kmh", "service_handover_count"]:
            rho, corr_p = spearmanr(group[variable], group["latency_violations"])
            records.append(
                {
                    "analysis_section": "spearman_correlation",
                    "policy": policy,
                    "variable": variable,
                    "statistic": "spearman_rho",
                    "value": float(rho),
                    "p_value": float(corr_p),
                    "effect_size": np.nan,
                    "n": int(len(group)),
                }
            )

    output = pd.DataFrame(records)

    print("\n[TASK 1-2] latency_violations 기술 통계")
    print(_format_table(descriptive, ["mean", "median", "std", "min", "max"]))
    print("\n[TASK 1-2] Mann-Whitney U test")
    print(
        f"u_statistic={u_stat:.4f} p_value={p_value:.8f} "
        f"rank_biserial_effect_size={rank_biserial:.6f}"
    )
    print("note: rank_biserial < 0 이면 proactive의 latency_violations가 더 낮다는 뜻입니다.")

    corr_view = output[output["analysis_section"] == "spearman_correlation"][
        ["policy", "variable", "value", "p_value"]
    ].rename(columns={"value": "spearman_rho"})
    print("\n[TASK 1-2] latency_violations 상관관계")
    print(_format_table(corr_view, ["spearman_rho", "p_value"]))

    return output


def analyze_handover_failures(run_df: pd.DataFrame, flight_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []

    overall = (
        run_df.groupby("policy", as_index=False)
        .agg(
            handover_attempts=("handover_attempts", "sum"),
            radio_handover_failures=("radio_handover_failures", "sum"),
        )
    )
    overall["handover_failure_rate_pct"] = _pct(
        overall["radio_handover_failures"], overall["handover_attempts"]
    )
    for _, row in overall.iterrows():
        records.append(
            {
                "analysis_scope": "overall",
                "policy": row["policy"],
                "phase": np.nan,
                "speed_profile": np.nan,
                "altitude_profile": np.nan,
                "bs_density_profile": np.nan,
                "origin": np.nan,
                "destination": np.nan,
                "run_id": np.nan,
                "flight_id": np.nan,
                "speed_kmh": np.nan,
                "altitude_m": np.nan,
                "service_handover_count": np.nan,
                "handover_attempts": int(row["handover_attempts"]),
                "radio_handover_failures": int(row["radio_handover_failures"]),
                "handover_failure_rate_pct": float(row["handover_failure_rate_pct"]),
            }
        )

    for scope in ["phase", "speed_profile", "altitude_profile", "bs_density_profile"]:
        grouped = (
            run_df.groupby([scope, "policy"], as_index=False)
            .agg(
                handover_attempts=("handover_attempts", "sum"),
                radio_handover_failures=("radio_handover_failures", "sum"),
            )
        )
        grouped["handover_failure_rate_pct"] = _pct(
            grouped["radio_handover_failures"], grouped["handover_attempts"]
        )
        for _, row in grouped.iterrows():
            records.append(
                {
                    "analysis_scope": f"by_{scope}",
                    "policy": row["policy"],
                    "phase": row[scope] if scope == "phase" else np.nan,
                    "speed_profile": row[scope] if scope == "speed_profile" else np.nan,
                    "altitude_profile": row[scope] if scope == "altitude_profile" else np.nan,
                    "bs_density_profile": row[scope] if scope == "bs_density_profile" else np.nan,
                    "origin": np.nan,
                    "destination": np.nan,
                    "run_id": np.nan,
                    "flight_id": np.nan,
                    "speed_kmh": np.nan,
                    "altitude_m": np.nan,
                    "service_handover_count": np.nan,
                    "handover_attempts": int(row["handover_attempts"]),
                    "radio_handover_failures": int(row["radio_handover_failures"]),
                    "handover_failure_rate_pct": float(row["handover_failure_rate_pct"]),
                }
            )

    proactive_top10 = flight_df.loc[flight_df["policy"] == "proactive"].copy()
    proactive_top10["handover_failure_rate"] = np.where(
        proactive_top10["service_handover_count"] > 0,
        proactive_top10["radio_handover_failures"] / proactive_top10["service_handover_count"],
        0.0,
    )
    proactive_top10 = proactive_top10.sort_values(
        ["handover_failure_rate", "radio_handover_failures", "service_handover_count"],
        ascending=[False, False, False],
    ).head(10)
    for _, row in proactive_top10.iterrows():
        records.append(
            {
                "analysis_scope": "proactive_top10_flights",
                "policy": row["policy"],
                "phase": row["phase"],
                "speed_profile": row["speed_profile"],
                "altitude_profile": row["altitude_profile"],
                "bs_density_profile": row["bs_density_profile"],
                "origin": row["origin"],
                "destination": row["destination"],
                "run_id": int(row["run_id"]),
                "flight_id": int(row["flight_id"]),
                "speed_kmh": float(row["speed_kmh"]),
                "altitude_m": float(row["altitude_m"]),
                "service_handover_count": int(row["service_handover_count"]),
                "handover_attempts": int(row["service_handover_count"]),
                "radio_handover_failures": int(row["radio_handover_failures"]),
                "handover_failure_rate_pct": float(row["handover_failure_rate"] * 100.0),
            }
        )

    output = pd.DataFrame(records)

    print("\n[TASK 1-3] 전체 핸드오버 실패율")
    print(_format_table(overall[["policy", "handover_attempts", "radio_handover_failures", "handover_failure_rate_pct"]], ["handover_failure_rate_pct"]))
    print("\n[TASK 1-3] proactive 실패율 상위 10개 비행")
    print(
        _format_table(
            proactive_top10[
                [
                    "run_id",
                    "flight_id",
                    "origin",
                    "destination",
                    "speed_kmh",
                    "altitude_m",
                    "bs_density_profile",
                    "service_handover_count",
                    "radio_handover_failures",
                    "handover_failure_rate",
                ]
            ],
            ["speed_kmh", "altitude_m", "handover_failure_rate"],
        )
    )

    return output


def build_additional_condition_sweep_summary(flight_df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        flight_df.groupby(
            ["phase", "speed_profile", "altitude_profile", "bs_density_profile", "policy"],
            as_index=False,
        )
        .agg(
            mean_handovers=("handover_count", "mean"),
            mean_ping_pong=("ping_pong_events", "mean"),
            mean_interruption_ms=("total_interruption_ms", "mean"),
            mean_latency_violations=("latency_violations", "mean"),
            service_continuity_successes=("service_continuity_successes", "sum"),
            service_handover_count=("service_handover_count", "sum"),
            mean_throughput_mbps=("mean_throughput_mbps", "mean"),
            mean_sinr_db=("mean_sinr_db", "mean"),
            sample_size=("flight_id", "size"),
        )
    )
    grouped["mean_interruption_s"] = grouped["mean_interruption_ms"] / 1000.0
    grouped["service_success_rate_pct"] = _pct(
        grouped["service_continuity_successes"],
        grouped["service_handover_count"],
    )
    output = grouped[
        [
            "phase",
            "speed_profile",
            "altitude_profile",
            "bs_density_profile",
            "policy",
            "mean_handovers",
            "mean_ping_pong",
            "mean_interruption_s",
            "mean_latency_violations",
            "service_success_rate_pct",
            "mean_throughput_mbps",
            "mean_sinr_db",
            "sample_size",
        ]
    ].sort_values(["phase", "speed_profile", "altitude_profile", "bs_density_profile", "policy"])
    return output


def build_additional_phase_progression(run_df: pd.DataFrame) -> pd.DataFrame:
    output = run_df[
        [
            "phase",
            "policy",
            "run_index",
            "total_interruption_ms",
            "total_handovers",
            "ping_pong_events",
            "service_success_rate_pct",
        ]
    ].sort_values(["phase", "policy", "run_index"])
    return output


def build_additional_route_performance(flight_df: pd.DataFrame) -> pd.DataFrame:
    output = (
        flight_df.groupby(["origin", "destination", "policy"], as_index=False)
        .agg(
            mean_handovers=("handover_count", "mean"),
            mean_interruption_ms=("total_interruption_ms", "mean"),
            mean_latency_violations=("latency_violations", "mean"),
            mean_throughput_mbps=("mean_throughput_mbps", "mean"),
            mean_sinr_db=("mean_sinr_db", "mean"),
            flight_count=("flight_id", "size"),
        )
        .sort_values(["origin", "destination", "policy"])
    )
    return output


def build_additional_failure_analysis(flight_df: pd.DataFrame) -> pd.DataFrame:
    original_columns = [
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

    output = flight_df.loc[
        (flight_df["radio_handover_failures"] > 0)
        | (flight_df["service_continuity_failures"] > 0)
        | (flight_df["total_interruption_ms"] > 5000)
    , original_columns + ["service_handover_count"]].copy()
    output["handover_failure_rate"] = np.where(
        output["service_handover_count"] > 0,
        output["radio_handover_failures"] / output["service_handover_count"],
        0.0,
    )
    output["is_high_speed"] = (output["speed_kmh"] > 180.0).astype(int)
    output["is_high_altitude"] = (output["altitude_m"] >= 600.0).astype(int)
    output["is_dense"] = (output["bs_density_profile"] == "dense").astype(int)
    return output.sort_values(
        ["handover_failure_rate", "radio_handover_failures", "total_interruption_ms"],
        ascending=[False, False, False],
    )


def main() -> None:
    if not RUN_CSV.exists() or not FLIGHT_CSV.exists():
        raise FileNotFoundError("simulation_sweep_run_results.csv and simulation_sweep_flight_results.csv are required.")

    run_df, flight_df = load_frames()

    service_continuity_df = analyze_service_continuity(run_df, flight_df)
    latency_df = analyze_latency_violations(flight_df)
    handover_failure_df = analyze_handover_failures(run_df, flight_df)

    additional_condition_df = build_additional_condition_sweep_summary(flight_df)
    additional_phase_df = build_additional_phase_progression(run_df)
    additional_route_df = build_additional_route_performance(flight_df)
    additional_failure_df = build_additional_failure_analysis(flight_df)

    ANALYSIS_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _save_csv(service_continuity_df, ANALYSIS_RESULTS_DIR / "analysis_service_continuity_breakdown.csv")
    _save_csv(latency_df, ANALYSIS_RESULTS_DIR / "analysis_latency_violation_deep.csv")
    _save_csv(handover_failure_df, ANALYSIS_RESULTS_DIR / "analysis_handover_failure_rate.csv")
    _save_csv(additional_condition_df, ANALYSIS_RESULTS_DIR / "additional_condition_sweep_summary.csv")
    _save_csv(additional_phase_df, ANALYSIS_RESULTS_DIR / "additional_phase_progression.csv")
    _save_csv(additional_route_df, ANALYSIS_RESULTS_DIR / "additional_route_performance.csv")
    _save_csv(additional_failure_df, ANALYSIS_RESULTS_DIR / "additional_failure_analysis.csv")

    print("\n[TASK 2] 추가 추출 파일 요약")
    for filename in [
        "additional_condition_sweep_summary.csv",
        "additional_phase_progression.csv",
        "additional_route_performance.csv",
        "additional_failure_analysis.csv",
    ]:
        path = BASE_DIR / filename
        df = pd.read_csv(path)
        print(f"- {filename}: rows={len(df)} columns={list(df.columns)}")

    print("\n=============================================")
    print("[추가 시뮬레이션 필요 항목]")
    print("없음: 현재 요청된 분석은 제공된 CSV 두 개만으로 모두 수행 가능합니다.")
    print("=============================================")


if __name__ == "__main__":
    main()
