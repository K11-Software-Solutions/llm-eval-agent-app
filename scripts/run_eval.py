"""
Local eval runner for LLM Eval Agent.
Runs evaluation with a timestamped run_id, stores results in results/{run_id}/,
and prints a readable scorecard on completion.

Usage:
    python scripts/run_eval.py                          # run with default config + data
    python scripts/run_eval.py --data data/test_data.jsonl
    python scripts/run_eval.py --config config/config.yaml --data data/test_data.jsonl
    python scripts/run_eval.py --list                   # list all past runs
    python scripts/run_eval.py --report <run_id>        # show scorecard for a past run
"""

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
RESULTS_ROOT = ROOT / "results"
DEFAULT_CONFIG = ROOT / "config" / "config.yaml"
DEFAULT_DATA   = ROOT / "data" / "test_data.jsonl"


# ── formatting helpers ────────────────────────────────────────────────────────

def ok(msg):     print(f"  [PASS]  {msg}")
def info(msg):   print(f"  [INFO]  {msg}")
def err(msg):    print(f"  [ERROR] {msg}"); sys.exit(1)
def header(msg): print(f"\n{'-'*60}\n{msg}\n{'-'*60}")


# ── scorecard renderer ────────────────────────────────────────────────────────

def render_scorecard(run_id, model_name, data):
    indices = sorted(data["category"].keys(), key=int)
    rows = [{
        "category":  data["category"][i],
        "test_type": data["test_type"][i],
        "pass":      data["pass_count"][i],
        "fail":      data["fail_count"][i],
        "rate":      data["pass_rate"][i],
        "min":       data["minimum_pass_rate"][i],
        "passed":    data["pass"][i],
    } for i in indices]

    overall = all(r["passed"] for r in rows)

    print(f"\n{'='*60}")
    print(f"  LLM EVAL AGENT - SCORECARD")
    print(f"{'='*60}")
    print(f"  Run ID    : {run_id}")
    print(f"  Model     : {model_name}")
    print(f"  Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Result    : {'[PASS] All checks passed' if overall else '[FAIL] One or more checks failed'}")
    print(f"{'='*60}")

    col = [18, 30, 6, 6, 8, 8, 8]
    def fmt(c, t, p, f, r, m, s):
        return f"  {c:<{col[0]}} {t:<{col[1]}} {p:>{col[2]}} {f:>{col[3]}} {r:>{col[4]}} {m:>{col[5]}} {s:>{col[6]}}"

    print(fmt("Category", "Test", "Pass", "Fail", "Rate", "Min", "Status"))
    print(f"  {'-'*58}")
    for r in rows:
        print(fmt(r["category"], r["test_type"], r["pass"], r["fail"],
                  r["rate"], r["min"], "[PASS]" if r["passed"] else "[FAIL]"))
    print(f"  {'-'*58}")
    print(f"\n  Overall: {'PASS' if overall else 'FAIL'}\n")
    return overall


# ── list past runs ────────────────────────────────────────────────────────────

def list_runs():
    RESULTS_ROOT.mkdir(exist_ok=True)
    runs = sorted([d for d in RESULTS_ROOT.iterdir() if d.is_dir()])
    if not runs:
        print("\n  No runs found.\n")
        return

    print(f"\n{'='*60}")
    print(f"  Past Eval Runs")
    print(f"{'='*60}")
    print(f"  {'Run ID':<20} {'Timestamp':<22} {'Status'}")
    print(f"  {'-'*58}")

    for run_dir in runs:
        meta_file = run_dir / "run_metadata.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
            ts     = meta.get("timestamp", "unknown")
            status = meta.get("status", "unknown")
        else:
            ts, status = "unknown", "unknown"
        print(f"  {run_dir.name:<20} {ts:<22} {status}")
    print()


# ── show report for a past run ────────────────────────────────────────────────

def show_report(run_id):
    run_dir = RESULTS_ROOT / run_id
    if not run_dir.exists():
        err(f"Run not found: {run_id}")
    json_files = list(run_dir.rglob("langtest_report.json"))
    if not json_files:
        err(f"No report found in {run_dir}")
    for json_file in json_files:
        model_name = json_file.parent.name
        data = json.loads(json_file.read_text())
        render_scorecard(run_id, model_name, data)


# ── run evaluation ────────────────────────────────────────────────────────────

def run_eval(config_path, data_file, test_id=None):
    run_id   = test_id if test_id else datetime.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:4]
    run_dir  = RESULTS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "run_id":    run_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config":    str(config_path),
        "data_file": str(data_file),
        "status":    "running",
    }
    meta_file = run_dir / "run_metadata.json"
    meta_file.write_text(json.dumps(meta, indent=2))

    header(f"Starting eval run: {run_id}")
    info(f"Config    : {config_path}")
    info(f"Data file : {data_file}")
    info(f"Results   : {run_dir}")

    try:
        sys.path.insert(0, str(ROOT))
        from app.agent import LLMEvalAgent

        agent = LLMEvalAgent(
            config_path=str(config_path),
            results_dir=str(run_dir),
            data_file_override=str(data_file),
        )
        agent.run_tests()
        meta["status"] = "completed"
        meta_file.write_text(json.dumps(meta, indent=2))
        ok(f"Eval completed — run_id: {run_id}")

    except Exception as e:
        meta["status"] = "failed"
        meta["error"]  = str(e)
        meta_file.write_text(json.dumps(meta, indent=2))
        err(f"Eval failed: {e}")

    # print scorecard and write audit log
    json_files = list(run_dir.rglob("langtest_report.json"))
    for jf in json_files:
        render_scorecard(run_id, jf.parent.name, json.loads(jf.read_text()))

    try:
        from app.eval_runner import _parse_results, _append_audit_log
        results = _parse_results(run_dir)
        overall = "pass" if results.get("all_passed", False) else "fail"
        _append_audit_log({
            "timestamp":  datetime.now().astimezone().isoformat(),
            "run_id":     run_id,
            "repo":       "local",
            "pr":         None,
            "sha":        None,
            "model":      results.get("model", ""),
            "overall":    overall,
            "categories": results.get("categories", {}),
            "confidence": {},
        })
        info(f"Audit log updated — overall: {overall.upper()}")
    except Exception as e:
        info(f"Audit log skipped: {e}")

    return run_id


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LLM Eval Agent — local runner")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")
    parser.add_argument("--data",   default=str(DEFAULT_DATA),   help="Path to test data (JSONL)")
    parser.add_argument("--test-id", metavar="TEST_ID",           help="Named test ID for result folder (e.g. eval_run_1, bias_study_v2)")
    parser.add_argument("--list",   action="store_true",         help="List all past runs")
    parser.add_argument("--report", metavar="RUN_ID",            help="Show scorecard for a past run")
    args = parser.parse_args()

    if args.list:
        list_runs()
    elif args.report:
        show_report(args.report)
    else:
        config = Path(args.config)
        data   = Path(args.data)
        if not config.exists(): err(f"Config not found: {config}")
        if not data.exists():   err(f"Data file not found: {data}")
        run_eval(config, data, test_id=args.test_id)


if __name__ == "__main__":
    main()
