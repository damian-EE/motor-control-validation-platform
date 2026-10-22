#!/usr/bin/env python3
"""
plot_results.py - turn a motor_logger CSV into plots and a summary table.

Usage:
    python plot_results.py test_results/run_20261015_101500.csv
    python plot_results.py run.csv --outdir media --title "Run 1, 12 V supply"

Outputs (in --outdir, default media/):
    <name>_timeseries.png   PWM, speed, current and voltage vs time
    <name>_response.png     steady-state speed and current vs PWM
    <name>_summary.csv      one row per PWM level (steady-state means)
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

# Colors: reference categorical slots (blue, orange, violet), one per measure,
# each on its own panel. Ink and grid kept recessive.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
C_RPM = "#2a78d6"
C_CUR = "#eb6834"
C_VOLT = "#6250d6"
C_PWM = "#52514e"


def style_axes(ax, ylabel):
    ax.set_facecolor(SURFACE)
    ax.set_ylabel(ylabel, color=INK_2, fontsize=10)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def load(path):
    df = pd.read_csv(path)
    need = {"time_ms", "pwm", "rpm", "current_mA", "voltage_V"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"CSV is missing columns: {sorted(missing)}")
    df = df.dropna().reset_index(drop=True)
    df["t_s"] = (df["time_ms"] - df["time_ms"].iloc[0]) / 1000.0
    return df


def steady_state_table(df, settle_fraction=0.5):
    """Mean of each measure over the last part of every constant-PWM stretch."""
    # A "step" is a run of consecutive rows with the same pwm value
    step_id = (df["pwm"] != df["pwm"].shift()).cumsum()
    rows = []
    for _, g in df.groupby(step_id):
        if len(g) < 4:  # too short to say anything
            continue
        tail = g.iloc[int(len(g) * settle_fraction):]
        rows.append({
            "pwm": int(g["pwm"].iloc[0]),
            "start_s": round(g["t_s"].iloc[0], 1),
            "samples": len(g),
            "rpm_mean": tail["rpm"].mean(),
            "rpm_std": tail["rpm"].std(),
            "current_mA_mean": tail["current_mA"].mean(),
            "voltage_V_mean": tail["voltage_V"].mean(),
            "power_W_mean": (tail["current_mA"] / 1000.0 * tail["voltage_V"]).mean(),
        })
    return pd.DataFrame(rows).round(2)


def timeseries_figure(df, title):
    fig, axes = plt.subplots(4, 1, figsize=(9, 8), sharex=True, facecolor=SURFACE,
                             gridspec_kw={"height_ratios": [0.8, 1.2, 1.2, 0.9]})
    panels = [
        ("pwm", "PWM command", C_PWM, True),
        ("rpm", "Speed (RPM)", C_RPM, False),
        ("current_mA", "Current (mA)", C_CUR, False),
        ("voltage_V", "Bus voltage (V)", C_VOLT, False),
    ]
    for ax, (col, label, color, step) in zip(axes, panels):
        style_axes(ax, label)
        if step:
            ax.step(df["t_s"], df[col], where="post", color=color, linewidth=2)
        else:
            ax.plot(df["t_s"], df[col], color=color, linewidth=2)
    axes[-1].set_xlabel("Time (s)", color=INK_2, fontsize=10)
    fig.suptitle(title, color=INK, fontsize=13, x=0.02, ha="left", y=0.995)
    fig.tight_layout()
    return fig


def split_passes(table):
    """Split the steady-state table into the ramp-up and ramp-down passes.

    Levels visited twice (e.g. 100 and 180 in the default sweep) are kept as
    separate points, because a real motor does not give the same answer going
    up as coming down (friction, warm-up). Averaging them would hide that.
    """
    fwd = table[table["pwm"] > 0].reset_index(drop=True)
    if fwd.empty:
        return fwd, fwd
    peak = int(fwd["pwm"].idxmax())
    return fwd.iloc[: peak + 1], fwd.iloc[peak + 1:]


def response_figure(table, title):
    up, down = split_passes(table)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.9), facecolor=SURFACE)
    specs = [
        (axes[0], "rpm_mean", "Steady-state speed (RPM)", C_RPM, "rpm_std"),
        (axes[1], "current_mA_mean", "Steady-state current (mA)", C_CUR, None),
    ]
    for ax, col, label, color, err in specs:
        style_axes(ax, label)
        ax.set_xlabel("PWM command (0-255)", color=INK_2, fontsize=10)
        ax.errorbar(up["pwm"], up[col], yerr=up[err] if err else None,
                    color=color, linewidth=2, marker="o", markersize=7,
                    markeredgecolor=SURFACE, markeredgewidth=2, capsize=3,
                    label="Ramp up")
        if len(down):
            ax.errorbar(down["pwm"], down[col], yerr=down[err] if err else None,
                        color=color, linewidth=2, linestyle="--", marker="o",
                        markersize=7, markerfacecolor=SURFACE,
                        markeredgecolor=color, markeredgewidth=2, capsize=3,
                        label="Ramp down")
            # Explicit handles: matplotlib's errorbar legend entries can show the
            # wrong line style, so draw the legend swatches ourselves.
            handles = [
                Line2D([0], [0], color=color, lw=2, marker="o", markersize=7,
                       markeredgecolor=SURFACE, markeredgewidth=2, label="Ramp up"),
                Line2D([0], [0], color=color, lw=2, linestyle="--", marker="o",
                       markersize=7, markerfacecolor=SURFACE,
                       markeredgecolor=color, markeredgewidth=2, label="Ramp down"),
            ]
            ax.legend(handles=handles, frameon=False, fontsize=9,
                      labelcolor=INK_2, loc="lower right", handlelength=3.6)
        ax.set_ylim(bottom=0)
    fig.suptitle(title, color=INK, fontsize=13, x=0.02, ha="left")
    fig.tight_layout()
    return fig


def main():
    ap = argparse.ArgumentParser(description="Plot a motor_logger CSV.")
    ap.add_argument("csv")
    ap.add_argument("--outdir", default="media")
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    df = load(args.csv)
    name = Path(args.csv).stem
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    title = args.title or name

    table = steady_state_table(df)
    table.to_csv(out / f"{name}_summary.csv", index=False)
    print(table.to_string(index=False))

    f1 = timeseries_figure(df, f"{title} - time series")
    f1.savefig(out / f"{name}_timeseries.png", dpi=160, facecolor=SURFACE)
    if (table["pwm"] > 0).sum() >= 2:
        f2 = response_figure(table, f"{title} - steady-state response")
        f2.savefig(out / f"{name}_response.png", dpi=160, facecolor=SURFACE)
    else:
        print("Fewer than 2 forward PWM steps found; skipped the response plot.")
    print(f"Wrote plots and summary to {out}/")


if __name__ == "__main__":
    main()
