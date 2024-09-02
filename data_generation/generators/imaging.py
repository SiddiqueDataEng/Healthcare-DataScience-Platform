"""Medical Imaging Metadata Generator — 3,000,000 records"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator

IMAGE_TYPES = ["X-Ray","MRI","CT Scan","PET Scan","Ultrasound","Mammogram","DEXA","Fluoroscopy"]
TYPE_WEIGHTS = [0.38, 0.22, 0.25, 0.04, 0.07, 0.02, 0.01, 0.01]
MODALITIES  = ["CR",  "MR",  "CT",   "PT",   "US",   "MG",  "DX",  "RF"]

BODY_PARTS = [
    ("Chest","CR"),("Brain","MR"),("Abdomen","CT"),("Spine","MR"),
    ("Knee","MR"),("Hip","CR"),("Pelvis","CT"),("Breast","MG"),
    ("Shoulder","MR"),("Ankle","CR"),("Wrist","CR"),("Head/Neck","CT"),
    ("Cardiac","MR"),("Whole Body","PT"),("Liver","US"),("Thyroid","US"),
]

FINDINGS_TEMPLATES = [
    "No acute cardiopulmonary process. Heart size normal. No pneumothorax or pleural effusion.",
    "Small bilateral pleural effusions. Mild pulmonary edema pattern. No focal consolidation.",
    "Right lower lobe opacity consistent with pneumonia. No pleural effusion.",
    "No acute intracranial abnormality. Ventricles normal in size. No mass effect or midline shift.",
    "Diffuse cerebral atrophy consistent with age. No acute infarct or hemorrhage.",
    "Acute ischemic infarct in the right middle cerebral artery territory.",
    "No acute fracture or dislocation. Mild degenerative changes.",
    "Severe osteoarthritis of the right knee with joint space narrowing.",
    "Heterogeneous liver with nodular contour consistent with cirrhosis. No focal lesion.",
    "Gallbladder sludge without definite stones. Common bile duct not dilated.",
    "Normal appendix. No free fluid. Mild nonspecific bowel gas pattern.",
    "BIRADS 4 — Suspicious calcifications in right upper outer quadrant. Biopsy recommended.",
    "BIRADS 2 — Benign finding. Routine screening recommended.",
    "Pulmonary nodule measuring 8mm in right upper lobe. Follow-up CT recommended in 3 months.",
    "No evidence of acute pulmonary embolism. No pneumothorax.",
]

REPORT_STATUSES = ["Final","Draft","Preliminary","Addendum"]
REPORT_STATUS_WEIGHTS = [0.85, 0.05, 0.06, 0.04]


class ImagingGenerator(BaseGenerator):
    def table_name(self): return "imaging_records"
    def _get_pk_column(self): return "image_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])
        doctor_ids = self.context.get("doctors_ids", [f"DR{str(i+1).zfill(5)}" for i in range(100)])
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        image_dates = self.random_dates("2018-01-01", "2024-12-31", n)
        type_indices = self.rng.choice(len(IMAGE_TYPES), n, p=TYPE_WEIGHTS)
        body_part_indices = self.rng.choice(len(BODY_PARTS), n)
        findings = self.rng.choice(FINDINGS_TEMPLATES, n)
        critical_finding = self.rng.random(n) < 0.06

        patient_sample = self.rng.choice(patient_ids, n)
        doctor_sample = self.rng.choice(doctor_ids, n)
        radiologist_sample = self.rng.choice(doctor_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        records = []
        for i in range(n):
            global_idx = start_idx + i + 1
            img_type = IMAGE_TYPES[type_indices[i]]
            modality = MODALITIES[type_indices[i]]
            body_part, _ = BODY_PARTS[body_part_indices[i]]
            image_dt = image_dates[i]
            report_dt = image_dt + pd.Timedelta(hours=int(self.rng.integers(1, 48)))

            records.append({
                "image_id":           f"IMG{str(global_idx).zfill(8)}",
                "patient_id":         patient_sample[i],
                "ordering_doctor_id": doctor_sample[i],
                "radiologist_id":     radiologist_sample[i],
                "hospital_id":        hospital_sample[i],
                "image_type":         img_type,
                "modality":           modality,
                "body_part":          body_part,
                "laterality":         self.rng.choice(["Left","Right","Bilateral","NA"]),
                "image_date":         image_dt.isoformat(),
                "study_instance_uid": f"1.2.840.10008.{global_idx}.{self.rng.integers(1000,9999)}",
                "accession_number":   f"ACC{str(global_idx).zfill(8)}",
                "findings":           findings[i],
                "impression":         findings[i][:120],
                "critical_finding":   bool(critical_finding[i]),
                "contrast_used":      self.rng.choice([True, False], p=[0.35, 0.65]),
                "image_count":        int(self.rng.integers(1, 800)),
                "image_storage_path": f"s3://healthcare-pacs/{hospital_sample[i]}/{image_dt.year}/{img_type.lower().replace(' ','_')}/{global_idx}.dcm",
                "ai_confidence_score": round(float(self.rng.uniform(0.70, 0.99)), 4),
                "report_status":      self.rng.choice(REPORT_STATUSES, p=REPORT_STATUS_WEIGHTS),
                "report_datetime":    report_dt.isoformat(),
            })
        return pd.DataFrame(records)
