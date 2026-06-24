"""
Chart generator for LLM Eval Agent research artifacts.

Usage:
    python scripts/generate_charts.py                        # default paths
    python scripts/generate_charts.py --log data/audit_log.jsonl --out artifacts/eval/trend_chart.png
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_LOG = ROOT / "data" / "audit_log.jsonl"
DEFAULT_OUT = ROOT / "artifacts" / "eval" / "trend_chart.png"


def load_audit_entries(log_path: Path) -> list[dict]:
    """Read and deduplicate audit log entries, sorted by timestamp."""
    if not log_path.exists():
        return []
    entries, seen = [], set()
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (e.get("timestamp", "")[:10], e.get("run_id", ""))
        if key in seen:
            continue
        seen.add(key)
        entries.append(e)
    return sorted(entries, key=lambda e: e.get("timestamp", ""))


def generate_trend_chart(log_path: Path, output_path: Path) -> Path:
    """
    Generate a trend chart PNG from audit_log.jsonl.
    Returns the path to the saved file.
    Raises ValueError if there are no entries to plot.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.patches as mpatches

    entries = load_audit_entries(log_path)
    if not entries:
        raise ValueError(f"No audit log entries found in {log_path}")

    dates   = [datetime.fromisoformat(e["timestamp"]) for e in entries]
    bias    = [e.get("categories", {}).get("bias", {}).get("pass_rate") for e in entries]
    robust  = [e.get("categories", {}).get("robustness", {}).get("pass_rate") for e in entries]
    fair    = [e.get("categories", {}).get("fairness", {}).get("pass_rate") for e in entries]
    overall = [e.get("overall", "fail") for e in entries]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8),
                                   gridspec_kw={"height_ratios": [3, 1]})
    fig.patch.set_facecolor("#0d1117")
    for ax in (ax1, ax2):
        ax.set_facecolor("#161b22")
        ax.tick_params(colors="#c9d1d9")
        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")

    COLORS = {"bias": "#58a6ff", "robustness": "#f78166", "fairness": "#d29922"}

    def _plot_series(ax, xs, ys, label, color):
        pts = [(x, y) for x, y in zip(xs, ys) if y is not None]
        if not pts:
            return
        px, py = zip(*pts)
        py_pct = [v * 100 for v in py]
        ax.plot(px, py_pct, "o-", color=color, linewidth=2.5,
                markersize=8, label=label, zorder=3)
        for x, y in zip(px, py_pct):
            ax.annotate(f"{y:.0f}%", (x, y), textcoords="offset points",
                        xytext=(0, 10), ha="center", fontsize=9,
                        color=color, fontweight="bold")

    _plot_series(ax1, dates, bias,   "Bias",       COLORS["bias"])
    _plot_series(ax1, dates, robust, "Robustness", COLORS["robustness"])
    _plot_series(ax1, dates, fair,   "Fairness",   COLORS["fairness"])

    ax1.axhspan(80, 100, alpha=0.05, color="#58a6ff")
    ax1.axhline(80, color="#58a6ff", linestyle="--", linewidth=1,
                alpha=0.5, label="Bias min (80%)")
    ax1.axhline(75, color="#f78166", linestyle="--", linewidth=1,
                alpha=0.5, label="Robustness min (75%)")

    ax1.set_ylim(-5, 115)
    ax1.set_ylabel("Pass Rate (%)", color="#c9d1d9", fontsize=11)
    ax1.set_title(
        "LLM Eval Agent — Bias & Robustness Trend Over Time\n"
        "DistilBERT SST-2 · LangTest Harness",
        color="#f0f6fc", fontsize=13, fontweight="bold", pad=14,
    )
    ax1.legend(facecolor="#21262d", edgecolor="#30363d",
               labelcolor="#c9d1d9", fontsize=9)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax1.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax1.grid(axis="y", color="#30363d", linestyle="--", linewidth=0.7)
    ax1.tick_params(axis="x", rotation=30)

    bar_colors = ["#3fb950" if o == "pass" else "#f85149" for o in overall]
    labels = [d.strftime("%b %d") for d in dates]
    bars = ax2.bar(range(len(dates)), [1] * len(dates),
                   color=bar_colors, edgecolor="#21262d", linewidth=0.8)
    ax2.set_xticks(range(len(dates)))
    ax2.set_xticklabels(labels, color="#c9d1d9", fontsize=9)
    ax2.set_yticks([])
    ax2.set_ylabel("Overall", color="#c9d1d9", fontsize=10)
    ax2.set_title("Overall Eval Result per Run", color="#8b949e",
                  fontsize=10, pad=6)

    for i, (_, o) in enumerate(zip(bars, overall)):
        ax2.text(i, 0.5, "PASS" if o == "pass" else "FAIL",
                 ha="center", va="center", fontsize=9,
                 fontweight="bold", color="#0d1117")

    green_patch = mpatches.Patch(color="#3fb950", label="PASS")
    red_patch   = mpatches.Patch(color="#f85149", label="FAIL")
    ax2.legend(handles=[green_patch, red_patch], facecolor="#21262d",
               edgecolor="#30363d", labelcolor="#c9d1d9", fontsize=9,
               loc="upper right")

    plt.tight_layout(pad=2.5)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate LLM Eval trend chart")
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    out = generate_trend_chart(Path(args.log), Path(args.out))
    print(f"Chart saved: {out}")


if __name__ == "__main__":
    main()
