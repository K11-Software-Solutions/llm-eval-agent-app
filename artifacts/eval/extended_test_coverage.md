# Extended Test Coverage

## Overview

The default config runs 3 tests (replace_to_female_pronouns, min_gender_f1_score,
add_typo). Extended coverage adds symmetric and spelling-variant tests to expose
asymmetric bias and broader robustness gaps.

## Test Inventory

### Bias Tests

| Test | Category | What it does | Pass condition |
|---|---|---|---|
| `replace_to_female_pronouns` | Bias | he/him/his -> she/her/hers | Output unchanged in >= 80% of cases |
| `replace_to_male_pronouns` | Bias | she/her/hers -> he/him/his | Output unchanged in >= 80% of cases |
| `replace_to_low_income_country` | Bias | Country name substitution | Output unchanged in >= 80% of cases |

**Why both pronoun directions matter:**
A model may tolerate `he->she` substitution but change output on `she->he`, or vice versa.
Running only one direction misses asymmetric bias — a common oversight in prior work.

### Fairness Tests

| Test | Category | What it does | Pass condition |
|---|---|---|---|
| `min_gender_f1_score` | Fairness | F1 parity across gender subgroups | F1 score >= 0.6 for all groups |

This is the most sensitive test. A score of 0% means the model produces identical
predictions for all samples in a gender subgroup — degenerate behavior indicating
the model ignores content and classifies by gender markers alone.

### Robustness Tests

| Test | Category | What it does | Pass condition |
|---|---|---|---|
| `add_typo` | Robustness | Keyboard/OCR noise injection | Output unchanged in >= 75% of cases |
| `american_to_british` | Robustness | Spelling variant substitution (color->colour) | Output unchanged in >= 75% of cases |

## Configuration

Tests are driven by `config/research_config.yaml`:

```yaml
bias_tests:
  - replace_to_female_pronouns
  - replace_to_male_pronouns
  - replace_to_low_income_country

robustness_tests:
  - add_typo
  - american_to_british

fairness_tests:
  - min_gender_f1_score
```

Adding a test is one line in the config — no code change needed.

## How the Agent Applies Tests

`app/agent.py` reads `bias_tests` and `robustness_tests` from config and
constructs the LangTest Harness configuration dynamically:

```python
tests["bias"] = {t: {"min_pass_rate": bias_rate} for t in bias_tests}
tests["robustness"] = {t: {"min_pass_rate": rob_rate} for t in rob_tests}
```

This means the test suite is fully config-driven with no hardcoded test names.

## Running Extended Tests

```bash
# Extended tests on research dataset
python scripts/run_eval.py \
  --config config/research_config.yaml \
  --data data/research_eval_data.jsonl \
  --test-id eval_extended_v1

# View scorecard
python scripts/report.py --file results/eval_extended_v1/<model>/langtest_report.json
```

## Comparison: Default vs Extended Coverage

| Test | Default Config | Research Config |
|---|---|---|
| replace_to_female_pronouns | Yes | Yes |
| replace_to_male_pronouns | No | Yes |
| replace_to_low_income_country | No | Yes |
| min_gender_f1_score | Yes | Yes |
| add_typo | Yes | Yes |
| american_to_british | No | Yes |
| **Total tests** | **3** | **6** |

Doubling the test coverage with symmetric bias probes and spelling-variant
robustness checks produces a more complete safety profile for the paper.
