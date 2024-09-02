"""
Chapter 11: Case Study 2 — NLP + Computer Vision + Operations
Combined case study demonstrating integration of multiple AI capabilities.

  - NLP: Extract diagnoses from discharge summaries → auto-code ICD-10
  - Computer Vision: Flag critical radiology findings for urgent review
  - Operations: Use predictions to prioritise patient flow

Usage:
    python case_studies/case_study_02_nlp_ops.py
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
from loguru import logger
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent))

from nlp.icd_prediction.icd_predictor   import predict_icd_codes_keyword
from nlp.entity_recognition.clinical_ner import extract_entities_regex, extract_risk_factors

OUTPUT_DIR = Path("case_studies/outputs/02_nlp_ops")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_case_study():
    logger.info("="*60)
    logger.info("CASE STUDY 2: NLP + Computer Vision + Operations")
    logger.info("="*60)

    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data/raw")

    # ── Part A: Auto-Coding from Discharge Summaries ───────────────
    logger.info("\nPart A: Automated ICD-10 Coding from Clinical Notes")

    try:
        notes_df = pd.read_parquet(data_dir / "clinical_notes").head(200)
        logger.info(f"Loaded {len(notes_df)} clinical notes")
    except FileNotFoundError:
        logger.error("clinical_notes parquet not found.")
        return

    # Run ICD prediction on all notes
    coding_results = []
    for _, row in notes_df.iterrows():
        text = row.get("clinical_text", "")
        if not text or len(text) < 50:
            continue
        predicted_codes  = predict_icd_codes_keyword(text, top_n=3)
        entities         = extract_entities_regex(text)
        risks            = extract_risk_factors(text)

        coding_results.append({
            "note_id":          row.get("note_id",""),
            "patient_id":       row.get("patient_id",""),
            "note_type":        row.get("note_type",""),
            "predicted_codes":  [c[0] for c in predicted_codes],
            "top_icd":          predicted_codes[0][0] if predicted_codes else None,
            "top_icd_name":     predicted_codes[0][1] if predicted_codes else None,
            "top_confidence":   predicted_codes[0][2] if predicted_codes else 0,
            "n_conditions":     len(entities.get("conditions",[])),
            "n_medications":    len(entities.get("medications",[])),
            "n_risks":          len(risks),
            "noncompliant":     "med_noncompliance" in risks,
            "smoker":           "smoking_current" in risks or "smoking_former" in risks,
        })

    results_df = pd.DataFrame(coding_results)
    results_df.to_csv(OUTPUT_DIR / "auto_coding_results.csv", index=False)

    logger.info(f"\n  Notes processed: {len(results_df)}")
    logger.info(f"  Notes with predicted ICD codes: {results_df['top_icd'].notna().sum()}")
    logger.info(f"  Avg confidence: {results_df['top_confidence'].mean():.3f}")
    logger.info(f"\nTop Predicted Diagnoses:")
    top_dx = results_df["top_icd_name"].value_counts().head(10)
    for name, count in top_dx.items():
        logger.info(f"  {name:45s}: {count:4d} notes")

    # ── Part B: Radiology Critical Finding Triage ──────────────────
    logger.info("\nPart B: Radiology Critical Finding Triage")

    try:
        imaging_df = pd.read_parquet(data_dir / "imaging_records")
        logger.info(f"Loaded {len(imaging_df)} imaging records")
    except FileNotFoundError:
        logger.warning("imaging_records not found — using placeholder analysis")
        imaging_df = pd.DataFrame()

    if not imaging_df.empty:
        critical_images = imaging_df[imaging_df["critical_finding"] == True]
        pending_reports  = imaging_df[imaging_df["report_status"].isin(["Draft","Preliminary"])]
        critical_pending = critical_images[critical_images["report_status"].isin(["Draft","Preliminary"])]

        logger.info(f"\n  Total Imaging Studies:      {len(imaging_df):,}")
        logger.info(f"  Critical Findings:          {len(critical_images):,} ({len(critical_images)/len(imaging_df)*100:.1f}%)")
        logger.info(f"  Pending Reports:            {len(pending_reports):,}")
        logger.info(f"  Critical + Pending (URGENT):{len(critical_pending):,}")

        # Triage queue
        if len(critical_pending) > 0:
            logger.info(f"\n  URGENT RADIOLOGY TRIAGE QUEUE:")
            triage_queue = critical_pending[["image_id","patient_id","image_type","body_part","report_status"]].head(10)
            logger.info(triage_queue.to_string(index=False))

    # ── Part C: Integrated Operations Dashboard ────────────────────
    logger.info("\nPart C: Integrated Clinical Operations Summary")

    try:
        er_visits = pd.read_parquet(data_dir / "emergency_visits")
        admissions = pd.read_parquet(data_dir / "admissions")
    except FileNotFoundError:
        logger.warning("ER/admission data not found.")
        er_visits = admissions = pd.DataFrame()

    if not admissions.empty:
        still_admitted = (admissions["discharge_status"] == "Still Admitted").sum()
        emergency_admits = (admissions["admission_type"] == "Emergency").sum()
        icu_patients = (admissions["ward"] == "ICU").sum()
        readmit_risk = admissions["readmission_within_30d"].astype(float).sum()

        logger.info(f"\n  Current Census:")
        logger.info(f"    Still Admitted:      {still_admitted:,}")
        logger.info(f"    Emergency Admits:    {emergency_admits:,}")
        logger.info(f"    ICU Patients:        {icu_patients:,}")
        logger.info(f"    Readmission Risk:    {int(readmit_risk):,} flagged")

    # ── Visualization ──────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Case Study 2: Integrated NLP + CV + Operations", fontsize=13, fontweight="bold")

    # ICD code prediction confidence distribution
    if len(results_df) > 0:
        axes[0].hist(results_df["top_confidence"].dropna(), bins=20, color="steelblue", edgecolor="white")
        axes[0].set_title("ICD-10 Prediction Confidence Distribution")
        axes[0].set_xlabel("Confidence Score")
        axes[0].set_ylabel("Number of Notes")
        axes[0].axvline(results_df["top_confidence"].mean(), color="red", linestyle="--",
                        label=f"Mean: {results_df['top_confidence'].mean():.2f}")
        axes[0].legend()

    # Top predicted diagnoses
    if len(results_df) > 0 and results_df["top_icd_name"].notna().any():
        top5 = results_df["top_icd_name"].value_counts().head(8)
        axes[1].barh(top5.index, top5.values, color="teal")
        axes[1].set_title("Most Frequently Predicted Diagnoses")
        axes[1].set_xlabel("Count")

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "case_study_02_integrated.png", dpi=120)
    plt.close()

    logger.success(f"\nCase Study 2 complete. Outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    run_case_study()
