"""
Healthcare Data Platform - Master Data Generator
Generates all 20 synthetic datasets with realistic distributions

Usage:
    python generate_all.py --scale small
    python generate_all.py --scale medium
    python generate_all.py --scale full
    python generate_all.py --tables patients,appointments --scale small
"""

import argparse
import os
import sys
import time
from loguru import logger
from pathlib import Path

# Ensure submodules are importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_generation.generators.hospitals        import HospitalGenerator
from data_generation.generators.patients         import PatientGenerator
from data_generation.generators.doctors          import DoctorGenerator
from data_generation.generators.appointments     import AppointmentGenerator
from data_generation.generators.admissions       import AdmissionGenerator
from data_generation.generators.diagnoses        import DiagnosisGenerator
from data_generation.generators.procedures       import ProcedureGenerator
from data_generation.generators.prescriptions    import PrescriptionGenerator
from data_generation.generators.lab_results      import LabResultGenerator
from data_generation.generators.imaging          import ImagingGenerator
from data_generation.generators.clinical_notes   import ClinicalNoteGenerator
from data_generation.generators.icu_vitals       import ICUVitalsGenerator
from data_generation.generators.wearable_data    import WearableDataGenerator
from data_generation.generators.emergency_visits import EmergencyVisitGenerator
from data_generation.generators.insurance_claims import InsuranceClaimGenerator
from data_generation.generators.billing          import BillingGenerator
from data_generation.generators.patient_feedback import PatientFeedbackGenerator
from data_generation.generators.staff_schedule   import StaffScheduleGenerator
from data_generation.generators.bed_management   import BedManagementGenerator

SCALE_CONFIG = {
    "small": {
        "hospitals": 10,
        "patients": 1_000,
        "doctors": 100,
        "departments": 100,
        "appointments": 10_000,
        "admissions": 2_000,
        "diagnoses": 15_000,
        "procedures": 8_000,
        "prescriptions": 20_000,
        "lab_results": 50_000,
        "imaging": 3_000,
        "clinical_notes": 10_000,
        "icu_vitals": 100_000,
        "wearable_data": 500_000,
        "emergency_visits": 5_000,
        "insurance_claims": 5_000,
        "billing": 15_000,
        "patient_feedback": 2_000,
        "staff_schedule": 5_000,
        "bed_management": 10_000,
    },
    "medium": {
        "hospitals": 50,
        "patients": 100_000,
        "doctors": 2_000,
        "departments": 500,
        "appointments": 1_000_000,
        "admissions": 200_000,
        "diagnoses": 1_500_000,
        "procedures": 800_000,
        "prescriptions": 2_000_000,
        "lab_results": 5_000_000,
        "imaging": 300_000,
        "clinical_notes": 1_000_000,
        "icu_vitals": 10_000_000,
        "wearable_data": 50_000_000,
        "emergency_visits": 500_000,
        "insurance_claims": 500_000,
        "billing": 1_500_000,
        "patient_feedback": 200_000,
        "staff_schedule": 50_000,
        "bed_management": 1_000_000,
    },
    "full": {
        "hospitals": 50,
        "patients": 1_000_000,
        "doctors": 10_000,
        "departments": 500,
        "appointments": 10_000_000,
        "admissions": 2_000_000,
        "diagnoses": 15_000_000,
        "procedures": 8_000_000,
        "prescriptions": 20_000_000,
        "lab_results": 50_000_000,
        "imaging": 3_000_000,
        "clinical_notes": 10_000_000,
        "icu_vitals": 2_000_000_000,
        "wearable_data": 500_000_000,
        "emergency_visits": 5_000_000,
        "insurance_claims": 5_000_000,
        "billing": 15_000_000,
        "patient_feedback": 2_000_000,
        "staff_schedule": 500_000,
        "bed_management": 10_000_000,
    },
}

# Generator registry — order matters (respect FK dependencies)
GENERATOR_ORDER = [
    ("hospitals",        HospitalGenerator),
    ("patients",         PatientGenerator),
    ("doctors",          DoctorGenerator),
    ("departments",      None),                # generated inside DoctorGenerator
    ("appointments",     AppointmentGenerator),
    ("admissions",       AdmissionGenerator),
    ("diagnoses",        DiagnosisGenerator),
    ("procedures",       ProcedureGenerator),
    ("prescriptions",    PrescriptionGenerator),
    ("lab_results",      LabResultGenerator),
    ("imaging",          ImagingGenerator),
    ("clinical_notes",   ClinicalNoteGenerator),
    ("icu_vitals",       ICUVitalsGenerator),
    ("wearable_data",    WearableDataGenerator),
    ("emergency_visits", EmergencyVisitGenerator),
    ("insurance_claims", InsuranceClaimGenerator),
    ("billing",          BillingGenerator),
    ("patient_feedback", PatientFeedbackGenerator),
    ("staff_schedule",   StaffScheduleGenerator),
    ("bed_management",   BedManagementGenerator),
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Healthcare Data Platform - Synthetic Data Generator"
    )
    parser.add_argument(
        "--scale",
        choices=["small", "medium", "full"],
        default="small",
        help="Data scale: small (dev/test) | medium (staging) | full (production)",
    )
    parser.add_argument(
        "--tables",
        type=str,
        default=None,
        help="Comma-separated list of tables to generate (default: all)",
    )
    parser.add_argument(
        "--output-format",
        choices=["parquet", "csv", "json"],
        default="parquet",
        help="Output file format",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data/raw",
        help="Output directory for generated files",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100_000,
        help="Batch size for chunked file writing",
    )
    return parser.parse_args()


def run_generator(name, generator_cls, count, output_dir, output_format, seed, batch_size, context):
    """Run a single table generator with timing and error handling."""
    if generator_cls is None:
        return context  # skip (handled by parent generator)

    logger.info(f"Generating {name}: {count:,} records ...")
    t0 = time.time()

    gen = generator_cls(
        n_records=count,
        seed=seed,
        output_dir=output_dir,
        output_format=output_format,
        batch_size=batch_size,
        context=context,  # shared state (patient_ids, doctor_ids, etc.)
    )
    result_context = gen.generate()

    elapsed = time.time() - t0
    logger.success(
        f"  ✓ {name}: {count:,} records | {elapsed:.1f}s | "
        f"{count/elapsed:,.0f} records/sec"
    )
    return result_context


def main():
    args = parse_args()
    scale = SCALE_CONFIG[args.scale]

    # Filter tables if specified
    requested_tables = None
    if args.tables:
        requested_tables = set(t.strip() for t in args.tables.split(","))

    logger.info(f"Healthcare Data Generator starting | scale={args.scale} | seed={args.seed}")
    logger.info(f"Output: {args.output_dir} ({args.output_format})")

    os.makedirs(args.output_dir, exist_ok=True)

    # Shared context passed between generators to maintain referential integrity
    # (e.g., PatientGenerator produces patient_ids used by AppointmentGenerator)
    context = {}
    total_start = time.time()

    for table_name, generator_cls in GENERATOR_ORDER:
        if requested_tables and table_name not in requested_tables:
            continue
        if table_name not in scale:
            continue

        context = run_generator(
            name=table_name,
            generator_cls=generator_cls,
            count=scale[table_name],
            output_dir=args.output_dir,
            output_format=args.output_format,
            seed=args.seed,
            batch_size=args.batch_size,
            context=context,
        )

    total_elapsed = time.time() - total_start
    logger.success(
        f"\n{'='*60}\n"
        f"All tables generated in {total_elapsed:.1f}s\n"
        f"Output directory: {args.output_dir}\n"
        f"{'='*60}"
    )


if __name__ == "__main__":
    main()
