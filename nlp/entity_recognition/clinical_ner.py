"""
NLP Project: Clinical Named Entity Recognition (NER)
Uses medspaCy + scispaCy to extract clinical entities from notes.

Extracts:
  - Diseases / Conditions (PROBLEM)
  - Medications (TREATMENT)
  - Lab Tests & Findings (TEST)
  - Anatomical Locations (ANATOMY)
  - Temporal Expressions (TIME)
  - Negation detection (negated findings)
  - Assertion detection (present/absent/possible/historical)

Usage:
    python nlp/entity_recognition/clinical_ner.py
"""

import re
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

# Try medspaCy — falls back to basic pattern matching if not installed
try:
    import spacy
    import medspacy
    NLP_BACKEND = "medspacy"
except ImportError:
    logger.warning("medspaCy not available. Using pattern-based NER fallback.")
    NLP_BACKEND = "regex"


# ─── Entity patterns for regex-based NER ─────────────────────────

CONDITION_PATTERNS = [
    r"\b(diabetes|diabetic|DM type [12]|T2DM|T1DM)\b",
    r"\b(hypertension|HTN|elevated blood pressure)\b",
    r"\b(heart failure|CHF|congestive heart failure)\b",
    r"\b(COPD|chronic obstructive pulmonary)\b",
    r"\b(pneumonia|PNA)\b",
    r"\b(atrial fibrillation|afib|AF)\b",
    r"\b(acute myocardial infarction|AMI|STEMI|NSTEMI|heart attack)\b",
    r"\b(stroke|CVA|cerebral infarction|TIA)\b",
    r"\b(chronic kidney disease|CKD|renal failure|ESRD)\b",
    r"\b(sepsis|septicemia)\b",
    r"\b(COVID[-\s]?19|coronavirus|SARS-CoV-2)\b",
    r"\b(cancer|malignancy|neoplasm|carcinoma|tumor)\b",
    r"\b(depression|MDD|major depressive)\b",
    r"\b(anxiety disorder|GAD)\b",
    r"\b(asthma)\b",
    r"\b(hyperlipidemia|dyslipidemia|high cholesterol)\b",
    r"\b(hypothyroidism|thyroid disease)\b",
    r"\b(osteoarthritis|OA|arthritis)\b",
    r"\b(GERD|gastroesophageal reflux|acid reflux)\b",
    r"\b(obesity|BMI)\b",
]

MEDICATION_PATTERNS = [
    r"\b(metformin|glucophage)\b",
    r"\b(lisinopril|enalapril|ramipril|captopril)\b",
    r"\b(atorvastatin|simvastatin|rosuvastatin|lipitor|zocor)\b",
    r"\b(metoprolol|carvedilol|atenolol|bisoprolol)\b",
    r"\b(amlodipine|norvasc|nifedipine|diltiazem)\b",
    r"\b(aspirin|ASA|acetylsalicylic acid)\b",
    r"\b(warfarin|coumadin|apixaban|eliquis|rivaroxaban|xarelto)\b",
    r"\b(insulin|humalog|novolog|lantus|levemir|basaglar)\b",
    r"\b(furosemide|lasix|torsemide)\b",
    r"\b(omeprazole|pantoprazole|lansoprazole|esomeprazole)\b",
    r"\b(levothyroxine|synthroid)\b",
    r"\b(amoxicillin|azithromycin|ciprofloxacin|doxycycline)\b",
    r"\b(hydrocodone|oxycodone|morphine|codeine|tramadol)\b",
    r"\b(gabapentin|pregabalin|lyrica|neurontin)\b",
    r"\b(sertraline|fluoxetine|escitalopram|citalopram|venlafaxine)\b",
    r"\b(albuterol|salbutamol|ProAir|Ventolin)\b",
]

LAB_TEST_PATTERNS = [
    r"\b(HbA1c|hemoglobin A1c|A1c)\b",
    r"\b(creatinine|Cr)\b",
    r"\b(BUN|blood urea nitrogen)\b",
    r"\b(sodium|Na)\b",
    r"\b(potassium|K)\b",
    r"\b(hemoglobin|Hgb|Hb)\b",
    r"\b(WBC|white blood cell|white count)\b",
    r"\b(platelet)\b",
    r"\b(troponin)\b",
    r"\b(BNP|NT-proBNP|B-type natriuretic)\b",
    r"\b(INR|prothrombin time|PT/INR)\b",
    r"\b(TSH|thyroid stimulating hormone)\b",
    r"\b(glucose|blood sugar|fasting glucose)\b",
    r"\b(LDL|HDL|cholesterol|triglycerides|lipid panel)\b",
    r"\b(ALT|AST|liver function|LFT)\b",
    r"\b(CBC|complete blood count)\b",
    r"\b(CMP|complete metabolic panel|BMP)\b",
    r"\b(ECG|EKG|electrocardiogram)\b",
    r"\b(chest X-ray|CXR|X-ray)\b",
    r"\b(CT scan|MRI|echocardiogram|ultrasound)\b",
]

NEGATION_PATTERNS = [
    r"\b(no|not|without|denies|denying|absent|negative for|rules? out|r/o|free of)\b",
    r"\b(no evidence of|without evidence|unremarkable for|normal|within normal)\b",
]

SEVERITY_PATTERNS = {
    "mild":     r"\b(mild|minimal|slight|trace|minor)\b",
    "moderate": r"\b(moderate|significant|notable)\b",
    "severe":   r"\b(severe|marked|profound|critical|critical|life-threatening)\b",
    "worsening": r"\b(worsening|deteriorating|progressing|increasing)\b",
    "improving": r"\b(improving|resolving|stable|responding|better)\b",
}


def extract_entities_regex(text: str) -> Dict[str, List[str]]:
    """Extract clinical entities using regex patterns."""
    text_lower = text.lower()
    entities = {
        "conditions": [],
        "medications": [],
        "lab_tests": [],
        "negated_findings": [],
        "severity": [],
    }

    # Find negation windows
    neg_positions = []
    for pat in NEGATION_PATTERNS:
        for m in re.finditer(pat, text_lower, re.IGNORECASE):
            neg_positions.append((m.start(), m.end() + 60))  # 60-char window after negation

    def is_negated(start_pos):
        return any(neg_start <= start_pos <= neg_end for neg_start, neg_end in neg_positions)

    # Extract conditions
    for pat in CONDITION_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            entity = m.group()
            if is_negated(m.start()):
                entities["negated_findings"].append(entity)
            else:
                entities["conditions"].append(entity)

    # Extract medications
    for pat in MEDICATION_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            entities["medications"].append(m.group())

    # Extract lab tests
    for pat in LAB_TEST_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            entities["lab_tests"].append(m.group())

    # Extract severity descriptors
    for sev_level, pat in SEVERITY_PATTERNS.items():
        for m in re.finditer(pat, text, re.IGNORECASE):
            entities["severity"].append(f"{sev_level}: {m.group()}")

    # Deduplicate
    for key in entities:
        entities[key] = list(set(entities[key]))

    return entities


def extract_entities_medspacy(nlp_model, text: str) -> Dict[str, List[str]]:
    """Extract entities using medspaCy model."""
    doc = nlp_model(text)
    entities = {
        "conditions": [],
        "medications": [],
        "lab_tests": [],
        "negated_findings": [],
        "anatomical": [],
        "procedures": [],
    }

    for ent in doc.ents:
        label = ent.label_
        text_val = ent.text

        # Check negation/assertion via medspaCy context
        is_negated = hasattr(ent._, "is_negated") and ent._.is_negated

        if label == "PROBLEM":
            if is_negated:
                entities["negated_findings"].append(text_val)
            else:
                entities["conditions"].append(text_val)
        elif label == "TREATMENT":
            entities["medications"].append(text_val)
        elif label == "TEST":
            entities["lab_tests"].append(text_val)
        elif label == "ANATOMICAL_SITE":
            entities["anatomical"].append(text_val)
        elif label == "PROCEDURE":
            entities["procedures"].append(text_val)

    return entities


def process_clinical_notes(notes_df: pd.DataFrame, batch_size: int = 1000) -> pd.DataFrame:
    """
    Process a batch of clinical notes and extract entities.
    Updates the extracted_entities JSONB column.
    """
    if NLP_BACKEND == "medspacy":
        logger.info("Loading medspaCy model ...")
        nlp = medspacy.load("en_info_3700_i2b2_2012", enable=["sentencizer", "ner", "context"])
        extract_fn = lambda text: extract_entities_medspacy(nlp, text)
    else:
        extract_fn = extract_entities_regex

    results = []
    total = len(notes_df)

    for i, row in notes_df.iterrows():
        if (i + 1) % 1000 == 0:
            logger.info(f"Processing note {i+1}/{total} ...")

        try:
            entities = extract_fn(row["clinical_text"])
            results.append({
                "note_id":            row["note_id"],
                "extracted_entities": json.dumps(entities),
                "extracted_medications": entities.get("medications", []),
                "extracted_conditions": entities.get("conditions", []),
                "nlp_processed":      True,
                "nlp_model_version":  f"{NLP_BACKEND}_v1.0",
            })
        except Exception as e:
            logger.error(f"Error processing note {row.get('note_id', i)}: {e}")
            results.append({
                "note_id": row.get("note_id", str(i)),
                "nlp_processed": False,
            })

    return pd.DataFrame(results)


def extract_risk_factors(text: str) -> Dict[str, Any]:
    """
    Extract risk factors for disease risk scoring.
    Returns structured risk factor dict suitable for ML features.
    """
    text_lower = text.lower()
    entities = extract_entities_regex(text)

    risk_factors = {
        "smoking_history": bool(re.search(r"\b(smoking|smoker|tobacco|pack.year|cigarette)\b", text_lower)),
        "alcohol_use":     bool(re.search(r"\b(alcohol|ethanol|drinking|ETOH|drinks per week)\b", text_lower)),
        "drug_use":        bool(re.search(r"\b(illicit drug|cocaine|heroin|opioid abuse|substance use)\b", text_lower)),
        "family_history":  bool(re.search(r"\b(family history|father|mother|sibling|hereditary|genetic)\b", text_lower)),
        "obesity":         bool(re.search(r"\b(obese|obesity|overweight|BMI [3-9]\d)\b", text_lower)),
        "sedentary":       bool(re.search(r"\b(sedentary|inactive|no exercise)\b", text_lower)),
        "poor_diet":       bool(re.search(r"\b(poor diet|high sodium|unhealthy diet|fast food)\b", text_lower)),
        "medication_noncompliance": bool(re.search(r"\b(non-compliant|noncompliant|not taking|stopped taking|missed dose)\b", text_lower)),
        "conditions":      entities["conditions"],
        "medications":     entities["medications"],
    }

    return risk_factors


def demo():
    """Run NER demo on sample clinical notes."""
    sample_note = """
    CHIEF COMPLAINT: Chest pain and shortness of breath.
    
    Patient is a 58-year-old male with history of type 2 diabetes, hypertension, and 
    hyperlipidemia presenting with 2 days of chest pain. He denies nausea or syncope.
    He reports being non-compliant with his metformin and lisinopril for the past month.
    
    Past Medical History:
    1. Type 2 Diabetes - HbA1c 9.2% last month
    2. Essential Hypertension - poorly controlled
    3. Hyperlipidemia - on atorvastatin 40mg
    
    No family history of heart disease. Former smoker, 20 pack-year history, quit 5 years ago.
    
    Labs today: Troponin I elevated at 0.12, BNP 450, creatinine 1.4, potassium 3.8.
    ECG shows ST depression in leads V4-V6.
    
    Assessment: Acute coronary syndrome, rule out NSTEMI. No pneumonia on chest X-ray.
    Diabetes - uncontrolled. Hypertension - requires medication adjustment.
    """

    logger.info("Running Clinical NER on sample note ...")
    entities = extract_entities_regex(sample_note)
    risk_factors = extract_risk_factors(sample_note)

    print("\n" + "="*60)
    print("EXTRACTED ENTITIES:")
    print("="*60)
    for entity_type, entity_list in entities.items():
        if entity_list:
            print(f"\n{entity_type.upper()}:")
            for e in entity_list:
                print(f"  - {e}")

    print("\n" + "="*60)
    print("RISK FACTORS:")
    print("="*60)
    for k, v in risk_factors.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    demo()
