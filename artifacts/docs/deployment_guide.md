# Deployment Guide — LLM Eval Agent

**Author:** Kavita Jadhav, K11 Software Solutions LLC  
**Version:** 1.0  
**Date:** June 2026

---

## 1. Overview

LLM Eval Agent is packaged as a Docker container and can be deployed to any container platform. This document covers three deployment targets: local development, Railway (recommended for quick start), and Google Cloud Run (recommended for production).

---

## 2. Prerequisites

| Requirement | Details |
|---|---|
| GitHub App | Created and configured (see Section 5) |
| Webhook secret | Generated with `openssl rand -hex 32` |
| Private key | `.pem` file downloaded from GitHub App settings |
| App ID | Numeric ID from GitHub App settings page |
| Docker | Required for local container testing |
| Python 3.11+ | Required for local development (non-containerized) |

---

## 3. Local Development

### 3.1 Clone and configure

```bash
git clone https://github.com/K11-Software-Solutions/llm-eval-agent-app
cd llm-eval-agent-app

cp .env.example .env
# Edit .env — fill in GITHUB_APP_ID, GITHUB_WEBHOOK_SECRET, GITHUB_PRIVATE_KEY_PATH
```

### 3.2 Install dependencies

```bash
pip install -r requirements.txt
```

### 3.3 Start the API server

```bash
uvicorn app.main:app --reload --port 8000
```

Swagger UI available at: `http://localhost:8000/docs`

### 3.4 Start the dashboard (separate terminal)

```bash
streamlit run app/llm_dashboard.py
```

Dashboard available at: `http://localhost:8501`

### 3.5 Expose locally for webhook testing

```bash
ngrok http 8000
# Copy the https://xxx.ngrok.io URL
# Paste into GitHub App → Webhook URL
```

### 3.6 Run with Docker locally

```bash
docker build -t llm-eval-agent .
docker run -p 8080:8080 --env-file .env llm-eval-agent
```

---

## 4. Railway Deployment

### 4.1 Live deployment

| | |
|---|---|
| **Base URL** | `https://llm-eval-agent-app-production.up.railway.app` |
| **Health** | `https://llm-eval-agent-app-production.up.railway.app/health` |
| **Swagger docs** | `https://llm-eval-agent-app-production.up.railway.app/docs` |
| **Webhook URL** | `https://llm-eval-agent-app-production.up.railway.app/github/webhook` |

### 4.2 Initial setup

1. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
2. Select `K11-Software-Solutions/llm-eval-agent-app`
3. Railway auto-detects the `Dockerfile` and begins building

### 4.3 Environment variables

In Railway dashboard → service → **Variables**, add:

| Variable | Value |
|---|---|
| `GITHUB_APP_ID` | Your App ID |
| `GITHUB_WEBHOOK_SECRET` | Your webhook secret |
| `GITHUB_PRIVATE_KEY` | Full PEM contents (including BEGIN/END lines) |
| `RESULTS_DIR` | `results` |
| `CONFIG_PATH` | `config/config.yaml` |

### 4.4 Auto-deploy

Railway auto-redeploys on every push to `master`. No manual steps needed after initial setup.

### 4.5 Memory requirements

| Plan | RAM | Model Inference |
|---|---|---|
| Free | 512 MB | Not supported (OOM) |
| Starter ($5/mo) | 8 GB | Supported |

> DistilBERT requires ~600 MB RAM minimum. Use `--skip-eval` flag in the test script on the free tier.

### 4.6 Verify deployment

```bash
python scripts/test_deployment.py --skip-eval   # free tier
python scripts/test_deployment.py               # paid tier
```

---

## 5. Google Cloud Run Deployment

### 5.1 One-time setup

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

# Store credentials in Secret Manager
echo -n "your_app_id"       | gcloud secrets create GITHUB_APP_ID --data-file=-
echo -n "your_webhook_secret" | gcloud secrets create GITHUB_WEBHOOK_SECRET --data-file=-
cat private-key.pem           | gcloud secrets create GITHUB_PRIVATE_KEY --data-file=-
```

### 5.2 Deploy

```bash
gcloud run deploy llm-eval-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --set-secrets=GITHUB_APP_ID=GITHUB_APP_ID:latest,GITHUB_WEBHOOK_SECRET=GITHUB_WEBHOOK_SECRET:latest,GITHUB_PRIVATE_KEY=GITHUB_PRIVATE_KEY:latest \
  --set-env-vars=RESULTS_DIR=results,CONFIG_PATH=config/config.yaml
```

### 5.3 CI/CD via Cloud Build

Connect the repo in **Cloud Console → Cloud Build → Triggers** to auto-deploy on every push to `master` using the included `cloudbuild.yaml`.

### 5.4 Pricing estimate

| Resource | Free Tier | Typical Usage |
|---|---|---|
| Requests | 2M/month | Webhook-only: negligible |
| CPU | 180,000 vCPU-sec | Scales to zero between requests |
| Memory | 360,000 GB-sec | Free for light usage |
| Secret Manager | 6 versions free | 3 secrets = free |
| Cloud Build | 120 min/day | ~2-3 min per deploy = free |

---

## 6. GitHub App Setup

### 6.1 Generate webhook secret

```bash
openssl rand -hex 32
# Save the output — needed in both GitHub and Railway/Cloud Run
```

### 6.2 Create the GitHub App

1. Go to **GitHub → Settings → Developer Settings → GitHub Apps → New GitHub App**
2. Fill in:

| Field | Value |
|---|---|
| App name | `LLM Eval Agent` |
| Homepage URL | `https://llm-eval-agent-app-production.up.railway.app` |
| Webhook URL | `https://llm-eval-agent-app-production.up.railway.app/github/webhook` |
| Webhook secret | *(from step 6.1)* |

3. **Permissions (Repository):**
   - Checks: Read & Write
   - Contents: Read
   - Pull requests: Read & Write
   - Metadata: Read (mandatory)

4. **Subscribe to events:** Pull request

5. Click **Create GitHub App**

### 6.3 Post-creation steps

1. Note the **App ID** from the settings page
2. Scroll to **Private keys → Generate a private key** → save the `.pem` file
3. Go to **Install App** → select your account → choose repos → click **Install**

---

## 7. Deployment Verification

### 7.1 Quick check

```bash
curl https://llm-eval-agent-app-production.up.railway.app/health
# Expected: {"status":"ok"}
```

### 7.2 Full automated check

```bash
python scripts/test_deployment.py --skip-eval
```

### 7.3 End-to-end GitHub App test

1. Open a PR on a repo where the app is installed
2. Check Railway logs — webhook hit should appear within seconds
3. Check PR — Check Run should appear as "in progress"
4. After eval completes — Check Run updates + scorecard comment posted

---

## 8. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| 502 on Railway during eval | OOM — model needs 600MB+ RAM | Upgrade to Railway Starter |
| No webhook received | Webhook URL wrong or app not installed | Check GitHub App settings → Recent Deliveries |
| 401 on webhook | Webhook secret mismatch | Ensure Railway var matches GitHub App secret |
| Check Run never appears | `GITHUB_APP_ID` or `GITHUB_PRIVATE_KEY` wrong | Check Railway logs for auth errors |
| `No module named 'psutil'` | Missing dependency | Ensure `psutil>=5.9.0` in `requirements.txt`, redeploy |
| `ImportError: cannot import 'app'` | Stale code | Ensure `app/main.py` imports only `router` from `api_server` |
