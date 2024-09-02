"""
Chapter 4: Predictive Modeling — Disease Risk Prediction
Model: Random Forest + XGBoost ensemble

Predicts patient risk for developing:
  - Type 2 Diabetes
  - Hypertension
  - Heart Failure
  - Chronic Kidney Disease

Uses demographics, vitals trends, lab values, and lifestyle factors.
Outputs individual risk scores per disease (0-100).

Usage:
    python ml_models/disease_risk/train.py
    python ml_models/disease_risk/train.py ./data/raw
"""

import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import roc_auc_score, classification_report, average_precision_score
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb
import shap
import joblib
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
MODEL_DIR    = Path("ml_models/disease_risk/artifacts")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Target diseases and their ICD-10 prefixes
DISEASE_TARGETS = {
    "diabetes":      ["E11", "E10"],
    "hypertension":  ["I10"],
    "heart_failure": ["I50"],
    "ckd":           ["N18"],
}


def build_features(patients, admissions, diagnoses, lab_results):
    """Build feature matrix for disease risk prediction."""
    logger.info("Engineering disease risk features ...")

    # Patient demographics
    pts = patients[["patient_id","dob","gender","ethnicity",
                    "marital_status","insurance_plan_type","annual_income_band"]].copy()
    pts["age"] = (
        pd.to_datetime("today") - pd.to_datetime(pts["dob"], errors="coerce")
    ).dt.days / 365.25
    pts.drop(columns=["dob"], inplace=True)

    # Admission history
    adm = admissions.copy()
    adm["los"] = (
        pd.to_datetime(adm["discharge_date"], errors="coerce") -
        pd.to_datetime(adm["admit_date"], errors="coerce")
    ).dt.days.fillna(0)
    adm_hist = adm.groupby("patient_id").agg(
        n_admissions    = ("admission_id", "count"),
        avg_los         = ("los", "mean"),
        total_icu_hours = ("icu_hours", "sum"),
        any_surgery     = ("surgery_performed", "any"),
    ).reset_index()

    # Lab value summaries (most recent per patient)
    key_labs = ["HbA1c","Glucose","Creatinine","BUN","Potassium","Sodium",
                "Hemoglobin","WBC","BNP","LDL Cholesterol","HDL Cholesterol",
                "Total Cholesterol","TSH","Troponin I"]
    lab_feat = (
        lab_results[lab_results["test_name"].isin(key_labs)]
        .sort_values("collection_datetime")
        .groupby(["patient_id","test_name"])["result_numeric"].last()
        .unstack()
        .reset_index()
    )
    lab_feat.columns = ["patient_id"] + [f"lab_{c.lower().replace(' ','_').replace('/','_')}"
                                          for c in lab_feat.columns[1:]]

    # Lab abnormal count
    lab_abn = (
        lab_results[lab_results["abnormal_flag"].isin(["H","HH","L","LL"])]
        .groupby("patient_id")["result_id"].count()
        .rename("abnormal_lab_count").reset_index()
    )

    # Existing chronic diagnosis flags (as features — not targets)
    existing_dx = {}
    for disease, codes in DISEASE_TARGETS.items():
        mask = diagnoses["icd10_code"].str.startswith(tuple(codes))
        existing_dx[f"prev_{disease}"] = (
            diagnoses[mask].groupby("patient_id")["diagnosis_id"].count().gt(0).astype(int)
        )
    existing_df = pd.DataFrame(existing_dx).reset_index()

    # Join all features
    feat = pts.merge(adm_hist,   on="patient_id", how="left")
    feat = feat.merge(lab_feat,  on="patient_id", how="left")
    feat = feat.merge(lab_abn,   on="patient_id", how="left")
    feat = feat.merge(existing_df, on="patient_id", how="left")

    # Build binary target labels — does patient DEVELOP the condition?
    # Here we use diagnosis presence as proxy target for demonstration
    for disease, codes in DISEASE_TARGETS.items():
        mask = diagnoses["icd10_code"].str.startswith(tuple(codes))
        has_disease = (
            diagnoses[mask].groupby("patient_id")["diagnosis_id"].count().gt(0).astype(int)
        )
        feat[f"target_{disease}"] = feat["patient_id"].map(has_disease).fillna(0).astype(int)

    # Encode categoricals + convert all bool columns to int
    cat_cols = ["gender","ethnicity","marital_status","insurance_plan_type","annual_income_band"]
    for col in cat_cols:
        if col in feat.columns:
            feat[col] = LabelEncoder().fit_transform(feat[col].astype(str).fillna("Unknown"))

    # Convert all bool/object columns to numeric
    for col in feat.columns:
        if feat[col].dtype == bool or str(feat[col].dtype) == "object":
            try:
                feat[col] = feat[col].astype(float)
            except (ValueError, TypeError):
                feat[col] = LabelEncoder().fit_transform(feat[col].astype(str).fillna("Unknown"))

    # Fill numeric nulls
    num_cols = feat.select_dtypes(include=np.number).columns
    feat[num_cols] = feat[num_cols].fillna(feat[num_cols].median())

    logger.info(f"Feature matrix: {feat.shape}")
    return feat


def train_disease_model(feat: pd.DataFrame, disease: str):
    """Train a binary classifier for one disease."""
    target_col    = f"target_{disease}"
    exclude_cols  = {"patient_id"} | {f"target_{d}" for d in DISEASE_TARGETS} | {f"prev_{disease}"}
    feature_cols  = [c for c in feat.columns if c not in exclude_cols]

    X = feat[feature_cols]
    y = feat[target_col]

    pos_rate = y.mean()
    logger.info(f"\n--- {disease.upper()} ---  prevalence: {pos_rate:.2%}")

    if pos_rate == 0 or pos_rate == 1:
        logger.warning(f"  Skipping {disease} — single class.")
        return None, None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )

    # Ensemble: RF + XGB
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=10,
        class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1
    )
    xgb_model = xgb.XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        scale_pos_weight=(y==0).sum()/(y==1).sum() if pos_rate < 0.5 else 1,
        eval_metric="auc", early_stopping_rounds=30,
        random_state=RANDOM_STATE, n_jobs=-1,
    )

    # Train both
    rf.fit(X_train, y_train)
    xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    # Soft ensemble (average probabilities)
    rf_prob  = rf.predict_proba(X_test)[:, 1]
    xgb_prob = xgb_model.predict_proba(X_test)[:, 1]
    ensemble_prob = (rf_prob + xgb_prob) / 2

    auc_roc = roc_auc_score(y_test, ensemble_prob)
    auc_pr  = average_precision_score(y_test, ensemble_prob)
    logger.info(f"  AUC-ROC: {auc_roc:.4f}  AUC-PR: {auc_pr:.4f}")

    y_pred = (ensemble_prob >= 0.50).astype(int)
    if len(set(y_test)) > 1:
        logger.info("\n" + classification_report(y_test, y_pred))

    # SHAP on XGBoost component
    explainer  = shap.TreeExplainer(xgb_model)
    sample_n   = min(300, len(X_test))
    shap_vals  = explainer.shap_values(X_test.iloc[:sample_n])

    feat_imp = pd.DataFrame({
        "feature":         feature_cols,
        "shap_importance": np.abs(shap_vals).mean(axis=0),
    }).sort_values("shap_importance", ascending=False).head(15)
    logger.info(f"\nTop 10 Risk Factors for {disease}:\n{feat_imp.head(10).to_string()}")

    # Risk score distribution plot
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(ensemble_prob[y_test==0], bins=30, alpha=0.6, color="steelblue", label="No Disease")
    ax.hist(ensemble_prob[y_test==1], bins=30, alpha=0.6, color="tomato",    label="Has Disease")
    ax.set_title(f"Disease Risk Score Distribution — {disease.title()}")
    ax.set_xlabel("Predicted Risk Probability")
    ax.set_ylabel("Count")
    ax.legend()
    plt.tight_layout()
    plt.savefig(MODEL_DIR / f"risk_dist_{disease}.png", dpi=100)
    plt.close()

    # Save model
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_bundle = {"rf": rf, "xgb": xgb_model, "feature_cols": feature_cols}
    joblib.dump(model_bundle, MODEL_DIR / f"disease_risk_{disease}_{run_id}.pkl")
    feat_imp.to_csv(MODEL_DIR / f"feature_importance_{disease}.csv", index=False)

    metrics = {
        "disease": disease, "run_id": run_id,
        "auc_roc": round(auc_roc, 4), "auc_pr": round(auc_pr, 4),
        "prevalence": round(float(pos_rate), 4),
    }
    return model_bundle, metrics


def score_patients(feat: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Generate a risk scorecard for every patient across all 4 diseases."""
    result = feat[["patient_id"]].copy()
    for disease, (model_bundle, _) in models.items():
        if model_bundle is None:
            continue
        X = feat[model_bundle["feature_cols"]]
        rf_prob  = model_bundle["rf"].predict_proba(X)[:, 1]
        xgb_prob = model_bundle["xgb"].predict_proba(X)[:, 1]
        risk = (rf_prob + xgb_prob) / 2
        result[f"risk_{disease}"] = (risk * 100).round(1)
        result[f"risk_{disease}_category"] = pd.cut(
            risk, bins=[0, 0.10, 0.25, 0.50, 1.0],
            labels=["Low","Moderate","High","Very High"]
        )
    return result


def main():
    logger.info("Chapter 4: Disease Risk Prediction")

    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data/raw")

    try:
        patients    = pd.read_parquet(data_dir / "patients")
        admissions  = pd.read_parquet(data_dir / "admissions")
        diagnoses   = pd.read_parquet(data_dir / "diagnoses")
        lab_results = pd.read_parquet(data_dir / "lab_results")
        logger.info(f"Loaded data from {data_dir}")
    except FileNotFoundError:
        logger.warning("Parquet files not found — generating synthetic data ...")
        rng = np.random.default_rng(RANDOM_STATE)
        n = 5000
        patients   = pd.DataFrame({"patient_id": [f"P{i:07d}" for i in range(n)],
                                    "dob": pd.date_range("1950-01-01", periods=n, freq="7D").astype(str),
                                    "gender": rng.choice(["M","F"], n),
                                    "ethnicity": rng.choice(["Caucasian","Hispanic","African American","Asian"], n),
                                    "marital_status": rng.choice(["Single","Married","Divorced"], n),
                                    "insurance_plan_type": rng.choice(["HMO","PPO","Medicare"], n),
                                    "annual_income_band": rng.choice(["<25K","25-50K","50-75K","100K+"], n)})
        admissions = pd.DataFrame({"admission_id": [f"A{i:08d}" for i in range(n)],
                                    "patient_id": [f"P{i:07d}" for i in range(n)],
                                    "admit_date": "2023-01-01", "discharge_date": "2023-01-05",
                                    "icu_hours": rng.integers(0, 50, n),
                                    "surgery_performed": rng.choice([True,False], n)})
        dx_codes = ["E11.9","I10","I50.9","N18.3","J18.9","E78.5","F32.9"]
        diagnoses = pd.DataFrame({"diagnosis_id": [f"DX{i:09d}" for i in range(n*3)],
                                   "patient_id": [f"P{i%n:07d}" for i in range(n*3)],
                                   "icd10_code": rng.choice(dx_codes, n*3),
                                   "diagnosis_type": rng.choice(["Primary","Secondary"], n*3)})
        lab_results = pd.DataFrame({
            "result_id": [f"LAB{i:010d}" for i in range(n*5)],
            "patient_id": [f"P{i%n:07d}" for i in range(n*5)],
            "test_name": rng.choice(["HbA1c","Glucose","Creatinine","WBC","Hemoglobin"], n*5),
            "result_numeric": rng.normal(5, 2, n*5),
            "collection_datetime": "2023-06-01",
            "abnormal_flag": rng.choice(["Normal","H","L"], n*5),
        })

    feat = build_features(patients, admissions, diagnoses, lab_results)

    all_metrics = []
    trained_models = {}
    for disease in DISEASE_TARGETS:
        model_bundle, metrics = train_disease_model(feat, disease)
        trained_models[disease] = (model_bundle, metrics)
        if metrics:
            all_metrics.append(metrics)

    # Save consolidated metrics
    metrics_df = pd.DataFrame(all_metrics)
    metrics_df.to_csv(MODEL_DIR / "all_disease_metrics.csv", index=False)
    logger.info(f"\n=== Disease Risk Model Summary ===\n{metrics_df.to_string(index=False)}")

    # Patient risk scorecard
    scorecard = score_patients(feat, trained_models)
    scorecard.to_csv(MODEL_DIR / "patient_risk_scorecard.csv", index=False)
    logger.info(f"Risk scorecard saved: {len(scorecard)} patients scored")

    with open(MODEL_DIR / "metrics.json", "w") as f:
        json.dump(all_metrics, f, indent=2)

    logger.success("Disease Risk Prediction complete.")
    return trained_models


if __name__ == "__main__":
    main()
