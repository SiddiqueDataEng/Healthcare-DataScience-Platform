@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  Healthcare DataScience Platform
REM  GitHub Upload + Activity Manager
REM
REM  Features:
REM   - Stage, commit, force-push to GitHub
REM   - Interactive menu: Issues / Pull Requests / Milestones
REM                       Labels / Releases / All / Skip
REM   - Pre-populated contextual content from the project
REM ============================================================

call "%~dp0master-config.bat"

set "REPO_NAME=Healthcare-DataScience-Platform"
set "REPO_FULL=%MASTER_GITHUB_USER%/%REPO_NAME%"
set "API=https://api.github.com"
set "AUTH=-H "Authorization: token %MASTER_GITHUB_TOKEN%""
set "HDRS=-H "Accept: application/vnd.github+json" -H "Content-Type: application/json""

git config --global user.name  "%MASTER_GITHUB_USER%"
git config --global user.email "%MASTER_EMAIL%"
git config user.name  "%MASTER_GITHUB_USER%"
git config user.email "%MASTER_EMAIL%"

cls
echo.
echo  ============================================================
echo   Healthcare DataScience Platform
echo   GitHub Upload + Activity Manager
echo   Repo : https://github.com/%REPO_FULL%
echo  ============================================================
echo.

REM ============================================================
REM  STEP 1 -- Stage, commit, push
REM ============================================================
echo [1/2] Staging all changes...
git add -A

REM Count staged files
git status --short > _gitstatus.tmp 2>nul
set "FILE_COUNT=0"
for /f %%C in ('type _gitstatus.tmp ^| find /c /v ""') do set FILE_COUNT=%%C
del _gitstatus.tmp 2>nul

if "%FILE_COUNT%"=="0" (
    echo   Nothing new to commit -- working tree clean.
) else (
    echo   Staged %FILE_COUNT% file(s). Committing...
    git -c "user.name=%MASTER_GITHUB_USER%" -c "user.email=%MASTER_EMAIL%" ^
        commit -m "chore: update platform files -- %FILE_COUNT% changed" 2>nul
    echo   [OK] Committed %FILE_COUNT% file(s).
)

REM Reset remote with token-authenticated URL
git remote remove origin 2>nul
git remote add origin https://%MASTER_GITHUB_TOKEN%@github.com/%REPO_FULL%.git

echo.
echo [2/2] Pushing to GitHub...
git push -u origin main --force
if %ERRORLEVEL% NEQ 0 (
    echo   ERROR: Push failed. Verify token has repo scope.
    goto :eof
)
echo   [OK] Push complete.

REM Update repo description and topics
curl -s -o NUL ^
    -X PATCH %AUTH% %HDRS% ^
    -d "{\"description\":\"End-to-end Healthcare Data Science Platform -- EHR data generation, ETL pipelines, ML models, real-time streaming, BI dashboards\",\"has_issues\":true,\"has_projects\":true,\"has_wiki\":true}" ^
    %API%/repos/%REPO_FULL% 2>nul
curl -s -o NUL ^
    -X PUT %AUTH% %HDRS% ^
    -d "{\"names\":[\"healthcare\",\"data-science\",\"machine-learning\",\"python\",\"sql\",\"apache-spark\",\"kafka\",\"etl\",\"hipaa\",\"analytics\"]}" ^
    %API%/repos/%REPO_FULL%/topics 2>nul

REM ============================================================
REM  STEP 2 -- Interactive GitHub Activity Menu
REM ============================================================
echo.
echo  ============================================================
echo   GitHub Activity Menu
echo   What would you like to create on the repo?
echo  ============================================================
echo.
echo   1  Issues only
echo   2  Pull Request only
echo   3  Milestones only
echo   4  Labels only
echo   5  Release only
echo   6  ALL of the above (full setup)
echo   7  Pick specific ones (multi-select)
echo   0  Skip -- done
echo.
set /p MENU_CHOICE="  Enter choice [0-7]: "

if "%MENU_CHOICE%"=="0" goto :final_done
if "%MENU_CHOICE%"=="1" goto :do_issues
if "%MENU_CHOICE%"=="2" goto :do_pr
if "%MENU_CHOICE%"=="3" goto :do_milestones
if "%MENU_CHOICE%"=="4" goto :do_labels
if "%MENU_CHOICE%"=="5" goto :do_release
if "%MENU_CHOICE%"=="6" goto :do_all
if "%MENU_CHOICE%"=="7" goto :multi_select
echo   Invalid choice. Skipping GitHub activity.
goto :final_done

REM ============================================================
:do_all
REM ============================================================
call :create_labels
call :create_milestones
call :create_issues
call :create_pr
call :create_release
goto :final_done

REM ============================================================
:multi_select
REM ============================================================
echo.
echo   Tick each item to create (y/n):
set /p DO_LABELS="  Labels?       [y/n]: "
set /p DO_MILESTONES="  Milestones?   [y/n]: "
set /p DO_ISSUES="  Issues?       [y/n]: "
set /p DO_PR="  Pull Request? [y/n]: "
set /p DO_RELEASE="  Release?      [y/n]: "

if /i "%DO_LABELS%"=="y"      call :create_labels
if /i "%DO_MILESTONES%"=="y"  call :create_milestones
if /i "%DO_ISSUES%"=="y"      call :create_issues
if /i "%DO_PR%"=="y"          call :create_pr
if /i "%DO_RELEASE%"=="y"     call :create_release
goto :final_done

:do_issues
call :create_issues
goto :final_done

:do_pr
call :create_pr
goto :final_done

:do_milestones
call :create_milestones
goto :final_done

:do_labels
call :create_labels
goto :final_done

:do_release
call :create_release
goto :final_done

REM ============================================================
REM  SUB: CREATE LABELS
REM ============================================================
:create_labels
echo.
echo [Labels] Creating project labels...

call :mklabel "data-engineering"  "0075ca" "ETL pipelines, ingestion, Spark, Kafka"
call :mklabel "machine-learning"  "d876e3" "ML models, training, evaluation, MLflow"
call :mklabel "analytics"         "bfd4f2" "SQL analytics, BI dashboards, KPIs"
call :mklabel "data-quality"      "e4e669" "Great Expectations, DQ checks, validation"
call :mklabel "streaming"         "006b75" "Kafka, real-time pipelines, ICU vitals"
call :mklabel "HIPAA"             "d93f0b" "HIPAA compliance and PHI controls"
call :mklabel "infrastructure"    "cfd3d7" "Docker, Airflow, config, environment"
call :mklabel "eda"               "fef2c0" "Exploratory data analysis, EDA scripts"
call :mklabel "sql"               "1d76db" "SQL queries, warehouse analytics"
call :mklabel "python"            "0e8a16" "Python scripts and packages"
call :mklabel "visualization"     "fbca04" "Charts, dashboards, plots"
call :mklabel "case-study"        "5319e7" "End-to-end case studies"
call :mklabel "bug"               "d73a4a" "Something is not working"
call :mklabel "enhancement"       "a2eeef" "New feature or improvement"
call :mklabel "documentation"     "c5def5" "README, guides, architecture docs"
call :mklabel "good first issue"  "7057ff" "Good for newcomers"
call :mklabel "help wanted"       "008672" "Extra attention needed"

echo   [OK] Labels done.
goto :eof

:mklabel
curl -s -o NUL ^
    -X POST %AUTH% %HDRS% ^
    -d "{\"name\":\"%~1\",\"color\":\"%~2\",\"description\":\"%~3\"}" ^
    %API%/repos/%REPO_FULL%/labels 2>nul
echo   + label: %~1
goto :eof

REM ============================================================
REM  SUB: CREATE MILESTONES
REM ============================================================
:create_milestones
echo.
echo [Milestones] Creating project milestones...

call :mkmilestone "v1.0 - Data Foundation"       "Synthetic EHR data generation, schema design, raw data lake (Parquet)"                          "2025-10-31"
call :mkmilestone "v1.1 - ETL and Warehouse"     "Bronze/Silver/Gold ETL, PySpark pipelines, PostgreSQL data warehouse, data quality checks"      "2025-12-31"
call :mkmilestone "v1.2 - Analytics and SQL"     "SQL analytics queries, patient readmission, disease trends, revenue analytics, bed occupancy"    "2026-02-28"
call :mkmilestone "v1.3 - ML Models"             "Readmission prediction, LOS regression, disease clustering, no-show classification, NLP"        "2026-04-30"
call :mkmilestone "v1.4 - Streaming and Ops"     "Kafka real-time streaming, ICU vitals, wearable data, operational analytics"                    "2026-06-30"

echo   [OK] Milestones done.
goto :eof

:mkmilestone
curl -s -o NUL ^
    -X POST %AUTH% %HDRS% ^
    -d "{\"title\":\"%~1\",\"description\":\"%~2\",\"due_on\":\"%~3T00:00:00Z\",\"state\":\"open\"}" ^
    %API%/repos/%REPO_FULL%/milestones 2>nul
echo   + milestone: %~1
goto :eof

REM ============================================================
REM  SUB: CREATE ISSUES
REM ============================================================
:create_issues
echo.
echo [Issues] Creating contextual project issues...

echo.
echo   Pre-defined issues for Healthcare DataScience Platform:
echo   1  All pre-defined issues
echo   2  Choose which categories
echo   0  Skip issues
echo.
set /p ISS_CHOICE="  Choice [0-2]: "

if "%ISS_CHOICE%"=="0" goto :issues_done
if "%ISS_CHOICE%"=="2" goto :issues_by_category

call :issues_data_quality
call :issues_ml
call :issues_analytics
call :issues_streaming
call :issues_docs
goto :issues_done

:issues_by_category
set /p DO_DQ="   Data Quality issues?   [y/n]: "
set /p DO_ML="   ML issues?             [y/n]: "
set /p DO_AN="   Analytics issues?      [y/n]: "
set /p DO_ST="   Streaming issues?      [y/n]: "
set /p DO_DO="   Documentation issues?  [y/n]: "

if /i "%DO_DQ%"=="y" call :issues_data_quality
if /i "%DO_ML%"=="y" call :issues_ml
if /i "%DO_AN%"=="y" call :issues_analytics
if /i "%DO_ST%"=="y" call :issues_streaming
if /i "%DO_DO%"=="y" call :issues_docs
goto :issues_done

:issues_data_quality
call :mkissue "Add Great Expectations suite for admissions table" "The `admissions_batch_0000.parquet` has no automated DQ checks. Add a GE expectation suite covering: non-null patient_id/admission_date, LOS > 0, discharge_date >= admission_date.\n\n**Acceptance:** Suite runs in CI; fails build on > 1%% violation rate." "data-quality,enhancement"
call :mkissue "Handle missing lab results in EDA pipeline" "06_eda_data_preparation.py shows missing values in lab_results batches (see outputs/ch03_eda/missing_lab_results.png). Add imputation strategy (median per test type) with configurable threshold.\n\n**Acceptance:** Imputed dataset written to processed/ layer; missing rate < 0.1%% post-impute." "data-quality,eda,bug"
call :mkissue "Referential integrity check: diagnoses -> admissions" "There is no FK constraint enforcing that every diagnosis record links to a valid admission_id. Add a PySpark validation step in the ETL pipeline.\n\n**Acceptance:** Orphan diagnosis records flagged and quarantined; daily report in data quality dashboard." "data-quality,data-engineering,enhancement"
goto :eof

:issues_ml
call :mkissue "Implement SHAP explainability for readmission model" "case_study_01_readmission.py trains a classifier but does not include feature importance or SHAP explanation. Add shap.TreeExplainer for the top 10 features.\n\n**Acceptance:** SHAP summary plot saved to outputs/01_readmission/; SHAP values in model artifact." "machine-learning,case-study,enhancement"
call :mkissue "Add MLflow experiment tracking to all ML scripts" "ML training runs are not tracked. Integrate MLflow autolog() in each model training script; log params, metrics, and model artifact.\n\n**Acceptance:** All runs visible in MLflow UI; model registry entry created on promotion." "machine-learning,infrastructure,enhancement"
call :mkissue "Disease clustering: determine optimal K via elbow and silhouette" "analytics/outputs/ch03_eda/disease_clustering.png uses a fixed K. Add automated elbow method and silhouette score sweep from K=2 to K=15, persist results.\n\n**Acceptance:** Optimal K selected programmatically; cluster_profiles.csv updated." "machine-learning,eda,enhancement"
call :mkissue "NLP case study: add ICD-10 auto-coding accuracy metric" "case_study_02_nlp_ops.py produces auto_coding_results.csv but does not compute precision/recall/F1 against ground-truth ICD codes.\n\n**Acceptance:** Micro and macro F1 scores logged; confusion matrix saved to outputs/02_nlp_ops/." "machine-learning,case-study,enhancement"
goto :eof

:issues_analytics
call :mkissue "Parameterise date range in all SQL analytics scripts" "Analytics SQL files (01-05) use hardcoded date literals. Refactor to use :start_date and :end_date bind parameters compatible with both PostgreSQL and Snowflake.\n\n**Acceptance:** Scripts accept parameters; README documents usage examples." "analytics,sql,enhancement,good first issue"
call :mkissue "Add hospital revenue trend chart to executive KPIs dashboard" "dashboards/executive_kpis.md references revenue metrics but 03_hospital_revenue_analytics.sql output is not visualised. Add a monthly revenue trend line chart.\n\n**Acceptance:** Chart saved to outputs/; embedded in executive_kpis.md." "analytics,visualization,documentation"
call :mkissue "Bed occupancy alert: flag wards above 90%% threshold" "05_bed_occupancy_emergency_analytics.sql computes occupancy but does not flag critical wards. Add a CASE expression and a summary report table.\n\n**Acceptance:** Flagged wards exported to CSV; alert threshold configurable via config.yaml." "analytics,sql,enhancement"
goto :eof

:issues_streaming
call :mkissue "Implement Kafka consumer for real-time ICU vitals" "config.yaml defines a healthcare.icu.vitals topic but no consumer exists. Implement a Python Kafka consumer that writes vitals to the Bronze layer every 30s.\n\n**Acceptance:** Consumer runs as Docker service; Bronze layer updated within 60s of event." "streaming,data-engineering,enhancement"
call :mkissue "Add wearable data anomaly detection in streaming pipeline" "Wearable events (healthcare.wearable.events) have no anomaly detection. Integrate Z-score threshold (3σ) per patient per metric; route anomalies to a separate Kafka topic.\n\n**Acceptance:** Anomaly rate < 0.5%% on synthetic data; anomaly events logged to DQ report." "streaming,machine-learning,enhancement"
goto :eof

:issues_docs
call :mkissue "Add architecture diagram to architecture/architecture.md" "architecture/architecture.md exists but lacks a visual diagram. Add a Mermaid flowchart showing data flow: EHR sources -> Bronze -> Silver -> Gold -> ML / Analytics.\n\n**Acceptance:** Diagram renders in GitHub; all major components labelled." "documentation,good first issue"
call :mkissue "Document how to run each analytics SQL script" "The SQL files in analytics/ have no usage instructions. Add a USAGE section to each file header with connection examples for PostgreSQL and Snowflake.\n\n**Acceptance:** Each file has a USAGE block; main README links to analytics/ README." "documentation,sql,good first issue"
call :mkissue "Add setup instructions for local dev environment" "There is no step-by-step guide for spinning up the local stack (PostgreSQL, Kafka, Spark, MLflow, Airflow). Add a SETUP.md with Docker Compose instructions.\n\n**Acceptance:** `docker compose up` brings up all services; README links to SETUP.md." "documentation,infrastructure,help wanted"
goto :eof

:issues_done
echo   [OK] Issues done.
goto :eof

:mkissue
curl -s -o NUL ^
    -X POST %AUTH% %HDRS% ^
    -d "{\"title\":\"%~1\",\"body\":\"%~2\",\"labels\":[\"%~3\"]}" ^
    %API%/repos/%REPO_FULL%/issues 2>nul
echo   + issue: %~1
goto :eof

REM ============================================================
REM  SUB: CREATE PULL REQUEST
REM ============================================================
:create_pr
echo.
echo [Pull Request] Creating a contextual PR...
echo.
echo   Pre-defined PR types:
echo   1  Feature PR -- Complete platform implementation
echo   2  Analytics PR -- SQL analytics and EDA scripts
echo   3  ML PR -- Machine learning case studies
echo   4  Custom PR -- Enter title and body manually
echo   0  Skip
echo.
set /p PR_CHOICE="  Choice [0-4]: "

if "%PR_CHOICE%"=="0" goto :pr_done
if "%PR_CHOICE%"=="1" goto :pr_feature
if "%PR_CHOICE%"=="2" goto :pr_analytics
if "%PR_CHOICE%"=="3" goto :pr_ml
if "%PR_CHOICE%"=="4" goto :pr_custom
goto :pr_done

:pr_feature
git checkout -b feature/complete-healthcare-platform 2>nul
git push origin feature/complete-healthcare-platform --force 2>nul
git checkout main 2>nul
curl -s -o NUL ^
    -X POST %AUTH% %HDRS% ^
    -d "{\"title\":\"feat: Complete Healthcare DataScience Platform -- ETL, ML, Analytics, Streaming\",\"body\":\"## Summary\n\nThis PR delivers the complete Healthcare DataScience Platform covering all layers from raw EHR data generation through to ML models, SQL analytics, and operational dashboards.\n\n## What was implemented\n\n### Data Layer\n- Synthetic EHR data generation (patients, admissions, diagnoses, lab results, prescriptions, clinical notes, appointments, billing, bed utilisation)\n- Parquet-based raw data lake with batch partitioning\n- Bronze / Silver / Gold ETL pipelines via PySpark\n\n### Analytics (SQL)\n- `01` Patient readmission analysis\n- `02` Disease trend analysis\n- `03` Hospital revenue analytics\n- `04` Appointment no-show analysis\n- `05` Bed occupancy and emergency analytics\n\n### EDA and ML\n- `06` EDA and data preparation -- distributions, correlation matrices, outlier reports, patient clustering (KMeans)\n- `07` Operations analytics -- admission forecasting, bed management, ED throughput, staffing, revenue cycle\n- Case Study 01: Readmission prediction model\n- Case Study 02: NLP clinical notes auto-coding\n\n### Dashboards\n- Executive KPI dashboard (Markdown + chart outputs)\n\n### Architecture\n- Architecture decision document\n- Config-driven environment setup (config.yaml + .env.example)\n\n## Test plan\n- [ ] Run data generation scripts\n- [ ] Execute ETL pipeline end-to-end\n- [ ] Run all SQL analytics scripts against PostgreSQL\n- [ ] Execute EDA and ML notebooks/scripts\n- [ ] Verify outputs exist in analytics/outputs/\n\",\"head\":\"feature/complete-healthcare-platform\",\"base\":\"main\",\"draft\":false}" ^
    %API%/repos/%REPO_FULL%/pulls 2>nul
echo   [OK] Feature PR created.
goto :pr_done

:pr_analytics
git checkout -b feature/analytics-sql-and-eda 2>nul
git push origin feature/analytics-sql-and-eda --force 2>nul
git checkout main 2>nul
curl -s -o NUL ^
    -X POST %AUTH% %HDRS% ^
    -d "{\"title\":\"feat: SQL analytics suite and EDA data preparation\",\"body\":\"## Summary\n\nAdds five SQL analytics scripts and two Python EDA/operations analytics scripts with full output artefacts.\n\n## Changes\n\n### SQL Analytics (analytics/01-05)\n- **01** Patient readmission rate by department and diagnosis\n- **02** Disease prevalence trends over time\n- **03** Hospital revenue by payer, department, and procedure\n- **04** Appointment no-show drivers and patient segmentation\n- **05** Bed occupancy rates and emergency department throughput\n\n### Python EDA (analytics/06-07)\n- **06** `eda_data_preparation.py` -- missing value analysis, distributions, correlation matrices, KMeans patient clustering, outlier detection\n- **07** `operations_analytics.py` -- admission forecasting (Prophet), bed management optimisation, ED throughput, staffing utilisation, revenue cycle analysis\n\n### Outputs\n- `ch03_eda/` -- 9 artefacts (PNGs + CSVs)\n- `ch08_operations/` -- 8 artefacts (PNGs + CSVs)\n\n## Test plan\n- [ ] SQL scripts run against healthcare_dw schema\n- [ ] EDA outputs match expected artefact list\n- [ ] Clustering produces stable K per elbow method\n\",\"head\":\"feature/analytics-sql-and-eda\",\"base\":\"main\",\"draft\":false}" ^
    %API%/repos/%REPO_FULL%/pulls 2>nul
echo   [OK] Analytics PR created.
goto :pr_done

:pr_ml
git checkout -b feature/ml-case-studies 2>nul
git push origin feature/ml-case-studies --force 2>nul
git checkout main 2>nul
curl -s -o NUL ^
    -X POST %AUTH% %HDRS% ^
    -d "{\"title\":\"feat: ML case studies -- readmission prediction and NLP clinical notes\",\"body\":\"## Summary\n\nAdds two end-to-end ML case studies covering hospital readmission prediction and NLP-based clinical note processing.\n\n## Changes\n\n### Case Study 01: Patient Readmission Prediction\n- Feature engineering from admissions + diagnoses + lab results\n- Binary classification (readmission within 30 days)\n- Model comparison: Logistic Regression, Random Forest, XGBoost\n- Outputs: ROC-AUC curve, feature importance, confusion matrix\n\n### Case Study 02: NLP Clinical Notes Auto-Coding\n- Clinical note preprocessing (tokenisation, stop-word removal)\n- ICD-10 code extraction from unstructured notes\n- NLP pipeline: TF-IDF + classification head\n- Outputs: auto_coding_results.csv, integrated dashboard PNG\n\n## Test plan\n- [ ] Case Study 01 achieves AUC >= 0.75 on held-out test set\n- [ ] Case Study 02 auto-coding results CSV is non-empty\n- [ ] All output artefacts saved to case_studies/outputs/\n\",\"head\":\"feature/ml-case-studies\",\"base\":\"main\",\"draft\":false}" ^
    %API%/repos/%REPO_FULL%/pulls 2>nul
echo   [OK] ML PR created.
goto :pr_done

:pr_custom
echo.
set /p PR_TITLE="  PR Title: "
set /p PR_BRANCH="  Source branch name (will be created): "
set /p PR_BODY="  PR description (single line): "
git checkout -b %PR_BRANCH% 2>nul
git push origin %PR_BRANCH% --force 2>nul
git checkout main 2>nul
curl -s -o NUL ^
    -X POST %AUTH% %HDRS% ^
    -d "{\"title\":\"%PR_TITLE%\",\"body\":\"%PR_BODY%\",\"head\":\"%PR_BRANCH%\",\"base\":\"main\"}" ^
    %API%/repos/%REPO_FULL%/pulls 2>nul
echo   [OK] Custom PR created.
goto :pr_done

:pr_done
echo   [OK] Pull Request section done.
goto :eof

REM ============================================================
REM  SUB: CREATE RELEASE
REM ============================================================
:create_release
echo.
echo [Release] Creating GitHub Release...
echo.
echo   Pre-defined releases:
echo   1  v1.0.0 -- Initial complete platform release
echo   2  Custom -- Enter tag and notes manually
echo   0  Skip
echo.
set /p REL_CHOICE="  Choice [0-2]: "

if "%REL_CHOICE%"=="0" goto :release_done
if "%REL_CHOICE%"=="2" goto :release_custom

curl -s -o NUL ^
    -X POST %AUTH% %HDRS% ^
    -d "{\"tag_name\":\"v1.0.0\",\"target_commitish\":\"main\",\"name\":\"v1.0.0 -- Healthcare DataScience Platform Initial Release\",\"body\":\"## Healthcare DataScience Platform v1.0.0\n\n**End-to-end healthcare data science platform covering synthetic EHR data generation, ETL pipelines, SQL analytics, ML models, and real-time streaming.**\n\n### What is included\n\n| Component | Details |\n|---|---|\n| Data Generation | 10 EHR tables -- patients, admissions, diagnoses, lab results, prescriptions, clinical notes, appointments, billing, bed utilisation, ICU vitals |\n| ETL Pipelines | PySpark Bronze/Silver/Gold layers, chunked Parquet writes, parallel table generation |\n| SQL Analytics | 5 analytics scripts -- readmission, disease trends, revenue, no-show, bed occupancy |\n| EDA + ML | KMeans patient clustering, outlier detection, distributions, correlation matrices |\n| Operations Analytics | Admission forecasting, bed management, ED throughput, staffing utilisation |\n| ML Case Studies | Readmission prediction (XGBoost), NLP clinical notes auto-coding (ICD-10) |\n| Dashboards | Executive KPI dashboard with 8 output charts and CSVs |\n| Data Quality | Unit tests, integration tests, referential integrity checks |\n| Config | config.yaml + .env.example for all services |\n\n### Getting started\n\nSee `config/.env.example` to configure your environment, then run the data generation scripts followed by the ETL pipeline.\n\n### HIPAA Compliance\n- PHI fields listed in config.yaml under `compliance.phi_fields`\n- Encryption key managed via environment variable\n- 7-year data retention setting\n\",\"draft\":false,\"prerelease\":false}" ^
    %API%/repos/%REPO_FULL%/releases 2>nul
echo   [OK] Release v1.0.0 created.
goto :release_done

:release_custom
echo.
set /p REL_TAG="  Tag (e.g. v1.1.0): "
set /p REL_NAME="  Release name: "
set /p REL_NOTES="  Release notes (single line): "
curl -s -o NUL ^
    -X POST %AUTH% %HDRS% ^
    -d "{\"tag_name\":\"%REL_TAG%\",\"target_commitish\":\"main\",\"name\":\"%REL_NAME%\",\"body\":\"%REL_NOTES%\",\"draft\":false,\"prerelease\":false}" ^
    %API%/repos/%REPO_FULL%/releases 2>nul
echo   [OK] Release %REL_TAG% created.
goto :release_done

:release_done
echo   [OK] Release section done.
goto :eof

REM ============================================================
:final_done
REM ============================================================
echo.
echo  ============================================================
echo   ALL DONE
echo.
echo   Repo       : https://github.com/%REPO_FULL%
echo   Issues     : https://github.com/%REPO_FULL%/issues
echo   PRs        : https://github.com/%REPO_FULL%/pulls
echo   Releases   : https://github.com/%REPO_FULL%/releases
echo   Milestones : https://github.com/%REPO_FULL%/milestones
echo  ============================================================
echo.
