"""
Diagnosis Generator — 15,000,000 records
ICD-10 coded diagnoses with realistic disease prevalence distributions.
"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator


# ICD-10 codes with (code, name, category, chronic, severity_dist, prevalence_weight)
DISEASES = [
    ("E11.9",  "Type 2 Diabetes Mellitus", "Endocrine", True,
     ["Mild","Moderate","Severe"], [0.35,0.45,0.20], 0.12),
    ("I10",    "Essential Hypertension", "Cardiovascular", True,
     ["Mild","Moderate","Severe"], [0.40,0.40,0.20], 0.14),
    ("I50.9",  "Heart Failure, Unspecified", "Cardiovascular", True,
     ["Moderate","Severe","Critical"], [0.30,0.50,0.20], 0.06),
    ("I21.9",  "Acute Myocardial Infarction", "Cardiovascular", False,
     ["Severe","Critical"], [0.60,0.40], 0.04),
    ("I63.9",  "Cerebral Infarction (Stroke)", "Cardiovascular", False,
     ["Moderate","Severe","Critical"], [0.25,0.50,0.25], 0.03),
    ("J18.9",  "Pneumonia", "Respiratory", False,
     ["Mild","Moderate","Severe"], [0.40,0.40,0.20], 0.07),
    ("J44.1",  "COPD with Exacerbation", "Respiratory", True,
     ["Moderate","Severe"], [0.60,0.40], 0.05),
    ("J45.50", "Severe Persistent Asthma", "Respiratory", True,
     ["Mild","Moderate","Severe"], [0.30,0.50,0.20], 0.04),
    ("N18.3",  "Chronic Kidney Disease Stage 3", "Genitourinary", True,
     ["Moderate","Severe"], [0.70,0.30], 0.04),
    ("N18.6",  "End-Stage Renal Disease", "Genitourinary", True,
     ["Severe","Critical"], [0.50,0.50], 0.02),
    ("C34.10", "Malignant Neoplasm of Lung", "Neoplasm", False,
     ["Moderate","Severe","Critical"], [0.20,0.50,0.30], 0.02),
    ("C50.919","Malignant Neoplasm of Breast", "Neoplasm", False,
     ["Mild","Moderate","Severe","Critical"], [0.15,0.35,0.35,0.15], 0.02),
    ("C18.9",  "Malignant Neoplasm of Colon", "Neoplasm", False,
     ["Moderate","Severe","Critical"], [0.25,0.50,0.25], 0.015),
    ("U07.1",  "COVID-19", "Infectious", False,
     ["Mild","Moderate","Severe","Critical"], [0.45,0.30,0.18,0.07], 0.05),
    ("A41.9",  "Sepsis", "Infectious", False,
     ["Severe","Critical"], [0.55,0.45], 0.03),
    ("F32.9",  "Major Depressive Disorder", "Mental Health", True,
     ["Mild","Moderate","Severe"], [0.35,0.40,0.25], 0.04),
    ("F41.1",  "Generalized Anxiety Disorder", "Mental Health", True,
     ["Mild","Moderate","Severe"], [0.45,0.40,0.15], 0.03),
    ("E78.5",  "Hyperlipidemia", "Endocrine", True,
     ["Mild","Moderate"], [0.60,0.40], 0.06),
    ("M54.5",  "Low Back Pain", "Musculoskeletal", False,
     ["Mild","Moderate","Severe"], [0.50,0.35,0.15], 0.05),
    ("K21.0",  "GERD with Esophagitis", "Digestive", True,
     ["Mild","Moderate","Severe"], [0.55,0.35,0.10], 0.03),
    ("G43.909","Migraine", "Neurological", True,
     ["Mild","Moderate","Severe"], [0.40,0.40,0.20], 0.03),
    ("E11.65", "Type 2 Diabetes with Hyperglycemia", "Endocrine", True,
     ["Moderate","Severe"], [0.60,0.40], 0.04),
    ("I48.91", "Unspecified Atrial Fibrillation", "Cardiovascular", True,
     ["Mild","Moderate","Severe"], [0.30,0.50,0.20], 0.03),
    ("K57.30", "Diverticulosis of Large Intestine", "Digestive", True,
     ["Mild","Moderate"], [0.70,0.30], 0.02),
    ("Z87.891","Personal History of Nicotine Dependence", "Preventive", False,
     ["Mild"], [1.0], 0.02),
]

# Normalize weights
TOTAL_WEIGHT = sum(d[6] for d in DISEASES)
DISEASE_WEIGHTS = [d[6] / TOTAL_WEIGHT for d in DISEASES]

DIAGNOSIS_TYPES = ["Primary", "Secondary", "Comorbidity", "Complication"]
DIAG_TYPE_WEIGHTS = [0.45, 0.30, 0.20, 0.05]

STATUSES = ["Active", "Resolved", "Chronic", "In Remission"]
STATUS_WEIGHTS = [0.45, 0.25, 0.25, 0.05]


class DiagnosisGenerator(BaseGenerator):

    def table_name(self):
        return "diagnoses"

    def _get_pk_column(self):
        return "diagnosis_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx

        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        admission_ids = self.context.get("admissions_ids", [None] * 1000)
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        diag_dates = self.random_dates("2018-01-01", "2024-12-31", n)
        diag_types = self.rng.choice(DIAGNOSIS_TYPES, n, p=DIAG_TYPE_WEIGHTS)
        statuses = self.rng.choice(STATUSES, n, p=STATUS_WEIGHTS)
        confirmed = self.rng.choice([True, False], n, p=[0.92, 0.08])

        # Select diseases by prevalence weight
        disease_indices = self.rng.choice(len(DISEASES), n, p=DISEASE_WEIGHTS)

        patient_sample = self.rng.choice(patient_ids, n)
        doctor_sample = self.rng.choice(doctor_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        # Admission linkage (~70% linked to an admission)
        has_admission = self.rng.choice([True, False], n, p=[0.70, 0.30])
        admission_sample = self.rng.choice(admission_ids, n) if admission_ids else [None] * n

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            d = DISEASES[disease_indices[i]]
            icd_code, disease_name, category, is_chronic, severities, sev_weights, _ = d

            severity = self.rng.choice(severities, p=sev_weights)
            diag_date = diag_dates[i]
            adm_id = admission_sample[i] if has_admission[i] and admission_ids else None

            records.append({
                "diagnosis_id":      f"DX{str(global_idx).zfill(9)}",
                "patient_id":        patient_sample[i],
                "admission_id":      adm_id,
                "doctor_id":         doctor_sample[i],
                "hospital_id":       hospital_sample[i],
                "icd10_code":        icd_code,
                "icd10_category":    icd_code[:3],
                "disease_name":      disease_name,
                "disease_category":  category,
                "diagnosis_date":    diag_date.date().isoformat(),
                "diagnosis_type":    diag_types[i],
                "severity":          severity,
                "chronic_flag":      is_chronic,
                "acute_flag":        not is_chronic and severity in ["Severe", "Critical"],
                "status":            statuses[i],
                "confirmed_flag":    bool(confirmed[i]),
            })

        return pd.DataFrame(records)
