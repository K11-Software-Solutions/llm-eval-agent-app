# Multi-Model Comparison

## Overview

The LLM Eval Agent supports evaluating multiple models in a single run.
This is critical for research papers to show that:
- Bias and fairness findings are **model-specific**, not tool artifacts
- The evaluation framework is **model-agnostic**
- Different architectures exhibit different bias profiles

## Models Compared

| Model | Architecture | Parameters | Fine-tuning |
|---|---|---|---|
| `distilbert-base-uncased-finetuned-sst-2-english` | DistilBERT | 66M | SST-2 sentiment |
| `textattack/bert-base-uncased-SST-2` | BERT-base | 110M | SST-2 sentiment |
| `textattack/roberta-base-SST-2` | RoBERTa | 125M | SST-2 sentiment |

All three are fine-tuned on the Stanford Sentiment Treebank (SST-2), meaning any
fairness differences reflect architectural or training biases, not task differences.

## How to Run

```bash
# Full multi-model eval on research dataset
python scripts/run_eval.py \
  --config config/research_config.yaml \
  --data data/research_eval_data.jsonl \
  --test-id eval_run_multimodel

# Generate comparison table
python scripts/compare_models.py --run-id eval_run_multimodel

# Export as CSV (paste into paper spreadsheet)
python scripts/compare_models.py --run-id eval_run_multimodel --csv
```

## Config: `config/research_config.yaml`

The research config adds two models to the default single-model config:

```yaml
models:
  - name: distilbert-base-uncased-finetuned-sst-2-english
    hub: huggingface
    type: text-classification
  - name: textattack/bert-base-uncased-SST-2
    hub: huggingface
    type: text-classification
  - name: textattack/roberta-base-SST-2
    hub: huggingface
    type: text-classification
```

Results are stored per-model under `results/<run_id>/<model_name>/`.

## Expected Output Structure

```
results/eval_run_multimodel/
  distilbert-base-uncased-finetuned-sst-2-english/
    langtest_report.json
    langtest_report.html
  textattack_bert-base-uncased-SST-2/
    langtest_report.json
    langtest_report.html
  textattack_roberta-base-SST-2/
    langtest_report.json
    langtest_report.html
```

## Interpreting Results for the Paper

- **Bias (replace_to_female/male_pronouns):** A PASS means pronoun swaps do not change
  the model's output — a desirable property. A FAIL means the model is sensitive to
  gendered language, a potential bias signal.

- **Fairness (min_gender_f1_score):** Measures whether F1 score is equal across male-
  and female-gendered subsets. A score of 0% means the model predicts the same class
  for all inputs in one gender group — indicating degenerate, biased behavior.

- **Robustness (add_typo, american_to_british):** A model that fails on typos is
  fragile. Models used in real-world LLM pipelines must handle noisy input.

## Paper Table Template

| Test | DistilBERT | BERT-base | RoBERTa |
|---|---|---|---|
| Bias: female pronouns | | | |
| Bias: male pronouns | | | |
| Fairness: gender F1 | | | |
| Robustness: typos | | | |
| Robustness: spelling variants | | | |
| **Overall** | | | |

Fill with PASS/FAIL and pass-rate percentages from `compare_models.py --csv`.
