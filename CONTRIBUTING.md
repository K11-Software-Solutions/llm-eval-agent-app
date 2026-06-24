# Contributing to LLM Eval Agent

Thank you for your interest in contributing! LLM Eval Agent is an open-source GitHub App for automated LLM bias, fairness, robustness, and confidence evaluation on every pull request.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [How to Contribute](#how-to-contribute)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Feature Areas](#feature-areas)
- [Reporting Issues](#reporting-issues)

---

## Getting Started

1. **Fork** the repository: [K11-Software-Solutions/llm-eval-agent-app](https://github.com/K11-Software-Solutions/llm-eval-agent-app)
2. **Clone** your fork:
   ```bash
   git clone https://github.com/<your-username>/llm-eval-agent-app.git
   cd llm-eval-agent-app
   ```
3. **Create a branch** for your change:
   ```bash
   git checkout -b feature/your-feature-name
   ```

---

## Development Setup

### Prerequisites

- Python 3.11+
- Git

### Install dependencies

```bash
pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|----------|-------------|
| `GITHUB_APP_ID` | Your GitHub App's numeric ID |
| `GITHUB_PRIVATE_KEY` | PEM private key (or base64-encoded for Railway) |
| `GITHUB_WEBHOOK_SECRET` | Secret set in your GitHub App settings |
| `EVAL_TIMEOUT_SECONDS` | Max seconds for an eval run (default: 600) |
| `AUDIT_LOG_PATH` | Path to JSONL audit log (default: `data/audit_log.jsonl`) |

### Run locally

```bash
uvicorn app.main:app --reload --port 8000
```

Use [ngrok](https://ngrok.com) or [smee.io](https://smee.io) to tunnel webhooks to your local server during development.

### Run the eval manually

```bash
python scripts/run_eval.py --data data/sample_data.jsonl
```

---

## Project Structure

```
llm-eval-agent-app/
├── app/
│   ├── main.py            # FastAPI entry point + APScheduler lifespan
│   ├── api_server.py      # REST API endpoints
│   ├── webhook.py         # GitHub webhook handler (HMAC + event routing)
│   ├── github_client.py   # Check Runs, PR comments, scorecard formatting
│   ├── eval_runner.py     # Background eval task, audit log, confidence scoring
│   ├── agent.py           # LLMEvalAgent (LangTest harness wrapper)
│   ├── scheduler.py       # APScheduler cron-based scheduled eval
│   └── utils.py           # Config loader, logging helpers
├── scripts/
│   ├── run_eval.py        # Local eval runner with scorecard output
│   ├── generate_charts.py # Trend chart PNG generator
│   ├── trend_chart.py     # CLI trend table + sparklines
│   ├── compare_models.py  # Multi-model comparison table
│   ├── domain_breakdown.py# Per-domain eval breakdown
│   └── report.py          # Parse + render saved JSON reports
├── config/
│   └── config.yaml        # Default eval config (models, categories, thresholds)
├── data/
│   ├── sample_data.jsonl  # 30-sample gender-balanced test dataset
│   └── audit_log.jsonl    # Persistent eval audit log
├── tests/                 # Pytest test suite (109 tests)
├── artifacts/
│   ├── docs/              # Research documents and guides
│   └── eval/              # Eval result artifacts and charts
└── results/               # Local eval run outputs (gitignored)
```

---

## How to Contribute

### Bug fixes

1. Open an [issue](https://github.com/K11-Software-Solutions/llm-eval-agent-app/issues) describing the bug
2. Reference the issue in your PR
3. Include a regression test that fails before your fix and passes after

### New features

1. Open an issue to discuss the feature before implementing
2. Keep scope focused — one feature per PR
3. Add tests covering the new code paths
4. Update `artifacts/docs/application_features.md` feature table

### Documentation

- Research docs live in `artifacts/docs/`
- User-facing docs go in the repo root or `artifacts/docs/`
- Do not create `README` files unless explicitly needed

### Evaluation test categories

To add a new LangTest test category (e.g. `toxicity`, `stereotype`):

1. Add the category name to `config/config.yaml` under `categories`
2. Add the test list (e.g. `toxicity_tests`) in `config.yaml`
3. Handle the new category in `app/agent.py::_build_tests_config()`
4. Add a threshold key in `config.yaml` under `thresholds`
5. Add unit tests in `tests/`

---

## Code Standards

- **Python 3.11+** — use native type hints (`list[str]`, `dict[str, int]`, `X | None`)
- **No comments** unless the *why* is non-obvious (a workaround, hidden constraint, or surprising invariant)
- **No docstrings** on trivial functions — function names should be self-explanatory
- **No extra abstractions** — solve the problem at hand; do not design for hypothetical future requirements
- **No backwards-compatibility shims** — if something is unused, delete it
- **Error handling only at boundaries** — trust internal code; validate at webhook receipt and API input only
- **Security** — never log secrets; always verify webhook HMAC; use `_safe_resolve()` for file paths

---

## Testing

Run the full test suite:

```bash
pytest tests/ -v
```

Expected: **109 tests, all passing, ~30 seconds**

### Test files

| File | What it covers |
|------|---------------|
| `tests/test_api.py` | REST endpoints, upload, path traversal |
| `tests/test_eval_runner.py` | `_parse_results`, `format_scorecard`, config |
| `tests/test_new_features.py` | Confidence, audit log, red-teaming, block merge, trend, scheduler |
| `tests/test_charts.py` | PNG generation, dimensions, load/dedup |
| `tests/test_report.py` | Report parsing and rendering |
| `tests/test_utils.py` | Config and data loading |
| `tests/test_webhook.py` | HMAC, file triggers, event routing |

### Writing tests

- Use `tmp_path` (pytest fixture) for all file I/O — never write to the real `data/` or `results/` dirs in tests
- Use `monkeypatch` to swap module-level paths (e.g. `AUDIT_LOG_PATH`, `BASE_DIR`)
- Use `unittest.mock.patch` for external calls (HuggingFace pipeline, GitHub API)
- Integration tests that hit real files should use `pytest.skip()` if the file is absent

---

## Submitting a Pull Request

1. **Run tests** and confirm all pass:
   ```bash
   pytest tests/ -v
   ```

2. **Push your branch** and open a PR against `master`:
   ```bash
   git push origin feature/your-feature-name
   ```

3. **PR title** — use the format: `type: short description`
   - `feat:` new feature
   - `fix:` bug fix
   - `test:` tests only
   - `docs:` documentation only
   - `refactor:` restructuring without behavior change

4. **PR description** — include:
   - What the change does
   - Why it's needed
   - How to test it manually

5. The **LLM Eval Agent** itself will run a Check Run on your PR if you have the GitHub App installed. This is the app eating its own dog food.

---

## Feature Areas

Looking for ideas? Here are open areas:

| Area | Idea |
|------|------|
| **Evaluation** | Add `toxicity` or `stereotype` test categories via LangTest |
| **Evaluation** | Add `deepeval` metric support (faithfulness, answer relevance) |
| **Reporting** | HTML report served via `/results/{run_id}/report.html` endpoint |
| **Reporting** | Remediation hints — suggest fixes for failing test categories |
| **Infrastructure** | Support GitHub Enterprise Server webhook URLs |
| **Infrastructure** | Redis-backed run status store (replace in-memory `RUN_STATUS` dict) |
| **Data** | Multi-language test datasets (beyond English SST-2) |
| **Dashboard** | Streamlit dashboard connected to live audit log |

---

## Reporting Issues

- **Bug reports:** [Open an issue](https://github.com/K11-Software-Solutions/llm-eval-agent-app/issues) with reproduction steps, expected vs. actual behavior, and relevant logs
- **Security issues:** Email `kavitaj11@gmail.com` directly — do not open a public issue for security vulnerabilities
- **Questions:** Open a [GitHub Discussion](https://github.com/K11-Software-Solutions/llm-eval-agent-app/discussions)

---

## License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).

---

*Built by [Kavita Jadhav](https://github.com/kavitaj11) · K11 Software Solutions LLC*
