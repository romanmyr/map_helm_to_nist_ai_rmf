# HELM to NIST AI RMF Mapping

Maps [HELM Classic](https://crfm.stanford.edu/helm/) benchmark metric categories to [NIST AI Risk Management Framework](https://airc.nist.gov/) playbook indicators.

## What It Does

This tool reads HELM v0.4.0 benchmark metadata and the NIST AI RMF playbook, then produces a weighted many-to-many mapping between HELM metric groups (accuracy, fairness, bias, toxicity, etc.) and NIST RMF indicators (GOVERN, MAP, MEASURE, MANAGE) based on topic-keyword alignment.

## Data Sources

- **HELM Classic v0.4.0** — `schema.json` (metric groups) and `groups_metadata.json` from the [HELM benchmark](https://crfm.stanford.edu/helm/)
- **NIST AI RMF Playbook** — 72 entries downloaded from `https://airc.nist.gov/docs/playbook.json`

## Usage

```bash
# Requires: Python 3.10+ (stdlib only, no pip dependencies)
# Requires: HELM data at ../helm_download/data/v0.4.0/

python map_helm_to_nist.py
```

On first run, the NIST playbook is downloaded and cached to `data/playbook.json`. Subsequent runs use the cached copy.

Output is written to `data/helm_to_nist_mapping.json`.

## Mapping Strategy

1. **Keyword matching** — Each HELM metric group is associated with NIST playbook topics (e.g., fairness → "Fairness and Bias", robustness → "Secure and Resilient" + "Safety")
2. **Topic search** — For each HELM group, all 72 NIST playbook entries are searched for matching `Topic[]` tags, producing a many-to-many mapping
3. **Weight normalization** — Each HELM category has a risk tier (high=1.0, medium=0.6). The per-indicator weight = `tier_value / num_matched_indicators`

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

## Output Format

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
    └── helm_to_nist_mapping.json  # Output mapping
```
