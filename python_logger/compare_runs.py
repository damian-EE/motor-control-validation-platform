#!/usr/bin/env python3
"""
compare_runs.py - repeatability across several sweep runs.

Usage:
    python compare_runs.py test_results/run_A.csv test_results/run_B.csv [run_C.csv ...]
    python compare_runs.py runs... --outdir media

Outputs:
    <outdir>/repeatability.png            speed and current vs PWM, every run overlaid
    <outdir>/repeatability_summary.csv    per PWM level and pass: each run, mean, spread
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

from plot_results import (C_CUR, C_RPM, INK, INK_2, SURFACE, load,
                          split_passes, steady_state_table, style_axes)

MARKERS = ["o", "s", "^", "D"]


def build_table(paths):
    """One row per (pass, pwm); one column per run for rpm and current."""
    frames = []
    for i, p in enumerate(paths, start=1):
        table = steady_state_table(load(p))
        up, down = split_passes(table)
        for name, part in (("up", up), ("down", down)):
            part = part.assign(run=f"run{i}", pass_=name)
            frames.append(part[["pass_", "pwm", "run", "rpm_mean", "current_mA_mean"]])
    long = pd.concat(frames, ignore_index=True)

    out = []
    for (pas, pwm), g in long.groupby(["pass_", "pwm"]):
        row = {"pass": pas, "pwm": pwm}
        for _, r in g.iterrows():
            row[f"rpm_{r['run']}"] = r["rpm_mean"]
        for _, r in g.iterrows():
            row[f"mA_{r['run']}"] = r["current_mA_mean"]
        rpm = g["rpm_mean"]
        cur = g["current_mA_mean"]
        row["rpm_mean"] = rpm.mean()
        row["rpm_spread_pct"] = (rpm.max() - rpm.min()) / rpm.mean() * 100
        row["mA_mean"] = cur.mean()
        row["mA_spread_pct"] = (cur.max() - cur.min()) / cur.mean() * 100
        out.append(row)
    res = pd.DataFrame(out)
    res["order"] = res["pass"].map({"up": 0, "down": 1})
    res = res.sort_values(["order", "pwm"]).drop(columns="order")
    return long, res.round(2)


def figure(long, paths):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), facecolor=SURFACE)
    panels = [("rpm_mean", "Steady-state speed (RPM)", C_RPM),
              ("current_mA_mean", "Steady-state current (mA)", C_CUR)]
    runs = sorted(long["run"].unique())
    for ax, (col, ylabel, color) in zip(axes, panels):
        style_axes(ax, ylabel)
        for i, run in enumerate(runs):
            m = MARKERS[i % len(MARKERS)]
            for pas, ls, fill in (("up", "-", color), ("down", "--", SURFACE)):
                g = long[(long["run"] == run) & (long["pass_"] == pas)]
                ax.plot(g["pwm"], g[col], linestyle=ls, linewidth=2, color=color,
                        marker=m, markersize=6, markerfacecolor=fill,
                        markeredgecolor=color, markeredgewidth=1.6)
        ax.set_xlabel("PWM command (0-255)", color=INK_2, fontsize=10)
        ax.set_ylim(bottom=0)
        ax.set_xlim(40, 270)
    handles = []
    for i, run in enumerate(runs):
        handles.append(Line2D([0], [0], color=INK_2, marker=MARKERS[i % len(MARKERS)],
                              linestyle="", markersize=7,
                              label=f"{run} ({Path(paths[i]).stem})"))
    handles += [Line2D([0], [0], color=INK_2, linewidth=2, linestyle="-", label="ramp up (filled)"),
                Line2D([0], [0], color=INK_2, linewidth=2, linestyle="--", label="ramp down (hollow)")]
    axes[0].legend(handles=handles, loc="lower right", frameon=False, fontsize=8.5,
                   handlelength=3.2, labelcolor=INK_2)
    fig.suptitle("Run-to-run repeatability (no load, 12 V)", color=INK, fontsize=13, x=0.02,
                 ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return fig


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("csvs", nargs="+", help="two or more sweep CSVs")
    ap.add_argument("--outdir", default="media")
    args = ap.parse_args()
    if len(args.csvs) < 2:
        raise SystemExit("Give at least two CSV files to compare.")

    long, table = build_table(args.csvs)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fig = figure(long, args.csvs)
    fig.savefig(outdir / "repeatability.png", dpi=160, facecolor=SURFACE)
    table.to_csv(outdir / "repeatability_summary.csv", index=False)
    print(table.to_string(index=False))
    print(f"\nWrote {outdir / 'repeatability.png'} and {outdir / 'repeatability_summary.csv'}")


if __name__ == "__main__":
    main()
