"""
Per-domain bias/fairness/robustness breakdown.
Splits research_eval_data.jsonl by domain, runs eval on each slice,
and produces a domain comparison table.

Usage:
    python scripts/domain_breakdown.py
    python scripts/domain_breakdown.py --data data/research_eval_data.jsonl
    python scripts/domain_breakdown.py --test-id domain_study_v1 --csv
"""

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
RESULTS_ROOT = ROOT / "results"
DEFAULT_DATA   = ROOT / "data" / "research_eval_data.jsonl"
DEFAULT_CONFIG = ROOT / "config" / "config.yaml"

SEP  = "-" * 80
SEP2 = "=" * 80


def err(msg):
    print(f"[ERROR] {msg}")
    sys.exit(1)


def split_by_domain(data_path: Path) -> dict[str, list]:
    domains = defaultdict(list)
    for line in data_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        domain = row.get("domain", "unknown")
        domains[domain].append(row)
    return dict(domains)


def run_domain_eval(domain: str, rows: list, run_dir: Path, config_path: Path) -> dict:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        tmp_path = f.name

    domain_out = run_dir / domain
    domain_out.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ROOT))
    from app.agent import LLMEvalAgent

    agent = LLMEvalAgent(
        config_path=str(config_path),
        results_dir=str(domain_out),
        data_file_override=tmp_path,
    )
    agent.run_tests()

    results = {}
    for model_dir in domain_out.iterdir():
        if not model_dir.is_dir():
            continue
        rpt = model_dir / "langtest_report.json"
        if rpt.exists():
            results[model_dir.name] = json.loads(rpt.read_text())

    Path(tmp_path).unlink(missing_ok=True)
    return results


def parse_summary(data: dict) -> tuple[int, int, bool]:
    pass_total = sum(data["pass_count"].values())
    fail_total = sum(data["fail_count"].values())
    overall    = all(data["pass"].values())
    return pass_total, fail_total, overall


def render_table(run_id: str, domain_results: dict[str, dict], csv_mode: bool = False):
    all_domains = sorted(domain_results.keys())
    first_domain = all_domains[0]
    first_model_results = domain_results[first_domain]
    model_names = list(first_model_results.keys())
    main_model = model_names[0] if model_names else "model"

    if csv_mode:
        print("Domain,Samples,Pass,Fail,Overall")
        for domain in all_domains:
            model_data = domain_results[domain].get(main_model, {})
            if not model_data:
                continue
            p, f, overall = parse_summary(model_data)
            print(f"{domain},{p+f},{p},{f},{'PASS' if overall else 'FAIL'}")
        return

    print()
    print(SEP2)
    print("  LLM EVAL AGENT - DOMAIN BREAKDOWN")
    print(SEP2)
    print(f"  Run ID : {run_id}")
    print(f"  Model  : {main_model}")
    print(SEP2)
    print(f"  {'Domain':<16} {'Samples':>8} {'Pass':>6} {'Fail':>6} {'Overall':>10}")
    print(SEP)

    for domain in all_domains:
        model_data = domain_results[domain].get(main_model, {})
        if not model_data:
            print(f"  {domain:<16} {'N/A':>8}")
            continue
        p, f, overall = parse_summary(model_data)
        label = "PASS" if overall else "FAIL"
        print(f"  {domain:<16} {p+f:>8} {p:>6} {f:>6} {label:>10}")

    print(SEP)
    print()


def main():
    parser = argparse.ArgumentParser(description="Per-domain eval breakdown")
    parser.add_argument("--data",    default=str(DEFAULT_DATA),   help="JSONL with 'domain' field")
    parser.add_argument("--config",  default=str(DEFAULT_CONFIG), help="Config YAML")
    parser.add_argument("--test-id", default="domain_breakdown",  help="Run ID for result storage")
    parser.add_argument("--csv",     action="store_true",         help="Output CSV table")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        err(f"Data file not found: {data_path}")

    print(f"\n[INFO] Splitting {data_path.name} by domain...")
    domains = split_by_domain(data_path)
    for d, rows in sorted(domains.items()):
        print(f"  {d:<16} {len(rows)} samples")

    run_dir = RESULTS_ROOT / args.test_id
    run_dir.mkdir(parents=True, exist_ok=True)

    domain_results = {}
    for domain, rows in sorted(domains.items()):
        print(f"\n[INFO] Evaluating domain: {domain} ({len(rows)} samples)...")
        domain_results[domain] = run_domain_eval(domain, rows, run_dir, Path(args.config))

    render_table(args.test_id, domain_results, csv_mode=args.csv)

    # save summary JSON for reference
    summary = {}
    for domain, model_map in domain_results.items():
        summary[domain] = {}
        for model, data in model_map.items():
            p, f, overall = parse_summary(data)
            summary[domain][model] = {"pass": p, "fail": f, "overall": "PASS" if overall else "FAIL"}
    (run_dir / "domain_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[INFO] Summary saved to {run_dir / 'domain_summary.json'}")


if __name__ == "__main__":
    main()
