"""
Chapter 6: NLP — Risk Factor Extraction from Clinical Notes
Extracts structured risk factors for downstream ML models.

Extracts:
  - Smoking/tobacco history (pack-years, quit status)
  - Alcohol use (drinks/week)
  - Drug use history
  - Family history of conditions
  - Medication non-compliance
  - Social determinants of health (SDOH)
  - Functional status indicators
  - Fall risk indicators

Usage:
    python nlp/risk_extraction/risk_extractor.py
"""

import re
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

OUTPUT_DIR = Path("nlp/risk_extraction/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Risk Factor Patterns ────────────────────────────────────────────

RISK_PATTERNS = {

    # ── Smoking ─────────────────────────────────────────────────────
    "smoking_current": {
        "patterns": [
            r"\b(?:current(?:ly)?\s+smok|active\s+smok|smokes?\s+cigarette|still\s+smok)\w*",
            r"\btobacco\s+use\b",
        ],
        "negation": [r"\b(?:former|ex|quit|stopped|ceased|no longer)\b"],
        "weight": 0.9,
    },
    "smoking_former": {
        "patterns": [
            r"\b(?:former|ex|quit|stopped)\s+smok\w*",
            r"\b(?:smok\w*|tobacco)\b.*?\b(?:quit|stopped|ceased)\b",
            r"\bpack[- ]year\b",
        ],
        "negation": [],
        "weight": 0.6,
    },
    "pack_years": {
        "patterns": [r"(\d+(?:\.\d+)?)\s*pack[- ]year"],
        "extract_value": True,
        "unit": "pack-years",
        "weight": 0.7,
    },

    # ── Alcohol ─────────────────────────────────────────────────────
    "alcohol_use": {
        "patterns": [
            r"\balcohol(?:\s+use|ic)?\b",
            r"\bETOH\b",
            r"\bdrinks?\s+(?:per\s+)?(?:week|day|daily|nightly)\b",
            r"\bheavy\s+drink\w*",
        ],
        "negation": [r"\bdenies?\s+alcohol\b", r"\bno\s+alcohol\b"],
        "weight": 0.7,
    },

    # ── Drug Use ─────────────────────────────────────────────────────
    "illicit_drug_use": {
        "patterns": [
            r"\billicit\s+drug\b",
            r"\bcocaine\b",
            r"\bheroin\b",
            r"\bmeth(?:amphetamine)?\b",
            r"\bIV\s+drug\b",
            r"\binjection\s+drug\b",
            r"\bsubstance\s+(?:use|abuse)\b",
            r"\bIDU\b",
        ],
        "negation": [r"\bdenies?\b", r"\bno\s+(?:illicit|drug)\b"],
        "weight": 0.8,
    },

    # ── Family History ───────────────────────────────────────────────
    "family_hx_heart_disease": {
        "patterns": [
            r"\bfamily\s+history\b.*?\b(?:heart\s+disease|MI|cardiac|CAD|coronary)\b",
            r"\b(?:father|mother|brother|sister|sibling|parent)\b.*?\b(?:heart|cardiac|MI)\b",
        ],
        "negation": [r"\bno\s+family\s+history\b"],
        "weight": 0.7,
    },
    "family_hx_diabetes": {
        "patterns": [
            r"\bfamily\s+history\b.*?\bdiabet\w*\b",
            r"\b(?:father|mother|parent|sibling)\b.*?\bdiabet\w*\b",
        ],
        "negation": [],
        "weight": 0.6,
    },
    "family_hx_cancer": {
        "patterns": [
            r"\bfamily\s+history\b.*?\b(?:cancer|malignancy|tumor)\b",
            r"\b(?:father|mother|parent|sibling)\b.*?\b(?:cancer|malignancy)\b",
        ],
        "negation": [],
        "weight": 0.7,
    },

    # ── Medication Non-Compliance ────────────────────────────────────
    "med_noncompliance": {
        "patterns": [
            r"\bnon[-\s]?compli(?:ant|ance)\b",
            r"\bnot\s+taking\s+(?:his|her|their|the)?\s*medications?\b",
            r"\bstopped?\s+taking\b",
            r"\bmissed?\s+doses?\b",
            r"\bmedication\s+(?:noncompliance|non-compliance|adherence\s+issues?)\b",
        ],
        "negation": [],
        "weight": 0.8,
    },

    # ── Social Determinants of Health (SDOH) ────────────────────────
    "homelessness": {
        "patterns": [
            r"\bhomeless\b", r"\bhousing\s+insecure\b",
            r"\bshelter\b.*\b(?:living|staying)\b",
        ],
        "negation": [],
        "weight": 0.85,
    },
    "food_insecurity": {
        "patterns": [
            r"\bfood\s+insecuri\w*\b",
            r"\bcan(?:not|'t)\s+afford\s+(?:food|meals|groceries)\b",
            r"\bnutritional\s+(?:defici|insecuri)\w*\b",
        ],
        "negation": [],
        "weight": 0.80,
    },
    "social_isolation": {
        "patterns": [
            r"\bsocially?\s+isolated?\b",
            r"\blives?\s+alone\b",
            r"\bno\s+social\s+support\b",
            r"\bpoor\s+social\s+support\b",
        ],
        "negation": [],
        "weight": 0.70,
    },
    "transportation_barrier": {
        "patterns": [
            r"\btransportation\s+(?:issue|barrier|problem|concern)\b",
            r"\bno\s+(?:car|transportation|ride)\b",
            r"\bdifficulty\s+(?:getting\s+to|attending)\b",
        ],
        "negation": [],
        "weight": 0.65,
    },

    # ── Functional Status ────────────────────────────────────────────
    "fall_risk": {
        "patterns": [
            r"\bfall\s+risk\b",
            r"\bhistory\s+of\s+falls?\b",
            r"\bfrequent\s+falls?\b",
            r"\bbalance\s+(?:issue|problem|disorder)\b",
            r"\bgait\s+(?:instability|disturbance|abnormality)\b",
        ],
        "negation": [],
        "weight": 0.75,
    },
    "functional_decline": {
        "patterns": [
            r"\bADL\s+(?:assist|dependence|decline)\b",
            r"\bdecline\s+in\s+(?:function|ADL|activity)\b",
            r"\bwheelchair\b",
            r"\bbed[- ]bound\b",
            r"\bassist(?:ance)?\s+with\s+(?:ADL|daily\s+activities)\b",
        ],
        "negation": [],
        "weight": 0.70,
    },

    # ── Obesity ─────────────────────────────────────────────────────
    "obesity": {
        "patterns": [
            r"\bBMI\s+(?:of\s+)?(\d+(?:\.\d+)?)\b",
            r"\bOBESE\b",
            r"\bobesity\b",
            r"\bmorbidly\s+obese\b",
        ],
        "negation": [],
        "weight": 0.7,
    },
}


def check_negation(text: str, match_pos: int, window: int = 80) -> bool:
    """Check if a match is preceded by a negation phrase within window chars."""
    preceding = text[max(0, match_pos - window):match_pos].lower()
    negation_words = [
        "denies", "denied", "no ", "not ", "without", "negative for",
        "absence of", "no evidence", "no history of", "rules out"
    ]
    return any(neg in preceding for neg in negation_words)


def extract_risk_factors(text: str) -> Dict:
    """
    Extract all risk factors from clinical note text.
    Returns structured dict of identified risk factors.
    """
    text_lower = text.lower()
    results = {}

    for factor_name, config in RISK_PATTERNS.items():
        found = False
        extracted_value = None

        for pattern in config["patterns"]:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for m in matches:
                # Check negation
                if check_negation(text, m.start()):
                    continue
                # Additional per-factor negation patterns
                factor_negated = False
                for neg_pat in config.get("negation", []):
                    if re.search(neg_pat, text_lower):
                        factor_negated = True
                        break
                if factor_negated:
                    continue

                found = True
                # Extract numeric value if applicable
                if config.get("extract_value") and m.lastindex:
                    try:
                        extracted_value = float(m.group(1))
                    except (IndexError, ValueError):
                        pass
                break
            if found:
                break

        if found:
            results[factor_name] = {
                "present":   True,
                "weight":    config["weight"],
                "value":     extracted_value,
                "unit":      config.get("unit"),
            }

    return results


def compute_composite_risk_score(risk_factors: Dict) -> Dict:
    """
    Compute a composite social and clinical risk score (0-100).
    Higher = more at-risk patient.
    """
    if not risk_factors:
        return {"score": 0, "category": "Low", "drivers": [], "n_factors": 0}

    # Weighted sum of identified risks
    total_weight  = sum(v["weight"] for v in risk_factors.values())
    max_possible  = len(RISK_PATTERNS)  # normalise against total possible factors
    raw_score     = min(total_weight / max_possible * 100 * 2, 100)  # scale to 0-100

    category = (
        "Critical" if raw_score >= 70 else
        "High"     if raw_score >= 45 else
        "Moderate" if raw_score >= 20 else
        "Low"
    )

    drivers = sorted(risk_factors.keys(),
                     key=lambda k: risk_factors[k]["weight"],
                     reverse=True)[:5]

    return {
        "score":    round(raw_score, 1),
        "category": category,
        "drivers":  drivers,
        "n_factors": len(risk_factors),
    }
def process_notes_for_risk(notes_df: pd.DataFrame) -> pd.DataFrame:
    """Batch-process clinical notes and extract risk factors."""
    records = []
    for _, row in notes_df.iterrows():
        risks = extract_risk_factors(row.get("clinical_text", ""))
        composite = compute_composite_risk_score(risks)
        records.append({
            "note_id":           row.get("note_id", ""),
            "patient_id":        row.get("patient_id", ""),
            "risk_score":        composite["score"],
            "risk_category":     composite["category"],
            "n_risk_factors":    composite["n_factors"],
            "top_drivers":       ", ".join(composite["drivers"]),
            "smoking_current":   "smoking_current"  in risks,
            "smoking_former":    "smoking_former"   in risks,
            "alcohol_use":       "alcohol_use"      in risks,
            "drug_use":          "illicit_drug_use" in risks,
            "family_hx":         any(k.startswith("family_hx") for k in risks),
            "noncompliant":      "med_noncompliance" in risks,
            "fall_risk":         "fall_risk"         in risks,
            "sdoh_flag":         any(k in risks for k in ["homelessness","food_insecurity","transportation_barrier"]),
        })
    return pd.DataFrame(records)


def demo():
    notes = [
        {
            "note_id": "N001",
            "patient_id": "P0000001",
            "note_type": "Admission H&P",
            "clinical_text": """
            67-year-old male. Current smoker, 30 pack-year history.
            Admits to drinking 6-8 beers per week. No illicit drug use.
            Family history significant for coronary artery disease (father had MI at 58).
            Non-compliant with Lisinopril for past 3 months.
            BMI 34.2, obese. Lives alone, has no transportation to follow-up appointments.
            Fall risk — 2 falls in past 6 months.
            """,
        },
        {
            "note_id": "N002",
            "patient_id": "P0000002",
            "note_type": "Progress Note",
            "clinical_text": """
            54-year-old female. No smoking history. Denies alcohol use.
            No family history of diabetes or heart disease.
            Medications: taking all medications as prescribed.
            Lives with supportive spouse. Good functional status, ADL independent.
            """,
        },
        {
            "note_id": "N003",
            "patient_id": "P0000003",
            "note_type": "Social Work Note",
            "clinical_text": """
            Patient is homeless, currently staying in a shelter. Food insecure —
            relies on food bank. Stopped taking medications due to cost.
            History of IV drug use, denies current use. Former smoker, quit 2 years ago.
            Requires assistance with ADL. Wheelchair dependent.
            No family support. Social isolation noted.
            """,
        },
    ]

    print("="*60)
    print("RISK FACTOR EXTRACTION DEMO")
    print("="*60)

    all_results = []
    for note in notes:
        risks = extract_risk_factors(note["clinical_text"])
        composite = compute_composite_risk_score(risks)

        print(f"\nPatient: {note['patient_id']}  ({note['note_type']})")
        print(f"  Risk Score:    {composite['score']} / 100  [{composite['category']}]")
        print(f"  Risk Factors:  {composite['n_factors']}")
        print(f"  Top Drivers:   {', '.join(composite['drivers'])}")
        print(f"  Factors Found:")
        for factor, info in risks.items():
            val_str = f" = {info['value']} {info['unit']}" if info.get("value") else ""
            print(f"    + {factor.replace('_',' ').title()}{val_str}  (weight: {info['weight']})")

        all_results.append({
            "note_id":    note["note_id"],
            "patient_id": note["patient_id"],
            **{k: v["present"] for k, v in risks.items()},
            "composite_score": composite["score"],
            "risk_category":   composite["category"],
        })

    # Save results
    pd.DataFrame(all_results).to_csv(OUTPUT_DIR / "risk_extraction_demo.csv", index=False)
    logger.success(f"Demo results saved: {OUTPUT_DIR / 'risk_extraction_demo.csv'}")


if __name__ == "__main__":
    demo()

    # Batch mode from parquet
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data/raw")
    notes_path = data_dir / "clinical_notes"
    if notes_path.exists():
        notes_df = pd.read_parquet(notes_path).head(1000)
        results  = process_notes_for_risk(notes_df)
        results.to_csv(OUTPUT_DIR / "patient_risk_factors.csv", index=False)
        logger.info(f"\nRisk Score Distribution:\n{results['risk_category'].value_counts().to_string()}")
        logger.success(f"Risk extraction complete. Saved: {OUTPUT_DIR / 'patient_risk_factors.csv'}")
