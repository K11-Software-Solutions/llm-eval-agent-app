# Implementation Details — LLM Eval Agent

**Author:** Kavita Jadhav, K11 Software Solutions LLC  
**Version:** 1.0  
**Date:** June 2026

---

## 1. Repository Structure

```
llm-eval-agent-app/
├── app/
│   ├── main.py            # FastAPI app, router registration
│   ├── api_server.py      # REST API endpoints
│   ├── webhook.py         # GitHub webhook handler
│   ├── github_client.py   # GitHub API: Check Runs + PR comments
│   ├── eval_runner.py     # Background eval task wrapper
│   ├── agent.py           # LLMEvalAgent (LangTest harness)
│   ├── scheduler.py       # Scheduled runs (cron)
│   ├── visualize.py       # Results chart generator
│   ├── llm_dashboard.py   # Streamlit dashboard
│   └── utils.py           # Config loader, logging setup
├── config/
│   └── config.yaml        # Default eval configuration
├── scripts/
│   ├── test_deployment.py # Automated deployment test script
│   └── report.py          # Readable scorecard generator
├── artifacts/
│   ├── k11_logo.png       # K11 Software Solutions logo
│   ├── DEPLOYMENT.md      # Deployment guide (owner reference)
│   └── docs/              # Project documentation
├── data/                  # Test data (gitignored)
├── results/               # Eval results (gitignored)
├── Dockerfile
├── docker-compose.yml
├── cloudbuild.yaml        # Google Cloud Build CI/CD
├── requirements.txt
└── .env.example
```

---

## 2. Key Implementation Decisions

### 2.1 Windows Path Compatibility
LangTest internally splits file paths using `"/"`. On Windows, `str(Path(...))` returns backslash-separated paths, causing an `IndexError`. All data file paths are converted to POSIX format before being passed to the LangTest Harness:

```python
# app/agent.py
self.data_file = Path(raw_data_file).as_posix() if raw_data_file else None
```

### 2.2 Import Fix
`app/main.py` previously imported a non-existent `app` object from `api_server`. The correct import is:

```python
from app.api_server import router as api_router  # not `app`
```

### 2.3 Dynamic PORT Binding
Railway and Cloud Run inject a `PORT` environment variable. The Dockerfile uses shell form CMD to evaluate it at runtime:

```dockerfile
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
```

### 2.4 Path Traversal Protection
All file access in the API server is validated to prevent directory traversal:

```python
def _safe_resolve(base: Path, relative: str) -> Path:
    p = (base / relative).resolve()
    if not str(p).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    return p
```

### 2.5 In-Memory Run Status
Run status is stored in a module-level dict (`RUN_STATUS`). This is intentionally simple for v1 but means status is lost on server restart. For production, replace with Redis or a database.

---

## 3. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |
| `POST` | `/run-tests` | Trigger an eval run (background task) |
| `GET` | `/runs` | List all run directories with status |
| `GET` | `/status/{run_id}` | Get status of a specific run |
| `GET` | `/results/{run_id}` | List result files for a run |
| `GET` | `/results/{run_id}/{filepath}` | Download a result file |
| `POST` | `/upload-data` | Upload test data (CSV or JSONL) |
| `GET` | `/logs/{run_id}` | Fetch run logs |
| `POST` | `/github/webhook` | GitHub webhook receiver |
| `GET` | `/docs` | Swagger UI (auto-generated) |

---

## 4. Eval Configuration

`config/config.yaml` controls all eval behavior:

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
  min_pass_rate: 0.8          # global default
  bias_min_pass_rate: 0.8
  min_gender_f1_score: 0.4    # fairness (lower = more lenient)
  robustness_min_pass_rate: 0.75

report:
  format: [json, html]
  dir: results
```

---

## 5. Test Data Format

Test data must be JSONL with `text` and `label` fields:

```jsonl
{"text": "The doctor reviewed her patient notes.", "label": 1}
{"text": "The product is terrible and broken.", "label": 0}
```

- `label: 1` = positive sentiment
- `label: 0` = negative sentiment
- Minimum recommended: 30 samples for Railway, 80+ for local runs
- For reliable fairness testing: include balanced male/female pronoun examples across both labels

---

## 6. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_APP_ID` | Yes | GitHub App numeric ID |
| `GITHUB_WEBHOOK_SECRET` | Yes | HMAC secret for webhook validation |
| `GITHUB_PRIVATE_KEY` | Yes (cloud) | Full PEM contents of private key |
| `GITHUB_PRIVATE_KEY_PATH` | Yes (local) | Path to `.pem` file |
| `RESULTS_DIR` | No | Override results directory (default: `results`) |
| `CONFIG_PATH` | No | Override config path (default: `config/config.yaml`) |
| `LLM_API_URL` | No | API URL for Streamlit dashboard (default: `http://localhost:8000`) |
| `PORT` | No | Server port injected by Railway/Cloud Run (default: `8080`) |
| `OPENAI_API_KEY` | No | For OpenAI model evaluation |
| `ANTHROPIC_API_KEY` | No | For Anthropic model evaluation |
| `HUGGINGFACE_TOKEN` | No | For private HuggingFace models |

---

## 7. Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| In-memory run status | Lost on restart | Use Redis or DB in production |
| Filesystem result storage | Not shared across instances | Use GCS/S3 in production |
| No log file handler | `/logs/{run_id}` always returns empty | Add `FileHandler` to `setup_logging()` |
| Railway free tier OOM | Model inference crashes at 512MB | Use Railway Starter ($5/mo) or Cloud Run |
| SST-2 domain mismatch | Fairness F1 low on non-review text | Use domain-matched model or lower threshold |

---

## 8. Dependencies

Key packages and their roles:

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | >=0.111.0 | REST API framework |
| `uvicorn` | >=0.29.0 | ASGI server |
| `langtest` | >=1.4.0 | Bias, fairness, robustness eval harness |
| `deepeval` | >=0.21.0 | Additional LLM eval metrics |
| `transformers` | >=4.40.0 | HuggingFace model loading |
| `torch` | >=2.2.0 | Model inference backend |
| `PyJWT` | >=2.8.0 | GitHub App JWT authentication |
| `streamlit` | >=1.35.0 | Dashboard UI |
| `psutil` | >=5.9.0 | System metrics (langtest dependency) |
| `pyyaml` | >=6.0.1 | Config file parsing |
