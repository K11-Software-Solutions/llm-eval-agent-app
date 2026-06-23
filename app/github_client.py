"""
GitHub API client for the LLM Eval Agent GitHub App.
Handles:
  - App authentication (JWT + installation access tokens)
  - Check Runs (create, update)
  - PR comments (post scorecard)
  - PR file listing
"""

import time
import os
import logging
from typing import Optional

import httpx
import jwt  # PyJWT

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
APP_ID = os.environ.get("GITHUB_APP_ID", "")
PRIVATE_KEY_PATH = os.environ.get("GITHUB_PRIVATE_KEY_PATH", "private-key.pem")
PRIVATE_KEY = os.environ.get("GITHUB_PRIVATE_KEY", "")  # raw PEM string (for cloud envs)


def _load_private_key() -> str:
    raw = PRIVATE_KEY
    if not raw:
        with open(PRIVATE_KEY_PATH, "r") as f:
            raw = f.read()
    # Railway sometimes stores literal \n instead of real newlines — fix both
    raw = raw.replace("\\n", "\n")
    # Ensure header/footer are on their own lines
    if "-----BEGIN" in raw and "\n" not in raw.split("-----BEGIN")[0] + "BEGIN":
        raw = raw.replace("-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----\n")
        raw = raw.replace("-----END RSA PRIVATE KEY-----", "\n-----END RSA PRIVATE KEY-----")
    return raw.strip()


def _generate_jwt() -> str:
    """Generate a short-lived JWT to authenticate as the GitHub App."""
    private_key = _load_private_key()
    now = int(time.time())
    payload = {
        "iat": now - 60,   # issued 60s ago (clock skew buffer)
        "exp": now + 540,  # expires in 9 minutes
        "iss": str(APP_ID),  # must be string for PyJWT
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


class GitHubClient:
    def __init__(self, installation_id: Optional[int] = None):
        self.installation_id = installation_id
        self._token: Optional[str] = None
        self._token_expiry: int = 0

    async def _get_installation_token(self) -> str:
        """Exchange JWT for an installation access token (cached until near expiry)."""
        now = int(time.time())
        if self._token and now < self._token_expiry - 60:
            return self._token

        app_jwt = _generate_jwt()
        url = f"{GITHUB_API}/app/installations/{self.installation_id}/access_tokens"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["token"]
            # GitHub installation tokens expire in 1 hour
            self._token_expiry = now + 3600
        return self._token

    async def _headers(self) -> dict:
        token = await self._get_installation_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # ------------------------------------------------------------------ #
    #  Check Runs                                                          #
    # ------------------------------------------------------------------ #

    async def create_check_run(
        self,
        owner: str,
        repo: str,
        head_sha: str,
        name: str = "LLM Eval Agent",
        status: str = "in_progress",
    ) -> int:
        """Create a Check Run and return its ID."""
        url = f"{GITHUB_API}/repos/{owner}/{repo}/check-runs"
        body = {
            "name": name,
            "head_sha": head_sha,
            "status": status,
            "started_at": _iso_now(),
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=await self._headers(), json=body)
            resp.raise_for_status()
            check_run_id = resp.json()["id"]
            logger.info(f"Created check run {check_run_id} on {owner}/{repo}@{head_sha}")
            return check_run_id

    async def update_check_run(
        self,
        owner: str,
        repo: str,
        check_run_id: int,
        conclusion: str,          # "success" | "failure" | "neutral"
        summary: str,             # Markdown summary shown in Check details
        title: str = "LLM Eval Results",
    ):
        """Update a Check Run with final results."""
        url = f"{GITHUB_API}/repos/{owner}/{repo}/check-runs/{check_run_id}"
        body = {
            "status": "completed",
            "conclusion": conclusion,
            "completed_at": _iso_now(),
            "output": {
                "title": title,
                "summary": summary,
            },
        }
        async with httpx.AsyncClient() as client:
            resp = await client.patch(url, headers=await self._headers(), json=body)
            resp.raise_for_status()
            logger.info(f"Updated check run {check_run_id} → {conclusion}")

    # ------------------------------------------------------------------ #
    #  PR Comments                                                         #
    # ------------------------------------------------------------------ #

    async def post_pr_comment(self, owner: str, repo: str, pr_number: int, body: str):
        """Post a comment on a pull request."""
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, headers=await self._headers(), json={"body": body}
            )
            resp.raise_for_status()
            logger.info(f"Posted PR comment on {owner}/{repo}#{pr_number}")

    # ------------------------------------------------------------------ #
    #  PR Files                                                            #
    # ------------------------------------------------------------------ #

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[str]:
        """Return list of filenames changed in a PR."""
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=await self._headers())
            resp.raise_for_status()
            return [f["filename"] for f in resp.json()]


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def format_scorecard(results: dict) -> str:
    """
    Format eval results as a Markdown table for PR comments and Check Run summaries.
    Expects results = {
        "model": str,
        "categories": {"bias": {"pass_rate": 0.9, "passed": True}, ...},
        "overall": "pass" | "fail"
    }
    """
    model = results.get("model", "unknown")
    cats = results.get("categories", {})
    overall = results.get("overall", "unknown")

    icon = "✅" if overall == "pass" else "❌"
    lines = [
        f"## {icon} LLM Eval Agent — `{model}`",
        "",
        "| Category | Pass Rate | Result |",
        "|----------|-----------|--------|",
    ]
    for cat, data in cats.items():
        rate = data.get("pass_rate", 0)
        passed = data.get("passed", False)
        result_icon = "✅ Pass" if passed else "❌ Fail"
        lines.append(f"| {cat.title()} | {rate:.0%} | {result_icon} |")

    lines += [
        "",
        f"**Overall: {overall.upper()}**",
        "",
        "_Powered by [LLM Eval Agent](https://github.com/K11-Software-Solutions/llm-eval-agent-app)_",
    ]
    return "\n".join(lines)
