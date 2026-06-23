# Test Plan — LLM Eval Agent

**Author:** Kavita Jadhav, K11 Software Solutions LLC  
**Version:** 1.0  
**Date:** June 2026

---

## 1. Scope

This test plan covers functional, integration, and deployment verification for the LLM Eval Agent GitHub App. It does not cover load testing or multi-tenant scenarios (out of scope for v1).

---

## 2. Test Environments

| Environment | URL | Purpose |
|---|---|---|
| Local | `http://localhost:8000` | Development and unit testing |
| Railway (production) | `https://llm-eval-agent-app-production.up.railway.app` | Deployment verification |
| Google Cloud Run | `https://llm-eval-agent-<hash>-uc.a.run.app` | Alternative production |

---

## 3. Automated Deployment Tests

Run the automated test script against any deployment:

```bash
# Full test (requires 600MB+ RAM on the server)
python scripts/test_deployment.py

# API-only test (works on Railway free tier)
python scripts/test_deployment.py --skip-eval

# Against a specific URL
python scripts/test_deployment.py --url https://your-url.up.railway.app
```

### Test Cases Covered by Script

| # | Test | Endpoint | Expected |
|---|---|---|---|
| 1 | Health check | `GET /health` | `{"status":"ok"}` |
| 2 | Swagger UI | `GET /docs` | HTTP 200 |
| 3 | Upload test data | `POST /upload-data` | `{"status":"uploaded"}` |
| 4 | Trigger eval run | `POST /run-tests` | `{"status":"started", "run_id":"..."}` |
| 5 | Poll run status | `GET /status/{run_id}` | `{"status":"completed"}` |
| 6 | List result files | `GET /results/{run_id}` | JSON + HTML files present |
| 7 | Run appears in list | `GET /runs` | run_id in response |
| 8 | Webhook smoke test | `POST /github/webhook` | HTTP < 500 |

---

## 4. Manual Test Cases

### 4.1 GitHub App Webhook Integration

**Preconditions:** GitHub App installed on a test repo, Railway URL set as webhook URL.

| Step | Action | Expected Result |
|---|---|---|
| 1 | Open a PR in the test repo | GitHub sends `pull_request` event to webhook |
| 2 | Check Railway logs | `POST /github/webhook` appears with HTTP 200 |
| 3 | Check PR on GitHub | Check Run appears as "in progress" |
| 4 | Wait for eval to complete | Check Run updates to pass or fail |
| 5 | Check PR comments | Scorecard comment posted with category results |

**Debug:** GitHub App settings → Advanced → Recent Deliveries shows payload + response.

### 4.2 Webhook Signature Validation

| Test | Action | Expected |
|---|---|---|
| Valid signature | Send webhook with correct HMAC-SHA256 | HTTP 200, processed |
| Missing signature | Send webhook without `X-Hub-Signature-256` header | HTTP 400 or 401 |
| Invalid signature | Send webhook with wrong secret | HTTP 400 or 401 |

### 4.3 Upload and Eval Flow

| Test | Action | Expected |
|---|---|---|
| Valid JSONL | Upload `test_data.jsonl` | `{"status":"uploaded"}` |
| Valid CSV | Upload a CSV file | `{"status":"uploaded"}` |
| Invalid file type | Upload a `.txt` file | Handled gracefully |
| Trigger run after upload | `POST /run-tests` | Uses uploaded file |
| Trigger run without upload | `POST /run-tests` (no prior upload) | Uses default from config |

### 4.4 Result Retrieval

| Test | Action | Expected |
|---|---|---|
| List results | `GET /results/{run_id}` | Lists JSON and HTML files |
| Download JSON | `GET /results/{run_id}/model/langtest_report.json` | Valid JSON file |
| Download HTML | `GET /results/{run_id}/model/langtest_report.html` | Valid HTML file |
| Invalid run ID | `GET /results/nonexistent` | HTTP 404 |
| Path traversal | `GET /results/../../../etc/passwd` | HTTP 400 |

### 4.5 Dashboard

| Test | Action | Expected |
|---|---|---|
| Launch dashboard | `streamlit run app/llm_dashboard.py` | Opens at `localhost:8501` |
| Upload via UI | Click Upload, select JSONL file | Success message |
| Trigger run via UI | Click Start Test Run | Run ID shown |
| View runs table | Check runs list | Run appears with status badge |

---

## 5. Eval Quality Tests

### 5.1 Bias Test (`replace_to_female_pronouns`)

- **What it tests:** Model performance is consistent when male pronouns are replaced with female
- **Pass threshold:** 80% pass rate
- **Expected result with current data:** PASS (100%)

### 5.2 Fairness Test (`min_gender_f1_score`)

- **What it tests:** Model F1 score is comparable across male and female gendered samples
- **Pass threshold:** min_score >= 0.4
- **Expected result:** FAIL on DistilBERT SST-2 with workplace text (domain mismatch — this is a real finding)
- **Note:** This test requires balanced gender representation across both positive and negative labels

### 5.3 Robustness Test (`add_typo`)

- **What it tests:** Model predictions are stable when random typos are introduced
- **Pass threshold:** 75% pass rate
- **Expected result with current data:** PASS (94%)

---

## 6. Scorecard Report Test

```bash
# From local file
python scripts/report.py --file results/test_v2/distilbert-.../langtest_report.json

# From live Railway run (auto-fetches latest)
python scripts/report.py

# From specific run
python scripts/report.py --run-id <run_id>
```

Expected output: formatted table with category, pass/fail counts, rates, and overall verdict.

---

## 7. Regression Checklist

Run before every deployment:

- [ ] `python scripts/test_deployment.py --skip-eval` — all 3 API checks pass
- [ ] `GET /health` returns `{"status":"ok"}`
- [ ] `GET /docs` returns HTTP 200
- [ ] `POST /github/webhook` with ping returns HTTP < 500
- [ ] Local: `python scripts/test_deployment.py` — all 8 checks pass
- [ ] Local: `python scripts/report.py --file results/.../langtest_report.json` — scorecard renders correctly

---

## 8. Known Test Gaps

| Gap | Risk | Planned Fix |
|---|---|---|
| No automated webhook signature validation test | Medium | Add to test script with `--test-auth` flag |
| No log file content verification | Low | Add file handler to `setup_logging()` |
| No multi-model eval test | Low | Add second model to config for integration tests |
| Railway free tier OOM on full eval | High | Upgrade to Starter plan for CI eval runs |
