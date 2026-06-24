"""
Trend chart — read audit_log.jsonl and display bias/robustness pass rates over time.

Usage:
    python scripts/trend_chart.py                        # table from data/audit_log.jsonl
    python scripts/trend_chart.py --log path/to/log.jsonl
    python scripts/trend_chart.py --category robustness
    python scripts/trend_chart.py --output md            # markdown (default)
    python scripts/trend_chart.py --output csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_LOG = ROOT / "data" / "audit_log.jsonl"

BLOCKS = "▁▂▃▄▅▆▇█"


def _sparkline(values: list[float]) -> str:
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn or 1.0
    return "".join(BLOCKS[min(7, int((v - mn) / rng * 7))] for v in values)


def load_entries(log_path: Path) -> list[dict]:
    if not log_path.exists():
        print(f"[WARN] Audit log not found: {log_path}", file=sys.stderr)
        return []
    entries = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return sorted(entries, key=lambda e: e.get("timestamp", ""))


def _rate(entry: dict, category: str) -> float | None:
    cats = entry.get("categories", {})
    if category in cats:
        return float(cats[category].get("pass_rate", 0))
    return None


def render_table(entries: list[dict], category: str) -> str:
    if not entries:
        return "_No eval runs recorded yet. Run an eval to populate the trend log._"

    # Collect all category names across entries
    all_cats = sorted({cat for e in entries for cat in e.get("categories", {})})
    if category and category not in all_cats:
        all_cats = sorted({cat for e in entries for cat in e.get("categories", {})})

    # Header
    cat_headers = [c.title() for c in all_cats]
    header = "| Date | Model | " + " | ".join(cat_headers) + " | Confidence | Overall |"
    sep    = "|------|-------|" + "|".join(["-" * (len(h) + 2) for h in cat_headers]) + "|------------|---------|"

    rows = [header, sep]
    for e in entries:
        date = e.get("timestamp", "")[:10]
        model = e.get("model", "unknown")
        model_short = model.split("/")[-1][:30]
        overall = e.get("overall", "?")
        overall_icon = "✅ PASS" if overall == "pass" else "❌ FAIL"

        conf = e.get("confidence", {})
        conf_str = f"{conf.get('avg_confidence', 0):.0%}" if conf else "—"

        cat_cells = []
        for cat in all_cats:
            rate = _rate(e, cat)
            passed = e.get("categories", {}).get(cat, {}).get("passed", False)
            if rate is not None:
                icon = "✅" if passed else "❌"
                cat_cells.append(f"{icon} {rate:.0%}")
            else:
                cat_cells.append("—")

        rows.append(f"| {date} | `{model_short}` | " +
                    " | ".join(cat_cells) +
                    f" | {conf_str} | {overall_icon} |")

    # Sparklines per category
    lines = ["\n".join(rows), ""]
    for cat in all_cats:
        rates = [_rate(e, cat) for e in entries if _rate(e, cat) is not None]
        if rates:
            spark = _sparkline(rates)
            latest = rates[-1]
            trend = "↑" if len(rates) > 1 and rates[-1] > rates[-2] else \
                    "↓" if len(rates) > 1 and rates[-1] < rates[-2] else "→"
            lines.append(f"**{cat.title()} trend** {trend} `{spark}` — latest: {latest:.0%}")

    lines += ["", f"_{len(entries)} eval run(s) recorded_"]
    return "\n".join(lines)


def render_csv(entries: list[dict]) -> str:
    if not entries:
        return "timestamp,model,overall,category,pass_rate,confidence_avg"
    all_cats = sorted({cat for e in entries for cat in e.get("categories", {})})
    out = []
    writer_rows = []
    for e in entries:
        base = {
            "timestamp":      e.get("timestamp", ""),
            "model":          e.get("model", ""),
            "repo":           e.get("repo", ""),
            "pr":             e.get("pr", ""),
            "sha":            e.get("sha", "")[:8] if e.get("sha") else "",
            "overall":        e.get("overall", ""),
            "confidence_avg": e.get("confidence", {}).get("avg_confidence", ""),
        }
        for cat in all_cats:
            base[f"{cat}_pass_rate"] = _rate(e, cat) or ""
            base[f"{cat}_passed"] = e.get("categories", {}).get(cat, {}).get("passed", "")
        writer_rows.append(base)

    if writer_rows:
        import io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=writer_rows[0].keys())
        w.writeheader()
        w.writerows(writer_rows)
        return buf.getvalue()
    return ""


def main():
    parser = argparse.ArgumentParser(description="LLM Eval Agent — trend chart")
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="Path to audit_log.jsonl")
    parser.add_argument("--category", default="", help="Filter to a specific category")
    parser.add_argument("--output", choices=["md", "csv"], default="md")
    parser.add_argument("--last", type=int, default=0, help="Show last N runs only")
    args = parser.parse_args()

    entries = load_entries(Path(args.log))
    if args.last:
        entries = entries[-args.last:]

    if args.output == "csv":
        print(render_csv(entries))
    else:
        print(render_table(entries, args.category))


if __name__ == "__main__":
    main()
