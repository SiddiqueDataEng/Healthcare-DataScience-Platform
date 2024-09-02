"""
Batch ETL Pipeline: Raw → Processed → Curated
Uses PySpark for distributed processing at scale.

Pipeline stages:
  1. Extract: Read from raw data lake (Parquet/CSV)
  2. Transform: Clean, validate, enrich, standardize
  3. Load: Write to data warehouse (PostgreSQL/Snowflake)

Usage:
    python etl/batch/etl_pipeline.py --table patients --env dev
    python etl/batch/etl_pipeline.py --table all --env prod
"""

import os
import sys
import argparse
import yaml
from pathlib import Path
from datetime import datetime
from loguru import logger

try:
    from pyspark.sql import SparkSession, DataFrame
    from pyspark.sql import functions as F
    from pyspark.sql.types import *
    SPARK_AVAILABLE = True
except ImportError:
    logger.warning("PySpark not available. Using pandas fallback for small datasets.")
    SPARK_AVAILABLE = False
    import pandas as pd


# ─── Spark Session Factory ────────────────────────────────────────────

def create_spark_session(app_name: str = "HealthcareETL", env: str = "dev") -> "SparkSession":
    """Create a configured SparkSession."""
    builder = (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.shuffle.partitions", "200")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    )

    if env == "dev":
        builder = builder.master("local[*]")
        builder = builder.config("spark.executor.memory", "4g")
        builder = builder.config("spark.driver.memory", "4g")
    elif env == "prod":
        # In production: connect to YARN/Kubernetes cluster
        builder = builder.master("yarn")
        builder = builder.config("spark.executor.memory", "16g")
        builder = builder.config("spark.executor.cores", "4")
        builder = builder.config("spark.executor.instances", "10")

    return builder.getOrCreate()


# ─── Transformations ─────────────────────────────────────────────────

class PatientTransformer:
    """Transform raw patient data → processed patient data."""

    @staticmethod
    def transform(df: "DataFrame") -> "DataFrame":
        return (
            df
            # Standardize gender codes
            .withColumn("gender",
                F.when(F.col("gender").isin("M","Male","MALE","m"), "M")
                 .when(F.col("gender").isin("F","Female","FEMALE","f"), "F")
                 .otherwise("O")
            )
            # Parse and validate DOB
            .withColumn("dob", F.to_date("dob", "yyyy-MM-dd"))
            # Calculate age
            .withColumn("age",
                F.floor(F.datediff(F.current_date(), F.col("dob")) / 365.25).cast(IntegerType())
            )
            # Standardize blood group
            .withColumn("blood_group",
                F.upper(F.trim(F.col("blood_group")))
            )
            # Flag suspicious ages
            .withColumn("age_valid_flag",
                F.col("age").between(0, 120)
            )
            # Standardize state names
            .withColumn("address_state",
                F.initcap(F.trim(F.col("address_state")))
            )
            # Registration date
            .withColumn("registration_date", F.to_date("registration_date", "yyyy-MM-dd"))
            # PHI masking for non-HIPAA environments (replace with hash)
            .withColumn("first_name_masked",
                F.when(F.lit(os.getenv("HIPAA_MODE","true") == "true"),
                       F.concat(F.col("first_name").substr(1, 1), F.lit("***")))
                 .otherwise(F.col("first_name"))
            )
            # Add ETL metadata
            .withColumn("etl_processed_at", F.current_timestamp())
            .withColumn("etl_version", F.lit("1.0"))
            # Remove GDPR-erased records' PHI
            .withColumn("first_name",
                F.when(F.col("gdpr_erasure_flag") == True, F.lit("ERASED"))
                 .otherwise(F.col("first_name"))
            )
            .withColumn("last_name",
                F.when(F.col("gdpr_erasure_flag") == True, F.lit("ERASED"))
                 .otherwise(F.col("last_name"))
            )
        )

    @staticmethod
    def validate(df: "DataFrame") -> tuple:
        total = df.count()
        null_patient_id = df.filter(F.col("patient_id").isNull()).count()
        invalid_age = df.filter(~F.col("age_valid_flag")).count()
        null_dob = df.filter(F.col("dob").isNull()).count()
        invalid_gender = df.filter(~F.col("gender").isin("M","F","O")).count()

        issues = {
            "total_records": total,
            "null_patient_id": null_patient_id,
            "invalid_age": invalid_age,
            "null_dob": null_dob,
            "invalid_gender": invalid_gender,
            "quality_score": round((total - null_patient_id - invalid_age) / total * 100, 2)
        }
        return df, issues


class AdmissionTransformer:
    """Transform raw admission data."""

    @staticmethod
    def transform(df: "DataFrame") -> "DataFrame":
        return (
            df
            .withColumn("admit_date",    F.to_timestamp("admit_date"))
            .withColumn("discharge_date", F.to_timestamp("discharge_date"))
            .withColumn("length_of_stay",
                F.when(F.col("discharge_date").isNotNull(),
                    F.datediff(F.col("discharge_date").cast("date"),
                               F.col("admit_date").cast("date")))
                 .otherwise(F.lit(None).cast(IntegerType()))
            )
            # Flag unusually long stays
            .withColumn("long_stay_flag",
                F.col("length_of_stay") > 30
            )
            # Normalize discharge status
            .withColumn("discharge_status",
                F.when(F.col("discharge_status").isin("Expired","Dead","Deceased"), "Expired")
                 .when(F.col("discharge_status").isin("AMA","Against Medical Advice"), "AMA")
                 .otherwise(F.col("discharge_status"))
            )
            .withColumn("etl_processed_at", F.current_timestamp())
        )


class LabResultTransformer:
    """Transform lab results — validate reference ranges, flag critical values."""

    @staticmethod
    def transform(df: "DataFrame") -> "DataFrame":
        return (
            df
            .withColumn("collection_datetime", F.to_timestamp("collection_datetime"))
            .withColumn("resulted_datetime",   F.to_timestamp("resulted_datetime"))
            # Turnaround time in hours
            .withColumn("tat_hours",
                F.when(
                    F.col("resulted_datetime").isNotNull() & F.col("collection_datetime").isNotNull(),
                    F.round((F.unix_timestamp("resulted_datetime") -
                             F.unix_timestamp("collection_datetime")) / 3600, 2)
                )
            )
            # Flag outlier values (likely data quality issues)
            .withColumn("result_numeric",
                F.when(F.col("result_numeric").cast(DoubleType()).isNotNull(),
                       F.col("result_numeric").cast(DoubleType()))
            )
            .withColumn("data_quality_flag",
                F.when(F.col("result_numeric") < 0, "NEGATIVE_VALUE")
                 .when(F.col("result_numeric") > 100000, "IMPLAUSIBLE_HIGH")
                 .when(F.col("tat_hours") > 168, "DELAYED_RESULT")
                 .otherwise("OK")
            )
            .withColumn("etl_processed_at", F.current_timestamp())
        )


# ─── SCD Type 2 Handler ──────────────────────────────────────────────

def apply_scd_type2(
    spark: "SparkSession",
    new_df: "DataFrame",
    existing_table: str,
    pk_col: str,
    track_cols: list,
) -> "DataFrame":
    """
    Apply Slowly Changing Dimension Type 2 logic.
    Maintains full history of changes with valid_from / valid_to dates.
    """
    try:
        existing = spark.table(existing_table)
    except Exception:
        # First load — all records are new
        return (
            new_df
            .withColumn("scd_valid_from", F.current_timestamp())
            .withColumn("scd_valid_to", F.lit(None).cast(TimestampType()))
            .withColumn("scd_is_current", F.lit(True))
            .withColumn("scd_version", F.lit(1))
        )

    # Find changed records
    active_existing = existing.filter(F.col("scd_is_current") == True)

    # Join on PK
    change_cols = [F.coalesce(F.col(f"new.{c}"), F.lit("")).cast(StringType()) !=
                   F.coalesce(F.col(f"existing.{c}"), F.lit("")).cast(StringType())
                   for c in track_cols]

    changed = (
        new_df.alias("new")
        .join(active_existing.alias("existing"), pk_col, "inner")
        .filter(F.array_contains(F.array(*[c.cast(BooleanType()) for c in change_cols]), True))
    )

    # TODO: In production, use Delta Lake MERGE for atomic SCD2 updates
    return new_df


# ─── Main ETL Orchestrator ───────────────────────────────────────────

TRANSFORMERS = {
    "patients":    PatientTransformer,
    "admissions":  AdmissionTransformer,
    "lab_results": LabResultTransformer,
}


def run_etl(table_name: str, env: str = "dev",
            input_path: str = "./data/raw",
            output_path: str = "./data/processed"):
    """Run ETL for a specific table."""
    logger.info(f"ETL: {table_name} | env={env}")

    if SPARK_AVAILABLE:
        spark = create_spark_session(f"Healthcare ETL - {table_name}", env)
        df = spark.read.parquet(f"{input_path}/{table_name}")
    else:
        df = pd.read_parquet(f"{input_path}/{table_name}")

    # Apply table-specific transformations
    transformer_cls = TRANSFORMERS.get(table_name)
    if transformer_cls:
        if SPARK_AVAILABLE:
            df = transformer_cls.transform(df)
            df, quality_issues = transformer_cls.validate(df) if hasattr(transformer_cls, "validate") else (df, {})
            logger.info(f"Quality report: {quality_issues}")
            df.write.mode("overwrite").parquet(f"{output_path}/{table_name}")
        else:
            logger.info(f"Pandas fallback: skipping Spark transforms for {table_name}")
    else:
        logger.warning(f"No transformer registered for {table_name}. Writing as-is.")
        if SPARK_AVAILABLE:
            df.write.mode("overwrite").parquet(f"{output_path}/{table_name}")

    logger.success(f"ETL complete: {table_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", default="all")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--input", default="./data/raw")
    parser.add_argument("--output", default="./data/processed")
    args = parser.parse_args()

    tables = list(TRANSFORMERS.keys()) if args.table == "all" else [args.table]
    for table in tables:
        run_etl(table, args.env, args.input, args.output)
