"""
Multi-model comparison report.
Reads all model sub-directories inside a results run and produces a
side-by-side scorecard table suitable for a research paper.

Usage:
    python scripts/compare_models.py --run-id eval_run_multimodel
    python scripts/compare_models.py --run-id eval_run_multimodel --csv
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
RESULTS_ROOT = ROOT / "results"

SEP  = "-" * 90
SEP2 = "=" * 90


def _short(name: str, max_len: int = 28) -> str:
    return name if len(name) <= max_len else name[:max_len - 2] + ".."


def load_run(run_id: str) -> dict[str, dict]:
    run_dir = RESULTS_ROOT / run_id
    if not run_dir.exists():
        print(f"[ERROR] Run not found: {run_id}")
        sys.exit(1)
    reports = {}
    for model_dir in sorted(run_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        rpt = model_dir / "langtest_report.json"
        if rpt.exists():
            reports[model_dir.name] = json.loads(rpt.read_text())
    if not reports:
        print(f"[ERROR] No langtest_report.json found under {run_dir}")
        sys.exit(1)
    return reports


def parse_model_results(data: dict) -> dict[str, dict]:
    indices = sorted(data["category"].keys(), key=int)
    out = {}
    for i in indices:
        key = f"{data['category'][i]}::{data['test_type'][i]}"
        out[key] = {
            "category":  data["category"][i],
            "test_type": data["test_type"][i],
            "pass_rate": data["pass_rate"][i],
            "passed":    data["pass"][i],
        }
    return out


def render_comparison(run_id: str, reports: dict[str, dict], csv_mode: bool = False):
    parsed = {m: parse_model_results(d) for m, d in reports.items()}
    all_keys = sorted({k for r in parsed.values() for k in r})
    model_names = list(parsed.keys())

    if csv_mode:
        header = "Category,Test," + ",".join(_short(m) for m in model_names)
        print(header)
        for key in all_keys:
            cat, test = key.split("::")
            row = [cat, test]
            for m in model_names:
                cell = parsed[m].get(key)
                if cell:
                    row.append(f"{'PASS' if cell['passed'] else 'FAIL'} ({cell['pass_rate']})")
                else:
                    row.append("N/A")
            print(",".join(row))
        return

    col_w = 22
    print()
    print(SEP2)
    print("  LLM EVAL AGENT - MULTI-MODEL COMPARISON")
    print(SEP2)
    print(f"  Run ID : {run_id}")
    print(f"  Models : {len(model_names)}")
    print(SEP2)

    hdr = f"  {'Category':<14} {'Test':<30}"
    for m in model_names:
        hdr += f"  {_short(m):<{col_w}}"
    print(hdr)
    print(SEP)

    for key in all_keys:
        cat, test = key.split("::")
        row = f"  {cat:<14} {test:<30}"
        for m in model_names:
            cell = parsed[m].get(key)
            if cell:
                status = "PASS" if cell["passed"] else "FAIL"
                row += f"  {status+' ('+cell['pass_rate']+')':<{col_w}}"
            else:
                row += f"  {'N/A':<{col_w}}"
        print(row)

    print(SEP)
    print(f"\n  {'OVERALL':<14} {'':<30}", end="")
    all_pass = {}
    for m in model_names:
        overall = all(v["passed"] for v in parsed[m].values())
        all_pass[m] = overall
        label = "PASS" if overall else "FAIL"
        print(f"  {label:<{col_w}}", end="")
    print("\n")
    print(SEP2)
    print()
    return all_pass


def main():
    parser = argparse.ArgumentParser(description="Multi-model comparison report")
    parser.add_argument("--run-id", required=True, help="Run ID to compare (e.g. eval_run_multimodel)")
    parser.add_argument("--csv",    action="store_true", help="Output in CSV format (paste into spreadsheet)")
    args = parser.parse_args()

    reports = load_run(args.run_id)
    print(f"\n  Found {len(reports)} model(s): {', '.join(reports)}")
    render_comparison(args.run_id, reports, csv_mode=args.csv)


if __name__ == "__main__":
    main()
