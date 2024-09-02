"""
Doctor Generator
Generates physician profiles with realistic specialization distributions.
"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator


SPECIALIZATIONS = [
    ("Cardiology",         "Interventional Cardiology",   "DEP001", 280000, 320000),
    ("Neurology",          "Stroke Neurology",             "DEP002", 250000, 300000),
    ("Oncology",           "Medical Oncology",             "DEP003", 320000, 380000),
    ("Orthopedics",        "Joint Replacement",            "DEP004", 300000, 400000),
    ("Pediatrics",         "Pediatric Emergency",          "DEP005", 180000, 240000),
    ("Emergency Medicine", "Trauma",                       "DEP006", 240000, 300000),
    ("Radiology",          "Interventional Radiology",     "DEP007", 300000, 420000),
    ("Dermatology",        "Mohs Surgery",                 "DEP008", 280000, 380000),
    ("Critical Care",      "ICU Medicine",                 "DEP009", 260000, 320000),
    ("Surgery",            "Colorectal Surgery",           "DEP010", 350000, 500000),
    ("Internal Medicine",  "Hospital Medicine",            "DEP001", 180000, 240000),
    ("Nephrology",         "Dialysis",                     "DEP011", 220000, 280000),
    ("Pulmonology",        "Sleep Medicine",               "DEP012", 230000, 300000),
    ("Gastroenterology",   "Hepatology",                   "DEP013", 280000, 380000),
    ("Endocrinology",      "Diabetes Management",          "DEP014", 200000, 260000),
    ("Psychiatry",         "Addiction Psychiatry",         "DEP015", 180000, 280000),
    ("Anesthesiology",     "Pain Management",              "DEP010", 280000, 380000),
    ("Urology",            "Robotic Surgery",              "DEP010", 300000, 420000),
    ("Ophthalmology",      "Retina Specialist",            "DEP007", 250000, 380000),
    ("OB/GYN",             "Maternal-Fetal Medicine",      "DEP005", 220000, 320000),
]

QUALIFICATIONS = ["MD", "DO", "MD, PhD", "MD, FACC", "MD, FACS", "MD, FACEP", "MBBS", "MD, FCCP", "MD, FASCO"]
EMPLOYMENT_TYPES = ["Full-Time", "Part-Time", "Contract", "Locum"]
EMPLOYMENT_WEIGHTS = [0.75, 0.12, 0.08, 0.05]
SHIFT_TYPES = ["Day", "Night", "Rotating"]
SHIFT_WEIGHTS = [0.55, 0.10, 0.35]


class DoctorGenerator(BaseGenerator):

    def table_name(self):
        return "doctors"

    def _get_pk_column(self):
        return "doctor_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            spec_data = SPECIALIZATIONS[i % len(SPECIALIZATIONS)]
            spec, sub_spec, dept_code, sal_low, sal_high = spec_data

            gender = self.rng.choice(["M", "F"], p=[0.60, 0.40])
            first_name = self.fake.first_name_male() if gender == "M" else self.fake.first_name_female()
            last_name = self.fake.last_name()

            exp_years = int(self.rng.integers(1, 35))
            joining_year = 2024 - exp_years
            joining_date = f"{joining_year}-{self.rng.integers(1,13):02d}-{self.rng.integers(1,28):02d}"

            salary = round(float(self.rng.uniform(sal_low, sal_high)), 2)
            hospital_id = self.rng.choice(hospital_ids)

            # NPI: 10-digit unique provider identifier (public info)
            npi = str(int(self.rng.integers(1000000000, 9999999999)))
            state_abbr = "TX"

            records.append({
                "doctor_id":          f"DR{str(global_idx).zfill(5)}",
                "hospital_id":        hospital_id,
                "department_id":      dept_code,
                "first_name":         first_name,
                "last_name":          last_name,
                "gender":             gender,
                "specialization":     spec,
                "sub_specialization": sub_spec,
                "qualification":      self.rng.choice(QUALIFICATIONS),
                "medical_license_no": f"{state_abbr}-{self.rng.integers(10000,99999)}",
                "npi_number":         npi,
                "years_experience":   exp_years,
                "joining_date":       joining_date,
                "employment_type":    self.rng.choice(EMPLOYMENT_TYPES, p=EMPLOYMENT_WEIGHTS),
                "salary":             salary,
                "shift_type":         self.rng.choice(SHIFT_TYPES, p=SHIFT_WEIGHTS),
                "is_active":          self.rng.choice([True, False], p=[0.92, 0.08]),
            })

        return pd.DataFrame(records)
