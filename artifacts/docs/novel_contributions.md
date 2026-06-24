# Novel Contributions — LLM Eval Agent

**Author:** Kavita Jadhav, K11 Software Solutions LLC  
**Date:** June 2026  
**Repository:** [K11-Software-Solutions/llm-eval-agent-app](https://github.com/K11-Software-Solutions/llm-eval-agent-app)

---

## 1. Prior Work Analysis

### 1.1 LLM Evaluation Frameworks

Existing LLM evaluation frameworks operate as standalone tools or research benchmarks. None provide native GitHub App integration with PR-level merge enforcement.

| Tool | Organization | Scope | GitHub App? | PR Gate? | Bias/Fairness? | Audit Log? |
|------|-------------|-------|:-----------:|:--------:|:--------------:|:----------:|
| **EleutherAI LM Eval Harness** | EleutherAI | Benchmarks (MMLU, HellaSwag) | ❌ | ❌ | ❌ | ❌ |
| **OpenAI Evals** | OpenAI | GPT model evaluation | ❌ | ❌ | Partial | ❌ |
| **HELM** | Stanford CRFM | Holistic LLM benchmarking | ❌ | ❌ | ✅ | ❌ |
| **DeepEval** | Confident AI | LLM unit testing | ❌ | ❌ | Partial | ❌ |
| **TruLens** | TruEra | RAG pipeline evaluation | ❌ | ❌ | ❌ | Partial |
| **Ragas** | explodinggradients | RAG evaluation | ❌ | ❌ | ❌ | ❌ |
| **PromptFlow** | Microsoft | LLM pipeline orchestration | ❌ | ❌ | Partial | ❌ |
| **LangTest** | John Snow Labs | NLP safety testing harness | ❌ | ❌ | ✅ | ❌ |

### 1.2 ML Fairness Libraries

Fairness toolkits exist as Python libraries or dashboards. None integrate with GitHub's CI/CD pipeline.

| Tool | Organization | Scope | GitHub App? | PR Gate? |
|------|-------------|-------|:-----------:|:--------:|
| **AI Fairness 360 (AIF360)** | IBM | Bias detection + mitigation | ❌ | ❌ |
| **Fairlearn** | Microsoft | Fairness assessment + mitigation | ❌ | ❌ |
| **What-If Tool** | Google | Interactive fairness exploration | ❌ | ❌ |
| **Responsible AI Toolbox** | Microsoft | Fairness + explainability dashboard | ❌ | ❌ |
| **FairML** | Julius Adebayo | Bias in ML predictions | ❌ | ❌ |

### 1.3 GitHub Apps for Code/ML Quality

Existing GitHub Apps focus on code quality, security, or generic ML pipelines — not LLM-specific safety evaluation.

| App | Scope | LLM Bias? | Robustness? | Confidence? |
|-----|-------|:---------:|:-----------:|:-----------:|
| **SonarQube** | Code quality, security | ❌ | ❌ | ❌ |
| **CodeClimate** | Code maintainability | ❌ | ❌ | ❌ |
| **GitGuardian** | Secret scanning | ❌ | ❌ | ❌ |
| **Snyk** | Vulnerability scanning | ❌ | ❌ | ❌ |
| **DagsHub** | ML experiment tracking | ❌ | ❌ | ❌ |
| **Weights & Biases** | ML training monitoring | ❌ | ❌ | Partial |

### 1.4 MLOps & CI/CD for ML

MLOps platforms provide model registry and pipeline tracking but do not surface evaluation results as GitHub Check Runs.

| Platform | PR Integration | Check Runs API | Block Merge? |
|----------|:--------------:|:--------------:|:------------:|
| MLflow | ❌ | ❌ | ❌ |
| Kubeflow | ❌ | ❌ | ❌ |
| Vertex AI Pipelines | ❌ | ❌ | ❌ |
| GitHub Actions (custom) | ✅ (Workflow) | Partial | Partial |
| CML (DVC) | ✅ (Comments) | ❌ | ❌ |

> **Note on GitHub Actions:** Teams can write custom Actions to run eval scripts, but these are workflow files (not GitHub Apps) and lack the persistent installation, webhook routing, JWT authentication, and Check Runs API integration that a proper GitHub App provides. Each repo must duplicate the workflow configuration; there is no shared app layer.

---

## 2. Identified Gaps in Prior Work

Based on the survey above, the following capabilities are absent from all existing tools:

1. **No GitHub App** for LLM bias/fairness/robustness evaluation exists on the GitHub Marketplace or in open-source as of August 2025.

2. **No PR-level merge gate** for LLM safety — existing tools are dashboards, CLIs, or research benchmarks. None use the GitHub Check Runs API to enforce a pass/fail result that blocks PR merges.

3. **No longitudinal audit log** tied to specific PRs, commit SHAs, repositories, and models — existing tools produce point-in-time results without a structured history.

4. **No confidence scoring** integrated into a bias/robustness evaluation pipeline within a CI/CD context.

5. **No real-time trend tracking** of LLM safety metrics across PRs in a developer workflow.

6. **No adversarial red-teaming** (typo injection, spelling variants) as a PR merge gate — existing tools treat robustness as a standalone benchmark, not a deployment requirement.

---

## 3. Novel Contributions

### Contribution 1 — GitHub App for LLM Safety Evaluation

**What:** A production-deployed GitHub App that installs on any repository and fires LLM safety evaluations automatically on every pull request via GitHub webhook events.

**How it differs:** Uses GitHub's native Check Runs API (not GitHub Actions) to report results. This means:
- Results appear in the PR's **Checks tab** alongside CI tests
- The app is a shared service — installed once, works across all repos
- Authentication uses GitHub App JWT + per-installation access tokens (more secure than PATs)
- No per-repo workflow files needed

**Implementation:** `app/webhook.py` (HMAC-SHA256 verification) → `app/eval_runner.py` (async background task) → `app/github_client.py` (Check Runs + PR comments)

---

### Contribution 2 — PR-Level Merge Enforcement for LLM Safety

**What:** Integration with GitHub branch protection to block PR merges when bias or robustness thresholds are not met. The LLM safety check becomes a required status check, equal in standing to unit tests or security scans.

**How it differs:** No prior tool blocks code deployment based on LLM evaluation results. This closes the gap between model evaluation (research) and model deployment (engineering).

**Demonstrated:** PR #4 on `kavitaj11/llm-eval-demo` was automatically blocked (`conclusion=failure`) on its first commit due to a timeout, and unblocked (`conclusion=success`) once the eval passed. No manual intervention was required.

**Implementation:** `app/eval_runner.py` → `github_client.update_check_run(conclusion="failure")` + GitHub branch protection requiring "LLM Eval Agent" check (App ID 4031993)

---

### Contribution 3 — Integrated Adversarial Red-Teaming in CI/CD

**What:** Adversarial robustness tests (`add_typo`, `american_to_british`) are run as standard CI checks on every PR alongside bias tests. A model that fails robustness is blocked from merging, the same as a model that fails bias.

**How it differs:** Red-teaming is typically a research-time or pre-deployment activity. This contribution embeds adversarial evaluation into the continuous integration loop, making it a first-class deployment gate.

**Results:** On 30-sample `sample_data.jsonl`, `add_typo` generated 25–28 adversarial test cases in < 2 seconds of test generation time. Pass rates: 82–86% across runs, consistently above the 75% threshold.

**Implementation:** `config/config.yaml` (`robustness_tests: [add_typo, american_to_british]`) → `app/agent.py` (`_build_tests_config`) → LangTest harness

---

### Contribution 4 — Confidence Score Reporting in PR Scorecards

**What:** After the LangTest evaluation completes, a second inference pass scores model confidence (avg/min/max) across the dataset and includes it in the Check Run scorecard.

**How it differs:** LLM evaluation tools report pass/fail on specific tests. Adding the model's own confidence distribution reveals whether the model is borderline uncertain even on cases it predicted correctly. A model with 55% minimum confidence on routine inputs warrants scrutiny even if bias tests pass.

**Results (PR #4):** Avg confidence 95.3%, min 55.0%, max 100.0% across 30 samples. The 55% minimum flagged 2–3 samples where the model was near-random in its prediction.

**Implementation:** `app/eval_runner.py::_compute_confidence()` using `transformers.pipeline` capped at 50 samples

---

### Contribution 5 — Structured Audit Log with Longitudinal Trend Tracking

**What:** Every evaluation (PR-triggered or scheduled) appends a structured JSON record to `data/audit_log.jsonl`, including timestamp, repository, PR number, commit SHA, model name, per-category pass rates, confidence statistics, and overall verdict.

**How it differs:** No existing LLM eval tool maintains a per-commit audit trail tied to the GitHub repository and PR graph. This enables:
- Detection of safety regression over time
- Evidence trail for compliance and governance
- Research data collection without manual instrumentation

**Demonstrated:** 5 evaluation runs recorded across May–June 2026, exposed via `GET /trend` API and visualised as a time-series chart with ASCII sparklines.

**Implementation:** `app/eval_runner.py::_append_audit_log()` + `scripts/trend_chart.py` + `scripts/generate_charts.py`

---

### Contribution 6 — Scheduled Drift Detection

**What:** An APScheduler-backed cron job that runs the full eval pipeline on a configured schedule (default: weekly Sunday midnight UTC) without requiring a PR trigger. Results are written to the audit log.

**Why it matters:** Model bias and fairness can drift even when code does not change — due to upstream model updates, data distribution shifts, or dependency version changes. Scheduled eval catches drift between PR cycles.

**Implementation:** `app/scheduler.py` (APScheduler, CronTrigger) wired into FastAPI lifespan in `app/main.py`

---

## 4. Contribution Summary Table

| Contribution | Prior Work | LLM Eval Agent |
|-------------|-----------|----------------|
| GitHub App for LLM safety | ❌ None | ✅ Installable, webhook-driven |
| PR merge gate on LLM eval | ❌ None | ✅ Check Runs API + branch protection |
| Adversarial red-teaming in CI | ❌ Research-time only | ✅ Required status check per PR |
| Confidence scoring in scorecard | ❌ None | ✅ Avg/min/max per eval run |
| Structured per-commit audit log | ❌ None | ✅ JSONL with SHA + PR reference |
| Longitudinal trend tracking | ❌ Point-in-time only | ✅ Time-series chart + `/trend` API |
| Scheduled drift detection | ❌ None | ✅ APScheduler cron integration |
| Multi-model comparison in CI | ❌ Dashboard only | ✅ Per-model Check Runs + CSV export |

---

## 5. Positioning Statement for Research Paper

> *"Existing LLM safety evaluation frameworks (EleutherAI LM Eval Harness, HELM, DeepEval, LangTest) and fairness toolkits (IBM AIF360, Microsoft Fairlearn) operate as standalone tools external to the software development lifecycle. MLOps platforms (MLflow, Vertex AI) track experiments but do not surface results as GitHub Check Runs or enforce them as merge gates. LLM Eval Agent introduces the first open-source GitHub App that integrates LLM bias, fairness, robustness, and confidence evaluation directly into the pull request workflow, enforcing safety thresholds as mandatory deployment gates. Its audit log and trend tracking provide a longitudinal safety record tied to specific commits and PRs — a capability absent from all prior tools."*

---

## 6. References

1. Gao et al. (2021). *A Framework for Few-Shot Language Model Evaluation.* EleutherAI. (LM Eval Harness)
2. Liang et al. (2022). *Holistic Evaluation of Language Models.* Stanford CRFM. (HELM)
3. Kocmi & Federmann (2023). *Large Language Models Are State-of-the-Art Evaluators of Translation Quality.* (LLM-as-judge)
4. Mehrabi et al. (2021). *A Survey on Bias and Fairness in Machine Learning.* ACM Computing Surveys.
5. John Snow Labs (2023). *LangTest: A Comprehensive NLP Testing Library.*
6. GitHub (2023). *GitHub Apps — Building GitHub Apps.* GitHub Developer Documentation.
7. Sculley et al. (2015). *Hidden Technical Debt in Machine Learning Systems.* NeurIPS.
