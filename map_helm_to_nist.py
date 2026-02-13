"""Map HELM Classic benchmark metric categories to NIST AI RMF playbook indicators.

Reads HELM v0.4.0 schema.json and groups_metadata.json, downloads the NIST AI RMF
playbook, and produces a weighted many-to-many mapping from HELM metric groups to
NIST RMF indicators based on topic-keyword alignment.

Dependencies: stdlib only (json, urllib, pathlib, datetime)
"""

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

    return mappings


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

    # Step 3: Build mapping
    print("\n[3/5] Matching HELM metric groups to NIST indicators via topic keywords...")
    mappings = build_mapping(helm_groups, playbook)
    print(f"  Produced {len(mappings)} category mappings")

    # Step 4: Save output
    print("\n[4/5] Saving mapping to disk...")
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
        "mappings": mappings,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"  Saved to {OUTPUT_PATH}")

    # Step 5: Print summary
    print("\n[5/5] Summary")
    print_summary(mappings)


if __name__ == "__main__":
    main()
