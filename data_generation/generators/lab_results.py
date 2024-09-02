"""
Lab Results Generator — 50,000,000 records
Realistic lab values with proper reference ranges, abnormal flags,
and correlated values (e.g., HbA1c and Glucose both elevated for diabetics).
"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator


# (loinc_code, test_name, panel, unit, normal_mean, normal_std, ref_low, ref_high, critical_low, critical_high)
LAB_TESTS = [
    ("4548-4",  "HbA1c",            "Diabetes",    "%",       5.4,  1.2,  4.0,   5.7,  None,  14.0),
    ("2345-7",  "Glucose",          "CMP",         "mg/dL",   90,   25,   70,    99,   40,    500),
    ("2160-0",  "Creatinine",       "CMP",         "mg/dL",   1.0,  0.4,  0.7,   1.3,  None,  10.0),
    ("3094-0",  "BUN",              "CMP",         "mg/dL",   14,   5,    7,     20,   None,  100),
    ("2823-3",  "Potassium",        "CMP",         "mEq/L",   4.0,  0.5,  3.5,   5.1,  2.5,   6.5),
    ("2951-2",  "Sodium",           "CMP",         "mEq/L",   140,  4,    136,   145,  120,   160),
    ("1742-6",  "ALT",              "LFT",         "U/L",     25,   20,   7,     56,   None,  1000),
    ("1920-8",  "AST",              "LFT",         "U/L",     22,   18,   10,    40,   None,  1000),
    ("14804-9", "LDL Cholesterol",  "Lipid",       "mg/dL",   120,  35,   None,  100,  None,  None),
    ("2085-9",  "HDL Cholesterol",  "Lipid",       "mg/dL",   52,   15,   40,    None, None,  None),
    ("2093-3",  "Total Cholesterol","Lipid",       "mg/dL",   185,  40,   None,  200,  None,  None),
    ("6301-6",  "INR",              "Coagulation", "INR",     1.0,  0.3,  0.8,   1.2,  None,  5.0),
    ("26464-8", "WBC",              "CBC",         "10^3/uL", 7.0,  2.0,  4.5,   11.0, 2.0,   30.0),
    ("718-7",   "Hemoglobin",       "CBC",         "g/dL",    14.0, 2.0,  12.0,  17.5, 7.0,   None),
    ("777-3",   "Platelets",        "CBC",         "10^3/uL", 250,  80,   150,   400,  50,    1000),
    ("10839-9", "Troponin I",       "Cardiac",     "ng/mL",   0.02, 0.04, None,  0.04, None,  None),
    ("33762-6", "BNP",              "Cardiac",     "pg/mL",   80,   60,   None,  125,  None,  None),
    ("11579-0", "TSH",              "Thyroid",     "mIU/L",   2.0,  1.5,  0.4,   4.0,  None,  None),
    ("17861-6", "Calcium",          "CMP",         "mg/dL",   9.4,  0.6,  8.5,   10.2, 6.0,   13.5),
    ("2028-9",  "CO2",              "CMP",         "mEq/L",   25,   3,    22,    29,   None,  None),
]

SPECIMEN_TYPES = ["Blood", "Urine", "Serum", "Plasma", "CSF", "Tissue", "Swab"]
SPECIMEN_WEIGHTS = [0.45, 0.20, 0.18, 0.10, 0.02, 0.03, 0.02]

RESULT_STATUSES = ["Final", "Preliminary", "Corrected", "Cancelled"]
RESULT_STATUS_WEIGHTS = [0.88, 0.06, 0.05, 0.01]


class LabResultGenerator(BaseGenerator):

    def table_name(self):
        return "lab_results"

    def _get_pk_column(self):
        return "result_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx

        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        collection_dts = self.random_dates("2018-01-01", "2024-12-31", n)
        test_indices = self.rng.choice(len(LAB_TESTS), n)
        specimens = self.rng.choice(SPECIMEN_TYPES, n, p=SPECIMEN_WEIGHTS)
        result_statuses = self.rng.choice(RESULT_STATUSES, n, p=RESULT_STATUS_WEIGHTS)

        patient_sample = self.rng.choice(patient_ids, n)
        doctor_sample = self.rng.choice(doctor_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        # ~20% of patients have chronic conditions (abnormal values)
        is_chronic_patient = self.rng.random(n) < 0.20

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            test = LAB_TESTS[test_indices[i]]
            loinc, test_name, panel, unit, mean, std, ref_low, ref_high, crit_low, crit_high = test

            # Chronic patients get values shifted toward abnormal
            if is_chronic_patient[i]:
                shift = self.rng.choice([-1.5, 1.5])
                value = float(self.rng.normal(mean + shift * std, std))
            else:
                value = float(self.rng.normal(mean, std))

            value = round(max(0.001, value), 4)

            # Determine abnormal flag
            abnormal_flag = "Normal"
            critical = False
            if ref_low is not None and value < ref_low:
                if crit_low is not None and value < crit_low:
                    abnormal_flag = "LL"
                    critical = True
                else:
                    abnormal_flag = "L"
            elif ref_high is not None and value > ref_high:
                if crit_high is not None and value > crit_high:
                    abnormal_flag = "HH"
                    critical = True
                else:
                    abnormal_flag = "H"

            collection_dt = collection_dts[i]
            result_dt = collection_dt + pd.Timedelta(hours=int(self.rng.integers(1, 24)))
            ref_range_text = f"{ref_low}-{ref_high}" if ref_low is not None and ref_high is not None else f"<{ref_high}" if ref_low is None else f">{ref_low}"

            records.append({
                "result_id":            f"LAB{str(global_idx).zfill(10)}",
                "patient_id":           patient_sample[i],
                "ordering_doctor_id":   doctor_sample[i],
                "hospital_id":          hospital_sample[i],
                "loinc_code":           loinc,
                "test_name":            test_name,
                "test_panel":           panel,
                "result_value":         str(value),
                "result_numeric":       value,
                "unit":                 unit,
                "reference_range_low":  ref_low,
                "reference_range_high": ref_high,
                "reference_range_text": ref_range_text,
                "abnormal_flag":        abnormal_flag,
                "critical_flag":        critical,
                "collection_datetime":  collection_dt.isoformat(),
                "resulted_datetime":    result_dt.isoformat(),
                "specimen_type":        specimens[i],
                "result_status":        result_statuses[i],
            })

        return pd.DataFrame(records)
