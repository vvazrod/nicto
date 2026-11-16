"""Plots the results of the spine-leaf churn benchmark.

Two views of the data:

- The cumulative path and schedule solving runtime. For each profile and
  iteration the per-insertion solver times are summed and cumulated over the
  insertion number, then the mean across iterations is shown as a line with
  one standard deviation as a shaded band, on a logarithmic y-axis.
- A table summarizing, per profile and frame size, the mean and standard
  deviation of latency, runtime, contiguous schedule availability, and number
  of unfeasible streams across iterations.

Run interactively with ``uv run marimo edit benchmarks/notebooks/flexcurve_spine_leaf_churn.py``
or headless with ``uv run python benchmarks/notebooks/flexcurve_spine_leaf_churn.py``.
"""

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import matplotlib.pyplot as plt
    import polars as pl
    import seaborn as sns

    sns.set_theme(style="ticks", font="Source Sans 3")
    return pl, plt, sns


@app.cell
def _(pl):
    from pathlib import Path

    results_dir = Path(__file__).parent.parent / "results"
    figures_dir = Path(__file__).parent.parent / "results" / "figures"
    figures_dir.mkdir(exist_ok=True, parents=True)
    times = pl.read_csv(results_dir / "flexcurve_spine_leaf_churn_times.csv")
    latencies = pl.read_csv(results_dir / "flexcurve_spine_leaf_churn_latencies.csv")
    availability = pl.read_csv(results_dir / "flexcurve_spine_leaf_churn_availability.csv")
    unfeasible = pl.read_csv(results_dir / "flexcurve_spine_leaf_churn_unfeasible.csv")
    return availability, figures_dir, latencies, times, unfeasible


@app.cell
def _(pl, times):
    # Cumulate path and schedule solver times within each (profile, iteration)
    # run, then aggregate over the iterations. Time in ns is converted to s.
    cumulative = times.sort("insertion").with_columns(
        (
            (pl.col("schedule_time_ns").fill_null(0))
            .cum_sum()
            .over(["profile", "iteration"])
            .alias("cumulative_solve_ns")
        ),
    )
    runtime_stats = (
        cumulative.group_by(["profile", "insertion"])
        .agg(
            (pl.col("cumulative_solve_ns").mean() / 1e9).alias("mean_s"),
            (pl.col("cumulative_solve_ns").std() / 1e9).alias("std_s"),
        )
        .sort("insertion")
    )
    profiles = runtime_stats["profile"].unique().sort().to_list()
    return profiles, runtime_stats


@app.cell
def _(figures_dir, pl, plt, profiles, runtime_stats, sns):
    fig_rt, ax_rt = plt.subplots(figsize=(3.5, 2.6), layout="constrained")
    for rt_profile in profiles:
        rt_run = runtime_stats.filter(pl.col("profile") == rt_profile)
        rt_x = rt_run["insertion"].to_numpy()
        rt_mean = rt_run["mean_s"].to_numpy()
        rt_std = rt_run["std_s"].to_numpy()
        rt_line = ax_rt.plot(rt_x, rt_mean, label=rt_profile)[0]
        ax_rt.fill_between(rt_x, rt_mean - rt_std, rt_mean + rt_std, alpha=0.3, color=rt_line.get_color())
    ax_rt.set_yscale("log")
    ax_rt.set_xlabel("Number of Insertions")
    ax_rt.set_ylabel("Cumulative Runtime [s]")
    fig_rt.legend(*ax_rt.get_legend_handles_labels(), loc="outside lower center", ncol=2)
    sns.despine(fig=fig_rt)
    fig_rt.savefig(figures_dir / "flexcurve_spine_leaf_churn.pdf", bbox_inches="tight", pad_inches=0.05)
    fig_rt


@app.cell
def _(availability, latencies, pl, times, unfeasible):
    # Total runtime per iteration (path + schedule summed over the insertions),
    # in s, and unfeasible stream counts aggregated across iterations. Latency
    # is aggregated by frame size across feasible insertions. Contiguous
    # availability is the mean largest free block across all port schedules.
    totals = times.group_by(["profile", "iteration"]).agg(
        ((pl.col("path_time_ns").fill_null(0) + pl.col("schedule_time_ns").fill_null(0)).sum() / 1e9).alias(
            "total_runtime_s",
        ),
    )
    summary = (
        totals.group_by("profile")
        .agg(
            pl.col("total_runtime_s").mean().alias("Total Runtime Mean [s]"),
            pl.col("total_runtime_s").std().alias("Total Runtime Std [s]"),
        )
        .join(
            unfeasible.group_by("profile").agg(
                pl.col("unfeasible").mean().alias("Unfeasible Streams Mean"),
                pl.col("unfeasible").std().alias("Unfeasible Streams Std"),
            ),
            on="profile",
        )
        .join(
            latencies.group_by(["profile", "frame_size"]).agg(
                (pl.col("latency_ns").mean() / 1e3).alias("Latency Mean [us]"),
                (pl.col("latency_ns").std() / 1e3).alias("Latency Std [us]"),
            ),
            on="profile",
        )
        .join(
            availability.group_by("profile").agg(
                pl.col("contiguous_slots_available_percent").mean().alias("Contiguous Availability Mean [%]"),
                pl.col("contiguous_slots_available_percent").std().alias("Contiguous Availability Std [%]"),
            ),
            on="profile",
        )
        .sort(["profile", "frame_size"])
        .rename({"profile": "Profile", "frame_size": "Frame Size [B]"})
    )
    summary


@app.cell
def _(pl, times):
    path_runtime = times.select(
        (pl.col("path_time_ns").mean() / 1e6).alias("mean_ms"),
        (pl.col("path_time_ns").std() / 1e6).alias("std_ms"),
    ).row(0, named=True)
    print(
        "Path solver runtime across all profiles and iterations: "
        f"{path_runtime['mean_ms']:.6f} ± {path_runtime['std_ms']:.6f} ms",
    )


if __name__ == "__main__":
    app.run()
