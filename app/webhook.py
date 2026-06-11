"""
GitHub webhook handler.
Listens for pull_request events, triggers LLM eval on relevant file changes,
and posts Check Run results + PR comment back to GitHub.
"""

import hashlib
import hmac
import json
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.github_client import GitHubClient
from app.eval_runner import run_eval_for_pr

logger = logging.getLogger(__name__)
router = APIRouter()

WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

# File patterns that should trigger an eval run
TRIGGER_PATTERNS = [
    ".yaml", ".yml", ".json",   # config / prompt files
    "prompt", "prompts",         # any path containing "prompt"
    ".txt",                      # plain-text prompt files
]


def _verify_signature(payload: bytes, sig_header: Optional[str]) -> bool:
    """Verify GitHub webhook HMAC signature."""
    if not WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET not set — skipping signature verification")
        return True
    if not sig_header or not sig_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


def _should_trigger(changed_files: list[str]) -> bool:
    """Return True if any changed file matches trigger patterns."""
    for f in changed_files:
        f_lower = f.lower()
        if any(pat in f_lower for pat in TRIGGER_PATTERNS):
            return True
    return False


@router.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
):
    body = await request.body()

    if not _verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = x_github_event
    payload = json.loads(body)

    if event == "ping":
        return {"message": "pong"}

    if event != "pull_request":
        return {"message": f"Ignoring event: {event}"}

    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return {"message": f"Ignoring PR action: {action}"}

    pr = payload["pull_request"]
    repo = payload["repository"]
    installation_id = payload.get("installation", {}).get("id")

    repo_owner = repo["owner"]["login"]
    repo_name = repo["name"]
    pr_number = pr["number"]
    head_sha = pr["head"]["sha"]

    logger.info(f"PR #{pr_number} {action} on {repo_owner}/{repo_name} @ {head_sha}")

    # Fetch changed files from GitHub API
    github = GitHubClient(installation_id=installation_id)
    changed_files = await github.get_pr_files(repo_owner, repo_name, pr_number)

    if not _should_trigger(changed_files):
        logger.info("No trigger-pattern files changed — skipping eval")
        return {"message": "No relevant files changed"}

    # Create a pending Check Run immediately so GitHub shows "in progress"
    check_run_id = await github.create_check_run(
        owner=repo_owner,
        repo=repo_name,
        head_sha=head_sha,
        name="LLM Eval Agent",
        status="in_progress",
    )

    run_id = uuid.uuid4().hex[:12]

    # Run eval in background; posts results back when done
    background_tasks.add_task(
        run_eval_for_pr,
        run_id=run_id,
        github=github,
        owner=repo_owner,
        repo=repo_name,
        pr_number=pr_number,
        head_sha=head_sha,
        check_run_id=check_run_id,
        changed_files=changed_files,
    )

    return {"message": "Eval started", "run_id": run_id}
