"""Plots the cumulative solve time of the line incremental benchmark.

For each profile and iteration, the per-insertion solve times are cumulated over
the stream number. The plot shows the mean cumulative runtime across iterations
as a line, with one standard deviation as a shaded band.

Run interactively with ``uv run marimo edit benchmarks/plots/flexcurve_line_incremental.py``
or headless with ``uv run python benchmarks/plots/flexcurve_line_incremental.py``.
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

    results_path = Path(__file__).parent.parent / "results" / "flexcurve_line_incremental.csv"
    figures_dir = Path(__file__).parent.parent / "results" / "figures"
    figures_dir.mkdir(exist_ok=True, parents=True)
    df = pl.read_csv(results_path)
    return (df, figures_dir)


@app.cell
def _(df, pl):
    # Cumulate the solve times within each (profile, iteration) run, then
    # aggregate over the iterations. Time in ns is converted to s.
    cumulative = df.sort("stream_number").with_columns(
        pl.col("solve_time_ns").cum_sum().over(["profile", "iteration"]).alias("cumulative_time_ns"),
    )
    stats = (
        cumulative.group_by(["profile", "stream_number"])
        .agg(
            (pl.col("cumulative_time_ns").mean() / 1e9).alias("mean_s"),
            (pl.col("cumulative_time_ns").std() / 1e9).alias("std_s"),
        )
        .sort("stream_number")
    )
    return (stats,)


@app.cell
def _(figures_dir, pl, plt, stats, sns):
    profiles = stats["profile"].unique().sort().to_list()
    fig, ax = plt.subplots(figsize=(3.5, 2.6), layout="constrained")
    for profile in profiles:
        run = stats.filter(pl.col("profile") == profile)
        x = run["stream_number"].to_numpy()
        mean = run["mean_s"].to_numpy()
        std = run["std_s"].to_numpy()
        line = ax.plot(x, mean, label=profile)[0]
        ax.fill_between(x, mean - std, mean + std, alpha=0.3, color=line.get_color())
    ax.set_yscale("log")
    ax.set_xlabel("Number of Insertions")
    ax.set_ylabel("Cumulative Runtime [s]")
    fig.legend(*ax.get_legend_handles_labels(), loc="outside lower center", ncol=2)
    sns.despine(fig=fig)
    fig.savefig(figures_dir / "flexcurve_line_incremental.pdf", bbox_inches="tight", pad_inches=0.05)
    fig


if __name__ == "__main__":
    app.run()
