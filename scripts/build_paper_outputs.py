from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from paths import (
    ANALYSIS_RESULTS_DIR,
    GUIDES_DIR,
    PAPER_FIGURES_DIR,
    RAW_RESULTS_DIR,
    TABLE_RESULTS_DIR,
)

RUN_CSV = RAW_RESULTS_DIR / "simulation_sweep_run_results.csv"
FLIGHT_CSV = RAW_RESULTS_DIR / "simulation_sweep_flight_results.csv"
LATENCY_ANALYSIS_CSV = ANALYSIS_RESULTS_DIR / "analysis_latency_violation_deep.csv"

TABLE_DIR = TABLE_RESULTS_DIR
FIG_DIR = PAPER_FIGURES_DIR


def _fmt_float(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def _save_fig(fig: plt.Figure, filename: str) -> None:
    path = FIG_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved figure] {path}")


def _save_table(df: pd.DataFrame, filename: str) -> None:
    path = TABLE_DIR / filename
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[saved table] {path} rows={len(df)}")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    run_df = pd.read_csv(RUN_CSV)
    flight_df = pd.read_csv(FLIGHT_CSV)
    latency_df = pd.read_csv(LATENCY_ANALYSIS_CSV)

    run_df["service_success_rate_pct"] = (
        run_df["service_continuity_successes"]
        .div(run_df["handover_attempts"].clip(lower=1))
        .mul(100.0)
    )
    run_df["total_interruption_s"] = run_df["total_interruption_ms"] / 1000.0

    flight_df["service_handover_count"] = flight_df["handover_count"]
    flight_df["total_interruption_s"] = flight_df["total_interruption_ms"] / 1000.0
    flight_df["service_success_rate_pct"] = (
        flight_df["service_continuity_successes"]
        .div(flight_df["service_handover_count"].clip(lower=1))
        .mul(100.0)
    )
    flight_df["handover_failure_rate_pct"] = (
        flight_df["radio_handover_failures"]
        .div(flight_df["service_handover_count"].clip(lower=1))
        .mul(100.0)
    )

    phase_order = ["introduction", "growth", "maturity"]
    speed_order = ["low", "medium", "high"]
    altitude_order = ["low", "mid", "high"]
    policy_order = ["reactive", "proactive"]

    for df in (run_df, flight_df):
        df["phase"] = pd.Categorical(df["phase"], categories=phase_order, ordered=True)
        df["policy"] = pd.Categorical(df["policy"], categories=policy_order, ordered=True)
        if "speed_profile" in df:
            df["speed_profile"] = pd.Categorical(df["speed_profile"], categories=speed_order, ordered=True)
        if "altitude_profile" in df:
            df["altitude_profile"] = pd.Categorical(df["altitude_profile"], categories=altitude_order, ordered=True)

    return run_df, flight_df, latency_df


def build_tables(run_df: pd.DataFrame, flight_df: pd.DataFrame, latency_df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    failure_by_policy = (
        run_df.groupby("policy", observed=True)[["handover_attempts", "radio_handover_failures"]]
        .sum()
        .reset_index()
    )
    failure_by_policy["handover_failure_rate_pct"] = (
        failure_by_policy["radio_handover_failures"]
        .div(failure_by_policy["handover_attempts"].clip(lower=1))
        .mul(100.0)
    )

    table1 = (
        run_df.groupby("policy", observed=True)
        .agg(
            mean_total_handovers=("total_handovers", "mean"),
            mean_ping_pong_events=("ping_pong_events", "mean"),
            mean_total_interruption_s=("total_interruption_s", "mean"),
            mean_service_success_rate_pct=("service_success_rate_pct", "mean"),
            mean_throughput_mbps=("mean_throughput_mbps", "mean"),
            mean_sinr_db=("mean_sinr_db", "mean"),
        )
        .reset_index()
        .merge(
            failure_by_policy[
                [
                    "policy",
                    "handover_attempts",
                    "radio_handover_failures",
                    "handover_failure_rate_pct",
                ]
            ],
            on="policy",
            how="left",
        )
    )

    table2 = (
        run_df.groupby(["phase", "policy"], observed=True)
        .agg(
            mean_total_handovers=("total_handovers", "mean"),
            mean_ping_pong_events=("ping_pong_events", "mean"),
            mean_total_interruption_s=("total_interruption_s", "mean"),
            mean_service_success_rate_pct=("service_success_rate_pct", "mean"),
            mean_throughput_mbps=("mean_throughput_mbps", "mean"),
            mean_sinr_db=("mean_sinr_db", "mean"),
        )
        .reset_index()
    )

    descriptive = latency_df[latency_df["analysis_section"] == "descriptive"].copy()
    descriptive = descriptive.pivot(index="policy", columns="statistic", values="value").reset_index()
    table3 = descriptive[
        [
            "policy",
            "mean",
            "median",
            "std",
            "min",
            "max",
            "count",
        ]
    ].copy()

    test_row = latency_df[latency_df["analysis_section"] == "mann_whitney_u"].iloc[0]
    table4 = pd.DataFrame(
        [
            {
                "comparison_target": str(test_row["policy"]),
                "test_name": str(test_row["statistic"]),
                "u_statistic": float(test_row["value"]),
                "mann_whitney_p_value": float(test_row["p_value"]),
                "rank_biserial_effect_size": float(test_row["effect_size"]),
                "total_n": int(test_row["n"]),
            }
        ]
    )

    route_summary = (
        flight_df.groupby(["origin", "destination", "policy"], observed=True)
        .agg(
            mean_handovers=("handover_count", "mean"),
            mean_interruption_ms=("total_interruption_ms", "mean"),
            mean_latency_violations=("latency_violations", "mean"),
            mean_throughput_mbps=("mean_throughput_mbps", "mean"),
            mean_sinr_db=("mean_sinr_db", "mean"),
            flight_count=("flight_id", "size"),
        )
        .reset_index()
    )
    proactive = route_summary[route_summary["policy"] == "proactive"].drop(columns="policy")
    reactive = route_summary[route_summary["policy"] == "reactive"].drop(columns="policy")
    table5 = proactive.merge(
        reactive,
        on=["origin", "destination"],
        suffixes=("_proactive", "_reactive"),
    )
    table5["interruption_reduction_pct"] = (
        (table5["mean_interruption_ms_reactive"] - table5["mean_interruption_ms_proactive"])
        .div(table5["mean_interruption_ms_reactive"].clip(lower=1e-9))
        .mul(100.0)
    )
    table5["handover_reduction_pct"] = (
        (table5["mean_handovers_reactive"] - table5["mean_handovers_proactive"])
        .div(table5["mean_handovers_reactive"].clip(lower=1e-9))
        .mul(100.0)
    )
    table5["latency_violation_reduction_pct"] = (
        (table5["mean_latency_violations_reactive"] - table5["mean_latency_violations_proactive"])
        .div(table5["mean_latency_violations_reactive"].clip(lower=1e-9))
        .mul(100.0)
    )
    table5 = table5.sort_values("interruption_reduction_pct", ascending=False).head(10)
    table5 = table5[
        [
            "origin",
            "destination",
            "flight_count_proactive",
            "mean_handovers_reactive",
            "mean_handovers_proactive",
            "handover_reduction_pct",
            "mean_interruption_ms_reactive",
            "mean_interruption_ms_proactive",
            "interruption_reduction_pct",
            "mean_latency_violations_reactive",
            "mean_latency_violations_proactive",
            "latency_violation_reduction_pct",
        ]
    ].rename(columns={"flight_count_proactive": "flight_count"})

    return [
        ("table_1_overall_policy_summary.csv", table1),
        ("table_2_phase_policy_summary.csv", table2),
        ("table_3_latency_descriptive.csv", table3),
        ("table_4_latency_mann_whitney.csv", table4),
        ("table_5_top_route_improvement.csv", table5),
    ]


def build_markdown_report(tables: dict[str, pd.DataFrame]) -> str:
    def df_to_markdown(df: pd.DataFrame, digits: int = 2) -> str:
        display_df = df.copy()
        for column in display_df.select_dtypes(include=["float64", "float32"]).columns:
            display_df[column] = display_df[column].map(
                lambda x: "" if pd.isna(x) else f"{x:.{digits}f}"
            )
        headers = [str(col) for col in display_df.columns]
        rows = display_df.astype(str).values.tolist()
        widths = [
            max(len(headers[idx]), *(len(row[idx]) for row in rows))
            for idx in range(len(headers))
        ]
        header_line = "| " + " | ".join(headers[idx].ljust(widths[idx]) for idx in range(len(headers))) + " |"
        separator = "| " + " | ".join("-" * widths[idx] for idx in range(len(headers))) + " |"
        body = [
            "| " + " | ".join(row[idx].ljust(widths[idx]) for idx in range(len(headers))) + " |"
            for row in rows
        ]
        return "\n".join([header_line, separator, *body])

    lines: list[str] = []
    lines.append("# Paper Tables Summary")
    lines.append("")
    lines.append("## Notes")
    lines.append("- Source column `total_interruption_ms` is stored in milliseconds.")
    lines.append("- All paper tables and figures report `mean_total_interruption_s`, which is `total_interruption_ms / 1000` converted to seconds.")
    lines.append("- Therefore, `162.37` in Table 1 means `162.37 s`, which corresponds to `162,366.26 ms` in the source CSV.")
    lines.append("- The source flight-level CSV does not contain `service_handover_count`; this report uses `handover_count` as an alias for that concept.")
    lines.append("- `handover_failure_rate_pct` is computed as `radio_handover_failures / handover_count × 100` at flight level and `sum(radio_handover_failures) / sum(handover_attempts) × 100` at run/policy summary level.")
    lines.append("- The latency violation summary is split into Table 3 (descriptive statistics) and Table 4 (Mann-Whitney U test result) to avoid structurally empty cells in the manuscript.")
    lines.append("")
    lines.append("## Table 1. Overall policy comparison")
    lines.append(df_to_markdown(tables["table_1_overall_policy_summary.csv"], digits=2))
    lines.append("")
    lines.append("## Table 2. Phase-wise policy comparison")
    lines.append(df_to_markdown(tables["table_2_phase_policy_summary.csv"], digits=2))
    lines.append("")
    lines.append("## Table 3. Latency violation descriptive statistics")
    lines.append(df_to_markdown(tables["table_3_latency_descriptive.csv"], digits=4))
    lines.append("")
    lines.append("## Table 4. Latency violation Mann-Whitney U test")
    lines.append(df_to_markdown(tables["table_4_latency_mann_whitney.csv"], digits=4))
    lines.append("")
    lines.append("## Table 5. Top routes with proactive interruption reduction")
    lines.append(df_to_markdown(tables["table_5_top_route_improvement.csv"], digits=2))
    lines.append("")
    return "\n".join(lines)


def plot_overall_policy_comparison(table1: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    metrics = [
        ("mean_total_handovers", "Mean Handovers"),
        ("mean_ping_pong_events", "Mean Ping-Pong Events"),
        ("mean_total_interruption_s", "Mean Interruption (s)"),
        ("mean_service_success_rate_pct", "Service Success Rate (%)"),
    ]
    palette = {"reactive": "#d95f02", "proactive": "#1b9e77"}

    for ax, (column, title) in zip(axes.flat, metrics):
        sns.barplot(
            data=table1,
            x="policy",
            y=column,
            hue="policy",
            palette=palette,
            legend=False,
            ax=ax,
        )
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")
        for container in ax.containers:
            labels = [f"{bar.get_height():.1f}" for bar in container]
            ax.bar_label(container, labels=labels, padding=3, fontsize=9)

    fig.suptitle("Overall Handover Performance Comparison", fontsize=15, y=1.02)
    _save_fig(fig, "figure_1_overall_policy_comparison.png")


def plot_phase_trends(table2: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    metrics = [
        ("mean_total_handovers", "Mean Handovers"),
        ("mean_ping_pong_events", "Mean Ping-Pong Events"),
        ("mean_total_interruption_s", "Mean Interruption (s)"),
        ("mean_service_success_rate_pct", "Service Success Rate (%)"),
    ]
    palette = {"reactive": "#d95f02", "proactive": "#1b9e77"}

    for ax, (column, title) in zip(axes.flat, metrics):
        sns.lineplot(
            data=table2,
            x="phase",
            y=column,
            hue="policy",
            style="policy",
            markers=True,
            dashes=False,
            linewidth=2.6,
            palette=palette,
            ax=ax,
        )
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.legend(title="")

    fig.suptitle("Phase-wise Performance Trend", fontsize=15, y=1.02)
    _save_fig(fig, "figure_2_phase_trends.png")


def plot_condition_heatmaps(flight_df: pd.DataFrame) -> None:
    grouped = (
        flight_df.groupby(["speed_profile", "altitude_profile", "policy"], observed=True)
        .agg(
            mean_interruption_s=("total_interruption_s", "mean"),
            mean_ping_pong=("ping_pong_events", "mean"),
            service_success_rate_pct=("service_success_rate_pct", "mean"),
        )
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
        (merged["mean_interruption_s_reactive"] - merged["mean_interruption_s_proactive"])
        .div(merged["mean_interruption_s_reactive"].clip(lower=1e-9))
        .mul(100.0)
    )
    merged["ping_pong_reduction_pct"] = (
        (merged["mean_ping_pong_reactive"] - merged["mean_ping_pong_proactive"])
        .div(merged["mean_ping_pong_reactive"].clip(lower=1e-9))
        .mul(100.0)
    )
    merged["service_gain_pp"] = (
        merged["service_success_rate_pct_proactive"] - merged["service_success_rate_pct_reactive"]
    )

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.5))
    specs = [
        ("interruption_reduction_pct", "Interruption Reduction (%)"),
        ("ping_pong_reduction_pct", "Ping-Pong Reduction (%)"),
        ("service_gain_pp", "Service Success Gain (pp)"),
    ]

    for ax, (column, title) in zip(axes.flat, specs):
        pivot = merged.pivot(index="altitude_profile", columns="speed_profile", values=column)
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
        ax.set_xlabel("Speed")
        ax.set_ylabel("Altitude")

    fig.suptitle("Condition-wise Proactive Gain over Reactive", fontsize=15, y=1.05)
    _save_fig(fig, "figure_3_condition_heatmaps.png")


def plot_top_route_improvement(table5: pd.DataFrame) -> None:
    plot_df = table5.copy()
    plot_df["route"] = plot_df["origin"] + " -> " + plot_df["destination"]
    plot_df = plot_df.sort_values("interruption_reduction_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(11, 6))
    sns.barplot(
        data=plot_df,
        y="route",
        x="interruption_reduction_pct",
        color="#1b9e77",
        ax=ax,
    )
    ax.set_title("Top Routes with Proactive Interruption Reduction")
    ax.set_xlabel("Interruption Reduction (%)")
    ax.set_ylabel("")
    for container in ax.containers:
        labels = [f"{bar.get_width():.1f}" for bar in container]
        ax.bar_label(container, labels=labels, padding=4, fontsize=9)

    _save_fig(fig, "figure_4_top_route_interruption_reduction.png")


def write_dataread_opinion() -> None:
    opinion = """DataRead.md에 대한 의견

1. 좋은 점
- 역할 분담이 명확하다. 시뮬레이션 실행과 데이터 분석 책임을 분리해 두어서 작업 경계가 분명하다.
- 가상 데이터 생성 금지, 기존 CSV만 사용, 추가 시뮬레이션은 사용자 직접 수행이라는 조건이 분명해서 분석의 신뢰성을 높인다.
- 산출물 파일명과 목적이 구체적으로 적혀 있어, 분석 결과를 논문 구성 요소와 바로 연결하기 쉽다.
- 문제 제기 방식이 좋다. 단순히 그래프를 그리라고 하지 않고, 왜 현재 결과가 이상해 보이는지 세 가지 포인트로 나눠 검증하도록 설계했다.

2. 실제로 분석해 보며 드러난 한계
- 가장 큰 문제는 지표 정의가 문서 안에서 약간 섞여 있다는 점이다.
  현재 CSV의 service_continuity_successes는 비행 단위 성공 여부가 아니라 핸드오버 이벤트 성공 횟수다.
  그런데 DataRead.md의 일부 문장은 이것을 비행 성공률처럼 읽히게 만든다.
- service_handover_count라는 컬럼명을 요구하지만, 실제 CSV에는 같은 의미의 handover_count만 있다.
  즉 문서와 실제 데이터 사전(data dictionary)이 완전히 일치하지 않는다.
- 완전 성공 비율을 interruption 0, ping-pong 0, latency violation 0의 동시 만족으로 정의했는데,
  현재 데이터에서는 interruption 0과 latency violation 0 비행이 아예 존재하지 않는다.
  따라서 이 지표는 현재 데이터 기준으로는 판별력보다 구조적 0값 확인에 더 가깝다.
- reactive의 radio_handover_failure가 0%인 반면 proactive만 실패가 존재하는 결과는 일반적인 기대와 다르게 보일 수 있다.
  이런 경우에는 DataRead.md 안에 지표 정의와 판정 로직 요약이 같이 있었으면 해석이 더 쉬웠을 것이다.

3. 개선하면 더 좋아질 점
- 맨 앞에 “이 문서에서 성공률은 비행 기준인지, 핸드오버 이벤트 기준인지”를 먼저 정의하는 것이 좋다.
- 실제 CSV 컬럼명과 문서의 요구 컬럼명을 1:1로 매핑한 표를 추가하는 것이 필요하다.
  예: service_handover_count -> handover_count
- run-level 지표와 flight-level 지표를 분리해서 써야 한다.
  현재 문서는 둘을 오가며 읽게 되어 있어 처음 보는 사람이 혼동할 수 있다.
- 추가로 데이터 사전 섹션을 하나 두고, 각 컬럼의 의미와 단위를 한 줄씩 적어두면 이후 재분석이 훨씬 쉬워진다.
- 논문용 지표는 “핸드오버 이벤트 성공률”과 “비행 단위 성공 비율”을 분리해서 요구하는 편이 더 정확하다.

4. 총평
DataRead.md는 분석 지시서로서 상당히 잘 작성된 편이다.
특히 “새로운 시뮬레이션을 돌리지 말고 기존 CSV만 분석하라”는 제약이 명확해서 작업 방향이 흔들리지 않는다.
다만 현재 데이터 구조와 비교했을 때, 성공률의 기준 단위와 일부 컬럼명 정의가 모호하다.
따라서 다음 버전에서는 데이터 사전과 지표 정의를 먼저 고정하면, 훨씬 더 강한 분석 문서가 될 것이다.
"""
    GUIDES_DIR.mkdir(parents=True, exist_ok=True)
    path = GUIDES_DIR / "DataRead_opinion.txt"
    path.write_text(opinion, encoding="utf-8")
    print(f"[saved text] {path}")


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="talk")

    run_df, flight_df, latency_df = load_data()
    table_pairs = build_tables(run_df, flight_df, latency_df)
    table_map: dict[str, pd.DataFrame] = {}
    for filename, df in table_pairs:
        rounded = df.copy()
        for column in rounded.select_dtypes(include=["float64", "float32"]).columns:
            rounded[column] = rounded[column].round(4)
        _save_table(rounded, filename)
        table_map[filename] = rounded

    markdown_report = build_markdown_report(table_map)
    report_path = TABLE_DIR / "paper_tables.md"
    report_path.write_text(markdown_report, encoding="utf-8")
    print(f"[saved table] {report_path}")

    plot_overall_policy_comparison(table_map["table_1_overall_policy_summary.csv"])
    plot_phase_trends(table_map["table_2_phase_policy_summary.csv"])
    plot_condition_heatmaps(flight_df)
    plot_top_route_improvement(table_map["table_5_top_route_improvement.csv"])

    write_dataread_opinion()


if __name__ == "__main__":
    main()
