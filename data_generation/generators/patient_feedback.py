"""Patient Satisfaction / HCAHPS Feedback Generator — 2,000,000 records"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator

POSITIVE_COMMENTS = [
    "The nurses were incredibly attentive and caring throughout my stay.",
    "Dr. Smith took the time to explain everything clearly. Very satisfied.",
    "Clean rooms and excellent food. Felt very well cared for.",
    "The discharge process was smooth and well-organized.",
    "Staff responded quickly whenever I needed assistance.",
    "I was kept informed about my treatment at every step.",
    "The facility was spotless and the staff professional.",
    "Felt genuinely cared for. Would definitely recommend.",
]
NEGATIVE_COMMENTS = [
    "Waited over 3 hours to be seen in the ER. Communication was poor.",
    "Staff seemed rushed and didn't explain my medications properly.",
    "Room was noisy at night, difficult to sleep.",
    "Discharge instructions were confusing and incomplete.",
    "Billing issues were not resolved during my visit.",
    "Pain management was inadequate.",
    "Call light took too long to be answered.",
    "Parking and facility navigation were very difficult.",
]
NEUTRAL_COMMENTS = [
    "Average experience overall. Nothing exceptional.",
    "Service was okay, room was acceptable.",
    "Mixed experience — some staff great, others not so much.",
    "Standard hospital experience. Met expectations.",
]

SURVEY_TYPES = ["Inpatient","Outpatient","ER","Telehealth","Post-Discharge"]
SURVEY_WEIGHTS = [0.40, 0.30, 0.15, 0.08, 0.07]


class PatientFeedbackGenerator(BaseGenerator):
    def table_name(self): return "patient_feedback"
    def _get_pk_column(self): return "feedback_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        survey_dates = self.random_dates("2018-01-01", "2024-12-31", n)
        survey_types = self.rng.choice(SURVEY_TYPES, n, p=SURVEY_WEIGHTS)

        # Overall ratings: bimodal (many 9-10, some 1-3)
        overall_ratings = self.rng.choice(range(0, 11), n, p=[0.02,0.02,0.03,0.03,0.04,0.05,0.07,0.10,0.15,0.22,0.27])
        recommend_scores = np.clip(overall_ratings + self.rng.integers(-1, 2, n), 0, 10)

        # HCAHPS domain scores (1-4 scale: Never/Sometimes/Usually/Always)
        def hcahps_score(base_rating):
            """Convert 0-10 rating to 1-4 HCAHPS."""
            return np.clip((base_rating / 3 + self.rng.normal(0, 0.3, n)).astype(int), 1, 4)

        patient_sample = self.rng.choice(patient_ids, n)
        doctor_sample = self.rng.choice(doctor_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            rating = overall_ratings[i]
            if rating >= 8:
                comment = self.rng.choice(POSITIVE_COMMENTS)
                sentiment = round(float(self.rng.uniform(0.5, 1.0)), 4)
            elif rating <= 4:
                comment = self.rng.choice(NEGATIVE_COMMENTS)
                sentiment = round(float(self.rng.uniform(-1.0, -0.1)), 4)
            else:
                comment = self.rng.choice(NEUTRAL_COMMENTS)
                sentiment = round(float(self.rng.uniform(-0.1, 0.4)), 4)

            records.append({
                "feedback_id":              f"FB{str(global_idx).zfill(9)}",
                "patient_id":               patient_sample[i],
                "hospital_id":              hospital_sample[i],
                "doctor_id":                doctor_sample[i],
                "survey_type":              survey_types[i],
                "survey_date":              survey_dates[i].date().isoformat(),
                "overall_rating":           int(rating),
                "likelihood_recommend":     int(recommend_scores[i]),
                "doctor_communication":     int(np.clip(rating // 3 + self.rng.integers(-1, 2), 1, 4)),
                "nurse_communication":      int(np.clip(rating // 3 + self.rng.integers(-1, 2), 1, 4)),
                "staff_responsiveness":     int(np.clip(rating // 3 + self.rng.integers(-1, 2), 1, 4)),
                "pain_management":          int(np.clip(rating // 3 + self.rng.integers(-1, 2), 1, 4)),
                "hospital_cleanliness":     int(np.clip(rating // 3 + self.rng.integers(-1, 2), 1, 4)),
                "hospital_quietness":       int(np.clip(rating // 3 + self.rng.integers(-1, 2), 1, 4)),
                "comments":                 comment,
                "sentiment_score":          sentiment,
            })
        return pd.DataFrame(records)
