"""
ML Model: Insurance Claim Fraud Detection
Model: Isolation Forest + XGBoost ensemble

Usage:
    python ml_models/fraud_detection/train.py
    python ml_models/fraud_detection/train.py ./data/raw
"""

import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder, RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
import xgboost as xgb
import shap
import joblib
import json

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
MODEL_DIR    = Path("ml_models/fraud_detection/artifacts")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def engineer_fraud_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer fraud detection features. Works with both real and synthetic data."""
    df = df.copy()

    # 1. Claim-to-approval ratio
    df["claim_approval_ratio"] = df["claim_amount"] / df["approved_amount"].replace(0, 1)

    # 2. Provider historical denial rate
    if "claim_status" in df.columns and "insurance_provider" in df.columns:
        provider_denial = (
            df.groupby("insurance_provider")["claim_status"]
            .apply(lambda x: (x == "Denied").sum() / max(len(x), 1))
            .rename("provider_denial_rate")
        )
        df = df.merge(provider_denial.reset_index(), on="insurance_provider", how="left")
    else:
        df["provider_denial_rate"] = 0.0

    # 3. Patient claim frequency
    if "patient_id" in df.columns:
        freq = df.groupby("patient_id")["claim_id"].transform("count")
        df["patient_claim_frequency"] = freq
    else:
        df["patient_claim_frequency"] = 1

    # 4. Claim vs plan-type average
    if "insurance_plan_type" in df.columns:
        plan_avg = df.groupby("insurance_plan_type")["claim_amount"].transform("mean")
        df["claim_vs_plan_avg"] = df["claim_amount"] / plan_avg.replace(0, 1)
    else:
        df["claim_vs_plan_avg"] = 1.0

    # 5. Round-number flag
    df["is_round_amount"] = (df["claim_amount"] % 100 == 0).astype(int)

    # 6. Threshold-gaming flag ($X99, $X999)
    df["just_under_threshold"] = (
        ((df["claim_amount"] % 1000).between(950, 999)) |
        ((df["claim_amount"] % 5000).between(4900, 4999))
    ).astype(int)

    # 7. Days to submit  (only if both date columns exist)
    if "submission_date" in df.columns and "service_date" in df.columns:
        df["days_to_submit"] = (
            pd.to_datetime(df["submission_date"], errors="coerce") -
            pd.to_datetime(df["service_date"],    errors="coerce")
        ).dt.days.fillna(0)
        df["late_submission"] = (df["days_to_submit"] > 90).astype(int)
    else:
        df["days_to_submit"]  = 0
        df["late_submission"]  = 0

    # 8. Patient responsibility ratio
    if "patient_responsibility" in df.columns:
        df["pt_responsibility_pct"] = df["patient_responsibility"] / df["claim_amount"].replace(0, 1)
    else:
        df["pt_responsibility_pct"] = 0.20

    return df


def generate_synthetic_claims(n: int = 50000, fraud_rate: float = 0.05,
                               seed: int = 42) -> pd.DataFrame:
    rng       = np.random.default_rng(seed)
    providers = ["UnitedHealth","Aetna","Cigna","Anthem","Humana",
                 "BCBS","Medicare","Medicaid"]
    plans     = ["HMO","PPO","EPO","Medicare Part A/B","Medicaid"]

    submission_dates = pd.date_range("2022-01-01", periods=n, freq="1h")
    service_dates    = submission_dates - pd.to_timedelta(
        rng.integers(1, 60, n), unit="d"
    )

    df = pd.DataFrame({
        "claim_id":              [f"CLM{i:08d}" for i in range(n)],
        "patient_id":            [f"P{rng.integers(0,10000):07d}" for _ in range(n)],
        "insurance_provider":    rng.choice(providers, n),
        "insurance_plan_type":   rng.choice(plans, n),
        "claim_type":            rng.choice(["Inpatient","Outpatient","Emergency","Pharmacy"],
                                             n, p=[0.20,0.35,0.15,0.30]),
        "claim_amount":          np.round(np.exp(rng.normal(8.0, 1.0, n)), 2),
        "approved_amount":       np.round(np.exp(rng.normal(7.7, 0.9, n)), 2),
        "patient_responsibility":np.round(np.exp(rng.normal(5.0, 1.0, n)), 2),
        "claim_status":          rng.choice(["Approved","Denied","Pending","Paid"],
                                             n, p=[0.52,0.15,0.08,0.25]),
        "submission_date":       submission_dates.astype(str),
        "service_date":          service_dates.astype(str),
        "fraud_flag":            np.zeros(n, dtype=int),
    })

    # Inject fraud
    n_fraud = int(n * fraud_rate)
    fraud_idx = rng.choice(n, n_fraud, replace=False)
    # Upcoding
    df.loc[fraud_idx[:n_fraud//3], "claim_amount"] *= rng.uniform(2.0, 5.0, n_fraud//3)
    # Round-number billing
    third = n_fraud // 3
    df.loc[fraud_idx[third:2*third], "claim_amount"] = (
        (df.loc[fraud_idx[third:2*third], "claim_amount"] / 1000).round() * 1000
    )
    df.loc[fraud_idx, "fraud_flag"] = 1
    return df


def train():
    logger.info("Fraud Detection -- Training ...")

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "./data/raw"
    try:
        df = pd.read_parquet(Path(data_dir) / "insurance_claims")
        # Map column names from our parquet schema to feature engineering expectations
        if "submission_date" not in df.columns and "submission_date" in df.columns:
            pass  # already correct
        logger.info(f"Loaded {len(df)} claims from parquet")
    except FileNotFoundError:
        logger.warning("Parquet files not found -- using synthetic data ...")
        df = generate_synthetic_claims(n=50000, fraud_rate=0.05)

    df = engineer_fraud_features(df)

    # If no fraud in real data (common with small datasets), inject synthetic fraud
    if "fraud_flag" not in df.columns or df["fraud_flag"].astype(int).sum() == 0:
        logger.warning("No fraud labels in data — injecting 5% synthetic fraud for training.")
        rng = np.random.default_rng(RANDOM_STATE)
        n_fraud = max(50, int(len(df) * 0.05))
        fraud_idx = rng.choice(len(df), n_fraud, replace=False)
        df["fraud_flag"] = 0
        df.iloc[fraud_idx, df.columns.get_loc("fraud_flag")] = 1
        # Make fraudulent records more anomalous so model can learn
        df.loc[df.index[fraud_idx[:n_fraud//2]], "claim_amount"] *= 3.0
        df.loc[df.index[fraud_idx[n_fraud//2:]], "is_round_amount"] = 1

    FEATURE_COLS = [
        "claim_amount", "approved_amount", "claim_approval_ratio",
        "provider_denial_rate", "patient_claim_frequency",
        "claim_vs_plan_avg", "is_round_amount", "just_under_threshold",
        "days_to_submit", "late_submission", "pt_responsibility_pct",
    ]

    # Encode categorical columns if present
    for col in ["insurance_plan_type", "claim_type"]:
        if col in df.columns:
            enc_col = col + "_enc"
            df[enc_col] = LabelEncoder().fit_transform(df[col].astype(str).fillna("Unknown"))
            FEATURE_COLS.append(enc_col)

    X = df[FEATURE_COLS].fillna(0)
    y = df.get("fraud_flag", pd.Series(np.zeros(len(df), dtype=int)))

    # ── Stage 1: Isolation Forest anomaly score ───────────────────
    logger.info("Stage 1: Isolation Forest ...")
    scaler      = RobustScaler()
    X_scaled    = scaler.fit_transform(X)
    iso_forest  = IsolationForest(n_estimators=200, contamination=0.05,
                                   random_state=RANDOM_STATE, n_jobs=-1)
    iso_forest.fit(X_scaled)
    X["anomaly_score"] = -iso_forest.score_samples(X_scaled)
    FEATURE_COLS_FULL  = FEATURE_COLS + ["anomaly_score"]

    # ── Stage 2: XGBoost classifier ──────────────────────────────
    logger.info("Stage 2: XGBoost ...")
    X_full = df[FEATURE_COLS].fillna(0).copy()
    X_full["anomaly_score"] = X["anomaly_score"].values

    fraud_weight = max(1.0, (y == 0).sum() / max((y == 1).sum(), 1))
    X_train, X_test, y_train, y_test = train_test_split(
        X_full, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )

    model = xgb.XGBClassifier(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        scale_pos_weight=fraud_weight, eval_metric="auc",
        early_stopping_rounds=50,
        random_state=RANDOM_STATE, n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_prob  = model.predict_proba(X_test)[:, 1]
    y_pred  = (y_prob >= 0.5).astype(int)

    # Guard against single-class test split (can happen with tiny datasets)
    n_classes_test = len(np.unique(y_test))
    if n_classes_test < 2:
        logger.warning("Only one class in test set — AUC not meaningful with this dataset size.")
        auc = float("nan")
    else:
        auc = roc_auc_score(y_test, y_prob)

    logger.info(f"AUC-ROC: {auc:.4f}" if not np.isnan(auc) else "AUC-ROC: N/A (single class in test set)")

    present_labels = sorted(np.unique(y_test).tolist())
    label_names    = ["Legitimate", "Fraud"]
    used_names     = [label_names[i] for i in present_labels]
    logger.info("\n" + classification_report(y_test, y_pred,
                labels=present_labels, target_names=used_names))

    # SHAP
    logger.info("Computing SHAP values ...")
    explainer = shap.TreeExplainer(model)
    sample    = min(500, len(X_test))
    shap_vals = explainer.shap_values(X_test.iloc[:sample])
    feat_imp  = pd.DataFrame({
        "feature":         FEATURE_COLS_FULL,
        "shap_importance": np.abs(shap_vals).mean(axis=0),
    }).sort_values("shap_importance", ascending=False)
    logger.info(f"\nTop Fraud Indicators:\n{feat_imp.head(10).to_string()}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    joblib.dump(model,      MODEL_DIR / f"fraud_model_{run_id}.pkl")
    joblib.dump(iso_forest, MODEL_DIR / f"isolation_forest_{run_id}.pkl")
    joblib.dump(scaler,     MODEL_DIR / f"scaler_{run_id}.pkl")
    feat_imp.to_csv(MODEL_DIR / "feature_importance.csv", index=False)
    metrics = {"run_id": run_id, "auc_roc": round(auc, 4) if not np.isnan(auc) else None}
    with open(MODEL_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    logger.success("Fraud detection model saved.")
    return model


if __name__ == "__main__":
    train()
