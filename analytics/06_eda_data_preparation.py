"""
Chapter 3: Data Preparation and Mining
EDA + Data Preparation Pipeline

Covers:
  - Missing value analysis and imputation
  - Outlier detection and treatment
  - Normalization and standardization
  - Feature distributions and correlations
  - Patient segmentation via K-Means clustering
  - Disease classification clustering (DBSCAN)
  - Exploratory visualizations

Usage:
    python analytics/06_eda_data_preparation.py
"""

import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # non-interactive backend — no display needed
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from loguru import logger
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

warnings.filterwarnings("ignore")

OUTPUT_DIR = Path("analytics/outputs/ch03_eda")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR   = Path("./data/raw")


# ─── 1. Load Data ────────────────────────────────────────────────────

def load_data():
    logger.info("Loading datasets ...")
    patients  = pd.read_parquet(DATA_DIR / "patients")
    admissions = pd.read_parquet(DATA_DIR / "admissions")
    lab_results = pd.read_parquet(DATA_DIR / "lab_results")
    diagnoses  = pd.read_parquet(DATA_DIR / "diagnoses")
    return patients, admissions, lab_results, diagnoses


# ─── 2. Missing Value Analysis ──────────────────────────────────────

def analyze_missing_values(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Report missing value counts and percentages per column."""
    missing = pd.DataFrame({
        "column":    df.columns,
        "dtype":     df.dtypes.values,
        "missing_n": df.isna().sum().values,
        "missing_pct": (df.isna().mean() * 100).round(2).values,
    }).sort_values("missing_pct", ascending=False)

    missing = missing[missing["missing_n"] > 0]
    logger.info(f"\n=== Missing Values: {name} ===")
    if missing.empty:
        logger.info("  No missing values found.")
    else:
        logger.info(f"\n{missing.to_string(index=False)}")

    # Heatmap
    if not df.select_dtypes(include=np.number).empty:
        fig, ax = plt.subplots(figsize=(12, 4))
        missing_matrix = df.isna().astype(int)
        cols_with_missing = missing_matrix.columns[missing_matrix.sum() > 0]
        if len(cols_with_missing) > 0:
            sns.heatmap(missing_matrix[cols_with_missing].head(200).T,
                        cmap="YlOrRd", cbar=False, ax=ax)
            ax.set_title(f"Missing Value Pattern — {name}")
            ax.set_xlabel("Sample index")
            plt.tight_layout()
            plt.savefig(OUTPUT_DIR / f"missing_{name.lower()}.png", dpi=100)
            plt.close()

    return missing


# ─── 3. Imputation Strategies ───────────────────────────────────────

def impute_data(df: pd.DataFrame, strategy: str = "median") -> pd.DataFrame:
    """
    Impute missing values.
    Strategies: mean | median | most_frequent | knn | forward_fill
    """
    df = df.copy()
    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    cat_cols = df.select_dtypes(include="object").columns.tolist()

    if num_cols:
        if strategy == "knn":
            imputer = KNNImputer(n_neighbors=5)
            df[num_cols] = imputer.fit_transform(df[num_cols])
        elif strategy == "forward_fill":
            df[num_cols] = df[num_cols].ffill()
        else:
            imputer = SimpleImputer(strategy=strategy)
            df[num_cols] = imputer.fit_transform(df[num_cols])

    if cat_cols:
        cat_imputer = SimpleImputer(strategy="most_frequent")
        df[cat_cols] = cat_imputer.fit_transform(df[cat_cols])

    logger.info(f"Imputation ({strategy}) complete. Remaining nulls: {df.isna().sum().sum()}")
    return df


# ─── 4. Outlier Detection ───────────────────────────────────────────

def detect_outliers_iqr(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Detect outliers using IQR method. Returns a boolean mask DataFrame."""
    outlier_mask = pd.DataFrame(False, index=df.index, columns=cols)
    report = []
    for col in cols:
        if col not in df.columns:
            continue
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        mask = (df[col] < lower) | (df[col] > upper)
        outlier_mask[col] = mask
        n_outliers = mask.sum()
        report.append({
            "column":    col,
            "q1":        round(q1, 3),
            "q3":        round(q3, 3),
            "iqr":       round(iqr, 3),
            "lower":     round(lower, 3),
            "upper":     round(upper, 3),
            "n_outliers": n_outliers,
            "outlier_pct": round(n_outliers / len(df) * 100, 2),
        })
    report_df = pd.DataFrame(report)
    logger.info(f"\n=== Outlier Report ===\n{report_df.to_string(index=False)}")
    return outlier_mask, report_df


def cap_outliers_iqr(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Winsorize (cap) outliers at IQR boundaries instead of dropping."""
    df = df.copy()
    for col in cols:
        if col not in df.columns:
            continue
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        df[col] = df[col].clip(q1 - 1.5*iqr, q3 + 1.5*iqr)
    return df


# ─── 5. Normalization & Standardization ────────────────────────────

def normalize_features(df: pd.DataFrame, cols: list, method: str = "standard") -> pd.DataFrame:
    """
    Normalize numeric features.
    method: standard (z-score) | minmax | robust
    """
    df = df.copy()
    valid_cols = [c for c in cols if c in df.columns and df[c].dtype in [np.float64, np.int64, float, int]]
    if not valid_cols:
        return df

    if method == "standard":
        scaler = StandardScaler()
    elif method == "minmax":
        scaler = MinMaxScaler()
    else:
        from sklearn.preprocessing import RobustScaler
        scaler = RobustScaler()

    df[valid_cols] = scaler.fit_transform(df[valid_cols])
    logger.info(f"Normalization ({method}) applied to {len(valid_cols)} columns.")
    return df, scaler


# ─── 6. EDA — Distributions ────────────────────────────────────────

def plot_distributions(patients: pd.DataFrame, admissions: pd.DataFrame):
    """Plot key demographic and clinical distributions."""
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle("Chapter 3: Healthcare Data Distributions", fontsize=14, fontweight="bold")

    # Age distribution
    patients_copy = patients.copy()
    patients_copy["age"] = (
        pd.to_datetime("today") - pd.to_datetime(patients_copy["dob"], errors="coerce")
    ).dt.days / 365.25
    axes[0,0].hist(patients_copy["age"].dropna(), bins=30, color="steelblue", edgecolor="white", alpha=0.8)
    axes[0,0].set_title("Patient Age Distribution")
    axes[0,0].set_xlabel("Age (years)")
    axes[0,0].axvline(patients_copy["age"].mean(), color="red", linestyle="--", label=f"Mean: {patients_copy['age'].mean():.1f}")
    axes[0,0].legend()

    # Gender distribution
    gender_counts = patients["gender"].value_counts()
    axes[0,1].bar(gender_counts.index, gender_counts.values, color=["steelblue","coral","green"])
    axes[0,1].set_title("Gender Distribution")
    axes[0,1].set_xlabel("Gender")
    axes[0,1].set_ylabel("Count")

    # Insurance plan types
    ins_counts = patients["insurance_plan_type"].value_counts().head(8)
    axes[0,2].barh(ins_counts.index, ins_counts.values, color="teal")
    axes[0,2].set_title("Insurance Plan Distribution")
    axes[0,2].set_xlabel("Count")

    # LOS distribution (compute from dates)
    adm = admissions.copy()
    adm["los"] = (
        pd.to_datetime(adm["discharge_date"], errors="coerce") -
        pd.to_datetime(adm["admit_date"], errors="coerce")
    ).dt.days
    los_clean = adm["los"].dropna().clip(0, 30)
    axes[1,0].hist(los_clean, bins=30, color="darkorange", edgecolor="white", alpha=0.8)
    axes[1,0].set_title("Length of Stay Distribution (capped at 30d)")
    axes[1,0].set_xlabel("Days")
    axes[1,0].axvline(los_clean.mean(), color="red", linestyle="--", label=f"Mean: {los_clean.mean():.1f}d")
    axes[1,0].legend()

    # Admission types
    adm_types = admissions["admission_type"].value_counts()
    axes[1,1].pie(adm_types.values, labels=adm_types.index, autopct="%1.1f%%",
                  colors=sns.color_palette("Set2", len(adm_types)))
    axes[1,1].set_title("Admission Types")

    # Readmission rates by ward
    if "readmission_within_30d" in admissions.columns:
        ward_readmit = (
            admissions.groupby("ward")["readmission_within_30d"]
            .apply(lambda x: x.astype(float).mean() * 100)
            .sort_values(ascending=True)
        )
        axes[1,2].barh(ward_readmit.index, ward_readmit.values, color="salmon")
        axes[1,2].set_title("30-Day Readmission Rate by Ward (%)")
        axes[1,2].set_xlabel("Readmission Rate %")
        axes[1,2].axvline(15.6, color="red", linestyle="--", label="CMS Benchmark 15.6%")
        axes[1,2].legend()

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "distributions_overview.png", dpi=120)
    plt.close()
    logger.info("Distribution plots saved.")


def plot_correlation_matrix(lab_results: pd.DataFrame):
    """Correlation matrix of key lab values."""
    key_labs = ["HbA1c","Creatinine","BUN","Sodium","Potassium",
                "Hemoglobin","WBC","BNP","Troponin I","Glucose"]
    pivot = (
        lab_results[lab_results["test_name"].isin(key_labs)]
        .groupby(["patient_id","test_name"])["result_numeric"].mean()
        .unstack()
    )
    pivot.columns.name = None
    pivot = pivot.dropna(thresh=3)

    if pivot.shape[1] > 1:
        corr = pivot.corr()
        fig, ax = plt.subplots(figsize=(10, 8))
        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(corr, mask=mask, annot=True, fmt=".2f", cmap="coolwarm",
                    center=0, square=True, ax=ax, annot_kws={"size": 9})
        ax.set_title("Lab Values Correlation Matrix", fontsize=13, fontweight="bold")
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "lab_correlation_matrix.png", dpi=120)
        plt.close()
        logger.info("Correlation matrix saved.")


# ─── 7. Patient Segmentation — K-Means Clustering ──────────────────

def patient_clustering(patients: pd.DataFrame, admissions: pd.DataFrame, lab_results: pd.DataFrame):
    """
    Segment patients into risk groups using K-Means.
    Features: age, LOS, comorbidity count, readmission flag, key lab values.
    """
    logger.info("Building patient clustering features ...")

    pts = patients[["patient_id","dob","gender","insurance_plan_type"]].copy()
    pts["age"] = (
        pd.to_datetime("today") - pd.to_datetime(pts["dob"], errors="coerce")
    ).dt.days / 365.25

    # Admission stats per patient
    adm = admissions.copy()
    adm["los"] = (
        pd.to_datetime(adm["discharge_date"], errors="coerce") -
        pd.to_datetime(adm["admit_date"], errors="coerce")
    ).dt.days.fillna(0)
    adm_stats = adm.groupby("patient_id").agg(
        n_admissions     = ("admission_id", "count"),
        avg_los          = ("los", "mean"),
        total_icu_hours  = ("icu_hours", "sum"),
        readmit_30d_flag = ("readmission_within_30d", lambda x: x.astype(float).max()),
    ).reset_index()

    # Lab summary per patient
    lab_pivot = (
        lab_results[lab_results["test_name"].isin(["HbA1c","Creatinine","BUN","WBC","Hemoglobin"])]
        .groupby(["patient_id","test_name"])["result_numeric"].mean()
        .unstack()
        .reset_index()
    )
    lab_pivot.columns = ["patient_id"] + [f"lab_{c.lower().replace(' ','_')}"
                                           for c in lab_pivot.columns[1:]]

    # Join
    feat = (pts[["patient_id","age","gender","insurance_plan_type"]]
            .merge(adm_stats, on="patient_id", how="left")
            .merge(lab_pivot,  on="patient_id", how="left"))

    # Encode categoricals
    feat["gender_enc"] = (feat["gender"] == "M").astype(int)

    numeric_cols = feat.select_dtypes(include=np.number).columns.tolist()
    numeric_cols = [c for c in numeric_cols if c != "patient_id"]

    X      = feat[numeric_cols].fillna(feat[numeric_cols].median())
    X      = X.fillna(0)          # fallback for all-NaN columns
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Find optimal K via elbow + silhouette
    k_range   = range(2, min(9, len(X_scaled)//10 + 2))
    inertias  = []
    sil_scores = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        inertias.append(km.inertia_)
        if len(set(labels)) > 1:
            sil_scores.append(silhouette_score(X_scaled, labels))
        else:
            sil_scores.append(0)

    best_k = list(k_range)[np.argmax(sil_scores)]
    logger.info(f"Optimal K={best_k} (silhouette={max(sil_scores):.3f})")

    # Final clustering
    km_final = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    feat["cluster"] = km_final.fit_predict(X_scaled)

    # Cluster profiles
    profile = feat.groupby("cluster")[numeric_cols].mean().round(2)
    logger.info(f"\n=== Patient Cluster Profiles ===\n{profile.to_string()}")

    # PCA visualization
    # Also impute X_scaled before PCA
    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(np.nan_to_num(X_scaled, nan=0.0))

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Chapter 3: Patient Segmentation via K-Means", fontsize=13, fontweight="bold")

    # Elbow + silhouette
    ax1 = axes[0]
    ax2 = ax1.twinx()
    ax1.plot(list(k_range), inertias, "b-o", label="Inertia")
    ax2.plot(list(k_range), sil_scores, "r-s", label="Silhouette")
    ax1.set_xlabel("Number of Clusters (K)")
    ax1.set_ylabel("Inertia", color="blue")
    ax2.set_ylabel("Silhouette Score", color="red")
    ax1.set_title("Elbow Method & Silhouette Score")
    ax1.axvline(best_k, color="green", linestyle="--", label=f"Best K={best_k}")
    ax1.legend(loc="upper right")

    # PCA scatter
    colors = plt.cm.tab10(np.linspace(0, 1, best_k))
    for c in range(best_k):
        mask = feat["cluster"] == c
        n = mask.sum()
        axes[1].scatter(X_pca[mask, 0], X_pca[mask, 1],
                        c=[colors[c]], label=f"Cluster {c} (n={n})", alpha=0.6, s=20)
    axes[1].set_title(f"PCA Projection — {best_k} Patient Segments")
    axes[1].set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%} var)")
    axes[1].set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%} var)")
    axes[1].legend(fontsize=8)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "patient_clustering.png", dpi=120)
    plt.close()

    # Save cluster assignments
    feat[["patient_id","cluster"]].to_csv(OUTPUT_DIR / "patient_clusters.csv", index=False)
    profile.to_csv(OUTPUT_DIR / "cluster_profiles.csv")
    logger.info(f"Clustering complete. Results saved to {OUTPUT_DIR}")

    return feat


# ─── 8. Disease Classification Clustering (DBSCAN) ─────────────────

def disease_clustering(lab_results: pd.DataFrame):
    """
    Use DBSCAN to identify patient sub-groups based on lab value patterns.
    Useful for discovering novel disease phenotypes.
    """
    logger.info("Disease pattern clustering (DBSCAN) ...")

    key_labs = ["HbA1c","Creatinine","Potassium","Sodium","WBC","Hemoglobin"]
    pivot = (
        lab_results[lab_results["test_name"].isin(key_labs)]
        .groupby(["patient_id","test_name"])["result_numeric"].mean()
        .unstack()
    )
    pivot.columns.name = None
    pivot = pivot.dropna(thresh=4).head(2000)  # cap for speed

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(pivot)

    # Disease clustering with DBSCAN — fill NaN before clustering
    X_scaled_clean = np.nan_to_num(X_scaled, nan=0.0)
    db = DBSCAN(eps=1.5, min_samples=5, n_jobs=-1)
    labels = db.fit_predict(X_scaled_clean)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise    = (labels == -1).sum()
    logger.info(f"DBSCAN: {n_clusters} clusters, {n_noise} noise points "
                f"({n_noise/len(labels):.1%} of patients)")

    if n_clusters > 0:
        pca = PCA(n_components=2, random_state=42)
        X_pca = pca.fit_transform(np.nan_to_num(X_scaled, nan=0.0))

        fig, ax = plt.subplots(figsize=(10, 6))
        unique_labels = sorted(set(labels))
        colors = plt.cm.tab20(np.linspace(0, 1, len(unique_labels)))
        for lbl, col in zip(unique_labels, colors):
            mask = labels == lbl
            label_name = f"Noise ({mask.sum()})" if lbl == -1 else f"Cluster {lbl} ({mask.sum()})"
            ax.scatter(X_pca[mask, 0], X_pca[mask, 1],
                       c=[col], label=label_name, alpha=0.6, s=15)
        ax.set_title("Chapter 3: Disease Pattern Clustering (DBSCAN)")
        ax.set_xlabel("PC1")
        ax.set_ylabel("PC2")
        ax.legend(fontsize=7, ncol=2)
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "disease_clustering.png", dpi=120)
        plt.close()

    return labels


# ─── Main ────────────────────────────────────────────────────────────

def main():
    logger.info("Chapter 3: Data Preparation and Mining")
    logger.info(f"Output directory: {OUTPUT_DIR}")

    patients, admissions, lab_results, diagnoses = load_data()

    # 1. Missing value analysis
    analyze_missing_values(patients,   "patients")
    analyze_missing_values(admissions, "admissions")
    analyze_missing_values(lab_results,"lab_results")

    # 2. Outlier detection on lab values
    numeric_lab = lab_results.select_dtypes(include=np.number).columns.tolist()
    numeric_lab = [c for c in numeric_lab if c not in ["result_id","patient_id"]]
    if numeric_lab:
        _, outlier_report = detect_outliers_iqr(lab_results, numeric_lab[:5])
        outlier_report.to_csv(OUTPUT_DIR / "outlier_report.csv", index=False)

    # 3. EDA plots
    plot_distributions(patients, admissions)
    plot_correlation_matrix(lab_results)

    # 4. Imputation demo
    adm_imputed = impute_data(admissions, strategy="median")
    logger.info(f"After imputation — null count: {adm_imputed.isna().sum().sum()}")

    # 5. Patient clustering
    patient_clusters = patient_clustering(patients, admissions, lab_results)

    # 6. Disease clustering
    disease_labels = disease_clustering(lab_results)

    logger.success(f"\nChapter 3 EDA complete. All outputs in: {OUTPUT_DIR}")
    return patient_clusters


if __name__ == "__main__":
    main()
