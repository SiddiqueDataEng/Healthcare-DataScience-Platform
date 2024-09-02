"""Staff Scheduling Generator — 500,000 records"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator

EMPLOYEE_TYPES = ["Physician","Nurse","PA","NP","Technician","Administrative","Case Manager","Social Worker"]
EMP_TYPE_WEIGHTS = [0.12, 0.42, 0.08, 0.10, 0.12, 0.08, 0.05, 0.03]
SHIFT_TYPES = ["Day","Evening","Night","On-Call"]
SHIFT_HOURS = {"Day": ("07:00","19:00",12), "Evening": ("15:00","23:00",8), "Night": ("19:00","07:00",12), "On-Call": ("08:00","17:00",8)}
STATUSES = ["Completed","Scheduled","Called Off","No-Show","Swapped"]
STATUS_WEIGHTS = [0.75, 0.15, 0.06, 0.02, 0.02]
CALLOFF_REASONS = ["Illness","Family emergency","No reason given","FMLA","Weather","Personal"]


class StaffScheduleGenerator(BaseGenerator):
    def table_name(self): return "staff_schedule"
    def _get_pk_column(self): return "schedule_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])

        shift_dates = self.random_dates("2022-01-01", "2024-12-31", n)
        employee_types = self.rng.choice(EMPLOYEE_TYPES, n, p=EMP_TYPE_WEIGHTS)
        shift_types = self.rng.choice(SHIFT_TYPES, n, p=[0.45, 0.20, 0.25, 0.10])
        statuses = self.rng.choice(STATUSES, n, p=STATUS_WEIGHTS)
        hospital_sample = self.rng.choice(hospital_ids, n)
        employee_sample = self.rng.choice(doctor_ids, n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            shift = shift_types[i]
            start_t, end_t, sched_hrs = SHIFT_HOURS[shift]
            status = statuses[i]
            called_off = status == "Called Off"
            actual_hrs = sched_hrs if status == "Completed" else None
            ot_hrs = max(0.0, self.rng.normal(0.3, 0.5)) if status == "Completed" else 0.0

            records.append({
                "schedule_id":     f"SCH{str(global_idx).zfill(8)}",
                "employee_id":     employee_sample[i],
                "hospital_id":     hospital_sample[i],
                "employee_type":   employee_types[i],
                "shift_type":      shift,
                "shift_date":      shift_dates[i].date().isoformat(),
                "start_time":      start_t,
                "end_time":        end_t,
                "scheduled_hours": sched_hrs,
                "actual_hours":    actual_hrs,
                "overtime_hours":  round(float(ot_hrs), 2),
                "status":          status,
                "call_off_reason": self.rng.choice(CALLOFF_REASONS) if called_off else None,
                "patients_assigned": int(self.rng.integers(3, 12)) if status == "Completed" else None,
            })
        return pd.DataFrame(records)
