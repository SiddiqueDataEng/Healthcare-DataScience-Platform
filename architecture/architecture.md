# Healthcare Data Platform — Architecture

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        HEALTHCARE DATA PLATFORM                                  │
│                  Predictive Patient Care & Clinical Analytics                    │
└─────────────────────────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 1: DATA SOURCES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   EMR    │  │Wearables │  │   ICU    │  │Insurance │  │  PACS    │  │  Lab     │
│ (Epic/   │  │(Apple,   │  │Monitors  │  │  Claims  │  │(DICOM    │  │ Systems  │
│ Cerner)  │  │ Fitbit)  │  │          │  │  APIs    │  │ Images)  │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │              │              │              │              │              │
     └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
                                        │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 2: INGESTION                      │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                               ┌─────────┴────────┐
                      ┌────────┤  INGESTION LAYER  ├────────┐
                      │        └──────────────────┘         │
               ┌──────┴──────┐                      ┌───────┴──────┐
               │  Batch ETL  │                      │  Streaming   │
               │  (PySpark)  │                      │ (Kafka+Spark)│
               │  Airflow    │                      │  ICU: 5-sec  │
               │  Schedules  │                      │  Wearable: RT│
               └──────┬──────┘                      └───────┬──────┘
                      │                                      │
━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━
LAYER 3: DATA LAKE    │                                      │
━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━
                      │                                      │
        ┌─────────────┴──────────────────────────────────────┴──────────┐
        │                   DATA LAKEHOUSE (Delta Lake)                  │
        │                                                                 │
        │  ┌──────────┐    ┌──────────────┐    ┌──────────────────────┐ │
        │  │  Bronze  │ →  │    Silver    │ →  │        Gold          │ │
        │  │  (Raw)   │    │ (Processed)  │    │  (Business-Ready)    │ │
        │  │          │    │              │    │                      │ │
        │  │ Parquet  │    │ Validated +  │    │ Star Schema / DW     │ │
        │  │ Files    │    │ Cleaned      │    │ Aggregations         │ │
        │  │ S3/ADLS  │    │ Delta Format │    │ Fact + Dim Tables    │ │
        │  └──────────┘    └──────────────┘    └──────────────────────┘ │
        └─────────────────────────────────────────────────────────────────┘
                                        │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 4: DATA WAREHOUSE                 │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                      ┌─────────────────┴────────────────────┐
                      │                                       │
               ┌──────┴───────┐                    ┌─────────┴────┐
               │  PostgreSQL  │                    │  Snowflake   │
               │  (On-prem /  │                    │  (Cloud DW / │
               │   OLTP)      │                    │  Analytics)  │
               └──────────────┘                    └──────────────┘
                      │
        ┌─────────────┴──────────────────────────────────────────────────┐
        │                  STAR SCHEMA (Data Warehouse)                   │
        │                                                                  │
        │  FACT TABLES:         DIMENSION TABLES:                         │
        │  • fact_admissions    • dim_patients    • dim_date              │
        │  • fact_lab_results   • dim_doctors     • dim_hospital          │
        │  • fact_claims        • dim_diagnoses   • dim_department        │
        │  • fact_billing       • dim_procedures  • dim_insurance         │
        └──────────────────────────────────────────────────────────────────┘
                                        │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 5: ANALYTICS & AI                 │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                      ┌─────────────────┴────────────────────┐
         ┌────────────┤        ANALYTICS PLATFORM            ├────────────┐
         │            └──────────────────────────────────────┘            │
  ┌──────┴──────┐  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐
  │    SQL      │  │  ML Models   │  │  NLP Pipeline │  │   Streaming   │
  │  Analytics  │  │              │  │               │  │   Analytics   │
  │             │  │ • Readmit    │  │ • Clinical NER│  │               │
  │ • 20 Query  │  │ • LOS Pred   │  │ • ICD Predict │  │ • ICU Alerts  │
  │   Projects  │  │ • ICU Mort   │  │ • Note Summary│  │ • Real-time   │
  │ • Ad-hoc    │  │ • Fraud Det  │  │ • Risk Extract│  │   Vitals      │
  │ • Reports   │  │ • Churn      │  │               │  │               │
  └──────┬──────┘  └──────┬───────┘  └───────┬───────┘  └───────┬───────┘
         │                │                  │                   │
━━━━━━━━━┿━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━
LAYER 6: PRESENTATION    │                  │                   │
━━━━━━━━━┿━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━
         └────────────────┴──────────────────┴───────────────────┘
                                        │
         ┌──────────────┐  ┌────────────┴──────┐  ┌──────────────────┐
         │   Power BI   │  │     Tableau        │  │ Apache Superset  │
         │  Executive   │  │  Clinical Quality  │  │  Operations      │
         │  Dashboards  │  │  Dashboards        │  │  Dashboards      │
         └──────────────┘  └───────────────────┘  └──────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CROSS-CUTTING: GOVERNANCE & SECURITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────────┐
│  HIPAA/GDPR COMPLIANCE                                                      │
│                                                                             │
│  • PHI Encryption (AES-256 at rest, TLS 1.3 in transit)                   │
│  • Role-Based Access Control (RBAC) — 7 roles defined                      │
│  • Audit Logging — all PHI access logged with 7-year retention             │
│  • Data Anonymization — HIPAA Safe Harbor de-identification                 │
│  • GDPR Right to Erasure — automated PHI zeroing workflow                  │
│  • Data Lineage — column-level lineage tracking                             │
│  • Data Catalog — Apache Atlas / DataHub integration                        │
│  • Data Quality — Great Expectations checks on all tables                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Source Systems | Epic/Cerner (simulated) | EMR data |
| Data Generation | Python (Faker, NumPy) | Synthetic data |
| Batch Ingestion | PySpark 3.5 | Large-scale ETL |
| Stream Ingestion | Apache Kafka 3.6 | Real-time ICU/wearable |
| Stream Processing | Spark Structured Streaming | Stateful aggregations |
| Data Lake | Delta Lake on S3 | Bronze/Silver/Gold |
| Data Warehouse | PostgreSQL / Snowflake | Analytical queries |
| Orchestration | Apache Airflow 2.8 | Pipeline scheduling |
| Data Quality | Great Expectations | Validation framework |
| Data Catalog | Apache Atlas | Metadata management |
| ML Framework | XGBoost, LightGBM, PyTorch | Predictive models |
| NLP | spaCy, medspaCy, HuggingFace | Clinical text processing |
| Explainability | SHAP | ML model interpretation |
| BI - Enterprise | Power BI | Executive dashboards |
| BI - Clinical | Tableau | Clinical analytics |
| BI - Open Source | Apache Superset | Operations dashboards |
| Container | Docker + Kubernetes | Deployment |
| IaC | Terraform | Infrastructure |
| Compliance | Custom framework | HIPAA/GDPR |

---

## Data Volume at Scale

| Table | Records | Storage (Parquet) | Partitioning |
|-------|---------|-------------------|--------------|
| ICU Vitals | 2,000,000,000 | ~800 GB | By month |
| Wearable Data | 500,000,000 | ~200 GB | By quarter |
| Lab Results | 50,000,000 | ~5 GB | By year |
| Prescriptions | 20,000,000 | ~2 GB | By year |
| Clinical Notes | 10,000,000 | ~15 GB (text) | By year |
| Diagnoses | 15,000,000 | ~1.5 GB | By year |
| Appointments | 10,000,000 | ~800 MB | By year |
| Billing | 15,000,000 | ~1.2 GB | By year |
| **TOTAL** | **~2.6 Billion** | **~1.2 TB** | |

---

## Latency SLAs

| Pipeline | Latency | SLA |
|----------|---------|-----|
| ICU Vitals Alert | 5 seconds | < 10 sec |
| Streaming Aggregations | 1 minute | < 5 min |
| Batch ETL (daily) | 4 hours | < 6 hours |
| ML Scoring | 30 minutes | < 1 hour |
| Dashboard Refresh | 30 minutes | < 1 hour |
| DW Query (analytical) | < 30 seconds | < 60 sec |
