"""Map HELM Classic benchmark metric categories to NIST AI RMF playbook indicators.

Reads HELM v0.4.0 schema.json and groups_metadata.json, downloads the NIST AI RMF
playbook, and produces a weighted many-to-many mapping from HELM metric groups to
NIST RMF indicators based on topic-keyword alignment.

Dependencies: stdlib only (json, urllib, pathlib, datetime, csv)
"""

import csv
import json
import urllib.request
import urllib.error
import ssl
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
HELM_DIR = PROJECT_DIR.parent / "helm_download" / "data" / "v0.4.0"

NIST_PLAYBOOK_URL = "https://airc.nist.gov/docs/playbook.json"
NIST_PLAYBOOK_PATH = DATA_DIR / "playbook.json"
OUTPUT_PATH = DATA_DIR / "helm_to_nist_mapping.json"
CSV_OUTPUT_PATH = DATA_DIR / "helm_to_nist_mapping.csv"

# ---------------------------------------------------------------------------
# HELM metric group -> NIST topic keyword mapping & weight tiers
# ---------------------------------------------------------------------------
# Each entry maps a HELM metric_group name to:
#   - keywords: list of substrings to match against NIST Topic[] entries
#   - weight_tier: "high" (1.0), "medium" (0.6), or "low" (0.3)
HELM_TO_NIST_TOPIC_MAP = {
    "accuracy": {
        "keywords": ["Validity and Reliability"],
        "weight_tier": "high",
    },
    "calibration": {
        "keywords": ["Validity and Reliability"],
        "weight_tier": "medium",
    },
    "calibration_detailed": {
        "keywords": ["Validity and Reliability"],
        "weight_tier": "medium",
    },
    "robustness": {
        "keywords": ["Secure and Resilient", "Safety"],
        "weight_tier": "high",
    },
    "robustness_detailed": {
        "keywords": ["Secure and Resilient", "Safety"],
        "weight_tier": "high",
    },
    "fairness": {
        "keywords": ["Fairness and Bias"],
        "weight_tier": "high",
    },
    "fairness_detailed": {
        "keywords": ["Fairness and Bias"],
        "weight_tier": "high",
    },
    "bias": {
        "keywords": ["Fairness and Bias"],
        "weight_tier": "high",
    },
    "toxicity": {
        "keywords": ["Safety"],
        "weight_tier": "high",
    },
    "efficiency": {
        "keywords": ["Accountability and Transparency"],
        "weight_tier": "medium",
    },
    "efficiency_detailed": {
        "keywords": ["Accountability and Transparency"],
        "weight_tier": "medium",
    },
    "summarization_metrics": {
        "keywords": ["Validity and Reliability"],
        "weight_tier": "medium",
    },
    "copyright_metrics": {
        "keywords": ["Legal and Regulatory"],
        "weight_tier": "medium",
    },
    "disinformation_metrics": {
        "keywords": ["Safety", "Risky Emergent Behavior"],
        "weight_tier": "high",
    },
    "bbq_metrics": {
        "keywords": ["Fairness and Bias"],
        "weight_tier": "high",
    },
    "classification_metrics": {
        "keywords": ["Validity and Reliability"],
        "weight_tier": "medium",
    },
}

WEIGHT_TIER_VALUES = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.3,
}


def load_json(path: Path) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def download_nist_playbook() -> list:
    """Download the NIST AI RMF playbook JSON and cache it locally."""
    if NIST_PLAYBOOK_PATH.exists():
        print(f"  Using cached playbook at {NIST_PLAYBOOK_PATH}")
        return load_json(NIST_PLAYBOOK_PATH)

    print(f"  Downloading NIST AI RMF playbook from {NIST_PLAYBOOK_URL} ...")
    # Create an SSL context that works in restrictive environments
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        NIST_PLAYBOOK_URL,
        headers={"User-Agent": "helm-nist-mapper/1.0"},
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        # Fallback: try without certificate verification for corporate proxies
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            raw = resp.read()

    playbook = json.loads(raw)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(NIST_PLAYBOOK_PATH, "w", encoding="utf-8") as f:
        json.dump(playbook, f, indent=2)
    print(f"  Saved playbook ({len(playbook)} entries) to {NIST_PLAYBOOK_PATH}")
    return playbook


def extract_helm_metric_groups(schema: dict) -> dict:
    """Extract metric groups from HELM schema.json into {name: {display_name, metrics[]}}."""
    groups = {}
    for mg in schema.get("metric_groups", []):
        name = mg["name"]
        metrics = [m["name"] for m in mg.get("metrics", [])]
        groups[name] = {
            "display_name": mg.get("display_name", name),
            "description": mg.get("description", ""),
            "metrics": metrics,
            "metric_count": len(metrics),
        }
    return groups


def match_nist_indicators(playbook: list, keywords: list[str]) -> list[dict]:
    """Find NIST playbook entries whose Topic[] contains any of the given keywords."""
    matched = []
    for entry in playbook:
        topics = entry.get("Topic", [])
        # Handle case where Topic might be a string instead of list
        if isinstance(topics, str):
            topics = [topics]
        # Check if any keyword appears as a substring in any topic
        for kw in keywords:
            kw_lower = kw.lower()
            if any(kw_lower in t.lower() for t in topics):
                matched.append({
                    "title": entry.get("title", ""),
                    "type": entry.get("type", ""),
                    "nist_type": entry.get("type", "").upper(),
                    "category": entry.get("category", ""),
                    "description": entry.get("description", ""),
                    "topics": topics,
                })
                break  # avoid duplicate entries for the same playbook item
    return matched


def build_mapping(
    helm_groups: dict,
    playbook: list,
) -> list[dict]:
    """Build the HELM -> NIST mapping with computed weights."""
    from collections import defaultdict

    mappings = []
    for group_name, topic_config in HELM_TO_NIST_TOPIC_MAP.items():
        if group_name not in helm_groups:
            continue

        helm_info = helm_groups[group_name]
        keywords = topic_config["keywords"]
        weight_tier = topic_config["weight_tier"]
        tier_value = WEIGHT_TIER_VALUES[weight_tier]

        nist_indicators = match_nist_indicators(playbook, keywords)

        # Compute per-indicator weight:
        # category_weight * (1 / num_matched_indicators) to normalize
        num_indicators = len(nist_indicators) if nist_indicators else 1
        per_indicator_weight = round(tier_value / num_indicators, 4)

        for indicator in nist_indicators:
            indicator["mapping_weight"] = per_indicator_weight

        mappings.append({
            "helm_category": group_name,
            "helm_display_name": helm_info["display_name"],
            "helm_metrics": helm_info["metrics"],
            "helm_metric_count": helm_info["metric_count"],
            "weight_tier": weight_tier,
            "nist_indicators": nist_indicators,
        })

    # Compute type_weight: rolled-up total of mapping_weight per NIST type
    # across all categories
    type_weight_totals: dict[str, float] = defaultdict(float)
    for m in mappings:
        for indicator in m["nist_indicators"]:
            nist_type = indicator["nist_type"]
            type_weight_totals[nist_type] += indicator["mapping_weight"]

    # Convert to percentages and attach to each indicator
    grand_total = sum(type_weight_totals.values())
    if grand_total > 0:
        type_weights = {
            t: f"{round((w / grand_total) * 100, 1)}%"
            for t, w in type_weight_totals.items()
        }
    else:
        type_weights = {t: "0.0%" for t in type_weight_totals}
    for m in mappings:
        for indicator in m["nist_indicators"]:
            indicator["type_weight"] = type_weights[indicator["nist_type"]]

    return mappings, type_weights


# ---------------------------------------------------------------------------
# HELM metric group -> representative metric names for status detection
# ---------------------------------------------------------------------------
# Maps each HELM metric group to the stat names and perturbation names used
# in runs.json to determine whether runs produced results (count > 0) or
# failed (count == 0).
HELM_GROUP_STAT_KEYS = {
    "accuracy": {"name": "exact_match"},
    "calibration": {"name": "ece_10_bin"},
    "calibration_detailed": {"name": "ece_10_bin"},
    "robustness": {"name": None, "perturbation_name": "robustness"},
    "robustness_detailed": {"name": None, "perturbation_name": "typos"},
    "fairness": {"name": None, "perturbation_name": "fairness"},
    "fairness_detailed": {"name": None, "perturbation_name": "dialect"},
    "bias": {"name": "bias_metric", "match": "prefix"},
    "toxicity": {"name": "toxic_frac"},
    "efficiency": {"name": "inference_denoised_runtime"},
    "efficiency_detailed": {"name": "inference_runtime"},
    "summarization_metrics": {"name": "summac"},
    "copyright_metrics": {"name": "longest_common_prefix_length"},
    "disinformation_metrics": {"name": "self_bleu"},
    "bbq_metrics": {"name": "bbq_metric_ambiguous_bias"},
    "classification_metrics": {"name": "classification_macro_f1"},
}


def _stat_matches_group(stat_name: str, perturbation: str, keys: dict) -> bool:
    """Check if a stat entry matches a HELM group's stat key definition."""
    expected_name = keys.get("name")
    expected_pert = keys.get("perturbation_name", "")
    match_mode = keys.get("match", "exact")

    if expected_pert:
        return perturbation == expected_pert
    if not expected_name:
        return False
    if perturbation:
        return False
    if match_mode == "prefix":
        return stat_name.startswith(expected_name)
    return stat_name == expected_name


def compute_per_model_signal_status(runs: list) -> tuple[dict[tuple[str, str], str], list[str]]:
    """Determine pass/fail status per (model, HELM metric group) from runs.json.

    Returns:
        status: dict mapping (model_name, group_name) -> "passed" | "failed"
        models: sorted list of unique model names
    """
    from collections import defaultdict

    # (model, group) -> {success: int, total: int}
    success_counts: dict[tuple[str, str], int] = defaultdict(int)
    total_counts: dict[tuple[str, str], int] = defaultdict(int)
    all_models: set[str] = set()

    for run in runs:
        model = run["run_spec"]["adapter_spec"]["model"]
        all_models.add(model)

        for stat in run.get("stats", []):
            stat_name = stat["name"]["name"]
            perturbation = stat["name"].get("perturbation_name", "")
            count = stat.get("count", 0)

            for group, keys in HELM_GROUP_STAT_KEYS.items():
                if _stat_matches_group(stat_name, perturbation, keys):
                    key = (model, group)
                    total_counts[key] += 1
                    if count > 0:
                        success_counts[key] += 1

    models = sorted(all_models)
    status = {}
    for model in models:
        for group in HELM_GROUP_STAT_KEYS:
            key = (model, group)
            if total_counts[key] == 0 or success_counts[key] == 0:
                status[key] = "failed"
            else:
                status[key] = "passed"

    return status, models


# ---------------------------------------------------------------------------
# Descriptive HELM signal labels for the CSV output
# ---------------------------------------------------------------------------
# Describes what each HELM metric group measures, used in the
# "stanford HELM signal" CSV column.
HELM_SIGNAL_LABELS = {
    "accuracy": "Accuracy metrics",
    "calibration": "Calibration scores",
    "calibration_detailed": "Calibration scores",
    "robustness": "Prompt resilience",
    "robustness_detailed": "Prompt resilience",
    "fairness": "Bias/fairness indicators",
    "fairness_detailed": "Bias/fairness indicators",
    "bias": "Bias/fairness indicators",
    "toxicity": "Toxicity metrics",
    "efficiency": "Inference efficiency",
    "efficiency_detailed": "Inference efficiency",
    "summarization_metrics": "Summarization quality",
    "copyright_metrics": "Copyright/memorization metrics",
    "disinformation_metrics": "Disinformation generation metrics",
    "bbq_metrics": "Bias/fairness indicators",
    "classification_metrics": "Classification accuracy",
}


def _compute_per_model_type_weights(
    mappings: list[dict],
    signal_status: dict[tuple[str, str], str],
    models: list[str],
) -> dict[tuple[str, str], float]:
    """Compute rolled-up type weight per (model, NIST type).

    For each model, sums the mapping_weight of all passed indicators grouped
    by NIST type (GOVERN, MAP, MEASURE, MANAGE).
    """
    from collections import defaultdict

    totals: dict[tuple[str, str], float] = defaultdict(float)
    for model in models:
        for m in mappings:
            is_failed = signal_status.get((model, m["helm_category"])) == "failed"
            if is_failed:
                continue
            for indicator in m["nist_indicators"]:
                nist_type = indicator["nist_type"]
                totals[(model, nist_type)] += indicator["mapping_weight"]

    # Convert to percentages using total possible weight as denominator
    # so that failed categories reduce the percentage
    grand_total = sum(
        WEIGHT_TIER_VALUES[m["weight_tier"]] for m in mappings
    )

    result = {}
    for (model, nist_type), val in totals.items():
        result[(model, nist_type)] = round((val / grand_total) * 100, 1) if grand_total > 0 else 0.0
    return result


def write_csv(
    mappings: list[dict],
    signal_status: dict[tuple[str, str], str],
    models: list[str],
) -> None:
    """Write the mapping to a CSV with columns:
    Model, Category, weight, stanford HELM signal, NIST AI RMF, type, type_weight

    One row per (model, category, NIST indicator) combination.
    - weight: percentage of total weight across all categories
    - stanford HELM signal: descriptive label of what HELM measures
    - NIST AI RMF: specific NIST indicator, or 'Do Not Use' if model failed
    - type: NIST function type (GOVERN, MAP, MEASURE, MANAGE)
    - type_weight: rolled-up total mapping_weight for this NIST type for this model
    """
    total_weight = sum(
        WEIGHT_TIER_VALUES[m["weight_tier"]] for m in mappings
    )

    model_type_weights = _compute_per_model_type_weights(
        mappings, signal_status, models
    )

    rows = []
    for model in models:
        for m in mappings:
            category = m["helm_display_name"]
            tier_value = WEIGHT_TIER_VALUES[m["weight_tier"]]
            weight_pct = f"{(tier_value / total_weight) * 100:.1f}%"
            helm_signal = HELM_SIGNAL_LABELS.get(
                m["helm_category"], m["helm_display_name"]
            )
            is_failed = signal_status.get((model, m["helm_category"])) == "failed"

            if is_failed or not m["nist_indicators"]:
                rows.append([
                    model, category, weight_pct, helm_signal,
                    "Do Not Use", "", "",
                ])
                continue

            for indicator in m["nist_indicators"]:
                nist_type = indicator["nist_type"]
                type_wt = model_type_weights.get((model, nist_type), 0.0)
                type_wt_pct = f"{type_wt}%"
                rows.append([
                    model, category, weight_pct, helm_signal,
                    indicator["title"].upper(), nist_type, type_wt_pct,
                ])

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CSV_OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Model", "Category", "weight", "stanford HELM signal",
            "NIST AI RMF", "type", "type_weight",
        ])
        writer.writerows(rows)


def print_summary(mappings: list[dict]) -> None:
    """Print a summary table of the mapping."""
    print("\n" + "=" * 90)
    print(f"{'HELM Category':<30} {'Tier':<8} {'NIST Indicators':<10} {'Top NIST Match':<35}")
    print("-" * 90)
    for m in mappings:
        top_match = m["nist_indicators"][0]["title"] if m["nist_indicators"] else "(none)"
        print(
            f"{m['helm_display_name']:<30} "
            f"{m['weight_tier']:<8} "
            f"{len(m['nist_indicators']):<10} "
            f"{top_match:<35}"
        )
    print("=" * 90)

    total_pairs = sum(len(m["nist_indicators"]) for m in mappings)
    print(f"\nTotal HELM categories mapped: {len(mappings)}")
    print(f"Total HELM->NIST pairs:       {total_pairs}")


def main() -> None:
    print("=== HELM -> NIST AI RMF Mapping ===\n")

    # Step 1: Load HELM data
    print("[1/5] Loading HELM schema and groups metadata...")
    schema_path = HELM_DIR / "schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"HELM schema not found at {schema_path}")
    schema = load_json(schema_path)
    helm_groups = extract_helm_metric_groups(schema)
    print(f"  Found {len(helm_groups)} metric groups in schema.json")

    groups_meta_path = HELM_DIR / "groups_metadata.json"
    if groups_meta_path.exists():
        groups_meta = load_json(groups_meta_path)
        print(f"  Found {len(groups_meta)} entries in groups_metadata.json")
    else:
        groups_meta = {}
        print("  groups_metadata.json not found, continuing without it")

    # Step 2: Download NIST playbook
    print("\n[2/5] Fetching NIST AI RMF playbook...")
    playbook = download_nist_playbook()
    print(f"  Playbook has {len(playbook)} entries")

    # Step 3: Load HELM runs for per-model signal status
    print("\n[3/7] Loading HELM runs for per-model signal status...")
    runs_path = HELM_DIR / "runs.json"
    if runs_path.exists():
        runs = load_json(runs_path)
        print(f"  Loaded {len(runs)} runs from runs.json")
        signal_status, models = compute_per_model_signal_status(runs)
        print(f"  Found {len(models)} models")
        passed = sum(1 for s in signal_status.values() if s == "passed")
        failed = sum(1 for s in signal_status.values() if s == "failed")
        print(f"  Per-model signal status: {passed} passed, {failed} failed")
    else:
        runs = []
        signal_status = {}
        models = []
        print("  runs.json not found, assuming all signals passed")

    # Step 4: Build mapping
    print("\n[4/7] Matching HELM metric groups to NIST indicators via topic keywords...")
    mappings, type_weights = build_mapping(helm_groups, playbook)
    print(f"  Produced {len(mappings)} category mappings")
    print(f"  Type weights: {type_weights}")

    # Step 5: Save JSON output
    print("\n[5/7] Saving JSON mapping to disk...")
    output = {
        "metadata": {
            "helm_version": "v0.4.0",
            "nist_source": NIST_PLAYBOOK_URL,
            "generated": datetime.now(timezone.utc).isoformat(),
            "description": (
                "Mapping from HELM Classic benchmark metric categories "
                "to NIST AI RMF playbook indicators, weighted by category "
                "importance and normalized by match count."
            ),
        },
        "type_weights": type_weights,
        "mappings": mappings,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"  Saved to {OUTPUT_PATH}")

    # Step 6: Save CSV output
    print("\n[6/7] Saving CSV mapping to disk...")
    write_csv(mappings, signal_status, models)
    print(f"  Saved to {CSV_OUTPUT_PATH}")

    # Step 7: Print summary
    print("\n[7/7] Summary")
    print_summary(mappings)


if __name__ == "__main__":
    main()
