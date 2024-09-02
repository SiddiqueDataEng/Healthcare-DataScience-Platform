"""
run_all.py  —  Run the complete Healthcare Data Platform pipeline in sequence.

Steps:
  1. Generate synthetic data  (small scale)
  2. Data quality checks
  3. Train all ML models
  4. Run NLP demos

Usage:
    python run_all.py
"""

import subprocess
import sys
import time
from loguru import logger

DATA_DIR = "./data/raw"
PYTHON   = sys.executable   # same interpreter that launched this script


def run(label: str, cmd: list, timeout: int = 300) -> bool:
    logger.info(f"{'='*60}")
    logger.info(f"STEP: {label}")
    logger.info(f"{'='*60}")
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=False, timeout=timeout)
    elapsed = time.time() - t0
    if result.returncode == 0:
        logger.success(f"  OK  {label}  ({elapsed:.1f}s)\n")
        return True
    else:
        logger.error(f"  FAIL  {label}  (exit={result.returncode}, {elapsed:.1f}s)\n")
        return False


steps = [
    ("1. Data Generation (small)",
     [PYTHON, "data_generation/generate_all.py", "--scale", "small"],
     600),

    ("2. Data Quality Checks",
     [PYTHON, "data_quality/run_checks.py", "--all", "--data-dir", DATA_DIR],
     120),

    ("3. ML – Readmission Prediction",
     [PYTHON, "ml_models/readmission/train.py", DATA_DIR],
     180),

    ("4. ML – LOS Prediction",
     [PYTHON, "ml_models/los_prediction/train.py", DATA_DIR],
     180),

    ("5. ML – ICU Mortality Prediction",
     [PYTHON, "ml_models/icu_mortality/train.py", DATA_DIR],
     180),

    ("6. ML – Fraud Detection",
     [PYTHON, "ml_models/fraud_detection/train.py", DATA_DIR],
     180),

    ("7. NLP – Clinical NER Demo",
     [PYTHON, "nlp/entity_recognition/clinical_ner.py"],
     60),

    ("8. NLP – ICD-10 Prediction Demo",
     [PYTHON, "nlp/icd_prediction/icd_predictor.py"],
     60),
]

passed, failed = [], []
for label, cmd, timeout in steps:
    ok = run(label, cmd, timeout)
    (passed if ok else failed).append(label)

logger.info(f"\n{'='*60}")
logger.info(f"PIPELINE COMPLETE — {len(passed)} passed, {len(failed)} failed")
if failed:
    for f in failed:
        logger.error(f"  FAILED: {f}")
else:
    logger.success("All steps completed successfully.")
logger.info(f"{'='*60}")
sys.exit(0 if not failed else 1)
