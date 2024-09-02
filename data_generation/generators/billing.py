"""Billing Generator — 15,000,000 records"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator

SERVICE_TYPES = ["Room & Board","Surgery","Lab","Medical Imaging","Pharmacy","ER","ICU","Physical Therapy","Anesthesia","Radiology","Consultation","Supplies"]
SERVICE_WEIGHTS = [0.1545, 0.1000, 0.1182, 0.0818, 0.1000, 0.0909, 0.0727, 0.0455, 0.0364, 0.0636, 0.0455, 0.0909]
PAYMENT_METHODS = ["Insurance","Self-Pay","Medicare","Medicaid","Credit Card","Payment Plan","Charity Care","Workers Comp"]
PAYMENT_WEIGHTS = [0.48,0.08,0.18,0.12,0.04,0.05,0.03,0.02]
PAYMENT_STATUSES = ["Paid","Pending","Partial","Written Off","Sent to Collections","Collections"]
PAYMENT_STATUS_WEIGHTS = [0.62,0.18,0.08,0.06,0.04,0.02]

SERVICE_UNIT_PRICES = {
    "Room & Board": (1200, 3500), "Surgery": (5000, 80000), "Lab": (50, 2000),
    "Medical Imaging": (200, 8000), "Pharmacy": (20, 5000), "ER": (800, 5000),
    "ICU": (4000, 12000), "Physical Therapy": (150, 400), "Anesthesia": (500, 8000),
    "Radiology": (200, 3000), "Consultation": (200, 800), "Supplies": (50, 2000),
}


class BillingGenerator(BaseGenerator):
    def table_name(self): return "billing"
    def _get_pk_column(self): return "invoice_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        service_dates = self.random_dates("2018-01-01", "2024-12-31", n)
        service_types = self.rng.choice(SERVICE_TYPES, n, p=SERVICE_WEIGHTS)
        payment_methods = self.rng.choice(PAYMENT_METHODS, n, p=PAYMENT_WEIGHTS)
        payment_statuses = self.rng.choice(PAYMENT_STATUSES, n, p=PAYMENT_STATUS_WEIGHTS)

        patient_sample = self.rng.choice(patient_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            stype = service_types[i]
            price_low, price_high = SERVICE_UNIT_PRICES.get(stype, (100, 1000))
            unit_price = round(float(self.rng.uniform(price_low, price_high)), 2)
            qty = max(1, int(self.rng.normal(1.5, 0.8)))
            gross = round(unit_price * qty, 2)
            ins_adj = round(gross * self.rng.uniform(0.10, 0.40), 2)
            ins_paid = round((gross - ins_adj) * self.rng.uniform(0.60, 0.90), 2)
            pt_paid = round(self.rng.uniform(0, gross - ins_paid - ins_adj), 2)
            amount_due = round(max(0, gross - ins_adj - ins_paid - pt_paid), 2)

            svc_dt = service_dates[i].date()
            bill_dt = svc_dt + pd.Timedelta(days=int(self.rng.integers(1, 15)))
            due_dt = bill_dt + pd.Timedelta(days=30)

            records.append({
                "invoice_id":              f"INV{str(global_idx).zfill(9)}",
                "patient_id":              patient_sample[i],
                "hospital_id":             hospital_sample[i],
                "service_type":            stype,
                "service_date":            svc_dt.isoformat(),
                "billing_date":            bill_dt.isoformat(),
                "quantity":                qty,
                "unit_price":              unit_price,
                "gross_amount":            gross,
                "insurance_adjustment":    ins_adj,
                "insurance_paid":          ins_paid,
                "patient_paid":            pt_paid,
                "amount_due":              amount_due,
                "payment_method":          payment_methods[i],
                "payment_status":          payment_statuses[i],
                "due_date":                due_dt.isoformat(),
                "bad_debt_flag":           payment_statuses[i] in ("Sent to Collections","Collections"),
                "charity_care_flag":       payment_methods[i] == "Charity Care",
            })
        return pd.DataFrame(records)
