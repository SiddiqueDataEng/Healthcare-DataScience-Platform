"""
ICU Vitals Generator — 2,000,000,000 records
Real-time ICU monitoring, every 5 seconds per patient.
Uses vectorized NumPy for high-throughput generation.
In production this would be Kafka-produced; here we simulate the data.
"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator


class ICUVitalsGenerator(BaseGenerator):

    def table_name(self):
        return "icu_vitals"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx

        patient_ids = self.context.get("patients_ids", [f"P{str(i+1).zfill(7)}" for i in range(100)])
        admission_ids = self.context.get("admissions_ids", [None] * 100)
        hospital_ids = self.context.get("hospitals_ids", [f"H{str(i+1).zfill(3)}" for i in range(10)])

        # Assign patients — ICU patients have many readings per stay
        patient_sample = self.rng.choice(patient_ids, n)
        hospital_sample = self.rng.choice(hospital_ids, n)

        # Generate timestamps spanning ICU stays
        # Each "patient session" is ~1-14 days, reading every 5 seconds
        base_timestamps = self.random_dates("2022-01-01", "2024-12-31", n)
        offsets_seconds = self.rng.integers(0, 86400 * 14, n)  # up to 14 days offset
        timestamps = base_timestamps + pd.to_timedelta(offsets_seconds, unit="s")

        # ── Vital Signs (physiologically correlated Gaussian) ──
        # Normal distributions with clinical plausibility
        hr = np.clip(self.rng.normal(78, 18, n).astype(int), 30, 200)
        bp_sys = np.clip(self.rng.normal(118, 20, n).astype(int), 60, 220)
        bp_dia = np.clip((bp_sys * 0.65 + self.rng.normal(0, 8, n)).astype(int), 40, 130)
        map_val = np.clip(((bp_sys + 2 * bp_dia) / 3).astype(int), 50, 160)
        spo2 = np.clip(self.rng.normal(97.2, 1.8, n), 70.0, 100.0).round(1)
        rr = np.clip(self.rng.normal(16, 4, n).astype(int), 8, 40)
        temp = np.clip(self.rng.normal(37.0, 0.6, n), 34.0, 41.5).round(2)

        # ~8% of readings trigger an alarm
        alarm_triggered = self.rng.random(n) < 0.08
        alarm_types = self.rng.choice(
            ["Tachycardia", "Bradycardia", "Hypotension", "Hypertension",
             "Hypoxia", "Apnea", "Tachypnea", "Fever", "Hypothermia"],
            n
        )
        alarm_severities = self.rng.choice(["Info", "Warning", "Critical"], n, p=[0.50, 0.35, 0.15])

        # Critical vitals flag (HR <40 or >150, SpO2 <88, etc.)
        critical = (
            (hr < 40) | (hr > 150) |
            (spo2 < 88) |
            (bp_sys < 70) | (bp_sys > 200) |
            (temp > 40.5) | (temp < 35.0)
        )

        # Ventilator — ~30% of ICU patients
        on_vent = self.rng.random(n) < 0.30
        fio2 = np.where(on_vent, self.rng.uniform(21, 100, n).round(1), None)
        peep = np.where(on_vent, self.rng.integers(5, 20, n), None)
        tidal_vol = np.where(on_vent, self.rng.integers(350, 600, n), None)

        records = []
        for i in range(n):
            records.append({
                "patient_id":             patient_sample[i],
                "hospital_id":            hospital_sample[i],
                "timestamp":              timestamps[i].isoformat(),
                "heart_rate":             int(hr[i]),
                "blood_pressure_sys":     int(bp_sys[i]),
                "blood_pressure_dia":     int(bp_dia[i]),
                "mean_arterial_pressure": int(map_val[i]),
                "spo2":                   round(float(spo2[i]), 1),
                "respiration_rate":       int(rr[i]),
                "temperature":            round(float(temp[i]), 2),
                "on_ventilator":          bool(on_vent[i]),
                "fio2":                   round(float(fio2[i]), 1) if on_vent[i] else None,
                "peep":                   int(peep[i]) if on_vent[i] else None,
                "tidal_volume":           int(tidal_vol[i]) if on_vent[i] else None,
                "alarm_triggered":        bool(alarm_triggered[i]),
                "alarm_type":             alarm_types[i] if alarm_triggered[i] else None,
                "alarm_severity":         alarm_severities[i] if alarm_triggered[i] else None,
                "critical_vitals_flag":   bool(critical[i]),
                "device_id":              f"ICU-{self.rng.integers(1000,9999)}",
                "data_quality_flag":      self.rng.choice(["Good","Poor","Artifact"], p=[0.93,0.04,0.03]),
            })

        return pd.DataFrame(records)
