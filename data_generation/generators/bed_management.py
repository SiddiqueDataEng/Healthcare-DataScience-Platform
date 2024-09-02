"""Bed Management / Utilization Generator — 10,000,000 records"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator

WARDS = ["Medical","Surgical","ICU","CCU","NICU","Maternity","Psychiatric","Observation","Telemetry","Rehabilitation"]
WARD_WEIGHTS = [0.28,0.18,0.12,0.07,0.04,0.08,0.05,0.10,0.05,0.03]
BED_TYPES = ["Medical","Surgical","ICU","CCU","NICU","Maternity","Psych","Step-Down","Bariatric"]
OCC_STATUSES = ["Occupied","Available","Housekeeping","Maintenance","Blocked"]
OCC_STATUS_WEIGHTS = [0.72, 0.14, 0.08, 0.03, 0.03]


class BedManagementGenerator(BaseGenerator):
    def table_name(self): return "bed_utilization"
    def _get_pk_column(self): return "bed_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])
        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])

        occ_starts = self.random_dates("2020-01-01", "2024-12-31", n)
        occ_statuses = self.rng.choice(OCC_STATUSES, n, p=OCC_STATUS_WEIGHTS)
        wards = self.rng.choice(WARDS, n, p=WARD_WEIGHTS)
        hospital_sample = self.rng.choice(hospital_ids, n)
        patient_sample = self.rng.choice(patient_ids, n)

        # LOS in hours: mean 72h (3 days), heavily right-skewed
        los_hours = np.clip(np.exp(self.rng.normal(4.2, 0.8, n)), 1, 2000)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            status = occ_statuses[i]
            occ_start = occ_starts[i] if status == "Occupied" else None
            occ_end = (occ_starts[i] + pd.Timedelta(hours=float(los_hours[i]))).isoformat() if status == "Occupied" else None
            is_occupied = status == "Occupied"

            # Cleaning time: 20-90 minutes between occupancies
            clean_start = (occ_starts[i] + pd.Timedelta(hours=float(los_hours[i]))).isoformat() if is_occupied else None
            clean_end = (occ_starts[i] + pd.Timedelta(hours=float(los_hours[i])) + pd.Timedelta(minutes=int(self.rng.integers(20, 91)))).isoformat() if is_occupied else None

            records.append({
                "bed_id":           f"BED{hospital_sample[i]}{str(global_idx).zfill(7)}",
                "hospital_id":      hospital_sample[i],
                "ward":             wards[i],
                "room_number":      f"{self.rng.integers(100,599)}",
                "bed_number":       f"B{self.rng.integers(1,5)}",
                "bed_type":         self.rng.choice(BED_TYPES),
                "is_isolation_room": self.rng.choice([True, False], p=[0.08, 0.92]),
                "patient_id":       patient_sample[i] if is_occupied else None,
                "occupancy_status": status,
                "occupancy_start":  occ_start.isoformat() if occ_start is not None else None,
                "occupancy_end":    occ_end,
                "cleaning_start":   clean_start,
                "cleaning_end":     clean_end,
            })
        return pd.DataFrame(records)
