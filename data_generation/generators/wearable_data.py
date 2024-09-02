"""Wearable Device Data Generator — 500,000,000 records"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator

DEVICE_TYPES = ["Smartwatch","Fitness Band","CGM","ECG Patch","BP Monitor","Smart Scale"]
DEVICE_WEIGHTS = [0.45, 0.30, 0.10, 0.05, 0.07, 0.03]
DEVICE_BRANDS = {
    "Smartwatch": ["Apple Watch","Samsung Galaxy Watch","Garmin","Fitbit Sense","Polar"],
    "Fitness Band": ["Fitbit Charge","Xiaomi Mi Band","Garmin Vivosmart","Whoop"],
    "CGM": ["Dexcom G7","Abbott FreeStyle Libre","Medtronic Guardian"],
    "ECG Patch": ["Zio Patch","BioTel Heart","BodyGuardian"],
    "BP Monitor": ["Withings","Omron","QardioArm"],
    "Smart Scale": ["Withings Body+","Fitbit Aria","Garmin Index"],
}
HR_ZONES = ["Rest","Fat Burn","Cardio","Peak"]
HR_ZONE_WEIGHTS = [0.55, 0.25, 0.15, 0.05]


class WearableDataGenerator(BaseGenerator):
    def table_name(self): return "wearable_data"
    def _get_pk_column(self): return None  # auto-generated bigserial in DB

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(1000)])

        timestamps = self.random_dates("2020-01-01", "2024-12-31", n)
        offsets = self.rng.integers(0, 86400, n)
        timestamps = timestamps + pd.to_timedelta(offsets, unit="s")

        device_type_idx = self.rng.choice(len(DEVICE_TYPES), n, p=DEVICE_WEIGHTS)
        patient_sample = self.rng.choice(patient_ids, n)

        # Steps: log-normal, varies by time of day (just use daily totals here)
        steps = np.clip(self.rng.lognormal(8.5, 0.9, n).astype(int), 0, 35000)
        calories = np.clip((steps * 0.04 + self.rng.normal(200, 80, n)), 50, 4000).astype(int)
        heart_rate = np.clip(self.rng.normal(72, 14, n).astype(int), 40, 180)
        sleep_hours = np.clip(self.rng.normal(7.0, 1.2, n), 2.0, 12.0).round(2)
        deep_sleep = np.clip(sleep_hours * self.rng.uniform(0.15, 0.25, n), 0, sleep_hours).round(2)
        rem_sleep = np.clip(sleep_hours * self.rng.uniform(0.20, 0.30, n), 0, sleep_hours - deep_sleep).round(2)
        light_sleep = (sleep_hours - deep_sleep - rem_sleep).clip(0).round(2)
        sleep_score = np.clip(self.rng.normal(72, 15, n).astype(int), 0, 100)
        spo2 = np.clip(self.rng.normal(97.5, 1.5, n), 88, 100).round(1)
        stress_level = np.clip(self.rng.normal(45, 25, n).astype(int), 1, 100)
        hrv = np.clip(self.rng.normal(55, 20, n), 10, 150).round(2)

        records = []
        for i in range(n):
            dtype = DEVICE_TYPES[device_type_idx[i]]
            brands = DEVICE_BRANDS[dtype]
            brand = self.rng.choice(brands)
            device_id = f"{dtype[:3].upper()}-{self.rng.integers(100000,999999)}"

            # CGM adds glucose
            bg = round(float(self.rng.normal(105, 30)), 1) if dtype == "CGM" else None

            records.append({
                "patient_id":     patient_sample[i],
                "device_id":      device_id,
                "device_type":    dtype,
                "device_brand":   brand,
                "timestamp":      timestamps[i].isoformat(),
                "steps":          int(steps[i]),
                "steps_goal":     10000,
                "calories_burned": int(calories[i]),
                "heart_rate":     int(heart_rate[i]),
                "heart_rate_zone": self.rng.choice(HR_ZONES, p=HR_ZONE_WEIGHTS),
                "heart_rate_variability": float(hrv[i]),
                "sleep_hours":    float(sleep_hours[i]),
                "deep_sleep_hours": float(deep_sleep[i]),
                "rem_sleep_hours":  float(rem_sleep[i]),
                "light_sleep_hours": float(light_sleep[i]),
                "sleep_score":    int(sleep_score[i]),
                "spo2":           float(spo2[i]),
                "stress_level":   int(stress_level[i]),
                "blood_glucose":  bg,
                "battery_level":  int(self.rng.integers(5, 101)),
                "data_quality":   self.rng.choice(["Good","Poor","Artifact"], p=[0.92, 0.05, 0.03]),
            })
        return pd.DataFrame(records)
