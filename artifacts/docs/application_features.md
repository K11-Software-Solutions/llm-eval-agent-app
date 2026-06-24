# LLM Eval Agent — Application Features

## Overview

LLM Eval Agent is a GitHub App that automatically evaluates LLM model changes on every pull request, posting bias, fairness, robustness, and confidence results as a Check Run and PR comment scorecard.

---

## Core Features

### GitHub App Integration
- **PR-triggered evaluation** — Automatically fires on `pull_request` events with actions `opened`, `synchronize`, or `reopened`
- **File-pattern triggers** — Evaluates only when relevant files change (`.yaml`, `.yml`, `.json`, `.txt`, paths containing `prompt`)
- **Webhook signature verification** — HMAC-SHA256 validation of all incoming webhook payloads using `GITHUB_WEBHOOK_SECRET`
- **JWT authentication** — RS256 JWT generation using GitHub App private key; supports raw PEM and base64-encoded keys for cloud deployments
- **Installation access token** — Exchanges JWT for per-repo installation tokens, cached for 1 hour

### Check Runs & PR Feedback
- **In-progress Check Run** — Created immediately on webhook receipt so GitHub shows status within seconds
- **Scorecard on completion** — Check Run updated with a detailed Markdown table (category, test, pass/fail counts, pass rate, threshold, status)
- **PR comment** — Same scorecard posted as a pull request comment for inline visibility
- **Graceful error reporting** — On eval failure or timeout, posts an error summary to both the Check Run and PR comment
- **Block merge on failure** — Branch protection enforces the LLM Eval Agent Check Run as a required status check; PRs with failing evals cannot be merged

### Evaluation Engine (LangTest Harness)
- **Bias testing** — Pronoun-swap tests (`replace_to_female_pronouns`, `replace_to_male_pronouns`) detect gender bias in model predictions
- **Fairness testing** — Gender F1 score measurement across demographic groups
- **Robustness / Red-teaming** — Adversarial perturbations (`add_typo`, `american_to_british`) test model stability under noisy inputs
- **Config-driven test categories** — Enable/disable bias, fairness, or robustness via `config.yaml`; set per-category pass thresholds independently
- **Multi-model support** — Iterates over a `models` list in config, producing per-model result directories and reports
- **Async-safe execution** — LangTest runs in a dedicated thread with a fresh event loop to avoid conflicts with FastAPI's async runtime

---

## Data Management

- **Custom data upload** — `POST /upload-data` accepts a JSONL file, saves it to the `data/` directory, and updates a `_latest.txt` pointer so the next eval uses the new data automatically
- **Data file resolution** — Priority order: uploaded file (`_latest.txt`) → `DATA_FILE` env var → bundled `data/sample_data.jsonl`
- **JSONL format** — Each line: `{"text": "...", "label": 0|1}`; gender-balanced paired samples recommended for bias testing

---

## Reporting

- **JSON report** — Machine-readable per-run results saved to `results/{run_id}/{model}/langtest_report.json`
- **HTML report** — Visual LangTest report saved alongside JSON for local review
- **Scorecard format** — Markdown table with per-test breakdown: category, test name, passed count, failed count, pass rate, min required rate, status icon
- **Confidence score section** — Post-eval inference pass reports avg / min / max model confidence across scored samples; flags low-confidence results (< 75%) with a warning
- **Audit log** — Every eval appends a structured entry to `data/audit_log.jsonl` including timestamp, repo, PR number, commit SHA, model name, overall outcome, category results, and confidence statistics

---

## Additional Features

### Scheduled Evaluation
- Enabled via `schedule.enabled: true` and `schedule.cron: "0 0 * * 0"` in `config.yaml`
- APScheduler starts with the FastAPI app (lifespan) and fires the full eval pipeline on the configured cron schedule
- Results saved to `results/scheduled/<timestamp>/`; outcome appended to audit log
- Supports any standard 5-part cron expression; defaults to weekly Sunday midnight UTC

### Trend Chart
- `scripts/trend_chart.py` reads `data/audit_log.jsonl` (written after every eval — PR-triggered or scheduled)
- Outputs a Markdown table: date, model, per-category pass rate with ✅/❌, avg confidence, overall result
- ASCII sparklines (`▁▂▃▄▅▆▇█`) show score trajectory per category across runs
- `--output csv` exports all fields for spreadsheet analysis
- `--last N` limits to the most recent N runs
- `GET /trend?last=N` returns the same data as JSON via the API

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/webhook` | GitHub webhook receiver |
| `GET`  | `/health` | Liveness check |
| `POST` | `/run-tests` | Trigger eval manually (background task) |
| `GET`  | `/runs` | List all eval runs |
| `GET`  | `/status/{run_id}` | Poll status of a specific run |
| `GET`  | `/results/{run_id}` | List result files for a run |
| `GET`  | `/results/{run_id}/{filepath}` | Download a specific result file |
| `POST` | `/upload-data` | Upload a custom JSONL evaluation dataset |
| `GET`  | `/logs/{run_id}` | Retrieve logs for a run |
| `DELETE` | `/runs/{run_id}` | Delete a run and its results |
| `GET`  | `/trend` | Return audit log as JSON trend data (`?last=N` for last N runs) |
| `GET`  | `/debug/jwt` | Test GitHub App JWT auth (dev only) |
| `GET`  | `/debug/env` | Inspect environment variable config (dev only) |

---

## Research & Analysis Scripts

| Script | Description |
|--------|-------------|
| `scripts/run_eval.py` | Run a local eval with `--test-id` flag; outputs scorecard to stdout |
| `scripts/report.py` | Parse and render a saved JSON report as a scorecard table |
| `scripts/compare_models.py` | Compare results across multiple models; outputs Markdown or CSV comparison table |
| `scripts/domain_breakdown.py` | Split dataset by `domain` field, run per-domain eval, report breakdown |
| `scripts/trend_chart.py` | Read `audit_log.jsonl`, render Markdown table with pass rates + ASCII sparklines, export CSV |

---

## Configuration (`config/config.yaml`)

```yaml
models:
  - name: distilbert-base-uncased-finetuned-sst-2-english
    hub: huggingface
    type: text-classification

data:
  file: data/sample_data.jsonl

categories:
  - bias
  - robustness

bias_tests:
  - replace_to_female_pronouns
  - replace_to_male_pronouns

robustness_tests:
  - add_typo
  - american_to_british

thresholds:
  min_pass_rate: 0.8
  bias_min_pass_rate: 0.8
  robustness_min_pass_rate: 0.75

report:
  format: [json, html]
  dir: results
```

---

## Deployment

- **Platform** — Railway (auto-deploys from `master` branch on push)
- **Environment variables** — `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY` (base64-encoded PEM), `GITHUB_WEBHOOK_SECRET`
- **Eval timeout** — Configurable via `EVAL_TIMEOUT_SECONDS` (default: 600s); posts timeout error to PR on expiry
- **Memory requirement** — ≥ 1GB RAM recommended for transformer model inference (Railway Starter plan or equivalent)

---

## Security

- Webhook payloads verified with HMAC-SHA256 before processing
- Private key loaded from environment variable (base64-encoded) to avoid filesystem exposure
- Path traversal protection on all result file endpoints (`_safe_resolve`)
- Installation tokens scoped per-repository; no cross-repo access
- Debug endpoints (`/debug/jwt`, `/debug/env`) should be removed before public production deployment

---

## Feature Summary Table

| Feature | Status |
|---------|--------|
| PR-triggered webhook evaluation | ✅ Implemented |
| GitHub Check Run (in-progress → result) | ✅ Implemented |
| PR comment scorecard | ✅ Implemented |
| HMAC webhook signature verification | ✅ Implemented |
| JWT + installation token auth | ✅ Implemented |
| Bias testing (pronoun swap) | ✅ Implemented |
| Fairness testing (gender F1) | ✅ Implemented |
| Robustness / red-teaming (adversarial) | ✅ Implemented |
| Multi-model support | ✅ Implemented |
| Custom data upload (`POST /upload-data`) | ✅ Implemented |
| Per-test breakdown in scorecard | ✅ Implemented |
| Confidence score reporting | ✅ Implemented |
| Audit log (JSONL trail) | ✅ Implemented |
| Block merge on eval failure | ✅ Implemented |
| Eval timeout with graceful error post | ✅ Implemented |
| Multi-model comparison script | ✅ Implemented |
| Per-domain breakdown script | ✅ Implemented |
| HTML + JSON report generation | ✅ Implemented |
| Scheduled evaluation (cron) | ✅ Implemented |
| Trend chart over time | ✅ Implemented |
| Remediation hints on failure | 🔲 Planned |
