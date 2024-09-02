"""
Hospital Generator
Generates the hospitals master table with realistic US hospital data.
"""
import numpy as np
import pandas as pd
from data_generation.generators.base_generator import BaseGenerator


HOSPITAL_NAMES = [
    "City General Hospital", "Memorial Medical Center", "Regional Health System",
    "University Hospital", "St. Mary Medical Center", "Community Health Hospital",
    "Presbyterian Medical Center", "Baptist Health Medical Center",
    "Methodist Hospital", "Mercy Medical Center", "Sacred Heart Hospital",
    "Kaiser Permanente Medical Center", "Cleveland Clinic Regional",
    "Mayo Clinic Health System", "Johns Hopkins Community Hospital",
    "Cedars-Sinai Medical Center", "Mass General Brigham",
    "UCSF Medical Center", "NYU Langone Health", "Vanderbilt University Medical Center",
]

HOSPITAL_TYPES = ["Public", "Private", "Non-Profit", "Teaching", "Specialty", "Critical Access"]
HOSPITAL_TYPE_WEIGHTS = [0.25, 0.30, 0.25, 0.12, 0.05, 0.03]

ACCREDITATIONS = ["JCI", "DNV", "ACHC", "The Joint Commission", "None"]
ACCREDITATION_WEIGHTS = [0.20, 0.15, 0.10, 0.45, 0.10]

TRAUMA_LEVELS = ["Level I", "Level II", "Level III", None]
TRAUMA_WEIGHTS = [0.10, 0.20, 0.25, 0.45]

US_CITIES = [
    ("Houston", "Texas", 29.7604, -95.3698),
    ("Dallas", "Texas", 32.7767, -96.7970),
    ("Austin", "Texas", 30.2672, -97.7431),
    ("San Antonio", "Texas", 29.4241, -98.4936),
    ("Los Angeles", "California", 34.0522, -118.2437),
    ("San Francisco", "California", 37.7749, -122.4194),
    ("San Diego", "California", 32.7157, -117.1611),
    ("Chicago", "Illinois", 41.8781, -87.6298),
    ("New York", "New York", 40.7128, -74.0060),
    ("Phoenix", "Arizona", 33.4484, -112.0740),
    ("Philadelphia", "Pennsylvania", 39.9526, -75.1652),
    ("Seattle", "Washington", 47.6062, -122.3321),
    ("Boston", "Massachusetts", 42.3601, -71.0589),
    ("Denver", "Colorado", 39.7392, -104.9903),
    ("Atlanta", "Georgia", 33.7490, -84.3880),
    ("Miami", "Florida", 25.7617, -80.1918),
    ("Orlando", "Florida", 28.5383, -81.3792),
    ("Minneapolis", "Minnesota", 44.9778, -93.2650),
    ("Detroit", "Michigan", 42.3314, -83.0458),
    ("Portland", "Oregon", 45.5051, -122.6750),
    ("Las Vegas", "Nevada", 36.1699, -115.1398),
    ("Nashville", "Tennessee", 36.1627, -86.7816),
    ("Charlotte", "North Carolina", 35.2271, -80.8431),
    ("Cleveland", "Ohio", 41.4993, -81.6944),
    ("Pittsburgh", "Pennsylvania", 40.4406, -79.9959),
]

NETWORKS = ["NET001", "NET002", "NET003", "NET004", "NET005"]


class HospitalGenerator(BaseGenerator):

    def table_name(self):
        return "hospitals"

    def _get_pk_column(self):
        return "hospital_id"

    def generate_batch(self, batch_idx, start_idx, end_idx):
        n = end_idx - start_idx
        records = []

        for i in range(start_idx, end_idx):
            idx = i + 1
            city_data = US_CITIES[i % len(US_CITIES)]
            city, state, lat, lon = city_data

            # Add small random offset to lat/lon for uniqueness
            lat += self.rng.uniform(-0.05, 0.05)
            lon += self.rng.uniform(-0.05, 0.05)

            h_type = self.rng.choice(HOSPITAL_TYPES, p=HOSPITAL_TYPE_WEIGHTS)
            total_beds = int(self.rng.integers(80, 2200))
            icu_ratio = self.rng.uniform(0.08, 0.18)
            icu_beds = max(10, int(total_beds * icu_ratio))
            nicu_beds = int(self.rng.integers(0, 40)) if h_type in ["Non-Profit", "Teaching", "Public"] else 0
            er_beds = int(total_beds * self.rng.uniform(0.05, 0.12))

            trauma = self.rng.choice(TRAUMA_LEVELS, p=TRAUMA_WEIGHTS)
            has_trauma = trauma is not None

            name_idx = i % len(HOSPITAL_NAMES)
            hospital_name = f"{HOSPITAL_NAMES[name_idx]}"
            if i >= len(HOSPITAL_NAMES):
                hospital_name = f"{city} {HOSPITAL_NAMES[name_idx % len(HOSPITAL_NAMES)]}"

            est_year = int(self.rng.integers(1880, 2010))

            records.append({
                "hospital_id":      f"H{str(idx).zfill(3)}",
                "hospital_name":    hospital_name,
                "hospital_type":    h_type,
                "city":             city,
                "state":            state,
                "country":          "USA",
                "zip_code":         f"{self.rng.integers(10000,99999):05d}",
                "latitude":         round(lat, 6),
                "longitude":        round(lon, 6),
                "total_beds":       total_beds,
                "icu_beds":         icu_beds,
                "nicu_beds":        nicu_beds,
                "er_beds":          er_beds,
                "trauma_center":    has_trauma,
                "trauma_level":     trauma,
                "accreditation":    self.rng.choice(ACCREDITATIONS, p=ACCREDITATION_WEIGHTS),
                "established_year": est_year,
                "network_id":       self.rng.choice(NETWORKS),
                "is_active":        True,
            })

        return pd.DataFrame(records)
