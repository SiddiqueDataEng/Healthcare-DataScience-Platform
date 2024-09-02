# Healthcare Data Platform
## Predictive Patient Care, Clinical Analytics & Hospital Operations Optimization

An enterprise-scale healthcare data platform covering the full data lifecycle:
Data Ingestion → ETL/ELT → Data Warehouse → Analytics → ML/AI → BI Dashboards

---

## Project Structure

```
healthcare_DataScience_Project/
├── data_generation/          # Synthetic data generators for all 20 tables
├── sql/
│   ├── ddl/                  # Table creation scripts
│   ├── views/                # Analytical views
│   └── procedures/           # Stored procedures & functions
├── etl/
│   ├── batch/                # Batch ETL (PySpark)
│   ├── cdc/                  # Change Data Capture
│   └── streaming/            # Real-time streaming (Kafka + Spark)
├── data_quality/             # Great Expectations checks
├── data_catalog/             # Metadata & data catalog
├── analytics/                # SQL analytics (20 projects)
├── ml_models/                # Machine learning models
│   ├── readmission/
│   ├── los_prediction/
│   ├── icu_mortality/
│   ├── disease_risk/
│   ├── fraud_detection/
│   └── patient_churn/
├── nlp/                      # NLP pipelines
│   ├── note_summarization/
│   ├── icd_prediction/
│   ├── entity_recognition/
│   └── risk_extraction/
├── dashboards/               # Dashboard specs and KPI definitions
├── governance/               # HIPAA/GDPR compliance
├── architecture/             # Architecture diagrams and docs
└── config/                   # Configuration files
```

---

## Datasets

| Dataset              | Records         |
|----------------------|-----------------|
| Hospitals            | 50              |
| Patients             | 1,000,000       |
| Doctors              | 10,000          |
| Departments          | 500             |
| Appointments         | 10,000,000      |
| Admissions           | 2,000,000       |
| Diagnoses            | 15,000,000      |
| Procedures           | 8,000,000       |
| Prescriptions        | 20,000,000      |
| Lab Results          | 50,000,000      |
| Medical Imaging      | 3,000,000       |
| Clinical Notes       | 10,000,000      |
| ICU Vitals           | 2,000,000,000   |
| Wearable Data        | 500,000,000     |
| Emergency Visits     | 5,000,000       |
| Insurance Claims     | 5,000,000       |
| Billing              | 15,000,000      |
| Patient Satisfaction | 2,000,000       |
| Staff Scheduling     | 500,000         |
| Bed Management       | 10,000,000      |

---

## Technology Stack

| Layer            | Technology                                    |
|------------------|-----------------------------------------------|
| Data Generation  | Python (Faker, NumPy, Pandas)                 |
| Storage          | PostgreSQL / Snowflake / Delta Lake           |
| Batch ETL        | Apache Spark (PySpark)                        |
| Streaming        | Apache Kafka + Spark Structured Streaming     |
| Orchestration    | Apache Airflow                                |
| Data Quality     | Great Expectations                            |
| ML/AI            | scikit-learn, XGBoost, PyTorch, HuggingFace   |
| NLP              | spaCy, HuggingFace Transformers, medspaCy     |
| BI Dashboards    | Power BI, Tableau, Apache Superset            |
| Infrastructure   | Docker, Kubernetes, Terraform                 |

---

## Quick Start

```bash
pip install -r requirements.txt
python data_generation/generate_all.py --scale small
python etl/batch/load_to_postgres.py
python data_quality/run_checks.py
python analytics/run_analytics.py
python ml_models/readmission/train.py
```
