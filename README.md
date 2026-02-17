# HELM to NIST AI RMF Mapping

Maps [HELM Classic](https://crfm.stanford.edu/helm/) benchmark metric categories to [NIST AI Risk Management Framework](https://airc.nist.gov/) playbook indicators.

## What It Does

This tool reads HELM v0.4.0 benchmark metadata and the NIST AI RMF playbook, then produces a weighted many-to-many mapping between HELM metric groups (accuracy, fairness, bias, toxicity, etc.) and NIST RMF indicators (GOVERN, MAP, MEASURE, MANAGE) based on topic-keyword alignment. Results are computed per model using HELM run data, with failed signals marked as "Do Not Use".

## Data Sources

- **HELM Classic v0.4.0** — `schema.json` (metric groups), `groups_metadata.json`, and `runs.json` (per-model results) from the [HELM benchmark](https://crfm.stanford.edu/helm/)
- **NIST AI RMF Playbook** — 72 entries downloaded from `https://airc.nist.gov/docs/playbook.json`

## Usage

```bash
# Requires: Python 3.10+ (stdlib only, no pip dependencies)
# Requires: HELM data at ../helm_download/data/v0.4.0/

python map_helm_to_nist.py
```

On first run, the NIST playbook is downloaded and cached to `data/playbook.json`. Subsequent runs use the cached copy.

Outputs:
- `data/helm_to_nist_mapping.json` — full mapping with metadata and weights
- `data/helm_to_nist_mapping.csv` — per-model results with 7 columns

## Mapping Strategy

1. **Keyword matching** — Each HELM metric group is associated with NIST playbook topics (e.g., fairness → "Fairness and Bias", robustness → "Secure and Resilient" + "Safety")
2. **Topic search** — For each HELM group, all 72 NIST playbook entries are searched for matching `Topic[]` tags, producing a many-to-many mapping
3. **Weight normalization** — Each HELM category has a risk tier (high=1.0, medium=0.6). The per-indicator weight = `tier_value / num_matched_indicators`
4. **Per-model status** — For each of the 70 models in `runs.json`, each metric group is checked for successful results (stat count > 0). Failed signals produce "Do Not Use" in the NIST column

## HELM Categories Mapped

| HELM Category | Weight Tier | NIST Topics Matched |
|---|---|---|
| Accuracy | high | Validity and Reliability |
| Calibration | medium | Validity and Reliability |
| Robustness | high | Secure and Resilient, Safety |
| Fairness | high | Fairness and Bias |
| Bias | high | Fairness and Bias |
| Toxicity | high | Safety |
| Efficiency | medium | Accountability and Transparency |
| Summarization metrics | medium | Validity and Reliability |
| Copyright metrics | medium | Legal and Regulatory |
| Disinformation metrics | high | Safety, Risky Emergent Behavior |
| BBQ metrics | high | Fairness and Bias |
| Classification metrics | medium | Validity and Reliability |

## Weight Calculation

### Weight Tiers

Each HELM category is assigned a risk tier based on how safety-critical it is:

| Tier | Value | Rationale | Categories |
|---|---|---|---|
| **high** | 1.0 | Directly measures safety, fairness, or core reliability — failure poses immediate risk | Accuracy, Robustness, Fairness, Bias, Toxicity, Disinformation, BBQ |
| **medium** | 0.6 | Important for trustworthiness but failure is less immediately dangerous | Calibration, Efficiency, Summarization, Copyright, Classification |

### Per-Indicator Weight (`mapping_weight`)

Each HELM category's tier value is split evenly across all NIST indicators it maps to:

```
mapping_weight = tier_value / num_matched_indicators
```

For example, Accuracy (high = 1.0) matches 8 NIST indicators, so each gets `1.0 / 8 = 0.125`.

### Category Weight (`weight` column)

The `weight` column in the CSV shows each category's tier value as a percentage of the total tier value across all 16 categories:

```
weight = (tier_value / sum_of_all_tier_values) × 100
```

The total across all 16 categories is 13.2 (9 high × 1.0 + 7 medium × 0.6). A high-tier category gets `1.0 / 13.2 = 7.6%`, a medium-tier gets `0.6 / 13.2 = 4.5%`.

### Type Weight (`type_weight` column)

The `type_weight` shows how much of the total possible assessment weight a given NIST function type (GOVERN, MAP, MEASURE, MANAGE) accounts for. It is computed as:

```
type_weight = (sum of mapping_weight for all passed indicators of this type) / sum_of_all_tier_values × 100
```

**Global (JSON):** Uses all categories (nothing failed), so GOVERN = 18.0%, MAP = 25.8%, MEASURE = 53.7%, MANAGE = 2.5%.

**Per-model (CSV):** Only includes categories that passed for that model. A model with failed categories will have lower type_weight percentages because the denominator stays the same (13.2) but the numerator shrinks. This means type_weight percentages for a given model may not sum to 100%.

## CSV Output

The CSV has one row per (model, category, NIST indicator) combination:

| Column | Description | Example values |
|---|---|---|
| Model | HELM model identifier | `openai/text-davinci-003`, `anthropic/stanford-online-all-v4-s3` |
| Category | HELM metric category | Accuracy, Fairness, Toxicity |
| weight | Category importance as % of total | 7.6%, 4.5% |
| stanford HELM signal | What HELM measures for this category | Accuracy metrics, Bias/fairness indicators, Prompt resilience |
| NIST AI RMF | Specific NIST indicator or failure flag | GOVERN 1.2, MAP 1.1, MEASURE 2.5, Do Not Use |
| type | NIST function type | GOVERN, MAP, MEASURE, MANAGE (empty for Do Not Use) |
| type_weight | Rolled-up total mapping weight for this NIST type for this model, as % | 18.0%, 53.7% (empty for Do Not Use) |

Each passed row maps to a specific NIST playbook indicator (e.g., GOVERN 1.2, MEASURE 2.11). Failed categories produce a single "Do Not Use" row per model/category with empty type and type_weight.

The `type_weight` is the sum of `mapping_weight` across all categories that map to indicators of a given NIST type for a given model. It varies per model because failed categories don't contribute.

Sample rows:

```csv
Model,Category,weight,stanford HELM signal,NIST AI RMF,type,type_weight
openai/text-davinci-003,Accuracy,7.6%,Accuracy metrics,GOVERN 1.2,GOVERN,18.0%
openai/text-davinci-003,Accuracy,7.6%,Accuracy metrics,MAP 1.1,MAP,25.8%
openai/text-davinci-003,Accuracy,7.6%,Accuracy metrics,MEASURE 2.5,MEASURE,53.7%
openai/text-davinci-003,Robustness,7.6%,Prompt resilience,Do Not Use,,
eleutherai/pythia-1b-v0,Bias,7.6%,Bias/fairness indicators,Do Not Use,,
```

When a model has no successful HELM results for a metric group, the NIST AI RMF column is set to "Do Not Use" instead of a specific indicator.

## JSON Output Format

```json
{
  "metadata": {
    "helm_version": "v0.4.0",
    "nist_source": "https://airc.nist.gov/docs/playbook.json",
    "generated": "2026-02-13T...",
    "description": "..."
  },
  "type_weights": {
    "GOVERN": "18.0%",
    "MAP": "25.8%",
    "MEASURE": "53.7%",
    "MANAGE": "2.5%"
  },
  "mappings": [
    {
      "helm_category": "fairness",
      "helm_display_name": "Fairness",
      "helm_metrics": ["${main_name}"],
      "helm_metric_count": 1,
      "weight_tier": "high",
      "nist_indicators": [
        {
          "title": "MEASURE 2.11",
          "type": "Measure",
          "nist_type": "MEASURE",
          "category": "MEASURE-2",
          "description": "...",
          "topics": ["Fairness and Bias", ...],
          "mapping_weight": 0.125,
          "type_weight": "53.7%"
        }
      ]
    }
  ]
}
```

## Project Structure

```
map_helm_to_nist_ai_rmf/
├── map_helm_to_nist.py    # Main script
├── .gitignore             # Excludes data/
├── README.md
└── data/                  # Created at runtime (git-ignored)
    ├── playbook.json      # Cached NIST AI RMF playbook
    ├── helm_to_nist_mapping.json  # JSON output (category-level)
    └── helm_to_nist_mapping.csv   # CSV output (per-model)
```
