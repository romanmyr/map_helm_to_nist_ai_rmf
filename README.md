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
- `data/helm_to_nist_mapping.csv` — per-model results with 5 columns

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

## CSV Output

The CSV has one row per (model, category, NIST indicator) combination:

| Column | Description | Example values |
|---|---|---|
| Model | HELM model identifier | `openai/text-davinci-003`, `anthropic/stanford-online-all-v4-s3` |
| Category | HELM metric category | Accuracy, Fairness, Toxicity |
| weight | Category importance as % of total | 7.6%, 4.5% |
| stanford HELM signal | What HELM measures for this category | Accuracy metrics, Bias/fairness indicators, Prompt resilience |
| NIST AI RMF | Specific NIST indicator or failure flag | GOVERN 1.2, MAP 1.1, MEASURE 2.5, Do Not Use |

Each passed row maps to a specific NIST playbook indicator (e.g., GOVERN 1.2, MEASURE 2.11). Failed categories produce a single "Do Not Use" row per model/category.

Sample rows:

```csv
Model,Category,weight,stanford HELM signal,NIST AI RMF
openai/text-davinci-003,Accuracy,7.6%,Accuracy metrics,GOVERN 1.2
openai/text-davinci-003,Accuracy,7.6%,Accuracy metrics,MAP 1.1
openai/text-davinci-003,Accuracy,7.6%,Accuracy metrics,MEASURE 2.5
openai/text-davinci-003,Robustness,7.6%,Prompt resilience,Do Not Use
eleutherai/pythia-1b-v0,Bias,7.6%,Bias/fairness indicators,Do Not Use
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
          "category": "MEASURE-2",
          "description": "...",
          "topics": ["Fairness and Bias", ...],
          "mapping_weight": 0.125
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
