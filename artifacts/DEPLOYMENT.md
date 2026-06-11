# Deployment Guide — LLM Eval Agent

## Local Development

```bash
git clone https://github.com/K11-Software-Solutions/llm-eval-agent-app
cd llm-eval-agent-app

cp .env.example .env
# Fill in GITHUB_APP_ID, GITHUB_WEBHOOK_SECRET, GITHUB_PRIVATE_KEY_PATH

pip install -r requirements.txt

# Start API server
uvicorn app.main:app --reload

# Start dashboard (separate terminal)
streamlit run app/llm_dashboard.py
```

Use [ngrok](https://ngrok.com) to expose your local server for webhook testing:

```bash
ngrok http 8000
# Copy the https URL → use as webhook URL in GitHub App settings
```

---

## Deploy to Google Cloud Run (recommended)

### One-time setup

```bash
# Authenticate and set project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

# Store GitHub App credentials in Secret Manager
echo -n "your_app_id" | gcloud secrets create GITHUB_APP_ID --data-file=-
echo -n "your_webhook_secret" | gcloud secrets create GITHUB_WEBHOOK_SECRET --data-file=-
cat private-key.pem | gcloud secrets create GITHUB_PRIVATE_KEY --data-file=-
```

### Deploy

```bash
gcloud run deploy llm-eval-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-secrets=GITHUB_APP_ID=GITHUB_APP_ID:latest,GITHUB_WEBHOOK_SECRET=GITHUB_WEBHOOK_SECRET:latest,GITHUB_PRIVATE_KEY=GITHUB_PRIVATE_KEY:latest \
  --set-env-vars=RESULTS_DIR=results,CONFIG_PATH=config/config.yaml
```

Your webhook URL will be:
```
https://llm-eval-agent-<hash>-uc.a.run.app/github/webhook
```

### Auto-deploy on push (CI/CD)

Connect the repo in **Google Cloud Console → Cloud Build → Triggers** to auto-deploy on every push to `master` using the included `cloudbuild.yaml`.

---

## Deploy to Railway

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Select `K11-Software-Solutions/llm-eval-agent-app`
3. Add environment variables from `.env.example`
4. Railway auto-detects the `Dockerfile` and deploys
5. Copy the generated public URL (e.g. `https://llm-eval-agent.up.railway.app`)

### Live deployment

| | |
|---|---|
| **Base URL** | `https://llm-eval-agent-app-production.up.railway.app` |
| **Health** | `https://llm-eval-agent-app-production.up.railway.app/health` |
| **Swagger docs** | `https://llm-eval-agent-app-production.up.railway.app/docs` |
| **Webhook URL** | `https://llm-eval-agent-app-production.up.railway.app/github/webhook` |

### Testing on Railway

```bash
# Health check
curl https://llm-eval-agent-app-production.up.railway.app/health

# Upload test data and trigger a run
curl -X POST https://llm-eval-agent-app-production.up.railway.app/upload-data \
  -F "file=@data/test_data.jsonl"

curl -X POST https://llm-eval-agent-app-production.up.railway.app/run-tests

# Poll status (use run_id from above response)
curl https://llm-eval-agent-app-production.up.railway.app/status/<run_id>

# Run dashboard locally against Railway backend
LLM_API_URL=https://llm-eval-agent-app-production.up.railway.app streamlit run app/llm_dashboard.py
```

---

## Register as a GitHub App

1. Go to **GitHub → Settings → Developer Settings → GitHub Apps → New GitHub App**
2. Fill in:
   - **App name:** LLM Eval Agent
   - **Homepage URL:** your deployed URL
   - **Webhook URL:** `https://YOUR-URL/github/webhook`
   - **Webhook secret:** generate a random string, add to `.env` as `GITHUB_WEBHOOK_SECRET`
3. **Permissions:**
   - Checks: Read & Write
   - Contents: Read
   - Pull requests: Read & Write
   - Metadata: Read (mandatory)
4. **Subscribe to events:** Pull request
5. Click **Create GitHub App**
6. Generate a private key → download `private-key.pem` → add to deployment
7. Note your **App ID** → add to `.env` as `GITHUB_APP_ID`

---

## Publish to GitHub Marketplace

Once the app is working on at least one repo:

1. Go to your GitHub App settings → **Edit**
2. Scroll to **Marketplace** → click **List this app on Marketplace**
3. GitHub will run a verification checklist (logo, description, pricing, support URL)
4. Add a free tier at minimum; optionally add paid plans via GitHub's billing
5. Submit for review

GitHub Marketplace listing requirements:
- A public GitHub App (not private)
- A homepage URL
- A support contact email
- At least one working installation
