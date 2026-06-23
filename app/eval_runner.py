"""
Background task: runs LLM eval and posts results back to GitHub.
Called from webhook.py after a PR event triggers an eval.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from app.agent import LLMEvalAgent
from app.github_client import GitHubClient, format_scorecard

logger = logging.getLogger(__name__)

RESULTS_ROOT = Path(os.environ.get("RESULTS_DIR", "results"))
CONFIG_PATH  = Path(os.environ.get("CONFIG_PATH", "config/config.yaml"))
DEFAULT_DATA = Path(os.environ.get("DATA_FILE", "data/sample_data.jsonl"))


def _resolve_data_file() -> str:
    """Return path to data file: uploaded > config > bundled default."""
    # Check for last uploaded file pointer
    latest_ptr = Path("data/_latest.txt")
    if latest_ptr.exists():
        candidate = Path(latest_ptr.read_text().strip())
        if candidate.exists():
            return str(candidate)
    # Fall back to bundled default
    if DEFAULT_DATA.exists():
        return str(DEFAULT_DATA)
    raise FileNotFoundError(
        f"No data file found. Upload one via POST /upload-data or set DATA_FILE env var."
    )


async def run_eval_for_pr(
    run_id: str,
    github: GitHubClient,
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str,
    check_run_id: int,
    changed_files: list[str],
):
    """Run eval agent and report results back to GitHub."""
    run_dir = RESULTS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[{run_id}] Starting eval for {owner}/{repo}#{pr_number}")

    try:
        data_file = _resolve_data_file()
        logger.info(f"[{run_id}] Using data file: {data_file}")
        agent = LLMEvalAgent(
            config_path=str(CONFIG_PATH),
            results_dir=str(run_dir),
            data_file_override=data_file,
        )
        # Run blocking langtest in a thread with its own fresh event loop
        # (langtest calls asyncio.get_event_loop() internally which conflicts with FastAPI's loop)
        def _run_in_new_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                agent.run_tests()
            finally:
                loop.close()

        eval_timeout = int(os.environ.get("EVAL_TIMEOUT_SECONDS", "300"))
        await asyncio.wait_for(asyncio.to_thread(_run_in_new_loop), timeout=eval_timeout)

        # Parse results to build scorecard
        results = _parse_results(run_dir)
        overall = "pass" if results.get("all_passed", False) else "fail"
        results["overall"] = overall

        scorecard_md = format_scorecard(results)
        conclusion = "success" if overall == "pass" else "failure"

        # Post Check Run result
        await github.update_check_run(
            owner=owner,
            repo=repo,
            check_run_id=check_run_id,
            conclusion=conclusion,
            summary=scorecard_md,
        )

        # Post PR comment — best-effort, don't let a 403 overwrite the Check Run
        try:
            await github.post_pr_comment(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                body=scorecard_md,
            )
        except Exception as comment_err:
            logger.warning(f"[{run_id}] PR comment failed (non-fatal): {comment_err}")

        logger.info(f"[{run_id}] Eval complete — {overall.upper()}")

    except asyncio.TimeoutError:
        msg = f"Eval timed out after {os.environ.get('EVAL_TIMEOUT_SECONDS', '300')}s. The model may be too large for this environment."
        logger.error(f"[{run_id}] {msg}")
        error_summary = f"## ⏱️ LLM Eval Agent — Timeout\n\n{msg}\n\n_Consider increasing `EVAL_TIMEOUT_SECONDS` or using a smaller model._"
        await github.update_check_run(owner=owner, repo=repo, check_run_id=check_run_id,
                                      conclusion="failure", summary=error_summary, title="Eval Timed Out")
        await github.post_pr_comment(owner=owner, repo=repo, pr_number=pr_number, body=error_summary)
        return

    except Exception as e:
        logger.error(f"[{run_id}] Eval failed: {e}", exc_info=True)
        error_summary = f"## ❌ LLM Eval Agent — Error\n\n```\n{e}\n```"

        await github.update_check_run(
            owner=owner,
            repo=repo,
            check_run_id=check_run_id,
            conclusion="failure",
            summary=error_summary,
            title="Eval Error",
        )
        await github.post_pr_comment(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            body=error_summary,
        )


def _parse_results(run_dir: Path) -> dict:
    """
    Walk run_dir for JSON reports and build a unified results dict.
    Returns:
    {
        "model": str,
        "categories": {"bias": {"pass_rate": float, "passed": bool}, ...},
        "all_passed": bool,
    }
    """
    categories = {}
    tests = []          # per-test rows for detailed scorecard
    model = "unknown"
    all_passed = True

    json_files = list(run_dir.rglob("*.json"))
    logger.info(f"_parse_results: found {len(json_files)} JSON file(s) in {run_dir}")

    for json_file in json_files:
        try:
            with open(json_file) as f:
                report = json.load(f)
        except Exception:
            continue

        logger.info(f"_parse_results: parsing {json_file.name}, type={type(report).__name__}, keys={list(report.keys()) if isinstance(report, dict) else 'list'}")
        # Try to extract model name from parent dir
        model = json_file.parent.name

        if isinstance(report, list):
            for row in report:
                cat = row.get("category", "unknown")
                rate = row.get("pass_rate", 0)
                if isinstance(rate, str) and rate.endswith("%"):
                    rate = float(rate.strip("%")) / 100
                passed = float(rate) >= 0.8
                categories[cat] = {"pass_rate": float(rate), "passed": passed}
                if not passed:
                    all_passed = False

        elif isinstance(report, dict) and isinstance(report.get("category"), dict):
            # LangTest pandas-style JSON: {"category":{"0":"bias",...}, "pass_rate":{"0":"100%",...}}
            cat_rows: dict = {}
            for idx in report["category"]:
                cat = report["category"][idx]
                test_type = report.get("test_type", {}).get(idx, "")
                rate_raw = report.get("pass_rate", {}).get(idx, "0%")
                min_rate_raw = report.get("minimum_pass_rate", {}).get(idx, "")
                pass_count = int(report.get("pass_count", {}).get(idx, 0))
                fail_count = int(report.get("fail_count", {}).get(idx, 0))
                passed_val = report.get("pass", {}).get(idx, False)
                if isinstance(rate_raw, str) and rate_raw.endswith("%"):
                    rate = float(rate_raw.strip("%")) / 100
                else:
                    rate = float(rate_raw or 0)
                tests.append({
                    "category": cat,
                    "test_type": test_type,
                    "pass_count": pass_count,
                    "fail_count": fail_count,
                    "pass_rate": rate,
                    "min_pass_rate": min_rate_raw,
                    "passed": bool(passed_val),
                })
                if cat not in cat_rows:
                    cat_rows[cat] = {"rates": [], "passed": True}
                cat_rows[cat]["rates"].append(rate)
                if not passed_val:
                    cat_rows[cat]["passed"] = False
            for cat, data in cat_rows.items():
                avg_rate = sum(data["rates"]) / len(data["rates"])
                categories[cat] = {"pass_rate": avg_rate, "passed": data["passed"]}
                if not data["passed"]:
                    all_passed = False

        elif isinstance(report, dict):
            summary = report.get("summary", {})
            for cat, data in summary.items():
                score = data.get("score", data.get("pass_rate", 0))
                if isinstance(score, str) and score.endswith("%"):
                    score = float(score.strip("%")) / 100
                passed = float(score) >= 0.8
                categories[cat] = {"pass_rate": float(score), "passed": passed}
                if not passed:
                    all_passed = False

    if not categories:
        all_passed = False

    return {"model": model, "categories": categories, "tests": tests, "all_passed": all_passed}
