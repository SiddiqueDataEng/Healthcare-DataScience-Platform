"""
ML Model: 30-Day Readmission Prediction
Model: XGBoost + SHAP explainability

Usage:
    python ml_models/readmission/train.py
    python ml_models/readmission/train.py ./data/raw
"""

import os
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger

from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    roc_auc_score, classification_report,
    average_precision_score, brier_score_loss,
)
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb
import shap
import joblib
import json

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
TEST_SIZE    = 0.20
MODEL_DIR    = Path("ml_models/readmission/artifacts")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# XGBoost 3.x: early_stopping_rounds belongs in the constructor, not fit()
XGB_PARAMS = {
    "n_estimators":         500,
    "max_depth":            6,
    "learning_rate":        0.05,
    "subsample":            0.8,
    "colsample_bytree":     0.8,
    "min_child_weight":     10,
    "gamma":                0.1,
    "reg_alpha":            0.1,
    "reg_lambda":           1.0,
    "scale_pos_weight":     5,
    "eval_metric":          "auc",
    "early_stopping_rounds": 50,        # XGBoost 3.x: constructor param
    "random_state":         RANDOM_STATE,
    "n_jobs":               -1,
}


# ─── Feature Engineering ─────────────────────────────────────────────

def load_features_from_parquet(data_dir: str = "./data/raw") -> pd.DataFrame:
    data_dir = Path(data_dir)
    logger.info("Loading admissions ...")
    adm  = pd.read_parquet(data_dir / "admissions")
    logger.info("Loading patients ...")
    pts  = pd.read_parquet(data_dir / "patients")
    logger.info("Loading diagnoses ...")
    dx   = pd.read_parquet(data_dir / "diagnoses")
    logger.info("Loading lab results ...")
    labs = pd.read_parquet(data_dir / "lab_results")
    logger.info("Loading prescriptions ...")
    rx   = pd.read_parquet(data_dir / "prescriptions")
    return build_feature_matrix(adm, pts, dx, labs, rx)


def _safe_groupby_count(df, group_col, value_col, filter_mask=None, result_name="count"):
    """Safe groupby count that handles missing/all-null group columns."""
    if group_col not in df.columns or df[group_col].isna().all():
        return pd.Series(dtype="Int64", name=result_name)
    sub = df[df[group_col].notna()]
    if filter_mask is not None:
        sub = sub[filter_mask.reindex(sub.index, fill_value=False)]
    return sub.groupby(group_col)[value_col].count().rename(result_name)


def build_feature_matrix(adm, pts, dx, labs, rx) -> pd.DataFrame:
    logger.info("Engineering features ...")

    # ── Patient features ──────────────────────────────────────────
    pt_feat = pts[["patient_id", "gender", "ethnicity", "blood_group",
                   "marital_status", "insurance_plan_type",
                   "annual_income_band", "dob"]].copy()
    pt_feat["age"] = (
        pd.to_datetime("today") - pd.to_datetime(pt_feat["dob"], errors="coerce")
    ).dt.days / 365.25
    pt_feat.drop(columns=["dob"], inplace=True)

    # ── Admission features ────────────────────────────────────────
    needed = ["admission_id", "patient_id", "hospital_id",
              "admission_type", "admission_source", "ward",
              "icu_hours", "surgery_performed", "drg_code",
              "actual_cost", "discharge_status",
              "readmission_within_30d",
              "admit_date", "discharge_date"]
    adm_feat = adm[[c for c in needed if c in adm.columns]].copy()

    # Compute LOS (SQL generated column, not in parquet)
    adm_feat["length_of_stay"] = (
        pd.to_datetime(adm_feat.get("discharge_date"), errors="coerce") -
        pd.to_datetime(adm_feat.get("admit_date"),     errors="coerce")
    ).dt.days.fillna(0).clip(0, 365)

    adm_feat["readmitted_30d"] = adm_feat["readmission_within_30d"].astype(int)
    adm_feat = adm_feat[adm_feat["discharge_status"] != "Still Admitted"].copy()
    adm_feat.drop(columns=["admit_date", "discharge_date",
                            "readmission_within_30d"], errors="ignore", inplace=True)

    # ── Comorbidity counts ────────────────────────────────────────
    comorbidity_count = _safe_groupby_count(
        dx[dx["diagnosis_type"].isin(["Secondary", "Comorbidity"])],
        "admission_id", "diagnosis_id", result_name="comorbidity_count"
    )

    def condition_flag(codes, name):
        mask = dx["icd10_code"].str.startswith(tuple(codes))
        return _safe_groupby_count(
            dx, "admission_id", "diagnosis_id",
            filter_mask=mask, result_name=name
        ).gt(0).astype(int)

    has_diabetes   = condition_flag(["E11","E10"], "has_diabetes")
    has_htn        = condition_flag(["I10"],       "has_hypertension")
    has_hf         = condition_flag(["I50"],       "has_heart_failure")
    has_ckd        = condition_flag(["N18"],       "has_ckd")
    has_copd       = condition_flag(["J44"],       "has_copd")
    has_depression = condition_flag(["F32","F33"], "has_depression")

    # ── Lab features ──────────────────────────────────────────────
    key_labs = ["HbA1c","Creatinine","BUN","Sodium","Potassium",
                "Hemoglobin","WBC","BNP","Troponin I"]

    lab_pivot = pd.DataFrame()
    if "admission_id" in labs.columns and labs["admission_id"].notna().any():
        sub = (labs[labs["test_name"].isin(key_labs) & labs["admission_id"].notna()]
               .sort_values("collection_datetime"))
        lab_pivot = (
            sub.groupby(["admission_id","test_name"])["result_numeric"].last()
               .unstack(fill_value=np.nan)
        )
        lab_pivot.columns = [f"lab_{c.lower().replace(' ','_')}" for c in lab_pivot.columns]

    abnormal_count = _safe_groupby_count(
        labs[labs["abnormal_flag"] != "Normal"] if "abnormal_flag" in labs.columns else labs,
        "admission_id", "result_id", result_name="abnormal_lab_count"
    )

    # ── Rx count ──────────────────────────────────────────────────
    rx_count = _safe_groupby_count(rx, "admission_id", "prescription_id",
                                   result_name="medication_count")

    # ── Join ──────────────────────────────────────────────────────
    df = adm_feat.merge(pt_feat, on="patient_id", how="left")
    for series in [comorbidity_count, has_diabetes, has_htn, has_hf,
                   has_ckd, has_copd, has_depression, abnormal_count, rx_count]:
        if not series.empty:
            df = df.join(series, on="admission_id", how="left")
    if not lab_pivot.empty:
        df = df.join(lab_pivot, on="admission_id", how="left")

    # Fill nulls
    num_cols = df.select_dtypes(include=np.number).columns
    df[num_cols] = df[num_cols].fillna(df[num_cols].median())

    # Encode categoricals
    cat_cols = ["gender","ethnicity","blood_group","marital_status",
                "insurance_plan_type","annual_income_band",
                "admission_type","admission_source","ward",
                "drg_code","discharge_status"]
    for col in cat_cols:
        if col in df.columns:
            df[col] = LabelEncoder().fit_transform(df[col].astype(str).fillna("Unknown"))

    logger.info(f"Feature matrix shape: {df.shape}")
    return df


# ─── Training ────────────────────────────────────────────────────────

def train(df: pd.DataFrame):
    DROP_COLS = {"admission_id","patient_id","hospital_id",
                 "readmission_within_30d","readmitted_30d",
                 "readmission_within_90d","prior_admission_id"}
    FEATURE_COLS = [c for c in df.columns if c not in DROP_COLS]

    X = df[FEATURE_COLS].copy()
    y = df["readmitted_30d"].copy()

    logger.info(f"Target distribution: {y.value_counts().to_dict()}")
    logger.info(f"Positive rate: {y.mean():.3%}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE
    )
    logger.info(f"Train: {X_train.shape}  Test: {X_test.shape}")

    # ── 5-fold CV ─────────────────────────────────────────────────
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_scores = []
    for fold, (tr_idx, val_idx) in enumerate(cv.split(X_train, y_train)):
        Xtr, Xvl = X_train.iloc[tr_idx], X_train.iloc[val_idx]
        ytr, yvl = y_train.iloc[tr_idx], y_train.iloc[val_idx]
        m = xgb.XGBClassifier(**XGB_PARAMS)
        m.fit(Xtr, ytr, eval_set=[(Xvl, yvl)], verbose=False)
        score = roc_auc_score(yvl, m.predict_proba(Xvl)[:, 1])
        cv_scores.append(score)
        logger.info(f"  Fold {fold+1}/5 AUC-ROC: {score:.4f}")
    logger.info(f"CV AUC-ROC: {np.mean(cv_scores):.4f} +/- {np.std(cv_scores):.4f}")

    # ── Final model ───────────────────────────────────────────────
    logger.info("Training final model ...")
    final_model = xgb.XGBClassifier(**XGB_PARAMS)
    final_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=100)

    # ── Calibration ───────────────────────────────────────────────
    cal_model = CalibratedClassifierCV(final_model, method="isotonic", cv="prefit")
    cal_model.fit(X_test, y_test)

    # ── Evaluation ───────────────────────────────────────────────
    y_prob = cal_model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.30).astype(int)

    auc_roc = roc_auc_score(y_test, y_prob)
    auc_pr  = average_precision_score(y_test, y_prob)
    brier   = brier_score_loss(y_test, y_prob)

    logger.info(f"Test AUC-ROC: {auc_roc:.4f} | AUC-PR: {auc_pr:.4f} | Brier: {brier:.4f}")
    logger.info("\n" + classification_report(y_test, y_pred,
                target_names=["Not Readmitted","Readmitted"]))

    # ── SHAP ──────────────────────────────────────────────────────
    logger.info("Computing SHAP values ...")
    explainer   = shap.TreeExplainer(final_model)
    sample_size = min(500, len(X_test))
    shap_vals   = explainer.shap_values(X_test.iloc[:sample_size])

    feat_imp = pd.DataFrame({
        "feature":         FEATURE_COLS,
        "mean_abs_shap":   np.abs(shap_vals).mean(axis=0),
        "xgb_importance":  final_model.feature_importances_,
    }).sort_values("mean_abs_shap", ascending=False)
    logger.info(f"\nTop 15 features:\n{feat_imp.head(15).to_string()}")

    # ── Save ──────────────────────────────────────────────────────
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    joblib.dump(cal_model, MODEL_DIR / f"readmission_model_{run_id}.pkl")
    feat_imp.to_csv(MODEL_DIR / "feature_importance.csv", index=False)

    metrics = {
        "run_id": run_id, "auc_roc": round(auc_roc, 4),
        "auc_pr": round(auc_pr, 4), "brier_score": round(brier, 4),
        "cv_auc_mean": round(float(np.mean(cv_scores)), 4),
        "cv_auc_std":  round(float(np.std(cv_scores)), 4),
        "train_size": len(X_train), "test_size": len(X_test),
        "n_features": len(FEATURE_COLS),
        "positive_rate": round(float(y.mean()), 4),
        "timestamp": datetime.now().isoformat(),
    }
    with open(MODEL_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    logger.success(f"Model saved: readmission_model_{run_id}.pkl")
    return cal_model, metrics


if __name__ == "__main__":
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "./data/raw"

    try:
        df = load_features_from_parquet(data_dir)
    except FileNotFoundError:
        logger.warning("Parquet files not found — using synthetic data for demo ...")
        rng = np.random.default_rng(RANDOM_STATE)
        n = 20000
        df = pd.DataFrame({
            "age":               rng.normal(58, 18, n).clip(18, 100),
            "gender":            rng.integers(0, 2, n),
            "length_of_stay":    np.abs(rng.normal(5, 3, n)),
            "icu_hours":         np.abs(rng.normal(10, 20, n)),
            "comorbidity_count": rng.poisson(2.5, n),
            "has_diabetes":      rng.binomial(1, 0.25, n),
            "has_heart_failure": rng.binomial(1, 0.12, n),
            "has_ckd":           rng.binomial(1, 0.10, n),
            "medication_count":  rng.poisson(5, n),
            "abnormal_lab_count":rng.poisson(2, n),
            "admission_type":    rng.integers(0, 5, n),
            "ward":              rng.integers(0, 9, n),
            "actual_cost":       np.exp(rng.normal(9, 1, n)),
            "surgery_performed": rng.binomial(1, 0.28, n),
            "discharge_status":  rng.integers(0, 7, n),
        })
        log_odds = (-2.0 + 0.02*df["age"] + 0.3*df["has_heart_failure"]
                    + 0.2*df["has_ckd"] + 0.1*df["comorbidity_count"]
                    + 0.05*df["length_of_stay"] + rng.normal(0, 0.5, n))
        prob = 1 / (1 + np.exp(-log_odds))
        df["readmitted_30d"] = rng.binomial(1, np.clip(prob, 0.01, 0.99), n)

    model, metrics = train(df)
    logger.info(f"Done. Metrics: {metrics}")
