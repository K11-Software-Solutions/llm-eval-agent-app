# LLM Eval Agent — GitHub App

<p align="center">
  <img src="artifacts/k11_logo.png" alt="K11 Software Solutions" width="200"/>
</p>

> Automated LLM safety & quality evaluation on every pull request.  
> Posts **bias, fairness, and robustness scorecards** as GitHub Check Runs and PR comments.

[![GitHub App](https://img.shields.io/badge/GitHub-App-blue?logo=github)](https://github.com/apps/llm-eval-agent)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

---

## How it works

1. Install the app on your repo
2. Open or update a PR that touches prompt files, YAML configs, or model configs
3. The app triggers an eval run using **LangTest**, **DeepEval**, or **Promptfoo**
4. A Check Run appears on your PR with pass/fail status
5. A scorecard comment is posted showing results by category

**Example PR comment:**

| Category | Pass Rate | Result |
|----------|-----------|--------|
| Bias | 91% | ✅ Pass |
| Fairness | 85% | ✅ Pass |
| Robustness | 72% | ❌ Fail |

**Overall: FAIL**

---

## Repo structure

```
llm-eval-agent-app/
├── app/
│   ├── main.py            # FastAPI entry point
│   ├── api_server.py      # REST API (run-tests, status, results, uploads)
│   ├── webhook.py         # GitHub webhook handler
│   ├── github_client.py   # GitHub API: Check Runs + PR comments
│   ├── eval_runner.py     # Background eval task
│   ├── agent.py           # LLMEvalAgent (LangTest harness)
│   ├── scheduler.py       # Scheduled runs
│   ├── visualize.py       # Results chart generator
│   ├── llm_dashboard.py   # Streamlit dashboard
│   └── utils.py           # Config loader, logging
├── config/
│   └── config.yaml        # Default eval config
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .github/
    └── app-manifest.json  # GitHub App registration manifest
```

---

## Local development

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

## Deploy to Railway (recommended for Marketplace)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Add environment variables from `.env.example`
4. Railway auto-detects the `Dockerfile` and deploys
5. Copy the generated public URL (e.g. `https://llm-eval-agent.up.railway.app`)

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

---

## Configuration

Edit `config/config.yaml` to customise models, categories, and thresholds.  
You can also POST to `/config` at runtime to update without redeploying.

```yaml
models:
  - name: distilbert-base-uncased-finetuned-sst-2-english
    hub: huggingface
    type: text-classification

categories:
  - bias
  - fairness
  - robustness

thresholds:
  min_pass_rate: 0.8
```

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/run-tests` | Trigger an eval run |
| `GET` | `/runs` | List all runs + status |
| `GET` | `/status/{run_id}` | Get run status |
| `GET` | `/results/{run_id}` | List result files |
| `GET` | `/results/{run_id}/{file}` | Download result file |
| `POST` | `/upload-data` | Upload test data |
| `GET` | `/logs/{run_id}` | Fetch run logs |
| `POST` | `/github/webhook` | GitHub webhook (internal) |
| `GET` | `/health` | Health check |

---

## License

Apache 2.0 — Copyright 2026 Kavita Jadhav / K11 Software Solutions LLC. See [LICENSE](LICENSE) for details.
