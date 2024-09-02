"""Prescription Generator — 20,000,000 records"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator

MEDICATIONS = [
    ("Atorvastatin","Atorvastatin","Statin","10mg","Oral","Once daily",30,False),
    ("Metformin","Metformin HCL","Biguanide","1000mg","Oral","Twice daily",90,False),
    ("Lisinopril","Lisinopril","ACE Inhibitor","10mg","Oral","Once daily",90,False),
    ("Amlodipine","Amlodipine","Calcium Channel Blocker","5mg","Oral","Once daily",90,False),
    ("Metoprolol Succinate","Metoprolol","Beta Blocker","50mg","Oral","Once daily",90,False),
    ("Omeprazole","Omeprazole","PPI","20mg","Oral","Once daily",30,False),
    ("Losartan","Losartan","ARB","50mg","Oral","Once daily",90,False),
    ("Levothyroxine","Levothyroxine","Thyroid","50mcg","Oral","Once daily",90,False),
    ("Aspirin","Aspirin","Antiplatelet","81mg","Oral","Once daily",90,False),
    ("Furosemide","Furosemide","Loop Diuretic","40mg","Oral","Once daily",30,False),
    ("Apixaban","Apixaban","Anticoagulant","5mg","Oral","Twice daily",30,False),
    ("Gabapentin","Gabapentin","Anticonvulsant","300mg","Oral","Three times daily",30,False),
    ("Sertraline","Sertraline","SSRI","50mg","Oral","Once daily",30,False),
    ("Amoxicillin","Amoxicillin","Penicillin Antibiotic","500mg","Oral","Three times daily",10,False),
    ("Azithromycin","Azithromycin","Macrolide Antibiotic","250mg","Oral","Once daily",5,False),
    ("Insulin Glargine","Insulin Glargine U-100","Insulin","20 units","Subcutaneous","Once daily at bedtime",30,False),
    ("Hydrocodone/APAP","Hydrocodone","Opioid","5/325mg","Oral","Every 4-6 hours PRN",7,True),
    ("Oxycodone","Oxycodone HCL","Opioid","10mg","Oral","Every 4-6 hours PRN",7,True),
    ("Alprazolam","Alprazolam","Benzodiazepine","0.5mg","Oral","Twice daily PRN",30,True),
    ("Albuterol","Albuterol","Short-Acting Bronchodilator","90mcg/actuation","Inhaled","PRN",30,False),
]

STATUSES = ["Active","Discontinued","Expired","On Hold"]
STATUS_WEIGHTS = [0.65, 0.18, 0.12, 0.05]


class PrescriptionGenerator(BaseGenerator):
    def table_name(self): return "prescriptions"
    def _get_pk_column(self): return "prescription_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        start_dates = self.random_dates("2018-01-01", "2024-12-31", n)
        med_indices = self.rng.choice(len(MEDICATIONS), n)
        statuses = self.rng.choice(STATUSES, n, p=STATUS_WEIGHTS)
        refill_counts = self.rng.integers(0, 12, n)
        patient_sample = self.rng.choice(patient_ids, n)
        doctor_sample = self.rng.choice(doctor_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            med = MEDICATIONS[med_indices[i]]
            name, generic, drug_class, dosage, route, frequency, days_supply, controlled = med
            start_date = start_dates[i].date()
            end_date = start_date + pd.Timedelta(days=days_supply)

            records.append({
                "prescription_id":      f"RX{str(global_idx).zfill(9)}",
                "patient_id":           patient_sample[i],
                "doctor_id":            doctor_sample[i],
                "hospital_id":          hospital_sample[i],
                "medication_name":      name,
                "generic_name":         generic,
                "drug_class":           drug_class,
                "dosage":               dosage,
                "route":                route,
                "frequency":            frequency,
                "start_date":           start_date.isoformat(),
                "end_date":             end_date.isoformat(),
                "days_supply":          days_supply,
                "refill_count":         int(refill_counts[i]),
                "controlled_substance": controlled,
                "prescription_status":  statuses[i],
                "adverse_reaction":     self.rng.choice([True, False], p=[0.03, 0.97]),
            })
        return pd.DataFrame(records)
