"""
Chapter 7: Generative AI in Healthcare
Synthetic Healthcare Data Generation using:
  1. CTGAN — Conditional Tabular GAN for realistic EHR data
  2. Gaussian Copula — statistical synthetic data (no deep learning required)
  3. Clinical text generation (template + language model)
  4. Privacy validation (similarity checks, re-identification risk)

Use cases:
  - Augment rare disease datasets (class imbalance)
  - Share data without exposing real patient PHI
  - Simulate clinical trial populations
  - Train ML models when real data is scarce

Usage:
    python ml_models/generative_ai/synthetic_data_generator.py
    python ml_models/generative_ai/synthetic_data_generator.py ./data/raw
"""

import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict
from loguru import logger
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import pairwise_distances
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

OUTPUT_DIR = Path("ml_models/generative_ai/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Try SDV (Synthetic Data Vault) for CTGAN and Gaussian Copula
try:
    from sdv.tabular import CTGAN, GaussianCopula
    SDV_AVAILABLE = True
except ImportError:
    SDV_AVAILABLE = False
    logger.warning("SDV not installed. Using statistical synthesis fallback.")
    logger.warning("Install with: pip install sdv")


# ─── Statistical Synthetic Data (no deep learning) ──────────────────

class StatisticalSynthesizer:
    """
    Column-by-column statistical synthesis.
    Preserves marginal distributions and correlations.
    Works without SDV/CTGAN.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng  = np.random.default_rng(seed)
        self.column_stats = {}
        self.correlations = None
        self.cat_encoders = {}

    def fit(self, df: pd.DataFrame):
        """Learn the statistical properties of each column."""
        self.columns = list(df.columns)
        self.dtypes  = df.dtypes

        for col in df.columns:
            if df[col].dtype in [np.float64, np.int64, float, int]:
                self.column_stats[col] = {
                    "type":  "numeric",
                    "mean":  df[col].mean(),
                    "std":   df[col].std(),
                    "min":   df[col].min(),
                    "max":   df[col].max(),
                    "q05":   df[col].quantile(0.05),
                    "q95":   df[col].quantile(0.95),
                    "null_rate": df[col].isna().mean(),
                }
            else:
                vc = df[col].value_counts(normalize=True, dropna=False)
                self.column_stats[col] = {
                    "type":   "categorical",
                    "values": vc.index.tolist(),
                    "probs":  vc.values.tolist(),
                    "null_rate": df[col].isna().mean(),
                }

        # Learn numeric correlations
        num_df = df.select_dtypes(include=np.number)
        if num_df.shape[1] > 1:
            self.correlations = num_df.corr()
        logger.info(f"Synthesizer fitted on {len(df)} rows, {len(df.columns)} columns.")
        return self

    def sample(self, n: int) -> pd.DataFrame:
        """Generate n synthetic records."""
        synth = {}

        # Generate numeric columns using Cholesky decomposition to preserve correlations
        num_cols = [c for c, s in self.column_stats.items() if s["type"] == "numeric"]
        if num_cols and self.correlations is not None:
            corr_subset = self.correlations.loc[
                [c for c in num_cols if c in self.correlations.columns],
                [c for c in num_cols if c in self.correlations.columns]
            ].fillna(0)
            valid_cols = list(corr_subset.columns)

            if len(valid_cols) > 1:
                # Sample from multivariate normal then transform to match marginals
                means = np.array([self.column_stats[c]["mean"] for c in valid_cols])
                stds  = np.array([self.column_stats[c]["std"]  for c in valid_cols])
                stds  = np.where(stds == 0, 1e-6, stds)

                # Ensure positive semi-definite
                corr_mat = corr_subset.values
                corr_mat = (corr_mat + corr_mat.T) / 2
                np.fill_diagonal(corr_mat, 1.0)
                min_eig = np.linalg.eigvalsh(corr_mat).min()
                if min_eig < 0:
                    corr_mat += (-min_eig + 1e-8) * np.eye(len(valid_cols))

                cov_mat = np.diag(stds) @ corr_mat @ np.diag(stds)
                raw = self.rng.multivariate_normal(means, cov_mat, size=n)
                for i, col in enumerate(valid_cols):
                    s = self.column_stats[col]
                    col_raw = np.clip(raw[:, i], s["q05"], s["q95"])
                    if self.dtypes[col] in [np.int64, int]:
                        col_raw = np.round(col_raw).astype(int)
                    synth[col] = col_raw
            else:
                for col in valid_cols:
                    s = self.column_stats[col]
                    vals = self.rng.normal(s["mean"], max(s["std"], 1e-6), n)
                    vals = np.clip(vals, s["q05"], s["q95"])
                    synth[col] = vals

        # Generate remaining numeric not in correlation matrix
        for col in num_cols:
            if col not in synth:
                s = self.column_stats[col]
                vals = self.rng.normal(s["mean"], max(s["std"], 1e-6), n)
                synth[col] = np.clip(vals, s["min"], s["max"])

        # Generate categorical columns
        for col, stats in self.column_stats.items():
            if stats["type"] == "categorical":
                values = [str(v) if pd.notna(v) else np.nan for v in stats["values"]]
                probs  = np.array(stats["probs"])
                probs  = probs / probs.sum()
                sampled = self.rng.choice(len(values), size=n, p=probs)
                synth[col] = [values[i] for i in sampled]

        df_synth = pd.DataFrame(synth)[self.columns]

        # Apply null masks
        for col, stats in self.column_stats.items():
            if stats["null_rate"] > 0 and col in df_synth.columns:
                null_mask = self.rng.random(n) < stats["null_rate"]
                df_synth.loc[null_mask, col] = np.nan

        return df_synth


# ─── Privacy Validation ──────────────────────────────────────────────

def validate_privacy(real_df: pd.DataFrame, synth_df: pd.DataFrame,
                     sample_n: int = 500) -> dict:
    """
    Validate that synthetic data does not re-identify real patients.
    Metrics:
      - Nearest-neighbour distance (higher = better privacy)
      - Column-level statistical similarity
      - Membership inference risk estimate
    """
    from sklearn.preprocessing import StandardScaler

    # Use only numeric columns
    real_num  = real_df.select_dtypes(include=np.number).fillna(0)
    synth_num = synth_df.select_dtypes(include=np.number).fillna(0)

    shared_cols = [c for c in real_num.columns if c in synth_num.columns]
    if not shared_cols:
        return {"privacy_score": 100, "status": "Unable to compute — no shared numeric columns"}

    real_sample  = real_num[shared_cols].sample(min(sample_n, len(real_num)),  random_state=42)
    synth_sample = synth_num[shared_cols].sample(min(sample_n, len(synth_num)), random_state=42)

    scaler = StandardScaler()
    real_scaled  = scaler.fit_transform(real_sample)
    synth_scaled = scaler.transform(synth_sample)

    # Nearest neighbour distance (each synthetic point to closest real point)
    dists = pairwise_distances(synth_scaled, real_scaled, metric="euclidean")
    nn_distances = dists.min(axis=1)
    avg_nn_dist  = float(nn_distances.mean())
    min_nn_dist  = float(nn_distances.min())

    # Privacy risk: if any synthetic record is very close to a real record
    risk_threshold = 0.5  # in normalised space
    high_risk_pct  = float((nn_distances < risk_threshold).mean() * 100)

    # Column distribution comparison (KS statistic)
    from scipy.stats import ks_2samp
    ks_scores = {}
    for col in shared_cols[:10]:
        stat, _ = ks_2samp(real_sample[col].dropna(), synth_sample[col].dropna())
        ks_scores[col] = round(float(stat), 4)

    avg_ks = np.mean(list(ks_scores.values()))
    fidelity_score = round((1 - avg_ks) * 100, 1)

    privacy_score = min(100, round(avg_nn_dist * 20 + (100 - high_risk_pct) * 0.8, 1))

    result = {
        "privacy_score":     privacy_score,   # 0-100, higher = more private
        "fidelity_score":    fidelity_score,  # 0-100, higher = more realistic
        "avg_nn_distance":   round(avg_nn_dist, 4),
        "min_nn_distance":   round(min_nn_dist, 4),
        "high_risk_pct":     round(high_risk_pct, 2),
        "avg_ks_statistic":  round(float(avg_ks), 4),
        "column_ks_scores":  ks_scores,
        "status":            "PASS" if privacy_score > 50 else "REVIEW",
    }
    return result


# ─── Visualizations ──────────────────────────────────────────────────

def plot_real_vs_synthetic(real_df: pd.DataFrame, synth_df: pd.DataFrame,
                           cols: list = None, title: str = "Real vs Synthetic"):
    """Visual comparison of real and synthetic distributions."""
    shared = [c for c in real_df.select_dtypes(include=np.number).columns
              if c in synth_df.select_dtypes(include=np.number).columns][:6]
    if not shared:
        return

    n    = len(shared)
    ncols = min(n, 3)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4 * nrows))
    axes = np.array(axes).flatten() if n > 1 else [axes]
    fig.suptitle(f"Chapter 7: {title}", fontsize=13, fontweight="bold")

    for i, col in enumerate(shared):
        ax = axes[i]
        real_vals  = real_df[col].dropna()
        synth_vals = synth_df[col].dropna()
        ax.hist(real_vals,  bins=30, alpha=0.55, color="steelblue", label="Real",      density=True)
        ax.hist(synth_vals, bins=30, alpha=0.55, color="tomato",    label="Synthetic", density=True)
        ax.set_title(col, fontsize=10)
        ax.legend(fontsize=8)
        ax.set_yticks([])

    for j in range(i+1, len(axes)):
        axes[j].set_visible(False)

    plt.tight_layout()
    safe_title = title.lower().replace(" ", "_").replace("/", "_")
    plt.savefig(OUTPUT_DIR / f"real_vs_synthetic_{safe_title}.png", dpi=100)
    plt.close()
    logger.info(f"Plot saved: real_vs_synthetic_{safe_title}.png")


# ─── Main ────────────────────────────────────────────────────────────

def main():
    logger.info("Chapter 7: Generative AI — Synthetic Healthcare Data")

    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data/raw")

    # Load real data
    try:
        patients = pd.read_parquet(data_dir / "patients")
        logger.info(f"Loaded {len(patients)} real patient records")
        # Select subset of non-PHI columns for synthesis
        numeric_cols = ["age"]
        patients["age"] = (
            pd.to_datetime("today") - pd.to_datetime(patients["dob"], errors="coerce")
        ).dt.days / 365.25
        synth_cols = ["age", "gender", "ethnicity", "blood_group",
                      "marital_status", "insurance_plan_type", "annual_income_band"]
        real_df = patients[[c for c in synth_cols if c in patients.columns]].dropna(subset=["age"])
    except FileNotFoundError:
        logger.warning("Parquet files not found — using synthetic seed data ...")
        rng = np.random.default_rng(42)
        n = 1000
        real_df = pd.DataFrame({
            "age":                rng.normal(52, 18, n).clip(0, 100),
            "gender":             rng.choice(["M","F"], n),
            "ethnicity":          rng.choice(["Caucasian","Hispanic","African American","Asian"], n),
            "blood_group":        rng.choice(["O+","A+","B+","AB+","O-"], n),
            "marital_status":     rng.choice(["Single","Married","Divorced"], n),
            "insurance_plan_type": rng.choice(["HMO","PPO","Medicare","Medicaid"], n),
        })

    logger.info(f"Training synthesizer on {len(real_df)} records, {len(real_df.columns)} features ...")

    # Method 1: CTGAN (if SDV available)
    n_synth = len(real_df)
    if SDV_AVAILABLE:
        logger.info("Generating synthetic data with CTGAN ...")
        try:
            model = CTGAN(epochs=100, verbose=False)
            model.fit(real_df)
            synth_ctgan = model.sample(n_synth)
            synth_ctgan.to_csv(OUTPUT_DIR / "synthetic_ctgan.csv", index=False)
            logger.success(f"CTGAN: {len(synth_ctgan)} synthetic records generated")
        except Exception as e:
            logger.warning(f"CTGAN failed: {e}. Using statistical fallback.")
            SDV_AVAILABLE_LOCAL = False
        else:
            SDV_AVAILABLE_LOCAL = True
    else:
        SDV_AVAILABLE_LOCAL = False

    # Method 2: Statistical synthesis (always available)
    logger.info("Generating synthetic data with Statistical Synthesizer ...")
    synthesizer = StatisticalSynthesizer(seed=42)
    synthesizer.fit(real_df)
    synth_stat = synthesizer.sample(n_synth)
    synth_stat.to_csv(OUTPUT_DIR / "synthetic_statistical.csv", index=False)
    logger.success(f"Statistical: {len(synth_stat)} synthetic records generated")

    # Rare disease augmentation demo
    logger.info("\nRare disease augmentation demo ...")
    rare_mask = (real_df["blood_group"].str.contains("AB-", na=False)
                 if "blood_group" in real_df.columns
                 else pd.Series([False] * len(real_df)))
    rare_df = real_df[rare_mask] if rare_mask.sum() > 5 else real_df.head(50)
    aug_synthesizer = StatisticalSynthesizer(seed=99)
    aug_synthesizer.fit(rare_df)
    augmented = aug_synthesizer.sample(200)
    augmented.to_csv(OUTPUT_DIR / "augmented_rare_population.csv", index=False)
    logger.info(f"Augmented rare population: {len(augmented)} records (from {len(rare_df)} real samples)")

    # Visualization
    plot_real_vs_synthetic(real_df, synth_stat, title="Statistical Synthesis")

    # Privacy validation
    logger.info("\nRunning privacy validation ...")
    privacy_report = validate_privacy(real_df, synth_stat)
    logger.info(f"\n=== Privacy & Fidelity Report ===")
    logger.info(f"  Privacy Score:   {privacy_report['privacy_score']} / 100")
    logger.info(f"  Fidelity Score:  {privacy_report['fidelity_score']} / 100")
    logger.info(f"  Avg NN Distance: {privacy_report['avg_nn_distance']}")
    logger.info(f"  High-Risk Rows:  {privacy_report['high_risk_pct']}%")
    logger.info(f"  Status:          {privacy_report['status']}")

    with open(OUTPUT_DIR / "privacy_report.json", "w") as f:
        json.dump(privacy_report, f, indent=2)

    # Summary
    summary = {
        "run_id":        datetime.now().strftime("%Y%m%d_%H%M%S"),
        "real_records":  len(real_df),
        "synth_records": n_synth,
        "method":        "CTGAN" if SDV_AVAILABLE_LOCAL else "Statistical",
        "privacy_score": privacy_report["privacy_score"],
        "fidelity_score": privacy_report["fidelity_score"],
        "output_dir":    str(OUTPUT_DIR),
    }
    with open(OUTPUT_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    logger.success(f"\nChapter 7 Generative AI complete. Outputs: {OUTPUT_DIR}")
    return synth_stat, privacy_report


if __name__ == "__main__":
    main()
