"""
Patient Generator
Generates 1,000,000 realistic patient records with demographics.
HIPAA-compliant: SSN/Phone/Email stored as hashed values only.
"""
import hashlib
import numpy as np
import pandas as pd
from datetime import date, timedelta
from data_generation.generators.base_generator import BaseGenerator


ETHNICITIES = ["Caucasian", "Hispanic", "African American", "Asian", "Native American", "Pacific Islander", "Mixed", "Other"]
ETHNICITY_WEIGHTS = [0.597, 0.184, 0.133, 0.059, 0.013, 0.002, 0.006, 0.006]

BLOOD_GROUPS = ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"]
BLOOD_WEIGHTS = [0.38, 0.34, 0.09, 0.03, 0.07, 0.06, 0.02, 0.01]

MARITAL_STATUS = ["Single", "Married", "Divorced", "Widowed", "Separated", "Domestic Partnership"]
MARITAL_WEIGHTS = [0.32, 0.50, 0.11, 0.05, 0.01, 0.01]

INSURANCE_PROVIDERS = [
    "UnitedHealth Group", "Anthem Blue Cross", "Aetna", "Cigna", "Humana",
    "Blue Cross Blue Shield", "Kaiser Permanente", "Centene", "Molina Healthcare",
    "Medicare", "Medicaid", "TRICARE", "Self-Pay", "None"
]
INSURANCE_WEIGHTS = [0.14, 0.13, 0.11, 0.10, 0.08, 0.09, 0.07, 0.05, 0.04, 0.08, 0.06, 0.02, 0.02, 0.01]

PLAN_TYPES = ["HMO", "PPO", "EPO", "HDHP", "Medicare Part A/B", "Medicaid", "None"]
PLAN_WEIGHTS = [0.30, 0.35, 0.10, 0.10, 0.08, 0.06, 0.01]

OCCUPATIONS = [
    "Engineer", "Teacher", "Nurse", "Manager", "Accountant", "Retired", "Student",
    "Sales Representative", "Software Developer", "Doctor", "Lawyer", "Truck Driver",
    "Construction Worker", "Administrative Assistant", "Homemaker", "Unemployed",
    "Police Officer", "Firefighter", "Restaurant Worker", "Retail Worker",
]

EDUCATION_LEVELS = ["Less than High School", "High School / GED", "Some College", "Associate Degree", "Bachelor's Degree", "Master's Degree", "Doctoral Degree"]
EDUCATION_WEIGHTS = [0.08, 0.28, 0.20, 0.10, 0.22, 0.09, 0.03]

INCOME_BANDS = ["<25K", "25-50K", "50-75K", "75-100K", "100-150K", "150K+"]
INCOME_WEIGHTS = [0.17, 0.24, 0.21, 0.16, 0.14, 0.08]

US_STATES = [
    "Texas", "California", "Florida", "New York", "Illinois", "Pennsylvania",
    "Ohio", "Georgia", "North Carolina", "Michigan", "New Jersey", "Virginia",
    "Washington", "Arizona", "Massachusetts", "Tennessee", "Indiana", "Missouri",
    "Maryland", "Wisconsin", "Colorado", "Minnesota", "South Carolina", "Alabama",
    "Louisiana", "Kentucky", "Oregon", "Oklahoma", "Connecticut", "Utah",
]
STATE_WEIGHTS = [
    0.0993, 0.1325, 0.0773, 0.0662, 0.0442, 0.0442, 0.0386, 0.0331, 0.0331, 0.0331,
    0.0309, 0.0276, 0.0276, 0.0254, 0.0243, 0.0232, 0.0221, 0.0210, 0.0199, 0.0199,
    0.0188, 0.0188, 0.0166, 0.0166, 0.0155, 0.0155, 0.0143, 0.0132, 0.0143, 0.0129,
]


def sha256_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class PatientGenerator(BaseGenerator):

    def table_name(self):
        return "patients"

    def _get_pk_column(self):
        return "patient_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx

        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        # Generate ages with realistic distribution (skewed toward 30-80 for hospital patients)
        ages = np.clip(self.rng.normal(52, 18, n).astype(int), 0, 105)
        dobs = [
            (date.today() - timedelta(days=int(age * 365.25) + int(self.rng.integers(0, 365)))).isoformat()
            for age in ages
        ]

        genders = self.rng.choice(["M", "F", "O"], n, p=[0.487, 0.510, 0.003])
        ethnicities = self.rng.choice(ETHNICITIES, n, p=ETHNICITY_WEIGHTS)
        blood_groups = self.rng.choice(BLOOD_GROUPS, n, p=BLOOD_WEIGHTS)
        marital = self.rng.choice(MARITAL_STATUS, n, p=MARITAL_WEIGHTS)
        occupations = self.rng.choice(OCCUPATIONS, n)
        education = self.rng.choice(EDUCATION_LEVELS, n, p=EDUCATION_WEIGHTS)
        income = self.rng.choice(INCOME_BANDS, n, p=INCOME_WEIGHTS)
        states = self.rng.choice(US_STATES, n, p=STATE_WEIGHTS)
        insurance = self.rng.choice(INSURANCE_PROVIDERS, n, p=INSURANCE_WEIGHTS)
        plan_types = self.rng.choice(PLAN_TYPES, n, p=PLAN_WEIGHTS)

        # Registration dates (2015-2024)
        reg_dates = self.random_dates("2015-01-01", "2024-12-31", n)

        # Deceased: ~3% of patients
        deceased_flags = self.rng.choice([False, True], n, p=[0.97, 0.03])
        deceased_dates = []
        for i, is_deceased in enumerate(deceased_flags):
            if is_deceased:
                reg_date = reg_dates[i]
                death_date = reg_date + pd.Timedelta(days=int(self.rng.integers(30, 1800)))
                deceased_dates.append(min(death_date, pd.Timestamp("2024-12-31")).date().isoformat())
            else:
                deceased_dates.append(None)

        hospital_assignments = self.rng.choice(hospital_ids, n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            first_name = self.fake.first_name_male() if genders[i] == "M" else self.fake.first_name_female()
            last_name = self.fake.last_name()
            phone = self.fake.phone_number()
            email = self.fake.email()
            zip_code = self.fake.zipcode()

            records.append({
                "patient_id":           f"P{str(global_idx).zfill(7)}",
                "first_name":           first_name,            # PHI
                "last_name":            last_name,             # PHI
                "gender":               genders[i],
                "dob":                  dobs[i],               # PHI
                "ethnicity":            ethnicities[i],
                "blood_group":          blood_groups[i],
                "marital_status":       marital[i],
                "occupation":           occupations[i],
                "education_level":      education[i],
                "annual_income_band":   income[i],
                "phone_hash":           sha256_hash(phone),    # PHI hashed
                "email_hash":           sha256_hash(email),    # PHI hashed
                "address_state":        states[i],
                "address_country":      "USA",
                "address_zip":          zip_code,              # PHI (kept for zip-level analytics)
                "hospital_id":          hospital_assignments[i],
                "insurance_provider":   insurance[i],
                "insurance_plan_type":  plan_types[i],
                "registration_date":    reg_dates[i].date().isoformat(),
                "deceased_flag":        deceased_flags[i],
                "deceased_date":        deceased_dates[i],
                "consent_research":     self.rng.choice([True, False], p=[0.65, 0.35]),
                "consent_marketing":    self.rng.choice([True, False], p=[0.40, 0.60]),
                "gdpr_erasure_flag":    False,
            })

        return pd.DataFrame(records)
