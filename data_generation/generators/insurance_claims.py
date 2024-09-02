"""Insurance Claims Generator — 5,000,000 records"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator

PROVIDERS = ["UnitedHealth","Aetna","Cigna","Anthem","Humana","BCBS","Kaiser","Medicare","Medicaid","TRICARE"]
PLAN_TYPES = ["HMO","PPO","EPO","HDHP","Medicare Part A/B","Medicaid","Tricare Standard"]
CLAIM_TYPES = ["Inpatient","Outpatient","Emergency","Pharmacy","Radiology","Lab"]
CLAIM_TYPE_WEIGHTS = [0.20, 0.35, 0.15, 0.15, 0.08, 0.07]
STATUSES = ["Approved","Denied","Partially Approved","Pending","Appeal","Paid"]
STATUS_WEIGHTS = [0.52, 0.15, 0.12, 0.08, 0.05, 0.08]
DENIAL_REASONS = [
    "Not medically necessary","Prior authorization required","Out-of-network provider",
    "Coordination of benefits issue","Duplicate claim","Coding error",
    "Exceeded benefit limit","Non-covered service","Eligibility issue",
]
DENIAL_CODES = ["CO-4","CO-11","CO-15","CO-16","CO-50","CO-96","CO-97","PR-1","PR-2"]


class InsuranceClaimGenerator(BaseGenerator):
    def table_name(self): return "insurance_claims"
    def _get_pk_column(self): return "claim_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        submission_dates = self.random_dates("2018-01-01", "2024-12-31", n)
        claim_types = self.rng.choice(CLAIM_TYPES, n, p=CLAIM_TYPE_WEIGHTS)
        statuses = self.rng.choice(STATUSES, n, p=STATUS_WEIGHTS)
        providers = self.rng.choice(PROVIDERS, n)
        plan_types = self.rng.choice(PLAN_TYPES, n)

        # Claim amounts — log-normal (highly variable)
        claim_amounts = np.round(self.rng.lognormal(8.5, 1.2, n), 2)
        approved_pct = self.rng.uniform(0.60, 0.95, n)
        approved_amounts = np.where(
            np.isin(statuses, ["Approved", "Paid"]), np.round(claim_amounts * approved_pct, 2),
            np.where(statuses == "Partially Approved", np.round(claim_amounts * 0.50, 2), 0.0)
        )
        denied_amounts = np.maximum(0, claim_amounts - approved_amounts)

        is_denied = np.isin(statuses, ["Denied", "Partially Approved"])
        fraud_scores = self.rng.beta(1, 15, n)  # right-skewed, most have low fraud score
        fraud_flags = fraud_scores > 0.8

        patient_sample = self.rng.choice(patient_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            denied = bool(is_denied[i])
            records.append({
                "claim_id":             f"CLM{str(global_idx).zfill(8)}",
                "patient_id":           patient_sample[i],
                "hospital_id":          hospital_sample[i],
                "insurance_provider":   providers[i],
                "insurance_plan_type":  plan_types[i],
                "claim_type":           claim_types[i],
                "submission_date":      submission_dates[i].date().isoformat(),
                "claim_amount":         round(float(claim_amounts[i]), 2),
                "approved_amount":      round(float(approved_amounts[i]), 2),
                "denied_amount":        round(float(denied_amounts[i]), 2),
                "patient_responsibility": round(float(claim_amounts[i] * self.rng.uniform(0.05, 0.25)), 2),
                "claim_status":         statuses[i],
                "denial_reason":        self.rng.choice(DENIAL_REASONS) if denied else None,
                "denial_code":          self.rng.choice(DENIAL_CODES) if denied else None,
                "appeal_flag":          denied and self.rng.random() < 0.35,
                "fraud_flag":           bool(fraud_flags[i]),
                "fraud_score":          round(float(fraud_scores[i]), 4),
            })
        return pd.DataFrame(records)
