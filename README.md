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
