# GitHub App Installation & Setup Guide

## Overview

The LLM Eval Agent is distributed as a GitHub App. Once installed on a repository, it automatically evaluates LLM model changes on every pull request — no CI configuration required.

---

## Prerequisites

- A GitHub account with admin access to the target repository
- The LLM Eval Agent app must be registered and deployed (see [Deployment Guide](deployment_guide.md))

---

## Step 1 — Register the GitHub App

> Skip this step if you are installing a pre-existing deployment.

1. Go to **github.com/settings/apps** (personal) or **github.com/organizations/\<org\>/settings/apps** (organization)
2. Click **New GitHub App**
3. Fill in the following fields:

| Field | Value |
|-------|-------|
| App name | `LLM Eval Agent` (or any unique name) |
| Homepage URL | Your deployment URL (e.g. `https://your-app.up.railway.app`) |
| Webhook URL | `https://your-app.up.railway.app/webhook` |
| Webhook secret | A random secret string — save it for your env vars |

4. Under **Repository permissions**, set:

| Permission | Level |
|------------|-------|
| Checks | Read & write |
| Contents | Read-only |
| Pull requests | Read & write |
| Metadata | Read-only (auto-granted) |

5. Under **Subscribe to events**, check:
   - `Pull request`

6. Click **Create GitHub App**

7. On the app's settings page, note your **App ID** and generate a **Private key** (`.pem` file). Store both securely.

---

## Step 2 — Deploy the App

Deploy `llm-eval-agent-app` to Railway (or any platform):

```bash
# Set these environment variables on your deployment platform:
GITHUB_APP_ID=<your-app-id>
GITHUB_PRIVATE_KEY=<base64-encoded PEM>   # see note below
GITHUB_WEBHOOK_SECRET=<your-webhook-secret>
```

**Encoding the private key for Railway (avoids newline corruption):**
```powershell
# PowerShell
$bytes = [System.IO.File]::ReadAllBytes("private-key.pem")
[Convert]::ToBase64String($bytes) | Set-Clipboard
# Paste the result as GITHUB_PRIVATE_KEY in Railway
```

Verify the deployment:
```
GET https://your-app.up.railway.app/health   → {"status": "ok"}
```

---

## Step 3 — Install the App on a Repository

1. Go to your GitHub App page → **Install App**
2. Select the account or organization that owns the target repo
3. Choose **Only select repositories** → select the repo(s) to enable eval on
4. Click **Install**

GitHub will send a `ping` event to your webhook URL. The app responds with `{"message": "pong"}`.

---

## Step 4 — Configure the Target Repository

Add a `config/model_config.yaml` to the target repo. This file tells the app which model and thresholds to evaluate:

```yaml
model:
  name: distilbert-base-uncased-finetuned-sst-2-english
  hub: huggingface
  type: text-classification
  version: "1.0"

evaluation:
  categories:
    - bias
    - robustness
  thresholds:
    bias_min_pass_rate: 0.80
    robustness_min_pass_rate: 0.75
```

The app triggers an eval whenever a PR changes any of these file types:
- `.yaml` / `.yml` — model config files
- `.json` — data or prompt config files
- `.txt` — prompt files
- Any path containing `prompt` or `prompts`

---

## Step 5 — Open a Pull Request

1. Create a branch and modify the model config or a prompt file
2. Open a pull request against `main`
3. Within seconds, the **LLM Eval Agent** check appears as `in_progress`
4. After 2–5 minutes, the check completes and posts a scorecard:

```
## ✅ LLM Eval Agent — distilbert-base-uncased-finetuned-sst-2-english

| Category   | Pass Rate | Result   |
|------------|-----------|----------|
| Bias       | 100%      | ✅ Pass  |
| Robustness | 88%       | ✅ Pass  |

**Overall: PASS**
```

The same scorecard is posted as a PR comment and as the Check Run output in the Checks tab.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No check run appears | App not installed on repo | Go to App settings → Install App → select repo |
| `401 Invalid webhook signature` | Wrong `GITHUB_WEBHOOK_SECRET` | Match the secret in Railway env to the one set in App settings |
| `403 Could not parse public key` | PEM key corrupted in env | Re-encode as base64 (see Step 2) |
| `Ignoring event: check_suite` | Wrong event redelivered | Redeliver a `pull_request` event, not `check_run` or `check_suite` |
| `Ignoring PR action: closed` | PR was merged/closed | Push a new commit to an open PR branch |
| Check run stuck `in_progress` | Container OOM / crashed | Eval timed out — check Railway logs; upgrade to ≥1GB RAM plan |
| Scorecard table empty | No JSON report found | Verify `data/sample_data.jsonl` exists in the deployment |

---

## Revoking Access

To uninstall the app from a repository:

1. Go to **github.com/settings/installations** (personal) or **github.com/organizations/\<org\>/settings/installations**
2. Find **LLM Eval Agent** → click **Configure**
3. Scroll to **Danger zone** → **Uninstall**

This immediately stops all webhook deliveries to that repository.
