"""
Chapter 5: Image Analysis and Computer Vision in Healthcare
Medical Imaging Classification Pipeline

Implements:
  1. DICOM metadata analysis from imaging_records parquet
  2. CNN-based image classifier (PyTorch) — simulated with feature vectors
  3. Abnormality detection scoring
  4. U-Net style segmentation architecture (definition)
  5. AI confidence scoring on radiology findings
  6. Computer vision pipeline for: X-Ray, MRI, CT, Mammogram

In production: loads actual DICOM files from PACS/S3.
In demo: uses imaging metadata + synthetic feature vectors.

Usage:
    python ml_models/computer_vision/imaging_classifier.py
    python ml_models/computer_vision/imaging_classifier.py ./data/raw
"""

import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from loguru import logger
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.preprocessing import LabelEncoder
import joblib
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

# Try PyTorch — fall back to sklearn if DLL load fails
TORCH_OK = False
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_OK = True
except (ImportError, OSError):
    logger.warning("PyTorch not available (DLL issue). Using sklearn GBM fallback for CV model.")
    # Stub so class definitions using nn.Module don't fail at import
    class _NNStub:
        Module = object
        Sequential = object
        class Linear:
            def __init__(self, *a, **kw): pass
        class BatchNorm1d:
            def __init__(self, *a, **kw): pass
        class ReLU:
            def __init__(self, *a, **kw): pass
        class Dropout:
            def __init__(self, *a, **kw): pass
        class Conv2d:
            def __init__(self, *a, **kw): pass
        class BatchNorm2d:
            def __init__(self, *a, **kw): pass
        class MaxPool2d:
            def __init__(self, *a, **kw): pass
        @staticmethod
        def init(): pass
    nn = _NNStub()

RANDOM_STATE = 42
MODEL_DIR    = Path("ml_models/computer_vision/artifacts")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Abnormality categories (derived from radiology findings text)
FINDING_CATEGORIES = [
    "Normal / No Significant Finding",
    "Pulmonary Abnormality (Pneumonia/Effusion/Nodule)",
    "Cardiac Abnormality (Cardiomegaly/Effusion)",
    "Bone/Structural Abnormality (Fracture/Arthritis)",
    "Malignancy / Suspicious Mass",
    "Vascular Abnormality",
]

# Image modality characteristics (simulated feature dimensions)
MODALITY_FEATURE_DIM = {"CR": 512, "CT": 1024, "MR": 1024, "US": 256, "MG": 512, "PT": 512}


# ─── CNN Architecture (only when PyTorch available) ──────────────────

if TORCH_OK:
    class MedicalImageCNN(nn.Module):
        def __init__(self, input_dim: int, n_classes: int, dropout: float = 0.3):
            super().__init__()
            self.network = nn.Sequential(
                nn.Linear(input_dim, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(dropout),
                nn.Linear(512, 256),       nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(dropout),
                nn.Linear(256, 128),       nn.BatchNorm1d(128), nn.ReLU(), nn.Dropout(dropout*0.5),
                nn.Linear(128, n_classes),
            )
            for m in self.modules():
                if isinstance(m, nn.Linear):
                    nn.init.kaiming_normal_(m.weight)
                    nn.init.zeros_(m.bias)

        def forward(self, x):
            return self.network(x)

    class UNetEncoder(nn.Module):
        def __init__(self, in_channels: int = 1, base_filters: int = 32):
            super().__init__()
            def double_conv(in_ch, out_ch):
                return nn.Sequential(
                    nn.Conv2d(in_ch, out_ch, 3, padding=1), nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
                    nn.Conv2d(out_ch, out_ch, 3, padding=1), nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
                )
            self.enc1       = double_conv(in_channels, base_filters)
            self.enc2       = double_conv(base_filters,   base_filters*2)
            self.enc3       = double_conv(base_filters*2, base_filters*4)
            self.enc4       = double_conv(base_filters*4, base_filters*8)
            self.bottleneck = double_conv(base_filters*8, base_filters*16)
            self.pool       = nn.MaxPool2d(2)

        def forward(self, x):
            e1 = self.enc1(x)
            e2 = self.enc2(self.pool(e1))
            e3 = self.enc3(self.pool(e2))
            e4 = self.enc4(self.pool(e3))
            b  = self.bottleneck(self.pool(e4))
            return b, (e1, e2, e3, e4)

        def count_parameters(self):
            return sum(p.numel() for p in self.parameters() if p.requires_grad)

else:
    # Dummy placeholders so the rest of the file can reference these names
    class MedicalImageCNN:
        def __init__(self, *a, **kw): pass
    class UNetEncoder:
        def count_parameters(self): return 0


# ─── 2. Feature Extraction from Metadata ────────────────────────────

def extract_imaging_features(imaging_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract ML features from imaging metadata.
    In production: CNN embeddings from actual pixel data.
    Here: metadata-derived features + simulated image embeddings.
    """
    df = imaging_df.copy()

    # Binary features from metadata
    df["has_contrast"]    = df["contrast_used"].astype(int)
    df["is_critical"]     = df["critical_finding"].astype(int)
    df["has_ai_score"]    = df["ai_confidence_score"].notna().astype(int)
    df["is_final_report"] = (df["report_status"] == "Final").astype(int)
    df["image_count_log"] = np.log1p(df["image_count"].fillna(1))

    # Modality encoding
    df["modality_enc"] = LabelEncoder().fit_transform(df["modality"].astype(str).fillna("CR"))
    df["body_part_enc"] = LabelEncoder().fit_transform(df["body_part"].astype(str).fillna("Chest"))
    df["laterality_enc"] = LabelEncoder().fit_transform(df["laterality"].astype(str).fillna("NA"))

    # AI confidence (use as feature — represents prior model output)
    df["ai_conf"] = df["ai_confidence_score"].fillna(0.5)

    # Radiation dose — may not exist in all datasets
    if "radiation_dose" in df.columns:
        df["radiation_dose"] = df["radiation_dose"].fillna(df["radiation_dose"].median()
                               if df["radiation_dose"].notna().any() else 0)
    else:
        df["radiation_dose"] = 0.0

    # Simulated finding severity label from text keywords
    def classify_finding(text: str) -> int:
        if pd.isna(text) or not text.strip():
            return 0
        text = text.lower()
        if any(w in text for w in ["normal","no acute","unremarkable","clear"]):
            return 0
        if any(w in text for w in ["cancer","malignant","malignancy","tumor","mass","carcinoma"]):
            return 4
        if any(w in text for w in ["suspicious","birads 4","birads 5","nodule","lesion"]):
            return 3
        if any(w in text for w in ["pneumonia","consolidation","infiltrate","effusion","opacity"]):
            return 2
        return 1

    df["finding_severity"] = df["findings"].apply(classify_finding)

    # Target: abnormal finding (binary)
    df["is_abnormal"] = (df["finding_severity"] > 0).astype(int)

    feature_cols = ["has_contrast","is_critical","image_count_log",
                    "modality_enc","body_part_enc","laterality_enc",
                    "ai_conf","radiation_dose","finding_severity"]
    return df, feature_cols


# ─── 3. Synthetic Image Embedding Generation ─────────────────────────

def generate_simulated_embeddings(n: int, embed_dim: int = 128,
                                   labels: np.ndarray = None,
                                   seed: int = 42) -> np.ndarray:
    """
    Simulate CNN image embeddings.
    In production: extract embeddings from pre-trained ResNet/EfficientNet
    fine-tuned on medical images (ImageNet → medical domain transfer learning).
    """
    rng = np.random.default_rng(seed)
    embeddings = rng.normal(0, 1, (n, embed_dim)).astype(np.float32)
    if labels is not None:
        # Add class-separating signal
        for i, lbl in enumerate(labels):
            embeddings[i, :20] += lbl * 0.8
    return embeddings


# ─── 4. Training ─────────────────────────────────────────────────────

def train_imaging_classifier(imaging_df: pd.DataFrame):
    """Train classifier on imaging metadata + simulated embeddings."""
    logger.info(f"Imaging dataset: {imaging_df.shape}")

    df, metadata_features = extract_imaging_features(imaging_df)
    df = df.dropna(subset=["is_abnormal"])

    X_meta = df[metadata_features].fillna(0).values.astype(np.float32)
    y      = df["is_abnormal"].values.astype(np.int64)

    # Simulated CNN embeddings (64-dim)
    X_emb = generate_simulated_embeddings(len(df), embed_dim=64, labels=y)
    X     = np.concatenate([X_meta, X_emb], axis=1)

    logger.info(f"Feature dim: {X.shape[1]}  Abnormal rate: {y.mean():.2%}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )

    train_losses, val_aucs = [], []

    if TORCH_OK:
        # ── PyTorch CNN path ──────────────────────────────────────
        X_tr = torch.FloatTensor(X_train)
        y_tr = torch.LongTensor(y_train)
        X_te = torch.FloatTensor(X_test)
        y_te = torch.LongTensor(y_test)
        train_loader = DataLoader(TensorDataset(X_tr, y_tr), batch_size=64, shuffle=True)
        test_loader  = DataLoader(TensorDataset(X_te, y_te), batch_size=64)

        model_nn = MedicalImageCNN(input_dim=X.shape[1], n_classes=2)
        n_pos = y_train.sum()
        n_neg = len(y_train) - n_pos
        class_weights = torch.FloatTensor([1.0, n_neg / max(n_pos, 1)])
        criterion  = nn.CrossEntropyLoss(weight=class_weights)
        optimizer  = optim.AdamW(model_nn.parameters(), lr=1e-3, weight_decay=1e-4)
        scheduler  = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)

        n_epochs = 30
        best_auc = 0.0
        model_nn.train()
        for epoch in range(n_epochs):
            epoch_loss = 0
            for X_b, y_b in train_loader:
                optimizer.zero_grad()
                loss = criterion(model_nn(X_b), y_b)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            model_nn.eval()
            all_probs = []
            with torch.no_grad():
                for X_b, _ in test_loader:
                    probs = torch.softmax(model_nn(X_b), dim=1)[:, 1]
                    all_probs.extend(probs.numpy())
            val_auc = roc_auc_score(y_test, all_probs) if len(set(y_test)) > 1 else 0.5
            train_losses.append(epoch_loss / len(train_loader))
            val_aucs.append(val_auc)
            scheduler.step(epoch_loss)
            if val_auc > best_auc:
                best_auc = val_auc
                torch.save(model_nn.state_dict(), MODEL_DIR / "best_imaging_model.pt")
            model_nn.train()
            if (epoch + 1) % 10 == 0:
                logger.info(f"  Epoch {epoch+1}/{n_epochs} Loss={epoch_loss/len(train_loader):.4f} AUC={val_auc:.4f}")

        model_nn.load_state_dict(torch.load(MODEL_DIR / "best_imaging_model.pt", weights_only=True))
        model_nn.eval()
        final_probs = []
        with torch.no_grad():
            for X_b, _ in test_loader:
                probs = torch.softmax(model_nn(X_b), dim=1)[:, 1]
                final_probs.extend(probs.numpy())
        final_auc = roc_auc_score(y_test, final_probs) if len(set(y_test)) > 1 else float("nan")
        model_artifact = model_nn

    else:
        # ── sklearn GBM fallback ──────────────────────────────────
        logger.info("Using GradientBoostingClassifier (PyTorch not available) ...")
        n_epochs  = 10   # for plotting consistency
        gbm = GradientBoostingClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            subsample=0.8, random_state=RANDOM_STATE
        )
        gbm.fit(X_train, y_train)
        final_probs = gbm.predict_proba(X_test)[:, 1].tolist()
        final_auc   = roc_auc_score(y_test, final_probs) if len(set(y_test)) > 1 else float("nan")
        best_auc    = final_auc
        # Simulate a convergence curve using staged predictions
        for i, staged_pred in enumerate(gbm.staged_predict_proba(X_test)):
            auc = roc_auc_score(y_test, staged_pred[:, 1]) if len(set(y_test)) > 1 else 0.5
            train_losses.append(1 - auc)
            val_aucs.append(auc)
            if i >= n_epochs - 1:
                break
        joblib.dump(gbm, MODEL_DIR / "best_imaging_model_gbm.pkl")
        model_artifact = gbm

    logger.info(f"Best Val AUC: {best_auc:.4f}  Final Test AUC: {final_auc:.4f}" if not np.isnan(final_auc) else f"Best AUC: {best_auc:.4f}")

    y_pred = (np.array(final_probs) >= 0.5).astype(int)
    if len(set(y_test)) > 1:
        logger.info("\n" + classification_report(y_test, y_pred, target_names=["Normal","Abnormal"]))

    # Training curve
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.suptitle("Chapter 5: Medical Imaging Classifier Training", fontsize=13, fontweight="bold")
    axes[0].plot(train_losses, "b-", label="Training Loss")
    axes[0].set_title("Training Loss")
    axes[0].set_xlabel("Epoch / Iteration")
    axes[0].legend()
    axes[1].plot(val_aucs, "r-", label="Validation AUC")
    axes[1].axhline(0.8, linestyle="--", color="gray", label="AUC=0.80 target")
    axes[1].set_title("Validation AUC-ROC")
    axes[1].set_xlabel("Epoch / Iteration")
    axes[1].legend()
    plt.tight_layout()
    plt.savefig(MODEL_DIR / "training_curves.png", dpi=100)
    plt.close()

    # Modality breakdown
    for mod in imaging_df["modality"].dropna().unique():
        mask = (df["modality"].values == mod)
        mod_len = min(mask.sum(), len(final_probs))
        mod_probs = np.array(final_probs)[mask[:len(final_probs)]]
        mod_y     = y_test[mask[:len(y_test)]]
        if len(mod_probs) > 5 and len(set(mod_y)) > 1:
            mod_auc = roc_auc_score(mod_y, mod_probs)
            logger.info(f"  {mod:4s}: AUC={mod_auc:.4f}  n={mask.sum()}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    metrics = {
        "run_id": run_id, "backend": "pytorch" if TORCH_OK else "gbm_fallback",
        "best_val_auc": round(best_auc, 4),
        "final_test_auc": round(final_auc, 4) if not np.isnan(final_auc) else None,
        "n_images": len(df), "abnormal_rate": round(float(y.mean()), 4),
    }
    with open(MODEL_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    logger.success(f"Computer Vision model saved: {MODEL_DIR}")
    return model_artifact, metrics


def main():
    logger.info("Chapter 5: Image Analysis and Computer Vision in Healthcare")

    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data/raw")

    try:
        imaging_df = pd.read_parquet(data_dir / "imaging_records")
        logger.info(f"Loaded {len(imaging_df)} imaging records")
    except FileNotFoundError:
        logger.warning("Imaging records not found — generating synthetic metadata ...")
        rng = np.random.default_rng(RANDOM_STATE)
        n = 2000
        findings = [
            "No acute cardiopulmonary process.",
            "Right lower lobe opacity consistent with pneumonia.",
            "Small bilateral pleural effusions.",
            "BIRADS 4 — Suspicious calcifications. Biopsy recommended.",
            "No acute intracranial abnormality.",
            "Pulmonary nodule 8mm right upper lobe. Follow-up CT recommended.",
            "Normal appendix. No free fluid.",
            "BIRADS 2 — Benign. Routine screening.",
        ]
        imaging_df = pd.DataFrame({
            "image_id":          [f"IMG{i:08d}" for i in range(n)],
            "patient_id":        [f"P{i:07d}" for i in range(n)],
            "image_type":        rng.choice(["X-Ray","CT Scan","MRI","Mammogram","Ultrasound"], n),
            "modality":          rng.choice(["CR","CT","MR","MG","US"], n),
            "body_part":         rng.choice(["Chest","Brain","Abdomen","Breast","Knee"], n),
            "laterality":        rng.choice(["Left","Right","Bilateral","NA"], n),
            "contrast_used":     rng.choice([True, False], n, p=[0.35,0.65]),
            "critical_finding":  rng.choice([True, False], n, p=[0.06,0.94]),
            "ai_confidence_score": rng.uniform(0.70, 0.99, n),
            "image_count":       rng.integers(1, 800, n),
            "report_status":     rng.choice(["Final","Preliminary","Draft"], n, p=[0.85,0.10,0.05]),
            "radiation_dose":    rng.uniform(0.01, 20.0, n),
            "findings":          rng.choice(findings, n),
        })

    model, metrics = train_imaging_classifier(imaging_df)

    # Print U-Net architecture summary
    if TORCH_OK:
        unet = UNetEncoder(in_channels=1, base_filters=32)
        unet_params = unet.count_parameters()
    else:
        unet_params = 0
    logger.info(f"\nU-Net Encoder Architecture:")
    logger.info(f"  Encoder blocks: 4 + bottleneck")
    logger.info(f"  Trainable parameters: {unet_params:,}" if unet_params else "  (PyTorch unavailable — architecture defined but not instantiated)")
    logger.info(f"  Use case: Tumor segmentation, organ delineation")
    logger.info(f"  Input: (batch, 1, H, W) grayscale medical image")
    logger.info(f"  Output: Bottleneck features + skip connections for decoder")
    logger.info(f"\nFinal Metrics: {metrics}")


if __name__ == "__main__":
    main()
