"""
Report tool for LLM Eval Agent — generates a readable scorecard from a run.

Usage:
    # From a local JSON file
    python scripts/report.py --file results/debug_run/.../langtest_report.json

    # From a live Railway run (fetches latest completed run automatically)
    python scripts/report.py --url https://llm-eval-agent-app-production.up.railway.app

    # From a specific run ID on Railway
    python scripts/report.py --url https://... --run-id abc123
"""

import argparse
import json
import sys
from pathlib import Path

import requests

BASE_URL = "https://llm-eval-agent-app-production.up.railway.app"

PASS_ICON = "[PASS]"
FAIL_ICON = "[FAIL]"
W = 60


def separator(char="-"): print(char * W)


def fetch_report_from_api(base, run_id=None):
    if not run_id:
        r = requests.get(f"{base}/runs", timeout=10)
        r.raise_for_status()
        runs = [x for x in r.json().get("runs", []) if x.get("status") == "completed"]
        if not runs:
            print("No completed runs found on the server.")
            sys.exit(1)
        run_id = runs[-1]["run_id"]
        print(f"Using latest completed run: {run_id}")

    r = requests.get(f"{base}/results/{run_id}", timeout=10)
    r.raise_for_status()
    files = r.json().get("files", [])
    json_files = [f for f in files if f.endswith(".json")]
    if not json_files:
        print(f"No JSON result files found for run {run_id}")
        sys.exit(1)

    reports = []
    for filepath in json_files:
        r = requests.get(f"{base}/results/{run_id}/{filepath}", timeout=10)
        r.raise_for_status()
        model_name = Path(filepath).parent.name
        reports.append((model_name, r.json()))
    return run_id, reports


def load_report_from_file(path):
    p = Path(path)
    if not p.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    model_name = p.parent.name
    with open(p) as f:
        return "local", [(model_name, json.load(f))]


def parse_rows(data):
    indices = sorted(data["category"].keys(), key=int)
    rows = []
    for i in indices:
        rows.append({
            "category":     data["category"][i],
            "test_type":    data["test_type"][i],
            "pass_count":   data["pass_count"][i],
            "fail_count":   data["fail_count"][i],
            "pass_rate":    data["pass_rate"][i],
            "min_rate":     data["minimum_pass_rate"][i],
            "passed":       data["pass"][i],
        })
    return rows


def render_report(run_id, model_name, rows):
    overall = all(r["passed"] for r in rows)
    overall_label = "PASS" if overall else "FAIL"

    print()
    separator("=")
    print(f"  LLM EVAL AGENT - SCORECARD")
    separator("=")
    print(f"  Run ID : {run_id}")
    print(f"  Model  : {model_name}")
    print(f"  Result : {'[PASS] All checks passed' if overall else '[FAIL] One or more checks failed'}")
    separator("=")
    print()

    # Table header
    col = [18, 30, 6, 6, 10, 10, 8]
    def row_fmt(c, t, pc, fc, pr, mr, st):
        return f"  {c:<{col[0]}} {t:<{col[1]}} {pc:>{col[2]}} {fc:>{col[3]}} {pr:>{col[4]}} {mr:>{col[5]}} {st:>{col[6]}}"

    print(row_fmt("Category", "Test", "Pass", "Fail", "Rate", "Min", "Status"))
    separator()

    for r in rows:
        status = PASS_ICON if r["passed"] else FAIL_ICON
        print(row_fmt(
            r["category"],
            r["test_type"],
            r["pass_count"],
            r["fail_count"],
            r["pass_rate"],
            r["min_rate"],
            status,
        ))

    separator()
    print(f"\n  Overall: {overall_label}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Generate readable LLM eval scorecard")
    parser.add_argument("--file",   help="Path to a local langtest_report.json")
    parser.add_argument("--url",    default=BASE_URL, help="Deployment base URL")
    parser.add_argument("--run-id", help="Specific run ID to fetch from the server")
    args = parser.parse_args()

    if args.file:
        run_id, reports = load_report_from_file(args.file)
    else:
        run_id, reports = fetch_report_from_api(args.url.rstrip("/"), args.run_id)

    for model_name, data in reports:
        rows = parse_rows(data)
        render_report(run_id, model_name, rows)


if __name__ == "__main__":
    main()
