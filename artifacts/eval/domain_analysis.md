# Domain-Level Analysis

## Overview

Running evaluation across the full dataset gives aggregate scores, but bias
can be **domain-specific**. A model might be fair in healthcare language but
biased in workplace language. The domain breakdown surfaces these differences.

## Research Dataset Domains

The `data/research_eval_data.jsonl` dataset covers 5 real-world domains with
gender-matched sentence pairs (each sentence exists in male, female, and
neutral form):

| Domain | Samples | What is tested |
|---|---|---|
| workplace | 24 | Performance reviews, promotion, project delivery |
| healthcare | 20 | Diagnosis, treatment, research, errors |
| education | 20 | Scholarship, graduation, cheating, dropout |
| social | 16 | Volunteering, misconduct, community impact |
| tech | 20 | Engineering, open source, outages, security |
| neutral | 20 | Domain-agnostic (no gendered pronouns) |

## How to Run

```bash
# Run per-domain eval (uses default config)
python scripts/domain_breakdown.py

# Use research dataset explicitly
python scripts/domain_breakdown.py \
  --data data/research_eval_data.jsonl \
  --test-id domain_study_v1

# CSV output for paper table
python scripts/domain_breakdown.py \
  --data data/research_eval_data.jsonl \
  --test-id domain_study_v1 \
  --csv
```

## Output Structure

```
results/domain_study_v1/
  workplace/
    distilbert-base-uncased-finetuned-sst-2-english/
      langtest_report.json
  healthcare/
    ...
  education/
    ...
  social/
    ...
  tech/
    ...
  domain_summary.json       <- aggregated table
```

`domain_summary.json` contains pass/fail counts per domain per model —
directly usable as a paper table.

## Why This Matters

Aggregate scores can mask domain-level disparities. For example:

- A model may pass bias tests on healthcare sentences (clinical, neutral language)
  but fail on workplace sentences (performance evaluations use more gendered language)
- Fairness failure may be concentrated in one domain, which points to training
  data imbalance in that domain

This is a stronger finding than an aggregate number: it tells practitioners
*where* to focus remediation.

## Paper Table Template

| Domain | Samples | Bias Pass% | Fairness F1 | Robustness Pass% | Overall |
|---|---|---|---|---|---|
| workplace | | | | | |
| healthcare | | | | | |
| education | | | | | |
| social | | | | | |
| tech | | | | | |
| **All domains** | | | | | |

## Adding New Domains

Add rows to `data/research_eval_data.jsonl` with `"domain": "your_domain"`.
The `domain_breakdown.py` script auto-discovers all domain values — no code change needed.
