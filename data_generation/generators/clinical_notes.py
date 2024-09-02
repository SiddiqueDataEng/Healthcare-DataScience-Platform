"""
Clinical Notes Generator — 10,000,000 records
Generates realistic, varied clinical note text using templates.
Primary source for NLP pipelines.
"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator


NOTE_TYPES = ["Admission H&P", "Progress Note", "Discharge Summary",
              "Consultation", "Operative Note", "Nursing Note",
              "Radiology Report", "Pathology Report", "ED Note"]
NOTE_TYPE_WEIGHTS = [0.15, 0.35, 0.12, 0.10, 0.08, 0.10, 0.05, 0.02, 0.03]

# Template fragments for realistic clinical text generation
SYMPTOMS = [
    "chest pain", "shortness of breath", "fatigue", "nausea", "dizziness",
    "headache", "abdominal pain", "back pain", "palpitations", "syncope",
    "fever", "chills", "cough", "dyspnea on exertion", "leg swelling",
    "confusion", "weakness", "vision changes", "joint pain", "weight loss",
]

CONDITIONS = [
    "hypertension", "type 2 diabetes", "heart failure", "COPD", "atrial fibrillation",
    "chronic kidney disease", "hypothyroidism", "hyperlipidemia", "depression",
    "anxiety disorder", "osteoarthritis", "GERD", "sleep apnea", "obesity",
]

MEDICATIONS_TEXT = [
    "Metformin 1000mg BID", "Lisinopril 10mg daily", "Atorvastatin 40mg at bedtime",
    "Metoprolol 50mg BID", "Amlodipine 5mg daily", "Aspirin 81mg daily",
    "Insulin Glargine 20 units at bedtime", "Furosemide 40mg daily",
    "Omeprazole 20mg before meals", "Levothyroxine 50mcg in morning",
]

VITAL_TEMPLATES = [
    "BP {bp_sys}/{bp_dia}, HR {hr}, RR {rr}, SpO2 {spo2}%, Temp {temp}°F",
]

EXAM_FINDINGS = [
    "Alert and oriented x3. No acute distress.",
    "Well-appearing, no apparent distress.",
    "Alert, anxious-appearing in mild distress.",
    "Appears fatigued but cooperative.",
    "Chronically ill-appearing.",
]

PHYSICAL_EXAM_CVS = [
    "Regular rate and rhythm. No murmurs, rubs, or gallops. No JVD.",
    "Irregular rhythm, no murmurs. Mild JVD present.",
    "Regular rhythm, 2/6 systolic murmur at RUSB.",
    "Regular rate. S3 gallop present. Bilateral lower extremity edema 2+.",
]

PHYSICAL_EXAM_RESP = [
    "Clear to auscultation bilaterally. No wheezes, rales, or rhonchi.",
    "Diffuse expiratory wheezes bilaterally.",
    "Decreased breath sounds at the bases bilaterally. Dullness to percussion.",
    "Coarse crackles at the bilateral bases.",
]

PLAN_ITEMS = [
    "Continue current medications and monitor closely.",
    "Adjust medication dosage per response.",
    "Order serial troponins q6h.",
    "Cardiology consult placed.",
    "Nephrology consulted for AKI management.",
    "Start IV antibiotics for pneumonia.",
    "Physical therapy evaluation ordered.",
    "Dietary counseling for diabetes management.",
    "Increase fluid intake and electrolyte replacement.",
    "Follow-up in 2 weeks for labs and clinical reassessment.",
    "Patient and family educated on discharge instructions.",
    "Anticoagulation initiated for DVT prophylaxis.",
]


def generate_note_text(rng, note_type, age, gender):
    """Generate a realistic clinical note with dynamic content."""
    pronoun = "he" if gender == "M" else "she"
    pronoun_cap = pronoun.capitalize()
    gender_word = "male" if gender == "M" else "female"

    n_symptoms = rng.integers(1, 4)
    n_conditions = rng.integers(1, 4)
    n_meds = rng.integers(2, 6)
    n_plan = rng.integers(2, 6)

    symptoms_text = ", ".join(rng.choice(SYMPTOMS, n_symptoms, replace=False))
    conditions_text = "\n".join([f"{j+1}. {c.title()}" for j, c in enumerate(rng.choice(CONDITIONS, n_conditions, replace=False))])
    meds_text = "\n".join([f"- {m}" for m in rng.choice(MEDICATIONS_TEXT, n_meds, replace=False)])
    plan_text = "\n".join([f"{j+1}. {p}" for j, p in enumerate(rng.choice(PLAN_ITEMS, n_plan, replace=False))])

    bp_sys = rng.integers(100, 185)
    bp_dia = rng.integers(60, 115)
    hr = rng.integers(58, 115)
    rr = rng.integers(14, 24)
    spo2 = rng.integers(92, 100)
    temp = round(float(rng.uniform(97.2, 101.5)), 1)
    vitals_text = f"BP {bp_sys}/{bp_dia}, HR {hr}, RR {rr}, SpO2 {spo2}%, Temp {temp}°F"

    exam_general = rng.choice(EXAM_FINDINGS)
    exam_cvs = rng.choice(PHYSICAL_EXAM_CVS)
    exam_resp = rng.choice(PHYSICAL_EXAM_RESP)

    if note_type == "Admission H&P":
        duration = rng.integers(1, 14)
        unit = rng.choice(["days", "hours", "weeks"])
        text = f"""CHIEF COMPLAINT: {symptoms_text.capitalize()} for {duration} {unit}.

HISTORY OF PRESENT ILLNESS:
Patient is a {age}-year-old {gender_word} presenting with {duration} {unit} of {symptoms_text}. {pronoun_cap} denies any recent travel, sick contacts, or changes in medications.

PAST MEDICAL HISTORY:
{conditions_text}

MEDICATIONS:
{meds_text}

ALLERGIES: NKDA

REVIEW OF SYSTEMS:
Constitutional: {rng.choice(['No fever, chills, or weight loss.', 'Reports fatigue and mild weight loss.', 'Fever and chills present.'])}
Cardiovascular: {rng.choice(['No chest pain or palpitations.', 'Chest discomfort with exertion.', 'Occasional palpitations.'])}
Respiratory: {rng.choice(['No shortness of breath.', 'Mild dyspnea on exertion.', 'Orthopnea, uses 2 pillows.'])}

PHYSICAL EXAMINATION:
Vital Signs: {vitals_text}
General: {exam_general}
Cardiovascular: {exam_cvs}
Respiratory: {exam_resp}
Abdomen: Soft, non-tender, non-distended. Bowel sounds present.
Extremities: {rng.choice(['No edema.', '1+ pitting edema bilateral ankles.', '2+ pitting edema bilateral lower extremities.'])}

ASSESSMENT AND PLAN:
{plan_text}"""

    elif note_type == "Progress Note":
        text = f"""DATE: Progress Note

SUBJECTIVE:
Patient is a {age}-year-old {gender_word}. {pronoun_cap} reports {rng.choice(['improvement in symptoms', 'no significant change', 'worsening of ' + rng.choice(SYMPTOMS)])} since yesterday. {pronoun_cap} {rng.choice(['tolerated oral intake', 'had reduced appetite', 'is ambulating well'])}.

OBJECTIVE:
Vital Signs: {vitals_text}
General: {exam_general}
Cardiovascular: {exam_cvs}
Respiratory: {exam_resp}
Labs: {rng.choice(['Results reviewed - see chart.', 'Pending morning labs.', 'WBC trending down. Creatinine stable.'])}

ASSESSMENT:
{rng.choice(CONDITIONS).title()} - {rng.choice(['improving', 'stable', 'worsening', 'responding to treatment'])}.

PLAN:
{plan_text}"""

    elif note_type == "Discharge Summary":
        los = rng.integers(1, 15)
        text = f"""DISCHARGE SUMMARY

ADMISSION DATE: [DATE]
DISCHARGE DATE: [DATE]
LENGTH OF STAY: {los} days

PRINCIPAL DIAGNOSIS: {rng.choice(CONDITIONS).title()}

SECONDARY DIAGNOSES:
{conditions_text}

HOSPITAL COURSE:
Patient is a {age}-year-old {gender_word} admitted for {symptoms_text}. During the hospitalization, {pronoun} was treated with {rng.choice(MEDICATIONS_TEXT)} and {rng.choice(['showed improvement', 'remained stable', 'had improvement in symptoms'])}. {rng.choice(['Consultations were obtained from cardiology.', 'Nephrology was involved in care.', 'Physical therapy was consulted.'])}

DISCHARGE CONDITION: {rng.choice(['Stable', 'Good', 'Fair', 'Improved'])}
DISCHARGE DISPOSITION: {rng.choice(['Home with follow-up', 'Skilled Nursing Facility', 'Rehabilitation facility', 'Home with home health'])}

DISCHARGE MEDICATIONS:
{meds_text}

FOLLOW-UP:
{rng.choice(['Follow up with primary care physician in 1 week.', 'Return to cardiologist in 2 weeks.', 'Labs in 2 weeks and follow-up in 4 weeks.'])}

DISCHARGE INSTRUCTIONS: Patient educated on diet, activity, medications, and warning signs to return to ER."""

    else:
        # Generic note
        text = f"""Clinical Note - {note_type}

Patient: {age}-year-old {gender_word}
Chief complaint: {symptoms_text}

Clinical summary:
{pronoun_cap} presented with {symptoms_text}. Past medical history includes {rng.choice(CONDITIONS)}.
Vital signs: {vitals_text}

Current medications:
{meds_text}

Plan:
{plan_text}"""

    return text


class ClinicalNoteGenerator(BaseGenerator):

    def table_name(self):
        return "clinical_notes"

    def _get_pk_column(self):
        return "note_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx

        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        note_dates = self.random_dates("2018-01-01", "2024-12-31", n)
        note_types = self.rng.choice(NOTE_TYPES, n, p=NOTE_TYPE_WEIGHTS)

        patient_sample = self.rng.choice(patient_ids, n)
        doctor_sample = self.rng.choice(doctor_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        ages = self.rng.integers(18, 95, n)
        genders = self.rng.choice(["M", "F"], n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            note_text = generate_note_text(self.rng, note_types[i], ages[i], genders[i])
            word_count = len(note_text.split())

            records.append({
                "note_id":          f"NOTE{str(global_idx).zfill(9)}",
                "patient_id":       patient_sample[i],
                "doctor_id":        doctor_sample[i],
                "hospital_id":      hospital_sample[i],
                "note_datetime":    note_dates[i].isoformat(),
                "note_type":        note_types[i],
                "clinical_text":    note_text,
                "word_count":       word_count,
                "nlp_processed":    False,
                "is_signed":        self.rng.choice([True, False], p=[0.85, 0.15]),
            })

        return pd.DataFrame(records)
