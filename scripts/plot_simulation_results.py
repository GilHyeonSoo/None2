from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from paths import EXPLORATORY_FIGURES_DIR, RAW_RESULTS_DIR


RUN_CSV = RAW_RESULTS_DIR / "simulation_sweep_run_results.csv"
FLIGHT_CSV = RAW_RESULTS_DIR / "simulation_sweep_flight_results.csv"
OUTPUT_DIR = EXPLORATORY_FIGURES_DIR


def _prepare_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    run_df = pd.read_csv(RUN_CSV)
    flight_df = pd.read_csv(FLIGHT_CSV)

    run_df["service_success_rate_pct"] = (
        run_df["service_continuity_successes"]
        .div(run_df["handover_attempts"].clip(lower=1))
        .mul(100.0)
    )
    run_df["radio_success_rate_pct"] = (
        run_df["radio_handover_successes"]
        .div(run_df["handover_attempts"].clip(lower=1))
        .mul(100.0)
    )
    run_df["ping_pong_rate_pct"] = (
        run_df["ping_pong_events"]
        .div(run_df["handover_attempts"].clip(lower=1))
        .mul(100.0)
    )
    run_df["total_interruption_s"] = run_df["total_interruption_ms"] / 1000.0

    flight_df["service_success_rate_pct"] = (
        flight_df["service_continuity_successes"]
        .div((flight_df["service_continuity_successes"] + flight_df["service_continuity_failures"]).clip(lower=1))
        .mul(100.0)
    )
    flight_df["total_interruption_s"] = flight_df["total_interruption_ms"] / 1000.0

    phase_order = ["introduction", "growth", "maturity"]
    speed_order = ["low", "medium", "high"]
    altitude_order = ["low", "mid", "high"]
    policy_order = ["reactive", "proactive"]

    for df in (run_df, flight_df):
        if "phase" in df:
            df["phase"] = pd.Categorical(df["phase"], categories=phase_order, ordered=True)
        if "speed_profile" in df:
            df["speed_profile"] = pd.Categorical(
                df["speed_profile"], categories=speed_order, ordered=True
            )
        if "altitude_profile" in df:
            df["altitude_profile"] = pd.Categorical(
                df["altitude_profile"], categories=altitude_order, ordered=True
            )
        if "policy" in df:
            df["policy"] = pd.Categorical(
                df["policy"], categories=policy_order, ordered=True
            )

    return run_df, flight_df


def _save(fig: plt.Figure, filename: str) -> None:
    path = OUTPUT_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(path)


def plot_policy_overview(run_df: pd.DataFrame) -> None:
    summary = (
        run_df.groupby("policy", observed=True)[
            [
                "total_handovers",
                "ping_pong_events",
                "total_interruption_s",
                "service_success_rate_pct",
            ]
        ]
        .mean()
        .reset_index()
    )

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    metrics = [
        ("total_handovers", "Mean Handovers"),
        ("ping_pong_events", "Mean Ping-Pong Events"),
        ("total_interruption_s", "Mean Interruption (s)"),
        ("service_success_rate_pct", "Service Continuity Success Rate (%)"),
    ]

    for ax, (column, title) in zip(axes.flat, metrics):
        sns.barplot(data=summary, x="policy", y=column, hue="policy", palette="Set2", ax=ax, legend=False)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")
        for container in ax.containers:
            labels = [
                f"{value.get_height():.1f}" if value.get_height() < 100 else f"{value.get_height():.0f}"
                for value in container
            ]
            ax.bar_label(container, labels=labels, padding=3, fontsize=9)

    fig.suptitle("Overall Policy Comparison", fontsize=14, y=1.02)
    _save(fig, "01_policy_overview.png")


def plot_phase_comparison(run_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    metrics = [
        ("total_handovers", "Mean Handovers by Phase"),
        ("ping_pong_events", "Mean Ping-Pong Events by Phase"),
        ("total_interruption_s", "Mean Interruption (s) by Phase"),
        ("service_success_rate_pct", "Service Continuity Success Rate (%) by Phase"),
    ]

    for ax, (column, title) in zip(axes.flat, metrics):
        sns.barplot(
            data=run_df,
            x="phase",
            y=column,
            hue="policy",
            palette="Set2",
            estimator="mean",
            errorbar=None,
            ax=ax,
        )
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.legend(title="")

    fig.suptitle("Phase-Level Comparison", fontsize=14, y=1.02)
    _save(fig, "02_phase_comparison.png")


def plot_condition_gain_heatmaps(run_df: pd.DataFrame) -> None:
    grouped = (
        run_df.groupby(
            ["speed_profile", "altitude_profile", "policy"], observed=True
        )[
            ["total_interruption_s", "ping_pong_events", "service_success_rate_pct"]
        ]
        .mean()
        .reset_index()
    )

    reactive = grouped[grouped["policy"] == "reactive"].drop(columns="policy")
    proactive = grouped[grouped["policy"] == "proactive"].drop(columns="policy")
    merged = reactive.merge(
        proactive,
        on=["speed_profile", "altitude_profile"],
        suffixes=("_reactive", "_proactive"),
    )

    merged["interruption_reduction_pct"] = (
        (merged["total_interruption_s_reactive"] - merged["total_interruption_s_proactive"])
        .div(merged["total_interruption_s_reactive"].clip(lower=1e-9))
        .mul(100.0)
    )
    merged["ping_pong_reduction_pct"] = (
        (merged["ping_pong_events_reactive"] - merged["ping_pong_events_proactive"])
        .div(merged["ping_pong_events_reactive"].clip(lower=1e-9))
        .mul(100.0)
    )
    merged["service_gain_pct"] = (
        merged["service_success_rate_pct_proactive"] - merged["service_success_rate_pct_reactive"]
    )

    heatmaps = [
        ("interruption_reduction_pct", "Interruption Reduction (%)"),
        ("ping_pong_reduction_pct", "Ping-Pong Reduction (%)"),
        ("service_gain_pct", "Service Success Gain (pp)"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    for ax, (column, title) in zip(axes.flat, heatmaps):
        pivot = merged.pivot(
            index="altitude_profile",
            columns="speed_profile",
            values=column,
        )
        sns.heatmap(
            pivot,
            annot=True,
            fmt=".1f",
            cmap="YlGnBu",
            linewidths=0.5,
            cbar=True,
            ax=ax,
        )
        ax.set_title(title)
        ax.set_xlabel("Speed Profile")
        ax.set_ylabel("Altitude Profile")

    fig.suptitle("Proactive Gain over Reactive", fontsize=14, y=1.04)
    _save(fig, "03_condition_gain_heatmaps.png")


def plot_flight_distributions(flight_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    metrics = [
        ("handover_count", "Per-Flight Handovers"),
        ("total_interruption_s", "Per-Flight Interruption (s)"),
        ("latency_violations", "Per-Flight Latency Violations"),
    ]

    for ax, (column, title) in zip(axes.flat, metrics):
        sns.boxplot(
            data=flight_df,
            x="policy",
            y=column,
            hue="policy",
            palette="Set2",
            showfliers=False,
            ax=ax,
            legend=False,
        )
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")

    fig.suptitle("Flight-Level Distribution Comparison", fontsize=14, y=1.02)
    _save(fig, "04_flight_distributions.png")


def main() -> None:
    if not RUN_CSV.exists():
        raise FileNotFoundError(f"Missing run-level CSV: {RUN_CSV}")
    if not FLIGHT_CSV.exists():
        raise FileNotFoundError(f"Missing flight-level CSV: {FLIGHT_CSV}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="talk")

    run_df, flight_df = _prepare_frames()

    plot_policy_overview(run_df)
    plot_phase_comparison(run_df)
    plot_condition_gain_heatmaps(run_df)
    plot_flight_distributions(flight_df)

    print(f"saved_plots=4 output_dir={OUTPUT_DIR}")


if __name__ == "__main__":
    main()
