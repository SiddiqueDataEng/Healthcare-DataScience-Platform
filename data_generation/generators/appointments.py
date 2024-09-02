"""
Appointment Generator
10,000,000 appointment records with realistic scheduling patterns,
no-show rates by demographic, and wait time distributions.
"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator


APPOINTMENT_TYPES = ["New Patient", "Follow-Up", "Consultation", "Telehealth", "Urgent Care", "Annual Physical", "Pre-Op", "Post-Op"]
APPT_TYPE_WEIGHTS = [0.15, 0.40, 0.10, 0.12, 0.08, 0.10, 0.03, 0.02]

VISIT_TYPES = ["In-Person", "Virtual", "Phone"]
VISIT_WEIGHTS = [0.72, 0.20, 0.08]

# No-show rates vary by type and demographics
APPOINTMENT_STATUS = ["Completed", "No-Show", "Cancelled", "Rescheduled", "Scheduled"]
STATUS_WEIGHTS = [0.68, 0.08, 0.12, 0.07, 0.05]

CANCELLATION_REASONS = [
    "Patient called to cancel", "Transportation issues", "Work conflict",
    "Feeling better", "Insurance issue", "Financial concerns",
    "Doctor unavailable", "Weather", "Personal emergency", "No reason given"
]

CHIEF_COMPLAINTS = [
    "Chest pain", "Shortness of breath", "Back pain", "Headache",
    "Abdominal pain", "Fatigue", "Dizziness", "Cough", "Fever",
    "Knee pain", "Diabetes follow-up", "Hypertension management",
    "Annual wellness exam", "Medication refill", "Rash", "Anxiety",
    "Depression", "Joint pain", "Palpitations", "Swelling",
]


class AppointmentGenerator(BaseGenerator):

    def table_name(self):
        return "appointments"

    def _get_pk_column(self):
        return "appointment_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx

        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        # Appointment dates (2018-2024), weighted toward recent years
        appt_dates = self.random_dates("2018-01-01", "2024-12-31", n)

        appt_types = self.rng.choice(APPOINTMENT_TYPES, n, p=APPT_TYPE_WEIGHTS)
        visit_types = self.rng.choice(VISIT_TYPES, n, p=VISIT_WEIGHTS)
        statuses = self.rng.choice(APPOINTMENT_STATUS, n, p=STATUS_WEIGHTS)
        complaints = self.rng.choice(CHIEF_COMPLAINTS, n)

        # Wait times: log-normal distribution (typical 5-90 minutes)
        wait_times = np.clip(np.exp(self.rng.normal(3.0, 0.7, n)).astype(int), 2, 180)
        consult_times = np.clip(self.rng.normal(22, 10, n).astype(int), 5, 120)

        # Follow-up required: ~60% of completed appointments
        followup = self.rng.choice([True, False], n, p=[0.60, 0.40])
        followup_days = self.rng.choice([7, 14, 30, 60, 90, 180, 365], n)

        patient_sample = self.rng.choice(patient_ids, n)
        doctor_sample = self.rng.choice(doctor_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            status = statuses[i]
            is_cancelled = status in ("Cancelled", "No-Show", "Rescheduled")

            records.append({
                "appointment_id":       f"APT{str(global_idx).zfill(9)}",
                "patient_id":           patient_sample[i],
                "doctor_id":            doctor_sample[i],
                "hospital_id":          hospital_sample[i],
                "appointment_date":     appt_dates[i].date().isoformat(),
                "appointment_time":     f"{self.rng.integers(8,18):02d}:{self.rng.choice([0,15,30,45]):02d}:00",
                "appointment_type":     appt_types[i],
                "visit_type":           visit_types[i],
                "chief_complaint":      complaints[i],
                "wait_time_minutes":    int(wait_times[i]) if not is_cancelled else None,
                "consultation_minutes": int(consult_times[i]) if status == "Completed" else None,
                "appointment_status":   status,
                "cancellation_reason":  self.rng.choice(CANCELLATION_REASONS) if is_cancelled else None,
                "followup_required":    bool(followup[i]) if status == "Completed" else False,
                "followup_days":        int(followup_days[i]) if status == "Completed" and followup[i] else None,
                "insurance_verified":   self.rng.choice([True, False], p=[0.88, 0.12]),
            })

        return pd.DataFrame(records)
