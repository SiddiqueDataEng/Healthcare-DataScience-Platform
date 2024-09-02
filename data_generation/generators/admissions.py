"""
Admission Generator — 2,000,000 records
Realistic LOS, DRG codes, readmission rates, discharge statuses.
"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator


ADMISSION_TYPES = ["Emergency", "Elective", "Urgent", "Maternity", "Transfer"]
ADMISSION_TYPE_WEIGHTS = [0.38, 0.32, 0.18, 0.07, 0.05]

ADMISSION_SOURCES = ["ER", "Direct", "Transfer", "Clinic Referral", "EMS", "Physician Office"]
SOURCE_WEIGHTS = [0.38, 0.25, 0.12, 0.15, 0.07, 0.03]

DISCHARGE_STATUSES = ["Discharged Home", "Transferred to SNF", "Transferred to Rehab",
                      "Transferred to Another Hospital", "AMA", "Expired", "Hospice", "Still Admitted"]
DISCHARGE_WEIGHTS = [0.65, 0.10, 0.08, 0.05, 0.02, 0.03, 0.02, 0.05]

WARDS = ["Medical", "Surgical", "ICU", "CCU", "NICU", "Maternity", "Psychiatric", "Observation", "Telemetry"]
WARD_WEIGHTS = [0.30, 0.20, 0.12, 0.07, 0.03, 0.08, 0.05, 0.10, 0.05]

# Top DRG codes with (code, description, expected_los_days)
DRG_CODES = [
    ("871", "Septicemia or Severe Sepsis w MCC", 7),
    ("470", "Major Joint Replacement or Reattachment of Lower Extremity", 2),
    ("291", "Heart Failure & Shock w MCC", 6),
    ("392", "Esophagitis, Gastroent & Misc Digest Disorders w MCC", 3),
    ("194", "Simple Pneumonia & Pleurisy w MCC", 5),
    ("683", "Renal Failure w MCC", 5),
    ("603", "Cellulitis w MCC", 4),
    ("189", "Pulmonary Edema & Respiratory Failure", 6),
    ("312", "Syncope & Collapse", 3),
    ("641", "Misc Disorders of Nutrition, Metabolism, Fluids/Electrolytes", 4),
    ("177", "Respiratory Infections & Inflammations w MCC", 6),
    ("308", "Cardiac Arrhythmia & Conduction Disorders w MCC", 4),
    ("249", "Aftercare w CC/MCC", 3),
    ("881", "Depressive Neuroses", 7),
    ("303", "Atherosclerosis w MCC", 2),
]


class AdmissionGenerator(BaseGenerator):

    def table_name(self):
        return "admissions"

    def _get_pk_column(self):
        return "admission_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx

        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        admit_dates = self.random_dates("2018-01-01", "2024-12-31", n)

        adm_types = self.rng.choice(ADMISSION_TYPES, n, p=ADMISSION_TYPE_WEIGHTS)
        adm_sources = self.rng.choice(ADMISSION_SOURCES, n, p=SOURCE_WEIGHTS)
        disc_statuses = self.rng.choice(DISCHARGE_STATUSES, n, p=DISCHARGE_WEIGHTS)
        wards = self.rng.choice(WARDS, n, p=WARD_WEIGHTS)

        # LOS distribution: mostly 1-10 days, heavy tail for complex cases
        los_days = np.clip(np.exp(self.rng.normal(1.5, 0.8, n)).astype(int), 1, 90)

        # Readmission: 15% within 30 days, 22% within 90 days (industry benchmarks)
        readmit_30 = self.rng.choice([True, False], n, p=[0.15, 0.85])
        readmit_90 = readmit_30 | self.rng.choice([True, False], n, p=[0.07, 0.93])

        # ICU hours for ICU admissions
        icu_hours = np.where(
            wards == "ICU",
            self.rng.integers(4, 336, n),
            np.where(self.rng.random(n) < 0.10, self.rng.integers(1, 48, n), 0)
        )

        # Actual cost (DRG-based, highly variable)
        actual_costs = np.round(self.rng.lognormal(9.5, 0.8, n), 2)
        approved_costs = actual_costs * self.rng.uniform(0.60, 0.92, n)

        patient_sample = self.rng.choice(patient_ids, n)
        doctor_sample = self.rng.choice(doctor_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)
        drg_idx = int(self.rng.integers(0, len(DRG_CODES)))
        drg_sample_list = [DRG_CODES[int(self.rng.integers(0, len(DRG_CODES)))] for _ in range(n)]

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            admit_dt = admit_dates[i]
            los = int(los_days[i])
            status = disc_statuses[i]
            drg = drg_sample_list[i]

            if status != "Still Admitted":
                discharge_dt = admit_dt + pd.Timedelta(days=los)
            else:
                discharge_dt = None

            records.append({
                "admission_id":           f"ADM{str(global_idx).zfill(8)}",
                "patient_id":             patient_sample[i],
                "hospital_id":            hospital_sample[i],
                "attending_doctor_id":    doctor_sample[i],
                "admit_date":             admit_dt.isoformat(),
                "discharge_date":         discharge_dt.isoformat() if discharge_dt is not None else None,
                "ward":                   wards[i],
                "room_number":            f"{self.rng.integers(100,599)}{self.rng.choice(['A','B','C','D'])}",
                "bed_number":             f"B{self.rng.integers(1,5)}",
                "admission_type":         adm_types[i],
                "admission_source":       adm_sources[i],
                "discharge_status":       status,
                "drg_code":               drg[0],
                "drg_description":        drg[1],
                "icu_hours":              int(icu_hours[i]),
                "surgery_performed":      self.rng.choice([True, False], p=[0.28, 0.72]),
                "readmission_flag":       bool(readmit_30[i] | readmit_90[i]),
                "readmission_within_30d": bool(readmit_30[i]),
                "readmission_within_90d": bool(readmit_90[i]),
                "expected_los_days":      int(drg[2]),
                "actual_cost":            round(float(actual_costs[i]), 2),
                "insurance_approved_cost": round(float(approved_costs[i]), 2),
            })

        return pd.DataFrame(records)
