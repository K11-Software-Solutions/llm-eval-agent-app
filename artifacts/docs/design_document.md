# Design Document — LLM Eval Agent

**Author:** Kavita Jadhav, K11 Software Solutions LLC  
**Version:** 1.0  
**Date:** June 2026

---

## 1. Overview

LLM Eval Agent is a GitHub App that integrates automated bias, fairness, and robustness evaluation into the pull request lifecycle. Inspired by the shift-left principle from DevSecOps, it intercepts PR events and surfaces LLM safety scorecards as GitHub Check Runs and PR comments — blocking merge when thresholds are not met.

---

## 2. System Architecture

```
GitHub (PR event)
       │
       ▼ webhook POST
┌─────────────────────┐
│   FastAPI Server    │  ← app/main.py + app/webhook.py
│   (Railway / GCR)  │
└────────┬────────────┘
         │ background task
         ▼
┌─────────────────────┐
│   LLMEvalAgent      │  ← app/agent.py
│   (LangTest         │
│    Harness)         │
└────────┬────────────┘
         │ results
         ▼
┌─────────────────────┐     ┌──────────────────────┐
│   GitHub Client     │────▶│  GitHub Check Run    │
│   app/github_       │     │  + PR Comment        │
│   client.py         │     └──────────────────────┘
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   Results Store     │  ← /results/{run_id}/*.json|html
│   (filesystem)      │
└─────────────────────┘
```

---

## 3. Component Design

### 3.1 Webhook Handler (`app/webhook.py`)
- Receives `pull_request` events from GitHub
- Validates HMAC-SHA256 signature using `GITHUB_WEBHOOK_SECRET`
- Extracts repo, PR number, SHA, and installation ID
- Queues a background eval task

### 3.2 GitHub Client (`app/github_client.py`)
- Authenticates as GitHub App using JWT + installation token
- Creates a Check Run (`in_progress`) at webhook receipt
- Updates Check Run to `completed` (pass/fail) after eval
- Posts a formatted scorecard as a PR comment

### 3.3 Eval Agent (`app/agent.py`)
- Loads config from `config/config.yaml`
- Converts file paths to POSIX format for cross-platform compatibility
- Instantiates a LangTest `Harness` per model
- Runs bias, fairness, and robustness test suites
- Saves results as JSON and HTML reports

### 3.4 API Server (`app/api_server.py`)
- REST endpoints for manual runs, uploads, status polling, and log retrieval
- In-memory run status store (`RUN_STATUS` dict)
- Path traversal protection via `_safe_resolve()`

### 3.5 Dashboard (`app/llm_dashboard.py`)
- Streamlit UI for uploading test data, triggering runs, and viewing results
- Configurable via `LLM_API_URL` environment variable

---

## 4. Data Flow

1. Developer opens a PR → GitHub sends `pull_request` webhook
2. Webhook handler validates signature → queues background task
3. GitHub Client creates Check Run (`in_progress`)
4. Eval Agent loads test data → runs LangTest Harness
5. Results saved to `results/{run_id}/`
6. GitHub Client updates Check Run + posts PR comment scorecard
7. PR is blocked from merge if any category fails threshold

---

## 5. Security Design

| Concern | Mitigation |
|---|---|
| Webhook spoofing | HMAC-SHA256 signature validation on every request |
| Path traversal | `_safe_resolve()` validates all file paths stay within base dir |
| Credential exposure | GitHub App private key stored in Secret Manager / Railway env vars |
| Unauthenticated API | Webhook endpoint validates GitHub signature; REST API for internal use |

---

## 6. Deployment Architecture

| Environment | Platform | Notes |
|---|---|---|
| Production | Railway | Auto-deploys on push to `master` |
| Alternative | Google Cloud Run | `cloudbuild.yaml` included; Secret Manager for credentials |
| Local | uvicorn + ngrok | For development and webhook testing |

---

## 7. Technology Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| Eval Framework | LangTest (primary), DeepEval, Promptfoo |
| ML Models | HuggingFace Transformers (DistilBERT, etc.) |
| Dashboard | Streamlit |
| Auth | PyJWT + cryptography (GitHub App JWT) |
| Container | Docker (python:3.11-slim) |
| CI/CD | Railway (auto-deploy) / Google Cloud Build |

---

## 8. Scalability Considerations

- **Stateless design:** Run status is in-memory; a database (PostgreSQL/Redis) should replace `RUN_STATUS` for multi-instance deployments
- **Model loading:** Transformer models are loaded per-run; caching the model in memory would reduce latency for high-frequency repos
- **Filesystem results:** Should be replaced with cloud storage (GCS/S3) for persistent multi-instance access
- **Memory:** DistilBERT requires ~600MB RAM minimum; production deployments need at least 1GB allocated
