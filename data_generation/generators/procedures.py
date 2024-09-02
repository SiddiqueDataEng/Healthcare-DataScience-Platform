"""Procedures Generator — 8,000,000 records"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator

PROCEDURES = [
    ("99213","Office/Outpatient Visit Est.","E&M",25,"None"),
    ("99214","Office/Outpatient Visit Est.","E&M",35,"None"),
    ("93000","ECG Routine","Cardiology",15,"None"),
    ("93306","Echocardiography Transthoracic","Cardiology",45,"None"),
    ("93458","Left Heart Catheterization","Cardiology",90,"Sedation"),
    ("27447","Total Knee Arthroplasty","Orthopedics",120,"General"),
    ("27130","Total Hip Arthroplasty","Orthopedics",100,"General"),
    ("47562","Laparoscopic Cholecystectomy","Surgery",60,"General"),
    ("45378","Colonoscopy Diagnostic","Gastroenterology",30,"Sedation"),
    ("71046","Chest X-Ray 2 Views","Radiology",15,"None"),
    ("70553","MRI Brain w/wo Contrast","Radiology",60,"None"),
    ("74178","CT Abdomen Pelvis w Contrast","Radiology",45,"None"),
    ("36415","Venipuncture","Lab",5,"None"),
    ("90837","Psychotherapy 60 min","Psychiatry",60,"None"),
    ("64483","Epidural Steroid Injection","Pain Management",30,"Local"),
    ("43239","EGD with Biopsy","Gastroenterology",25,"Sedation"),
    ("19301","Partial Mastectomy","Surgery",90,"General"),
    ("33533","CABG Arterial Single","Cardiology",240,"General"),
    ("00100","Anesthesia Head","Anesthesiology",90,"General"),
    ("97110","Therapeutic Exercise","Physical Therapy",30,"None"),
]

OUTCOMES = ["Successful","Complication","Pending","Abandoned"]
OUTCOME_WEIGHTS = [0.90, 0.07, 0.02, 0.01]
ANESTHESIA_TYPES = ["General","Local","Regional","Sedation","None"]


class ProcedureGenerator(BaseGenerator):
    def table_name(self): return "procedures"
    def _get_pk_column(self): return "procedure_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        proc_dates = self.random_dates("2018-01-01", "2024-12-31", n)
        proc_indices = self.rng.choice(len(PROCEDURES), n)
        outcomes = self.rng.choice(OUTCOMES, n, p=OUTCOME_WEIGHTS)
        patient_sample = self.rng.choice(patient_ids, n)
        doctor_sample = self.rng.choice(doctor_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            proc = PROCEDURES[proc_indices[i]]
            cpt, name, category, base_dur, anesth = proc
            dur = int(self.rng.normal(base_dur, base_dur * 0.2))
            complication = outcomes[i] == "Complication"
            facility_fee = round(float(self.rng.uniform(100, 20000)), 2)
            physician_fee = round(float(self.rng.uniform(50, 5000)), 2)

            records.append({
                "procedure_id":       f"PROC{str(global_idx).zfill(8)}",
                "patient_id":         patient_sample[i],
                "doctor_id":          doctor_sample[i],
                "hospital_id":        hospital_sample[i],
                "cpt_code":           cpt,
                "procedure_name":     name,
                "procedure_category": category,
                "procedure_date":     proc_dates[i].isoformat(),
                "duration_minutes":   max(5, dur),
                "anesthesia_type":    anesth,
                "outcome":            outcomes[i],
                "complication_flag":  complication,
                "facility_fee":       facility_fee,
                "physician_fee":      physician_fee,
            })
        return pd.DataFrame(records)
