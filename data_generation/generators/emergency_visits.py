"""Emergency Department Visits Generator — 5,000,000 records"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator

ARRIVAL_MODES = ["Walk-In","EMS","Police","Transfer","Helicopter"]
ARRIVAL_WEIGHTS = [0.55, 0.30, 0.03, 0.08, 0.04]
TRIAGE_LEVELS = [1, 2, 3, 4, 5]
TRIAGE_WEIGHTS = [0.05, 0.15, 0.45, 0.25, 0.10]
TRIAGE_DESC = {1:"Immediate", 2:"Emergent", 3:"Urgent", 4:"Less Urgent", 5:"Non-Urgent"}
DISPOSITIONS = ["Discharged", "Admitted", "Transferred", "AMA", "Expired", "LWBS"]
DISP_WEIGHTS = [0.62, 0.24, 0.06, 0.03, 0.01, 0.04]
CHIEF_COMPLAINTS = [
    "Chest pain","Shortness of breath","Abdominal pain","Altered mental status",
    "Fall/Injury","Laceration","Motor vehicle accident","Syncope","Seizure",
    "Headache","Back pain","Allergic reaction","Drug overdose","Psychiatric emergency",
    "Fever","Stroke symptoms","Palpitations","Urinary symptoms","GI bleeding","Pregnancy complication",
]


class EmergencyVisitGenerator(BaseGenerator):
    def table_name(self): return "emergency_visits"
    def _get_pk_column(self): return "visit_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        arrival_dts = self.random_dates("2018-01-01", "2024-12-31", n)
        arrival_modes = self.rng.choice(ARRIVAL_MODES, n, p=ARRIVAL_WEIGHTS)
        triage_levels = self.rng.choice(TRIAGE_LEVELS, n, p=TRIAGE_WEIGHTS)
        dispositions = self.rng.choice(DISPOSITIONS, n, p=DISP_WEIGHTS)
        complaints = self.rng.choice(CHIEF_COMPLAINTS, n)

        # Wait times inversely correlated with triage severity
        base_wait = np.array([2, 8, 25, 50, 80])[triage_levels - 1]
        wait_times = np.clip(self.rng.normal(base_wait, base_wait * 0.4, n).astype(int), 0, 360)
        d2d = np.clip(wait_times + self.rng.integers(0, 15, n), 0, 360)

        # Total ED time (minutes)
        total_ed = np.clip(self.rng.normal(180, 80, n).astype(int), 30, 720)

        admitted = np.array(dispositions) == "Admitted"
        return_72h = self.rng.random(n) < 0.03

        patient_sample = self.rng.choice(patient_ids, n)
        doctor_sample = self.rng.choice(doctor_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            arr_dt = arrival_dts[i]
            triage_dt = arr_dt + pd.Timedelta(minutes=int(wait_times[i]))
            discharge_dt = arr_dt + pd.Timedelta(minutes=int(total_ed[i]))

            records.append({
                "visit_id":            f"ERV{str(global_idx).zfill(8)}",
                "patient_id":          patient_sample[i],
                "hospital_id":         hospital_sample[i],
                "arrival_datetime":    arr_dt.isoformat(),
                "arrival_mode":        arrival_modes[i],
                "triage_datetime":     triage_dt.isoformat(),
                "triage_level":        int(triage_levels[i]),
                "triage_level_desc":   TRIAGE_DESC[triage_levels[i]],
                "chief_complaint":     complaints[i],
                "wait_time_minutes":   int(wait_times[i]),
                "door_to_doc_minutes": int(d2d[i]),
                "physician_id":        doctor_sample[i],
                "disposition":         dispositions[i],
                "discharge_datetime":  discharge_dt.isoformat(),
                "admitted_flag":       bool(admitted[i]),
                "left_without_seen":   dispositions[i] == "LWBS",
                "return_within_72h":   bool(return_72h[i]),
                "pain_score_arrival":  int(self.rng.integers(0, 11)),
                "labs_ordered":        self.rng.choice([True, False], p=[0.72, 0.28]),
                "imaging_ordered":     self.rng.choice([True, False], p=[0.65, 0.35]),
            })
        return pd.DataFrame(records)
