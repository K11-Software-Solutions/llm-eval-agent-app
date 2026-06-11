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

### Step 1 — Generate a webhook secret

Run this locally to generate a secure random secret:

```bash
openssl rand -hex 32
```

Copy the output — you'll paste it in both GitHub and Railway.

### Step 2 — Create the GitHub App

1. Go to **GitHub → Settings → Developer Settings → GitHub Apps → New GitHub App**
2. Fill in the following fields:

| Field | Value |
|---|---|
| **App name** | `LLM Eval Agent` |
| **Homepage URL** | `https://llm-eval-agent-app-production.up.railway.app` |
| **Webhook URL** | `https://llm-eval-agent-app-production.up.railway.app/github/webhook` |
| **Webhook secret** | *(paste the secret generated above)* |

3. **Permissions** (Repository):
   - Checks: **Read & Write**
   - Contents: **Read**
   - Pull requests: **Read & Write**
   - Metadata: **Read** (mandatory)

4. **Subscribe to events:** check **Pull request**

5. Click **Create GitHub App**

### Step 3 — Save your App ID

After creation, you'll land on the app settings page.  
Note the **App ID** shown at the top (e.g. `1234567`).

### Step 4 — Generate a private key

1. Scroll down to **Private keys**
2. Click **Generate a private key**
3. A `*.pem` file downloads automatically — keep it safe

### Step 5 — Add credentials to Railway

In Railway dashboard → your service → **Variables**, add:

| Variable | Value |
|---|---|
| `GITHUB_APP_ID` | your App ID from Step 3 |
| `GITHUB_WEBHOOK_SECRET` | the secret from Step 1 |
| `GITHUB_PRIVATE_KEY` | full contents of the `.pem` file (including `-----BEGIN/END RSA PRIVATE KEY-----` lines) |

Railway auto-redeploys after saving. Health check to confirm:
```bash
curl https://llm-eval-agent-app-production.up.railway.app/health
```

### Step 6 — Install the app on a repo

1. GitHub App settings → **Install App** (left sidebar)
2. Choose your account → select a repo
3. Click **Install**

### Step 7 — Test with a Pull Request

Open a PR in the installed repo. Within seconds:
- A **Check Run** appears on the PR
- After eval completes, the check updates to pass/fail with a scorecard comment

**Debug tip:** GitHub App settings → **Advanced** → **Recent Deliveries** shows every webhook sent and your app's response code.

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
