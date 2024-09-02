"""
Chapter 6: NLP — Clinical Note Summarization
Summarizes long clinical notes into structured discharge-style summaries.

Approaches implemented:
  1. Extractive summarization (TF-IDF sentence ranking)
  2. Template-based structured extraction (Chief Complaint, History, Assessment, Plan)
  3. HuggingFace abstractive summarization (facebook/bart-large-cnn) — optional

Usage:
    python nlp/note_summarization/summarizer.py
"""

import re
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger

OUTPUT_DIR = Path("nlp/note_summarization/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

try:
    from transformers import pipeline
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False


# ─── Section Headers (regex patterns) ───────────────────────────────
SECTION_PATTERNS = {
    "chief_complaint":   r"(?:CHIEF COMPLAINT|CC)\s*[:：]\s*(.*?)(?=\n[A-Z]|\Z)",
    "hpi":               r"(?:HISTORY OF PRESENT ILLNESS|HPI)\s*[:：]\s*(.*?)(?=\n[A-Z]|\Z)",
    "past_medical":      r"(?:PAST MEDICAL HISTORY|PMH|MEDICAL HISTORY)\s*[:：]\s*(.*?)(?=\n[A-Z]|\Z)",
    "medications":       r"(?:MEDICATIONS?|CURRENT MEDICATIONS?)\s*[:：]\s*(.*?)(?=\n[A-Z]|\Z)",
    "allergies":         r"(?:ALLERGIES?)\s*[:：]\s*(.*?)(?=\n[A-Z]|\Z)",
    "physical_exam":     r"(?:PHYSICAL EXAMINATION|PHYSICAL EXAM|EXAM)\s*[:：]\s*(.*?)(?=\n[A-Z]|\Z)",
    "vital_signs":       r"(?:VITAL SIGNS?|VITALS?)\s*[:：]\s*(.*?)(?=\n[A-Z]|\Z)",
    "assessment":        r"(?:ASSESSMENT|IMPRESSION|DIAGNOSIS)\s*[:：]?\s*(.*?)(?=\n[A-Z]|\Z)",
    "plan":              r"(?:PLAN|RECOMMENDATIONS?)\s*[:：]?\s*(.*?)(?=\n[A-Z]|\Z)",
    "labs":              r"(?:LAB(?:ORATORY)?(?:\s+RESULTS?)?|LABS?)\s*[:：]\s*(.*?)(?=\n[A-Z]|\Z)",
    "imaging":           r"(?:IMAGING|RADIOLOGY)\s*[:：]\s*(.*?)(?=\n[A-Z]|\Z)",
    "discharge":         r"(?:DISCHARGE|DISPOSITION)\s*[:：]\s*(.*?)(?=\n[A-Z]|\Z)",
}


def extract_sections(text: str) -> Dict[str, str]:
    """Extract structured sections from a clinical note."""
    sections = {}
    for section_name, pattern in SECTION_PATTERNS.items():
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            # Limit to first 500 chars per section
            sections[section_name] = content[:500].replace("\n", " ").strip()
    return sections


def extractive_summarize(text: str, n_sentences: int = 5) -> str:
    """
    TF-IDF based extractive summarization.
    Ranks sentences by importance and selects top N.
    """
    if not SKLEARN_OK:
        # Fallback: return first n_sentences sentences
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 20]
        return ". ".join(sentences[:n_sentences]) + "."

    # Tokenize into sentences
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 15]
    if len(sentences) <= n_sentences:
        return text

    # TF-IDF similarity to full document
    vectorizer = TfidfVectorizer(stop_words="english", max_features=1000)
    try:
        tfidf_matrix = vectorizer.fit_transform(sentences + [text])
        sentence_vecs = tfidf_matrix[:-1]
        doc_vec       = tfidf_matrix[-1]
        scores = cosine_similarity(sentence_vecs, doc_vec).flatten()

        # Select top sentences while preserving order
        top_indices = sorted(np.argsort(scores)[-n_sentences:])
        summary_sentences = [sentences[i] for i in top_indices]
        return ". ".join(summary_sentences) + "."
    except Exception:
        return ". ".join(sentences[:n_sentences]) + "."


def abstractive_summarize(text: str, max_length: int = 150, min_length: int = 50) -> str:
    """
    HuggingFace BART abstractive summarization.
    Falls back to extractive if model not available.
    """
    if not HF_AVAILABLE:
        return extractive_summarize(text, n_sentences=3)

    try:
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        # BART max input is 1024 tokens — truncate if needed
        input_text = text[:3000]
        result = summarizer(input_text, max_length=max_length,
                            min_length=min_length, do_sample=False)
        return result[0]["summary_text"]
    except Exception as e:
        logger.warning(f"HuggingFace summarization failed: {e}. Using extractive fallback.")
        return extractive_summarize(text, n_sentences=3)


def generate_structured_summary(note_text: str, note_type: str = "Progress Note") -> Dict:
    """
    Generate a fully structured summary from a clinical note.
    Returns a dict with: sections, extractive_summary, key_findings, risk_indicators.
    """
    sections = extract_sections(note_text)
    extractive_summary = extractive_summarize(note_text, n_sentences=4)

    # Extract key findings (sentences with clinical significance markers)
    clinical_keywords = [
        "elevated", "decreased", "abnormal", "critical", "urgent",
        "rule out", "consistent with", "suggestive of", "diagnosis",
        "recommend", "ordered", "started", "initiated", "increased", "worsening",
    ]
    sentences = [s.strip() for s in re.split(r"[.!?]+", note_text) if len(s.strip()) > 20]
    key_findings = [
        s for s in sentences
        if any(kw in s.lower() for kw in clinical_keywords)
    ][:5]

    # Risk indicators
    risk_words = {
        "sepsis": 0.9, "hemorrhage": 0.9, "stroke": 0.85, "MI": 0.85,
        "STEMI": 0.95, "arrest": 0.95, "critical": 0.8, "urgent": 0.7,
        "elevated troponin": 0.85, "respiratory failure": 0.90,
        "hypotension": 0.75, "altered mental": 0.80,
    }
    found_risks = []
    note_lower = note_text.lower()
    for risk, score in risk_words.items():
        if risk.lower() in note_lower:
            found_risks.append({"risk": risk, "severity_score": score})

    return {
        "note_type":          note_type,
        "sections":           sections,
        "extractive_summary": extractive_summary,
        "key_findings":       key_findings,
        "risk_indicators":    found_risks,
        "word_count":         len(note_text.split()),
        "section_count":      len(sections),
    }


def process_notes_batch(notes_df: pd.DataFrame, batch_size: int = 100) -> pd.DataFrame:
    """Process a batch of clinical notes and add structured summaries."""
    results = []
    total = len(notes_df)
    for i, (_, row) in enumerate(notes_df.iterrows()):
        if i % batch_size == 0:
            logger.info(f"Summarizing note {i+1}/{total} ...")
        summary = generate_structured_summary(
            row.get("clinical_text", ""),
            row.get("note_type", "Clinical Note")
        )
        results.append({
            "note_id":           row.get("note_id", str(i)),
            "patient_id":        row.get("patient_id", ""),
            "note_type":         summary["note_type"],
            "extractive_summary": summary["extractive_summary"],
            "key_findings":      " | ".join(summary["key_findings"]),
            "risk_count":        len(summary["risk_indicators"]),
            "top_risk":          summary["risk_indicators"][0]["risk"] if summary["risk_indicators"] else None,
            "section_count":     summary["section_count"],
            "word_count":        summary["word_count"],
        })
    return pd.DataFrame(results)


def demo():
    sample_note = """
CHIEF COMPLAINT: Chest pain and shortness of breath for 2 days.

HISTORY OF PRESENT ILLNESS:
Patient is a 67-year-old male with known history of type 2 diabetes, hypertension,
and hyperlipidemia presenting with 2 days of progressive chest discomfort described
as pressure-like, 8/10 in severity, radiating to the left arm. Associated with
diaphoresis and mild shortness of breath. Denies nausea or syncope.
Troponin I elevated at 0.18 ng/mL on presentation. ECG shows ST depression V4-V6.

PAST MEDICAL HISTORY:
1. Type 2 Diabetes Mellitus — HbA1c 9.1% last month
2. Essential Hypertension — poorly controlled
3. Hyperlipidemia
4. Former smoker, 25 pack-year history

MEDICATIONS:
- Metformin 1000mg BID
- Lisinopril 10mg daily (non-compliant)
- Atorvastatin 40mg at bedtime
- Aspirin 81mg daily

VITAL SIGNS: BP 162/98, HR 92, RR 18, SpO2 94%, Temp 98.4°F

PHYSICAL EXAMINATION:
Cardiovascular: Regular rate with S4 gallop. No murmurs.
Respiratory: Mild bilateral basilar crackles.

LABS: Troponin I 0.18 (elevated), BNP 420 (elevated), HbA1c 9.1%, Creatinine 1.6

ASSESSMENT:
1. Rule out NSTEMI — serial troponins ordered, cardiology consulted
2. Hypertension — uncontrolled, medication adjustment needed
3. Type 2 Diabetes — poor glycemic control
4. Possible early heart failure — BNP elevated

PLAN:
1. Admit to telemetry unit for cardiac monitoring
2. Heparin drip initiated per ACS protocol
3. Cardiology consultation placed
4. Increase Lisinopril to 20mg, add Amlodipine 5mg
5. Endocrinology referral for diabetes management
6. Patient and family educated on medication compliance
"""

    logger.info("=== Clinical Note Summarization Demo ===\n")
    result = generate_structured_summary(sample_note, "Admission H&P")

    print("\n" + "="*60)
    print("STRUCTURED NOTE SUMMARY")
    print("="*60)
    print(f"\nNote Type: {result['note_type']}")
    print(f"Word Count: {result['word_count']}")
    print(f"Sections Extracted: {result['section_count']}")

    print("\n--- SECTIONS ---")
    for section, content in result["sections"].items():
        print(f"\n{section.upper().replace('_',' ')}:")
        print(f"  {content[:200]}")

    print("\n--- EXTRACTIVE SUMMARY ---")
    print(result["extractive_summary"])

    print("\n--- KEY FINDINGS ---")
    for finding in result["key_findings"]:
        print(f"  * {finding}")

    print("\n--- RISK INDICATORS ---")
    for risk in result["risk_indicators"]:
        print(f"  ! {risk['risk']} (severity: {risk['severity_score']})")


if __name__ == "__main__":
    demo()

    # Batch process from parquet if available
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data/raw")
    notes_path = data_dir / "clinical_notes"
    if notes_path.exists():
        logger.info("Processing clinical notes from parquet ...")
        notes_df = pd.read_parquet(notes_path).head(500)
        summaries = process_notes_batch(notes_df)
        summaries.to_csv(OUTPUT_DIR / "note_summaries.csv", index=False)
        logger.success(f"Summaries saved: {OUTPUT_DIR / 'note_summaries.csv'}")
