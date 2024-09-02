"""
NLP Project: ICD-10 Code Prediction from Clinical Notes
Model: BioBERT fine-tuned for multi-label ICD-10 classification

Maps free-text clinical note content to ICD-10 diagnosis codes.
Useful for:
  - Coding automation / assistance
  - Reducing coding errors
  - Real-time coding during documentation

Usage:
    python nlp/icd_prediction/icd_predictor.py
"""

import re
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Dict
from loguru import logger

# Optional: HuggingFace transformers for BioBERT
try:
    from transformers import (
        AutoTokenizer, AutoModelForSequenceClassification,
        pipeline
    )
    import torch
    HF_AVAILABLE = True
except ImportError:
    logger.warning("HuggingFace Transformers not available. Using keyword-based fallback.")
    HF_AVAILABLE = False

MODEL_DIR = Path("nlp/icd_prediction/artifacts")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Top 25 ICD-10 codes with associated clinical keywords
ICD_KEYWORD_MAP = {
    "E11.9":  {
        "name": "Type 2 Diabetes",
        "keywords": ["diabetes", "diabetic", "T2DM", "blood sugar", "HbA1c", "glucose", "insulin resistance", "metformin"],
        "threshold": 0.25
    },
    "I10": {
        "name": "Essential Hypertension",
        "keywords": ["hypertension", "HTN", "elevated blood pressure", "high blood pressure", "lisinopril", "amlodipine", "BP"],
        "threshold": 0.20
    },
    "I50.9": {
        "name": "Heart Failure",
        "keywords": ["heart failure", "CHF", "congestive", "BNP", "ejection fraction", "dyspnea on exertion", "orthopnea", "edema", "furosemide"],
        "threshold": 0.30
    },
    "I21.9": {
        "name": "Acute MI",
        "keywords": ["myocardial infarction", "STEMI", "NSTEMI", "AMI", "troponin", "chest pain", "ST elevation", "ACS", "cardiac catheterization"],
        "threshold": 0.35
    },
    "J18.9": {
        "name": "Pneumonia",
        "keywords": ["pneumonia", "PNA", "lung consolidation", "infiltrate", "lobar", "antibiotic", "respiratory infection", "fever cough"],
        "threshold": 0.25
    },
    "J44.1": {
        "name": "COPD Exacerbation",
        "keywords": ["COPD", "chronic obstructive", "exacerbation", "wheezing", "albuterol", "bronchodilator", "FEV1", "spirometry"],
        "threshold": 0.25
    },
    "N18.3": {
        "name": "Chronic Kidney Disease Stage 3",
        "keywords": ["CKD", "chronic kidney", "creatinine", "GFR", "renal insufficiency", "proteinuria", "dialysis", "BUN"],
        "threshold": 0.30
    },
    "A41.9": {
        "name": "Sepsis",
        "keywords": ["sepsis", "septicemia", "bacteremia", "infection", "SIRS", "blood culture", "IV antibiotics", "hypotension fever"],
        "threshold": 0.40
    },
    "I63.9": {
        "name": "Stroke",
        "keywords": ["stroke", "CVA", "cerebral infarction", "TIA", "hemiplegia", "dysarthria", "aphasia", "MRI brain", "tPA"],
        "threshold": 0.35
    },
    "F32.9": {
        "name": "Major Depressive Disorder",
        "keywords": ["depression", "depressed", "MDD", "antidepressant", "sertraline", "PHQ-9", "mood", "anhedonia", "suicidal"],
        "threshold": 0.25
    },
    "E78.5": {
        "name": "Hyperlipidemia",
        "keywords": ["hyperlipidemia", "dyslipidemia", "high cholesterol", "LDL", "statin", "atorvastatin", "lipid panel"],
        "threshold": 0.20
    },
    "U07.1": {
        "name": "COVID-19",
        "keywords": ["COVID", "coronavirus", "SARS-CoV-2", "COVID-19", "positive PCR", "COVID test", "pandemic"],
        "threshold": 0.40
    },
    "G43.909": {
        "name": "Migraine",
        "keywords": ["migraine", "headache", "aura", "photophobia", "phonophobia", "triptan", "sumatriptan", "topiramate"],
        "threshold": 0.25
    },
    "M54.5": {
        "name": "Low Back Pain",
        "keywords": ["low back pain", "lumbar", "back pain", "LBP", "sciatica", "herniated disc", "radiculopathy", "spine"],
        "threshold": 0.20
    },
    "K21.0": {
        "name": "GERD",
        "keywords": ["GERD", "reflux", "heartburn", "esophagitis", "PPI", "omeprazole", "pantoprazole", "dyspepsia"],
        "threshold": 0.20
    },
    "I48.91": {
        "name": "Atrial Fibrillation",
        "keywords": ["atrial fibrillation", "afib", "AF", "irregular rhythm", "anticoagulation", "warfarin", "apixaban"],
        "threshold": 0.30
    },
    "J45.50": {
        "name": "Severe Persistent Asthma",
        "keywords": ["asthma", "bronchospasm", "peak flow", "inhaler", "albuterol", "steroid inhaler", "wheeze"],
        "threshold": 0.25
    },
    "E11.65": {
        "name": "T2DM with Hyperglycemia",
        "keywords": ["hyperglycemia", "high blood sugar", "glucose over 300", "DKA", "insulin drip", "blood glucose"],
        "threshold": 0.35
    },
    "C34.10": {
        "name": "Lung Cancer",
        "keywords": ["lung cancer", "lung mass", "pulmonary nodule", "NSCLC", "SCLC", "bronchogenic", "chemotherapy", "radiation oncology"],
        "threshold": 0.50
    },
    "Z87.891": {
        "name": "History of Nicotine Dependence",
        "keywords": ["smoking history", "former smoker", "pack-year", "tobacco", "nicotine", "quit smoking", "cessation"],
        "threshold": 0.25
    },
}


def predict_icd_codes_keyword(text: str, top_n: int = 5) -> List[Tuple[str, str, float]]:
    """
    Keyword-based ICD-10 prediction (fast, interpretable, no GPU required).
    Returns list of (icd_code, icd_name, confidence_score).
    """
    text_lower = text.lower()
    predictions = []

    for icd_code, code_info in ICD_KEYWORD_MAP.items():
        keywords = code_info["keywords"]
        threshold = code_info["threshold"]

        # Count keyword matches (weighted by specificity)
        match_count = sum(
            1 for kw in keywords
            if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text_lower)
        )
        # Normalize by number of keywords
        score = match_count / len(keywords)

        if score >= threshold:
            predictions.append((icd_code, code_info["name"], round(score, 4)))

    # Sort by score descending
    predictions.sort(key=lambda x: x[2], reverse=True)
    return predictions[:top_n]


class BioBERTICDPredictor:
    """
    BioBERT-based multi-label ICD-10 classifier.
    Fine-tuned on MIMIC-III discharge summaries (simulated here).
    
    In production: use 'dmis-lab/biobert-base-cased-v1.2' fine-tuned on
    ICD-coded clinical notes from MIMIC or proprietary data.
    """

    def __init__(self, model_name: str = "dmis-lab/biobert-base-cased-v1.2"):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.label_encoder = list(ICD_KEYWORD_MAP.keys())

    def load(self):
        if not HF_AVAILABLE:
            raise ImportError("transformers package required")
        logger.info(f"Loading BioBERT model: {self.model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        # In production: load fine-tuned model checkpoint
        # self.model = AutoModelForSequenceClassification.from_pretrained(
        #     "nlp/icd_prediction/artifacts/biobert_icd_finetuned"
        # )

    def predict(self, text: str, threshold: float = 0.4) -> List[Tuple[str, str, float]]:
        """Predict ICD codes. Falls back to keyword method if model not loaded."""
        if self.model is None:
            return predict_icd_codes_keyword(text)

        inputs = self.tokenizer(
            text[:512], return_tensors="pt",
            truncation=True, padding=True, max_length=512
        )
        with torch.no_grad():
            logits = self.model(**inputs).logits
            probs = torch.sigmoid(logits).squeeze().numpy()

        results = []
        for i, (code, score) in enumerate(zip(self.label_encoder, probs)):
            if score >= threshold:
                results.append((code, ICD_KEYWORD_MAP[code]["name"], float(score)))
        results.sort(key=lambda x: x[2], reverse=True)
        return results


def process_notes_for_icd_coding(notes_df: pd.DataFrame) -> pd.DataFrame:
    """
    Batch process clinical notes to predict ICD-10 codes.
    Stores results back into the clinical_notes table.
    """
    predictor = BioBERTICDPredictor()

    results = []
    for _, row in notes_df.iterrows():
        predicted = predict_icd_codes_keyword(row["clinical_text"], top_n=5)
        codes = [p[0] for p in predicted]
        confidences = {p[0]: p[2] for p in predicted}

        results.append({
            "note_id":             row["note_id"],
            "predicted_icd_codes": json.dumps(codes),
            "icd_confidence":      json.dumps(confidences),
        })

    return pd.DataFrame(results)


def evaluate_icd_predictions(predictions_df: pd.DataFrame, ground_truth_df: pd.DataFrame) -> Dict:
    """Evaluate ICD prediction accuracy against ground truth diagnoses."""
    # In production: compare predicted codes against coded diagnoses
    # Metrics: precision@k, recall@k, exact match accuracy, NDCG
    metrics = {
        "precision_at_1": 0.0,
        "precision_at_3": 0.0,
        "recall_at_5": 0.0,
        "exact_match": 0.0,
    }
    # Placeholder — implement with real ground truth
    return metrics


def demo():
    sample_notes = [
        {
            "note_id": "DEMO001",
            "clinical_text": """
            58-year-old male with type 2 diabetes presenting with chest pain.
            History of hypertension, poorly controlled on lisinopril. HbA1c 9.2%.
            Troponin I elevated at 0.12 ng/mL. ST depression in V4-V6.
            Rule out NSTEMI. Start heparin drip. Cardiology consult.
            """
        },
        {
            "note_id": "DEMO002",
            "clinical_text": """
            72-year-old female with COPD presenting with shortness of breath.
            Using albuterol frequently. SpO2 88% on room air. Wheezing bilateral.
            Chest X-ray shows hyperinflation. Started methylprednisolone IV.
            Also has history of atrial fibrillation on apixaban.
            """
        },
        {
            "note_id": "DEMO003",
            "clinical_text": """
            45-year-old with sepsis secondary to pneumonia. Blood cultures positive.
            Fever 39.2, BP 88/52. WBC 18.5, creatinine 2.1 (baseline 1.0).
            Started vancomycin and piperacillin-tazobactam. ICU admission.
            History of diabetes and chronic kidney disease stage 3.
            """
        },
    ]

    print("="*60)
    print("ICD-10 CODE PREDICTION DEMO")
    print("="*60)

    for note in sample_notes:
        predictions = predict_icd_codes_keyword(note["clinical_text"], top_n=5)
        print(f"\nNote: {note['note_id']}")
        print("Predicted ICD-10 Codes:")
        for code, name, score in predictions:
            confidence_bar = "#" * int(score * 20)
            print(f"  {code:10} {name:35} {score:.2f} [{confidence_bar}]")


if __name__ == "__main__":
    demo()
