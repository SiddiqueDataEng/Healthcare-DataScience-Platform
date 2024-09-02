"""
Apache Airflow DAG: Healthcare Data Platform
Orchestrates the full daily batch pipeline.

Pipeline Schedule: Daily at 02:00 UTC

Stages:
  1. Data ingestion (raw → data lake)
  2. Data quality checks
  3. ETL transforms (raw → processed → curated)
  4. Data warehouse load
  5. ML model scoring
  6. NLP processing
  7. Dashboard refresh notification

Usage:
    Place this file in $AIRFLOW_HOME/dags/
    airflow dags trigger healthcare_daily_pipeline
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.sensors.filesystem import FileSensor
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable

# ─── DAG Default Args ────────────────────────────────────────────────

default_args = {
    "owner":            "healthcare_data_team",
    "depends_on_past":  False,
    "start_date":       datetime(2024, 1, 1),
    "email_on_failure": True,
    "email_on_retry":   False,
    "email":            ["data-engineering@healthcare.org"],
    "retries":          2,
    "retry_delay":      timedelta(minutes=10),
    "execution_timeout": timedelta(hours=4),
}


# ─── Task Functions ───────────────────────────────────────────────────

def check_source_data_availability(**context):
    """Check that upstream data files are available before processing."""
    import os
    from pathlib import Path
    data_dir = Variable.get("raw_data_dir", default_var="/data/raw")
    required_files = ["patients", "admissions", "diagnoses", "lab_results"]
    missing = [f for f in required_files if not Path(f"{data_dir}/{f}").exists()]
    if missing:
        raise FileNotFoundError(f"Missing data files: {missing}")
    return f"All required files available: {data_dir}"


def run_data_quality_checks(table_name: str, **context):
    """Run Great Expectations checks for a table."""
    import subprocess
    result = subprocess.run(
        ["python", "data_quality/run_checks.py", "--table", table_name],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"DQ checks failed for {table_name}: {result.stderr}")

    # Push quality score to XCom for downstream monitoring
    context["ti"].xcom_push(key=f"dq_score_{table_name}", value=result.stdout)
    return result.stdout


def branch_on_dq_result(**context):
    """Branch: if DQ fails, skip downstream; otherwise proceed."""
    ti = context["ti"]
    dq_scores = [
        ti.xcom_pull(task_ids=f"data_quality.dq_{t}", key=f"dq_score_{t}")
        for t in ["patients", "admissions", "lab_results", "diagnoses"]
    ]
    # If any critical DQ check failed, go to failure path
    all_passed = all(score and "PASS" in str(score) for score in dq_scores if score)
    return "etl_transforms" if all_passed else "dq_failure_notification"


def run_etl_transform(table_name: str, **context):
    """Run PySpark ETL transform for a table."""
    import subprocess
    result = subprocess.run(
        ["python", "etl/batch/etl_pipeline.py", "--table", table_name, "--env", "prod"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ETL failed for {table_name}: {result.stderr}")
    return f"ETL complete: {table_name}"


def score_readmission_model(**context):
    """Run readmission prediction model on new admissions."""
    import subprocess
    result = subprocess.run(
        ["python", "ml_models/readmission/score.py", "--date", "today"],
        capture_output=True, text=True
    )
    return "Readmission scoring complete"


def process_clinical_notes_nlp(**context):
    """Run NLP pipeline on new clinical notes."""
    import subprocess
    result = subprocess.run(
        ["python", "nlp/entity_recognition/clinical_ner.py", "--mode", "batch"],
        capture_output=True, text=True
    )
    return "NLP processing complete"


def send_pipeline_success_notification(**context):
    """Send pipeline completion notification."""
    run_date = context["ds"]
    # In production: send to Slack/PagerDuty/email
    print(f"Healthcare pipeline completed successfully for {run_date}")


# ─── DAG Definition ───────────────────────────────────────────────────

with DAG(
    dag_id="healthcare_daily_pipeline",
    default_args=default_args,
    description="Healthcare Data Platform — Daily Batch Pipeline",
    schedule_interval="0 2 * * *",          # 2:00 AM UTC daily
    catchup=False,
    max_active_runs=1,
    tags=["healthcare", "etl", "production"],
) as dag:

    # ── Start ──────────────────────────────────────────────────────
    pipeline_start = DummyOperator(task_id="pipeline_start")

    # ── Source availability check ──────────────────────────────────
    check_sources = PythonOperator(
        task_id="check_source_availability",
        python_callable=check_source_data_availability,
    )

    # ── Data Quality Checks ────────────────────────────────────────
    with TaskGroup("data_quality") as dq_group:
        dq_tasks = {}
        for table in ["patients", "admissions", "lab_results", "diagnoses",
                      "prescriptions", "billing", "insurance_claims"]:
            dq_tasks[table] = PythonOperator(
                task_id=f"dq_{table}",
                python_callable=run_data_quality_checks,
                op_kwargs={"table_name": table},
            )

    # ── Branch on DQ result ────────────────────────────────────────
    dq_branch = BranchPythonOperator(
        task_id="dq_branch",
        python_callable=branch_on_dq_result,
    )

    dq_failure = BashOperator(
        task_id="dq_failure_notification",
        bash_command="echo 'DATA QUALITY FAILURE - Pipeline halted. Notify data engineering team.'",
    )

    # ── ETL Transforms ─────────────────────────────────────────────
    with TaskGroup("etl_transforms") as etl_group:
        etl_tasks = {}
        # Tables with no dependencies
        independent_tables = ["hospitals", "departments", "patients", "doctors"]
        for table in independent_tables:
            etl_tasks[table] = PythonOperator(
                task_id=f"etl_{table}",
                python_callable=run_etl_transform,
                op_kwargs={"table_name": table},
            )

        # Tables with FK dependencies
        dependent_tables = {
            "appointments":     ["patients", "doctors"],
            "admissions":       ["patients"],
            "diagnoses":        ["patients", "admissions"],
            "prescriptions":    ["patients", "doctors"],
            "lab_results":      ["patients", "admissions"],
            "billing":          ["patients", "admissions"],
            "insurance_claims": ["patients"],
            "clinical_notes":   ["patients", "admissions"],
            "emergency_visits": ["patients"],
            "icu_vitals":       ["patients", "admissions"],
        }
        for table, deps in dependent_tables.items():
            etl_tasks[table] = PythonOperator(
                task_id=f"etl_{table}",
                python_callable=run_etl_transform,
                op_kwargs={"table_name": table},
            )
            for dep in deps:
                if dep in etl_tasks:
                    etl_tasks[dep] >> etl_tasks[table]

    # ── ML Scoring ─────────────────────────────────────────────────
    with TaskGroup("ml_scoring") as ml_group:
        readmission_scoring = PythonOperator(
            task_id="readmission_scoring",
            python_callable=score_readmission_model,
        )
        los_scoring = BashOperator(
            task_id="los_scoring",
            bash_command="python ml_models/los_prediction/score.py --date {{ ds }}",
        )
        fraud_scoring = BashOperator(
            task_id="fraud_scoring",
            bash_command="python ml_models/fraud_detection/score.py --date {{ ds }}",
        )

    # ── NLP Processing ─────────────────────────────────────────────
    with TaskGroup("nlp_processing") as nlp_group:
        ner_task = PythonOperator(
            task_id="clinical_ner",
            python_callable=process_clinical_notes_nlp,
        )
        icd_coding = BashOperator(
            task_id="icd_code_prediction",
            bash_command="python nlp/icd_prediction/icd_predictor.py --mode batch --date {{ ds }}",
        )
        ner_task >> icd_coding

    # ── Dashboard Refresh ──────────────────────────────────────────
    refresh_dashboards = BashOperator(
        task_id="refresh_dashboard_cache",
        bash_command="echo 'Refreshing Power BI / Superset dashboard caches ...'",
    )

    # ── Success notification ───────────────────────────────────────
    pipeline_success = PythonOperator(
        task_id="pipeline_success_notification",
        python_callable=send_pipeline_success_notification,
        trigger_rule="all_success",
    )

    pipeline_end = DummyOperator(
        task_id="pipeline_end",
        trigger_rule="none_failed_min_one_success",
    )

    # ── DAG Wiring ─────────────────────────────────────────────────
    pipeline_start >> check_sources >> dq_group >> dq_branch
    dq_branch >> [etl_group, dq_failure]
    etl_group >> [ml_group, nlp_group] >> refresh_dashboards >> pipeline_success >> pipeline_end
    dq_failure >> pipeline_end
