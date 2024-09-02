"""
Chapter 4: Predictive Modeling — Patient Churn / Retention Prediction
Model: XGBoost + SHAP

"Churn" in healthcare = patient disengaging from care:
  - No follow-up appointment after discharge
  - No visit in 12+ months after chronic condition diagnosis
  - Switching providers / going out-of-network
  - Non-adherence to prescribed medications

Used by: Patient retention teams, population health managers

Usage:
    python ml_models/patient_churn/train.py
    python ml_models/patient_churn/train.py ./data/raw
"""

import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger

from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import roc_auc_score, average_precision_score, classification_report
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb
import shap
import joblib
import json

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
CHURN_DAYS   = 365       # patient not seen in 12 months = churned
MODEL_DIR    = Path("ml_models/patient_churn/artifacts")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def build_churn_features(patients, appointments, admissions, prescriptions):
    """
    Build churn prediction features.
    Target: patient has no visit/appointment in last 12 months = churned (1).
    """
    logger.info("Building churn features ...")
    today = pd.Timestamp("2024-12-31")
    cutoff = today - pd.Timedelta(days=CHURN_DAYS)

    # Patient demographics
    pts = patients[["patient_id","dob","gender","ethnicity",
                    "insurance_plan_type","marital_status",
                    "annual_income_band","registration_date",
                    "deceased_flag"]].copy()
    pts["age"] = (today - pd.to_datetime(pts["dob"], errors="coerce")).dt.days / 365.25
    pts["years_registered"] = (today - pd.to_datetime(pts["registration_date"], errors="coerce")).dt.days / 365.25
    pts = pts[pts["deceased_flag"] == False].copy()

    # Appointment engagement
    appt = appointments.copy()
    appt["appt_dt"] = pd.to_datetime(appt["appointment_date"], errors="coerce")

    appt_stats = appt.groupby("patient_id").agg(
        total_appointments  = ("appointment_id", "count"),
        completed_appts     = ("appointment_status", lambda x: (x == "Completed").sum()),
        no_shows            = ("appointment_status", lambda x: (x == "No-Show").sum()),
        cancellations       = ("appointment_status", lambda x: (x == "Cancelled").sum()),
        last_appt_date      = ("appt_dt", "max"),
        avg_wait_minutes    = ("wait_time_minutes", "mean"),
    ).reset_index()
    appt_stats["days_since_last_appt"] = (today - appt_stats["last_appt_date"]).dt.days
    appt_stats["no_show_rate"]  = appt_stats["no_shows"] / appt_stats["total_appointments"].clip(1)
    appt_stats["cancel_rate"]   = appt_stats["cancellations"] / appt_stats["total_appointments"].clip(1)
    appt_stats["completion_rate"] = appt_stats["completed_appts"] / appt_stats["total_appointments"].clip(1)

    # Admission engagement
    adm = admissions.copy()
    adm["admit_dt"] = pd.to_datetime(adm["admit_date"], errors="coerce")
    adm_stats = adm.groupby("patient_id").agg(
        total_admissions  = ("admission_id", "count"),
        last_admission    = ("admit_dt", "max"),
        readmit_30d       = ("readmission_within_30d", lambda x: x.astype(float).sum()),
    ).reset_index()
    adm_stats["days_since_last_admission"] = (today - adm_stats["last_admission"]).dt.days

    # Medication adherence proxy — refill count
    rx_stats = prescriptions.groupby("patient_id").agg(
        total_rx      = ("prescription_id", "count"),
        avg_refills   = ("refill_count", "mean"),
        controlled_rx = ("controlled_substance", lambda x: x.astype(float).sum()),
    ).reset_index()

    # Join all
    feat = (pts[["patient_id","age","years_registered","gender","ethnicity",
                 "insurance_plan_type","marital_status","annual_income_band"]]
            .merge(appt_stats[["patient_id","total_appointments","no_show_rate",
                                "cancel_rate","completion_rate","days_since_last_appt",
                                "avg_wait_minutes"]], on="patient_id", how="left")
            .merge(adm_stats[["patient_id","total_admissions","readmit_30d",
                               "days_since_last_admission"]], on="patient_id", how="left")
            .merge(rx_stats,  on="patient_id", how="left"))

    # ── Target: churned = 1 if days_since_last_contact > CHURN_DAYS ──
    # Use min of days_since_last_appt and days_since_last_admission
    feat["days_since_last_contact"] = feat[
        ["days_since_last_appt","days_since_last_admission"]
    ].min(axis=1)
    feat["churned"] = (feat["days_since_last_contact"] > CHURN_DAYS).astype(int)

    # Encode categoricals
    cat_cols = ["gender","ethnicity","insurance_plan_type","marital_status","annual_income_band"]
    for col in cat_cols:
        if col in feat.columns:
            feat[col] = LabelEncoder().fit_transform(feat[col].astype(str).fillna("Unknown"))

    num_cols = feat.select_dtypes(include=np.number).columns
    feat[num_cols] = feat[num_cols].fillna(feat[num_cols].median())

    churn_rate = feat["churned"].mean()
    logger.info(f"Feature matrix: {feat.shape}  Churn rate: {churn_rate:.2%}")
    return feat


def train(feat: pd.DataFrame):
    DROP = {"patient_id","churned","days_since_last_contact",
            "days_since_last_appt","days_since_last_admission"}
    FEATURE_COLS = [c for c in feat.columns if c not in DROP]

    X = feat[FEATURE_COLS]
    y = feat["churned"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )

    scale_pos = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    model = xgb.XGBClassifier(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=scale_pos, eval_metric="auc",
        early_stopping_rounds=50, random_state=RANDOM_STATE, n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.40).astype(int)

    n_classes = len(np.unique(y_test))
    if n_classes > 1:
        auc_roc = roc_auc_score(y_test, y_prob)
        auc_pr  = average_precision_score(y_test, y_prob)
        logger.info(f"AUC-ROC: {auc_roc:.4f}  AUC-PR: {auc_pr:.4f}")
        logger.info("\n" + classification_report(y_test, y_pred,
                    target_names=["Retained","Churned"]))
    else:
        auc_roc, auc_pr = float("nan"), float("nan")
        logger.warning("Single class in test set — increase dataset size.")

    # SHAP
    explainer = shap.TreeExplainer(model)
    sample    = min(500, len(X_test))
    shap_vals = explainer.shap_values(X_test.iloc[:sample])
    feat_imp  = pd.DataFrame({
        "feature":         FEATURE_COLS,
        "shap_importance": np.abs(shap_vals).mean(axis=0),
    }).sort_values("shap_importance", ascending=False)
    logger.info(f"\nTop 10 Churn Drivers:\n{feat_imp.head(10).to_string()}")

    # Churn risk segments
    risk_segments = pd.cut(y_prob, bins=[0,0.10,0.25,0.50,1.0],
                           labels=["Low","Moderate","High","Critical"])
    logger.info(f"\nChurn Risk Distribution:\n{pd.Series(risk_segments).value_counts().to_string()}")

    # Save
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    joblib.dump(model, MODEL_DIR / f"churn_model_{run_id}.pkl")
    feat_imp.to_csv(MODEL_DIR / "feature_importance.csv", index=False)
    metrics = {
        "run_id": run_id,
        "auc_roc": round(auc_roc, 4) if not np.isnan(auc_roc) else None,
        "auc_pr":  round(auc_pr, 4)  if not np.isnan(auc_pr)  else None,
        "churn_rate": round(float(y.mean()), 4),
        "churn_threshold_days": CHURN_DAYS,
    }
    with open(MODEL_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    logger.success("Patient Churn model saved.")
    return model, metrics


def main():
    logger.info("Chapter 4: Patient Churn / Retention Prediction")
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data/raw")

    try:
        patients      = pd.read_parquet(data_dir / "patients")
        appointments  = pd.read_parquet(data_dir / "appointments")
        admissions    = pd.read_parquet(data_dir / "admissions")
        prescriptions = pd.read_parquet(data_dir / "prescriptions")
    except FileNotFoundError:
        logger.warning("Parquet files not found — using synthetic data ...")
        rng = np.random.default_rng(RANDOM_STATE)
        n = 3000
        patients = pd.DataFrame({
            "patient_id": [f"P{i:07d}" for i in range(n)],
            "dob": pd.date_range("1950-01-01", periods=n, freq="7D").astype(str),
            "gender": rng.choice(["M","F"], n),
            "ethnicity": rng.choice(["Caucasian","Hispanic"], n),
            "insurance_plan_type": rng.choice(["HMO","PPO","Medicare"], n),
            "marital_status": rng.choice(["Single","Married"], n),
            "annual_income_band": rng.choice(["<25K","25-50K","50K+"], n),
            "registration_date": "2018-01-01",
            "deceased_flag": False,
        })
        appt_dates = pd.date_range("2020-01-01","2024-12-01", periods=n*3)
        appointments = pd.DataFrame({
            "appointment_id": [f"A{i:09d}" for i in range(n*3)],
            "patient_id": [f"P{i%n:07d}" for i in range(n*3)],
            "appointment_date": rng.choice(appt_dates.astype(str), n*3),
            "appointment_status": rng.choice(["Completed","No-Show","Cancelled"], n*3, p=[0.68,0.08,0.24]),
            "wait_time_minutes": rng.integers(5, 90, n*3),
        })
        admissions = pd.DataFrame({
            "admission_id": [f"ADM{i:08d}" for i in range(n)],
            "patient_id": [f"P{i:07d}" for i in range(n)],
            "admit_date": rng.choice(pd.date_range("2021-01-01","2024-01-01",periods=100).astype(str), n),
            "readmission_within_30d": rng.choice([True,False], n, p=[0.15,0.85]),
        })
        prescriptions = pd.DataFrame({
            "prescription_id": [f"RX{i:09d}" for i in range(n*2)],
            "patient_id": [f"P{i%n:07d}" for i in range(n*2)],
            "refill_count": rng.integers(0, 6, n*2),
            "controlled_substance": rng.choice([True,False], n*2, p=[0.05,0.95]),
        })

    feat  = build_churn_features(patients, appointments, admissions, prescriptions)
    model, metrics = train(feat)
    logger.info(f"Metrics: {metrics}")


if __name__ == "__main__":
    main()
