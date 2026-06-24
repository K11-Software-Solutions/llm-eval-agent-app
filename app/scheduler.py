"""
Scheduled evaluation — runs the LLM eval on a cron schedule without a PR trigger.
Enabled via config.yaml:

    schedule:
      enabled: true
      cron: "0 0 * * 0"   # weekly on Sunday midnight UTC

Writes results to results/scheduled/<timestamp>/ and appends to audit log.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agent import LLMEvalAgent
from app.eval_runner import _append_audit_log, _compute_confidence, _parse_results, _resolve_data_file
from app.utils import load_config

logger = logging.getLogger(__name__)

CONFIG_PATH   = Path(os.environ.get("CONFIG_PATH", "config/config.yaml"))
RESULTS_ROOT  = Path(os.environ.get("RESULTS_DIR", "results"))

_scheduler: AsyncIOScheduler | None = None


def _run_scheduled_eval():
    """Blocking eval — called inside a thread by APScheduler."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RESULTS_ROOT / "scheduled" / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[scheduler] Starting scheduled eval → {run_dir}")
    try:
        data_file = _resolve_data_file()
        agent = LLMEvalAgent(
            config_path=str(CONFIG_PATH),
            results_dir=str(run_dir),
            data_file_override=data_file,
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent.run_tests()
        finally:
            loop.close()

        results = _parse_results(run_dir)
        overall = "pass" if results.get("all_passed", False) else "fail"

        model_name = agent.models[0].get("name", "") if agent.models else ""
        confidence = _compute_confidence(model_name, data_file) if model_name else {}

        _append_audit_log({
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "run_id":     f"scheduled/{timestamp}",
            "repo":       "scheduled",
            "pr":         None,
            "sha":        None,
            "model":      results.get("model", "unknown"),
            "overall":    overall,
            "categories": results.get("categories", {}),
            "confidence": confidence,
        })

        logger.info(f"[scheduler] Scheduled eval complete — {overall.upper()}")

    except Exception as e:
        logger.error(f"[scheduler] Scheduled eval failed: {e}", exc_info=True)


def start_scheduler():
    """Read config and start APScheduler if schedule.enabled is true."""
    global _scheduler
    try:
        config = load_config(str(CONFIG_PATH))
    except Exception as e:
        logger.warning(f"[scheduler] Could not load config: {e}")
        return

    schedule_cfg = config.get("schedule", {})
    if not schedule_cfg.get("enabled", False):
        logger.info("[scheduler] Scheduled eval disabled (schedule.enabled=false)")
        return

    cron_expr = schedule_cfg.get("cron", "0 0 * * 0")  # default: Sunday midnight
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        logger.warning(f"[scheduler] Invalid cron expression: {cron_expr!r} — skipping")
        return

    minute, hour, day, month, day_of_week = parts
    trigger = CronTrigger(
        minute=minute, hour=hour,
        day=day, month=month,
        day_of_week=day_of_week,
        timezone="UTC",
    )

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_scheduled_eval,
        trigger=trigger,
        id="scheduled_eval",
        name="LLM Eval Agent — scheduled run",
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info(f"[scheduler] Scheduled eval active — cron: {cron_expr!r}")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] Scheduler stopped")
