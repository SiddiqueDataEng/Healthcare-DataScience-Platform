"""
ML Model: Length of Stay (LOS) Prediction
Model: XGBoost Regressor

Usage:
    python ml_models/los_prediction/train.py
    python ml_models/los_prediction/train.py ./data/raw
"""

import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import shap
import joblib
import json

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
MODEL_DIR    = Path("ml_models/los_prediction/artifacts")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

LOS_BINS   = [0, 1, 3, 7, 14, 30, float("inf")]
LOS_LABELS = ["<1d", "1-3d", "3-7d", "7-14d", "14-30d", "30d+"]

XGB_PARAMS = {
    "n_estimators":          500,
    "max_depth":             7,
    "learning_rate":         0.05,
    "subsample":             0.8,
    "colsample_bytree":      0.8,
    "min_child_weight":      10,
    "gamma":                 0.1,
    "reg_alpha":             0.1,
    "reg_lambda":            1.0,
    "objective":             "reg:squarederror",
    "early_stopping_rounds": 50,
    "random_state":          RANDOM_STATE,
    "n_jobs":                -1,
}


def generate_synthetic_los_data(n: int = 30000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "age":                rng.normal(58, 18, n).clip(18, 100),
        "gender":             rng.integers(0, 2, n),
        "admission_type":     rng.choice(range(5), n, p=[0.38,0.32,0.18,0.07,0.05]),
        "ward":               rng.integers(0, 9, n),
        "icu_hours":          np.where(rng.random(n)<0.15, rng.exponential(20, n), 0),
        "surgery_performed":  rng.binomial(1, 0.28, n),
        "comorbidity_count":  rng.poisson(2.5, n),
        "has_diabetes":       rng.binomial(1, 0.25, n),
        "has_heart_failure":  rng.binomial(1, 0.12, n),
        "has_ckd":            rng.binomial(1, 0.10, n),
        "has_sepsis":         rng.binomial(1, 0.04, n),
        "abnormal_lab_count": rng.poisson(2, n),
        "medication_count":   rng.poisson(5, n),
        "insurance_type":     rng.integers(0, 7, n),
    })
    log_los = (0.5 + 0.008*df["age"]
               + 0.4*(df["admission_type"]==0).astype(int)
               + 0.8*(df["ward"]==2).astype(int)
               + 0.003*df["icu_hours"]
               + 0.5*df["surgery_performed"]
               + 0.1*df["comorbidity_count"]
               + 0.3*df["has_heart_failure"]
               + 0.3*df["has_sepsis"]
               + rng.normal(0, 0.5, n))
    df["length_of_stay"] = np.clip(np.exp(log_los), 0.5, 90)
    return df


def train():
    logger.info("LOS Prediction -- Training ...")

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "./data/raw"
    try:
        adm = pd.read_parquet(Path(data_dir) / "admissions")
        # Compute LOS from dates (SQL generated column, not in parquet)
        adm["length_of_stay"] = (
            pd.to_datetime(adm["discharge_date"], errors="coerce") -
            pd.to_datetime(adm["admit_date"],     errors="coerce")
        ).dt.days.clip(0, 365)

        feature_cols = ["length_of_stay", "admission_type", "ward",
                        "icu_hours", "surgery_performed", "actual_cost", "drg_code"]
        df = adm[[c for c in feature_cols if c in adm.columns]].dropna(subset=["length_of_stay"])
        logger.info(f"Loaded {len(df)} admission records from parquet")
    except FileNotFoundError:
        logger.warning("Parquet files not found -- using synthetic data ...")
        df = generate_synthetic_los_data()

    # Encode any object columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = LabelEncoder().fit_transform(df[col].astype(str))

    target = "length_of_stay"
    feature_cols = [c for c in df.columns if c != target]
    X = df[feature_cols].fillna(df[feature_cols].median())
    y = df[target].clip(0.5, 90)

    logger.info(f"LOS stats: mean={y.mean():.1f}d  median={y.median():.1f}d  "
                f"p95={y.quantile(0.95):.1f}d")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_STATE
    )

    model = xgb.XGBRegressor(**XGB_PARAMS)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=100)

    y_pred = model.predict(X_test).clip(0.5, 90)

    mae  = mean_absolute_error(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2   = r2_score(y_test, y_pred)
    mask = y_test > 1
    mape = float(np.mean(np.abs((y_test[mask] - y_pred[mask]) / y_test[mask])) * 100)

    logger.info(f"MAE={mae:.2f}d  RMSE={rmse:.2f}d  R2={r2:.4f}  MAPE={mape:.1f}%")

    y_test_bucket = pd.cut(y_test.reset_index(drop=True),
                           bins=LOS_BINS, labels=LOS_LABELS)
    y_pred_bucket = pd.cut(pd.Series(y_pred),
                           bins=LOS_BINS, labels=LOS_LABELS)
    bucket_acc = (y_test_bucket.values == y_pred_bucket.values).mean()
    logger.info(f"LOS bucket accuracy: {bucket_acc:.2%}")

    # SHAP
    logger.info("Computing SHAP values ...")
    explainer = shap.TreeExplainer(model)
    sample    = min(500, len(X_test))
    shap_vals = explainer.shap_values(X_test.iloc[:sample])
    feat_imp  = pd.DataFrame({
        "feature":        feature_cols,
        "shap_importance": np.abs(shap_vals).mean(axis=0),
    }).sort_values("shap_importance", ascending=False)
    logger.info(f"\nTop 10 LOS predictors:\n{feat_imp.head(10).to_string()}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    joblib.dump(model, MODEL_DIR / f"los_model_{run_id}.pkl")
    feat_imp.to_csv(MODEL_DIR / "feature_importance.csv", index=False)
    metrics = {"run_id": run_id, "mae": round(mae,3), "rmse": round(rmse,3),
               "r2": round(r2,4), "mape": round(mape,2),
               "bucket_accuracy": round(bucket_acc,4)}
    with open(MODEL_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    logger.success("LOS model saved.")
    return model, metrics


if __name__ == "__main__":
    train()
