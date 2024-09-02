"""
ML Model: ICU Mortality Prediction
Model: LightGBM on time-series aggregated ICU vitals

Usage:
    python ml_models/icu_mortality/train.py
    python ml_models/icu_mortality/train.py ./data/raw
"""

import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger

import lightgbm as lgb
import shap
import joblib
import json
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
MODEL_DIR    = Path("ml_models/icu_mortality/artifacts")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

LGBM_PARAMS = {
    "objective":         "binary",
    "metric":            ["auc", "binary_logloss"],
    "n_estimators":      500,
    "num_leaves":        63,
    "learning_rate":     0.03,
    "feature_fraction":  0.8,
    "bagging_fraction":  0.8,
    "bagging_freq":      5,
    "min_child_samples": 20,
    "lambda_l1":         0.1,
    "lambda_l2":         0.1,
    "is_unbalance":      True,
    "verbose":           -1,
    "random_state":      RANDOM_STATE,
    "n_jobs":            -1,
}


def aggregate_icu_vitals(icu_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-patient vital statistics from raw ICU readings."""
    logger.info("Aggregating ICU vitals ...")
    vitals = ["heart_rate","blood_pressure_sys","blood_pressure_dia",
              "spo2","respiration_rate","temperature","mean_arterial_pressure"]

    agg = {}
    for v in vitals:
        if v in icu_df.columns:
            agg[f"{v}_mean"]  = (v, "mean")
            agg[f"{v}_min"]   = (v, "min")
            agg[f"{v}_max"]   = (v, "max")
            agg[f"{v}_std"]   = (v, "std")

    extra = {}
    if "alarm_triggered"    in icu_df.columns: extra["alarm_count"]    = ("alarm_triggered",    "sum")
    if "critical_vitals_flag" in icu_df.columns: extra["critical_count"] = ("critical_vitals_flag","sum")
    if "on_ventilator"      in icu_df.columns: extra["on_vent_flag"]   = ("on_ventilator",      "any")
    extra["n_readings"] = (vitals[0] if vitals[0] in icu_df.columns else icu_df.columns[0], "count")

    feat = icu_df.groupby("patient_id").agg(**{**agg, **extra}).reset_index()

    # Derived features
    if "heart_rate_mean" in feat.columns and "blood_pressure_sys_mean" in feat.columns:
        feat["shock_index"]    = feat["heart_rate_mean"] / feat["blood_pressure_sys_mean"].replace(0, 1)
    if "spo2_min"   in feat.columns: feat["hypoxia"]     = (feat["spo2_min"]   < 88).astype(int)
    if "heart_rate_max" in feat.columns: feat["tachycardia"] = (feat["heart_rate_max"] > 120).astype(int)
    if "temperature_max" in feat.columns: feat["fever"]      = (feat["temperature_max"] > 39.0).astype(int)
    if "alarm_count" in feat.columns and "n_readings" in feat.columns:
        feat["alarm_rate"] = feat["alarm_count"] / feat["n_readings"].replace(0, 1)

    return feat


def generate_synthetic_data(n: int = 8000, seed: int = 42):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "heart_rate_mean":          rng.normal(85, 20, n).clip(40, 180),
        "heart_rate_max":           rng.normal(110, 25, n).clip(60, 200),
        "heart_rate_min":           rng.normal(65, 15, n).clip(30, 100),
        "heart_rate_std":           rng.uniform(2, 25, n),
        "blood_pressure_sys_mean":  rng.normal(115, 22, n).clip(60, 220),
        "blood_pressure_sys_min":   rng.normal(90, 20, n).clip(50, 180),
        "spo2_mean":                rng.normal(96.5, 2.5, n).clip(70, 100),
        "spo2_min":                 rng.normal(93, 4, n).clip(60, 100),
        "respiration_rate_mean":    rng.normal(18, 5, n).clip(8, 50),
        "temperature_max":          rng.normal(37.5, 1.0, n).clip(34, 42),
        "mean_arterial_pressure_mean": rng.normal(80, 15, n).clip(40, 150),
        "alarm_count":              rng.poisson(8, n),
        "critical_count":           rng.poisson(1, n),
        "n_readings":               rng.integers(200, 18000, n),
        "on_vent_flag":             rng.choice([1,0], n, p=[0.30,0.70]),
        "shock_index":              rng.normal(0.72, 0.15, n).clip(0.3, 2.0),
        "hypoxia":                  rng.choice([1,0], n, p=[0.15,0.85]),
        "tachycardia":              rng.choice([1,0], n, p=[0.35,0.65]),
        "fever":                    rng.choice([1,0], n, p=[0.18,0.82]),
        "alarm_rate":               rng.uniform(0, 0.15, n),
    })
    log_odds = (-3.5
                + 1.2*df["on_vent_flag"]
                + 0.8*df["hypoxia"]
                + 0.5*df["critical_count"]/10
                + 0.4*df["tachycardia"]
                + 0.3*df["fever"]
                + rng.normal(0, 0.5, n))
    prob = 1 / (1 + np.exp(-log_odds))
    mortality = rng.binomial(1, np.clip(prob, 0.01, 0.99), n)
    return df, pd.Series(mortality, name="mortality")


def train():
    logger.info("ICU Mortality Prediction -- Training ...")

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "./data/raw"
    try:
        icu_raw = pd.read_parquet(Path(data_dir) / "icu_vitals")
        feat_df = aggregate_icu_vitals(icu_raw)

        # Build mortality label from admissions (discharge_status == Expired)
        adm = pd.read_parquet(Path(data_dir) / "admissions")
        expired_patients = set(
            adm.loc[adm["discharge_status"] == "Expired", "patient_id"].unique()
        )
        feat_df["mortality"] = feat_df["patient_id"].isin(expired_patients).astype(int)

        X = feat_df.drop(columns=["patient_id","mortality"]).select_dtypes(include=np.number)
        y = feat_df["mortality"]
        logger.info(f"Loaded from parquet: {X.shape}, mortality rate: {y.mean():.2%}")
    except FileNotFoundError:
        logger.warning("Parquet files not found -- using synthetic data ...")
        X, y = generate_synthetic_data()

    X = X.fillna(X.median())

    logger.info(f"Dataset: {X.shape}  Mortality rate: {y.mean():.2%}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )

    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(100)],
    )

    y_prob  = model.predict_proba(X_test)[:, 1]
    auc_roc = roc_auc_score(y_test, y_prob)
    auc_pr  = average_precision_score(y_test, y_prob)
    brier   = brier_score_loss(y_test, y_prob)
    logger.info(f"AUC-ROC={auc_roc:.4f}  AUC-PR={auc_pr:.4f}  Brier={brier:.4f}")

    # SHAP
    logger.info("Computing SHAP values ...")
    explainer  = shap.TreeExplainer(model)
    sample     = min(500, len(X_test))
    shap_vals  = explainer.shap_values(X_test.iloc[:sample])
    # LightGBM returns list [neg_class, pos_class] — use positive class
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[1]

    feat_imp = pd.DataFrame({
        "feature":         list(X.columns),
        "shap_importance": np.abs(shap_vals).mean(axis=0),
    }).sort_values("shap_importance", ascending=False)
    logger.info(f"\nTop 10 Mortality Predictors:\n{feat_imp.head(10).to_string()}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    joblib.dump(model, MODEL_DIR / f"icu_mortality_model_{run_id}.pkl")
    feat_imp.to_csv(MODEL_DIR / "feature_importance.csv", index=False)
    metrics = {"run_id": run_id, "auc_roc": round(auc_roc,4),
               "auc_pr": round(auc_pr,4), "brier": round(brier,4)}
    with open(MODEL_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    logger.success("ICU Mortality model saved.")
    return model, metrics


if __name__ == "__main__":
    train()
