"""
Chapter 11: Case Study 1 — Reducing Hospital Readmissions
End-to-end walkthrough: data → features → model → intervention → outcome.

Real-world context:
  CMS penalises hospitals with excess 30-day readmissions under HRRP.
  A 1% reduction in readmissions saves ~$200K/year per hospital.

Pipeline:
  1. Load and explore readmission data
  2. Feature engineering
  3. Train predictive model
  4. Generate risk stratification
  5. Simulate intervention impact
  6. Build discharge checklist based on risk factors

Usage:
    python case_studies/case_study_01_readmission.py
"""

import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from loguru import logger
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent))

OUTPUT_DIR = Path("case_studies/outputs/01_readmission")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_case_study():
    logger.info("="*60)
    logger.info("CASE STUDY 1: Reducing Hospital Readmissions")
    logger.info("="*60)

    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data/raw")

    # ── Step 1: Load Data ──────────────────────────────────────────
    logger.info("\nStep 1: Loading and Exploring Data ...")
    try:
        admissions = pd.read_parquet(data_dir / "admissions")
        patients   = pd.read_parquet(data_dir / "patients")
        diagnoses  = pd.read_parquet(data_dir / "diagnoses")
        lab_results = pd.read_parquet(data_dir / "lab_results")
    except FileNotFoundError:
        logger.error("Data files not found. Run: python data_generation/generate_all.py --scale small")
        return

    # Compute LOS
    admissions["los"] = (
        pd.to_datetime(admissions["discharge_date"], errors="coerce") -
        pd.to_datetime(admissions["admit_date"], errors="coerce")
    ).dt.days.fillna(0)

    total = len(admissions[admissions["discharge_status"] != "Still Admitted"])
    readmit_30d = admissions["readmission_within_30d"].astype(float).sum()
    rate = readmit_30d / total * 100

    logger.info(f"\n  Total Discharges:        {total:,}")
    logger.info(f"  30-Day Readmissions:     {int(readmit_30d):,}")
    logger.info(f"  Readmission Rate:        {rate:.1f}%")
    logger.info(f"  CMS Benchmark:           15.6%")
    logger.info(f"  Status:                  {'ABOVE benchmark - PENALTY RISK' if rate > 15.6 else 'Below benchmark'}")

    # ── Step 2: Readmission by Diagnosis (DRG) ─────────────────────
    logger.info("\nStep 2: Readmission Pattern Analysis ...")
    drg_readmit = (
        admissions[admissions["discharge_status"] != "Still Admitted"]
        .groupby("drg_code").agg(
            total_admissions = ("admission_id", "count"),
            readmissions     = ("readmission_within_30d", lambda x: x.astype(float).sum()),
            avg_los          = ("los", "mean"),
            avg_cost         = ("actual_cost", "mean"),
        )
        .reset_index()
    )
    drg_readmit["readmit_rate"] = (drg_readmit["readmissions"] / drg_readmit["total_admissions"].clip(1) * 100).round(1)
    drg_readmit = drg_readmit[drg_readmit["total_admissions"] >= 20].sort_values("readmit_rate", ascending=False)

    logger.info(f"\nTop 10 DRGs by Readmission Rate:")
    logger.info(drg_readmit.head(10)[["drg_code","total_admissions","readmissions","readmit_rate","avg_los"]].to_string(index=False))

    # ── Step 3: Risk Factors ───────────────────────────────────────
    logger.info("\nStep 3: Identifying Risk Factors ...")

    patients["age"] = (
        pd.to_datetime("today") - pd.to_datetime(patients["dob"], errors="coerce")
    ).dt.days / 365.25

    merged = admissions.merge(patients[["patient_id","age","gender","insurance_plan_type"]], on="patient_id", how="left")
    merged = merged[merged["discharge_status"] != "Still Admitted"].copy()
    merged["readmitted"] = merged["readmission_within_30d"].astype(float)

    # Age group analysis
    merged["age_group"] = pd.cut(merged["age"], bins=[0,35,50,65,80,120],
                                  labels=["<35","35-50","50-65","65-80","80+"])
    age_readmit = merged.groupby("age_group", observed=True)["readmitted"].mean().mul(100).round(1)
    logger.info(f"\nReadmission Rate by Age Group:\n{age_readmit.to_string()}")

    # LOS correlation
    los_corr = merged[["los","readmitted"]].corr().loc["los","readmitted"]
    logger.info(f"\nLOS-Readmission Correlation: {los_corr:.3f}")

    # Admission type
    type_readmit = merged.groupby("admission_type")["readmitted"].mean().mul(100).sort_values(ascending=False)
    logger.info(f"\nReadmission Rate by Admission Type:\n{type_readmit.round(1).to_string()}")

    # ── Step 4: Risk Stratification ────────────────────────────────
    logger.info("\nStep 4: Patient Risk Stratification ...")

    # Simple rule-based risk score (proxy for ML model output)
    merged["risk_score"] = (
        (merged["los"] > 7).astype(int) * 20 +
        (merged["admission_type"] == "Emergency").astype(int) * 15 +
        (merged["icu_hours"] > 24).astype(int) * 20 +
        (merged["age"] >= 65).astype(int) * 15 +
        (merged["readmission_within_90d"].astype(float) * 10) +
        np.random.default_rng(42).integers(0, 20, len(merged))
    ).clip(0, 100)

    merged["risk_category"] = pd.cut(merged["risk_score"],
                                      bins=[0, 25, 50, 75, 100],
                                      labels=["Low","Moderate","High","Critical"])

    risk_dist = merged["risk_category"].value_counts()
    logger.info(f"\nRisk Stratification:")
    for cat in ["Critical","High","Moderate","Low"]:
        if cat in risk_dist.index:
            n = risk_dist[cat]
            actual_rate = merged[merged["risk_category"]==cat]["readmitted"].mean() * 100
            logger.info(f"  {cat:10s}: {n:5,} patients  ({n/len(merged)*100:.1f}%)  "
                        f"Actual readmit rate: {actual_rate:.1f}%")

    # ── Step 5: Intervention Impact Simulation ─────────────────────
    logger.info("\nStep 5: Intervention Impact Simulation ...")

    # Target: High + Critical risk patients with care coordination
    high_risk = merged[merged["risk_category"].isin(["High","Critical"])].copy()

    # Assumptions based on literature:
    # - Transitional care program reduces readmission by 20% in high-risk
    # - Cost of program: $500/patient
    # - Avg readmission cost: $15,000

    current_readmissions   = int(high_risk["readmitted"].sum())
    intervention_reduction = 0.20
    prevented_readmissions = int(current_readmissions * intervention_reduction)
    program_cost           = len(high_risk) * 500
    savings_per_readmit    = 15000
    total_savings          = prevented_readmissions * savings_per_readmit
    net_savings            = total_savings - program_cost
    roi                    = (net_savings / program_cost * 100) if program_cost > 0 else 0

    logger.info(f"\n  High/Critical Risk Patients:   {len(high_risk):,}")
    logger.info(f"  Current Readmissions:          {current_readmissions:,}")
    logger.info(f"  Projected Prevention (20%):    {prevented_readmissions:,}")
    logger.info(f"  Program Cost:                  ${program_cost:,.0f}")
    logger.info(f"  Estimated Savings:             ${total_savings:,.0f}")
    logger.info(f"  Net Savings:                   ${net_savings:,.0f}")
    logger.info(f"  ROI:                           {roi:.0f}%")

    # ── Step 6: Discharge Checklist ────────────────────────────────
    logger.info("\nStep 6: Risk-Based Discharge Checklist ...")
    checklist = {
        "All patients": [
            "Medication reconciliation completed",
            "Discharge instructions provided in patient language",
            "Follow-up appointment scheduled within 7 days",
            "Emergency contact information verified",
        ],
        "High/Critical risk additions": [
            "Transitional care nurse assigned",
            "48-hour post-discharge phone call scheduled",
            "Home health evaluation ordered",
            "Social work consultation completed",
            "Primary care physician notified",
            "Medication adherence plan created",
            "Transportation for follow-up confirmed",
        ],
        "Specific conditions": [
            "HF: Daily weight monitoring instructions given",
            "COPD: Rescue inhaler technique verified",
            "Diabetes: Blood glucose monitoring plan confirmed",
            "CKD: Dietary restrictions explained, nephrology follow-up",
        ],
    }
    for category, items in checklist.items():
        logger.info(f"\n  [{category}]")
        for item in items:
            logger.info(f"    [ ] {item}")

    # ── Visualizations ─────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Case Study 1: Reducing Hospital Readmissions", fontsize=14, fontweight="bold")

    # Readmission rate by DRG (top 10)
    top10 = drg_readmit.head(10)
    axes[0,0].barh(top10["drg_code"], top10["readmit_rate"], color="tomato")
    axes[0,0].axvline(15.6, color="red", linestyle="--", label="CMS Benchmark")
    axes[0,0].set_title("Readmission Rate by DRG (Top 10)")
    axes[0,0].set_xlabel("Readmission %")
    axes[0,0].legend()

    # Readmission by age group
    age_readmit.plot(kind="bar", ax=axes[0,1], color="steelblue", rot=0)
    axes[0,1].axhline(15.6, color="red", linestyle="--", label="Benchmark")
    axes[0,1].set_title("Readmission Rate by Age Group")
    axes[0,1].set_ylabel("Readmission %")
    axes[0,1].legend()

    # Risk stratification
    risk_counts = merged["risk_category"].value_counts()
    colors_risk = {"Low":"green","Moderate":"goldenrod","High":"orangered","Critical":"red"}
    risk_colors = [colors_risk.get(c, "gray") for c in risk_counts.index]
    axes[1,0].bar(risk_counts.index, risk_counts.values, color=risk_colors)
    axes[1,0].set_title("Patient Risk Stratification")
    axes[1,0].set_ylabel("Number of Patients")

    # Intervention ROI
    labels = ["Program Cost", "Gross Savings", "Net Savings"]
    values = [program_cost, total_savings, net_savings]
    bar_colors = ["tomato","steelblue","green" if net_savings > 0 else "red"]
    axes[1,1].bar(labels, [v/1000 for v in values], color=bar_colors)
    axes[1,1].set_title("Intervention Financial Impact ($K)")
    axes[1,1].set_ylabel("Amount ($K)")
    for i, v in enumerate(values):
        axes[1,1].text(i, v/1000 + max(values)/50000, f"${v/1000:.0f}K",
                       ha="center", va="bottom", fontweight="bold")

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "case_study_01_readmission.png", dpi=120)
    plt.close()
    logger.success(f"\nCase Study 1 complete. Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    run_case_study()
