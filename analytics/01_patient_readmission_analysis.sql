-- ============================================================
-- Analytics Project 1: Patient Readmission Analysis
-- Business Question: Which patients are most likely to be
--   readmitted within 30 days? What factors drive readmissions?
-- ============================================================

-- 1. Overall 30-day readmission rate by hospital
SELECT
    h.hospital_name,
    h.hospital_type,
    COUNT(a.admission_id)                                           AS total_admissions,
    SUM(a.readmission_within_30d::int)                              AS readmissions_30d,
    ROUND(AVG(a.readmission_within_30d::int) * 100, 2)             AS readmission_rate_30d_pct,
    ROUND(AVG(a.readmission_within_90d::int) * 100, 2)             AS readmission_rate_90d_pct,
    -- CMS benchmark is 15.6% for all-cause 30-day readmissions
    CASE
        WHEN AVG(a.readmission_within_30d::int) * 100 > 15.6 THEN 'Above Benchmark'
        WHEN AVG(a.readmission_within_30d::int) * 100 < 12.0 THEN 'Below Benchmark'
        ELSE 'At Benchmark'
    END AS benchmark_status
FROM admissions a
JOIN hospitals h ON a.hospital_id = h.hospital_id
WHERE a.discharge_status != 'Still Admitted'
  AND a.admit_date >= CURRENT_DATE - INTERVAL '2 years'
GROUP BY h.hospital_name, h.hospital_type
ORDER BY readmission_rate_30d_pct DESC;


-- 2. Readmission rate by primary diagnosis (top 20 DRGs)
SELECT
    a.drg_code,
    a.drg_description,
    COUNT(*)                                                        AS total_admissions,
    SUM(a.readmission_within_30d::int)                             AS readmissions_30d,
    ROUND(AVG(a.readmission_within_30d::int) * 100, 2)            AS readmission_rate_pct,
    ROUND(AVG(a.length_of_stay), 1)                               AS avg_los,
    ROUND(AVG(a.actual_cost), 2)                                   AS avg_cost
FROM admissions a
WHERE a.discharge_status NOT IN ('Expired','Still Admitted')
GROUP BY a.drg_code, a.drg_description
HAVING COUNT(*) >= 100
ORDER BY readmission_rate_pct DESC
LIMIT 20;


-- 3. Readmission by patient demographics
SELECT
    p.age_band,
    p.gender,
    p.insurance_plan_type,
    COUNT(a.admission_id)                                          AS total_admissions,
    SUM(a.readmission_within_30d::int)                            AS readmissions_30d,
    ROUND(AVG(a.readmission_within_30d::int) * 100, 2)           AS readmission_rate_pct
FROM admissions a
JOIN (
    SELECT
        patient_id,
        gender,
        insurance_plan_type,
        CASE
            WHEN DATE_PART('year', AGE(CURRENT_DATE, dob::date)) < 18  THEN '0-17'
            WHEN DATE_PART('year', AGE(CURRENT_DATE, dob::date)) < 35  THEN '18-34'
            WHEN DATE_PART('year', AGE(CURRENT_DATE, dob::date)) < 50  THEN '35-49'
            WHEN DATE_PART('year', AGE(CURRENT_DATE, dob::date)) < 65  THEN '50-64'
            WHEN DATE_PART('year', AGE(CURRENT_DATE, dob::date)) < 80  THEN '65-79'
            ELSE '80+'
        END AS age_band
    FROM patients
) p ON a.patient_id = p.patient_id
GROUP BY p.age_band, p.gender, p.insurance_plan_type
ORDER BY readmission_rate_pct DESC;


-- 4. Time to readmission distribution
SELECT
    days_to_readmit_bucket,
    COUNT(*) AS readmissions,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct_of_total
FROM (
    SELECT
        CASE
            WHEN EXTRACT(DAY FROM (a2.admit_date - a1.discharge_date)) <= 3  THEN '0-3 days'
            WHEN EXTRACT(DAY FROM (a2.admit_date - a1.discharge_date)) <= 7  THEN '4-7 days'
            WHEN EXTRACT(DAY FROM (a2.admit_date - a1.discharge_date)) <= 14 THEN '8-14 days'
            WHEN EXTRACT(DAY FROM (a2.admit_date - a1.discharge_date)) <= 21 THEN '15-21 days'
            ELSE '22-30 days'
        END AS days_to_readmit_bucket
    FROM admissions a1
    JOIN admissions a2 ON a1.patient_id = a2.patient_id
        AND a2.admit_date > a1.discharge_date
        AND a2.admit_date <= a1.discharge_date + INTERVAL '30 days'
    WHERE a1.discharge_status NOT IN ('Expired', 'Still Admitted')
) t
GROUP BY days_to_readmit_bucket
ORDER BY MIN(days_to_readmit_bucket);


-- 5. Readmission risk factors — comorbidity analysis
WITH comorbidities AS (
    SELECT
        a.patient_id,
        a.admission_id,
        a.readmission_within_30d,
        BOOL_OR(d.icd10_code LIKE 'E11%')   AS has_diabetes,
        BOOL_OR(d.icd10_code = 'I10')        AS has_hypertension,
        BOOL_OR(d.icd10_code LIKE 'I50%')   AS has_heart_failure,
        BOOL_OR(d.icd10_code LIKE 'N18%')   AS has_ckd,
        BOOL_OR(d.icd10_code LIKE 'J44%')   AS has_copd,
        COUNT(DISTINCT d.icd10_code)         AS comorbidity_count
    FROM admissions a
    LEFT JOIN diagnoses d ON a.admission_id = d.admission_id
        AND d.diagnosis_type IN ('Secondary', 'Comorbidity')
    GROUP BY a.patient_id, a.admission_id, a.readmission_within_30d
)
SELECT
    CASE
        WHEN comorbidity_count = 0 THEN 'No comorbidities'
        WHEN comorbidity_count BETWEEN 1 AND 2 THEN '1-2 comorbidities'
        WHEN comorbidity_count BETWEEN 3 AND 5 THEN '3-5 comorbidities'
        ELSE '6+ comorbidities'
    END AS comorbidity_bucket,
    COUNT(*)                                                    AS total_admissions,
    SUM(readmission_within_30d::int)                           AS readmissions,
    ROUND(AVG(readmission_within_30d::int) * 100, 2)          AS readmission_rate_pct,
    SUM(has_diabetes::int)   AS n_diabetes,
    SUM(has_hypertension::int) AS n_hypertension,
    SUM(has_heart_failure::int) AS n_heart_failure,
    SUM(has_ckd::int)        AS n_ckd
FROM comorbidities
GROUP BY comorbidity_bucket
ORDER BY readmission_rate_pct DESC;


-- 6. Monthly readmission trend
SELECT
    DATE_TRUNC('month', admit_date)                              AS admission_month,
    COUNT(*)                                                      AS total_admissions,
    SUM(readmission_within_30d::int)                             AS readmissions,
    ROUND(AVG(readmission_within_30d::int) * 100, 2)            AS readmission_rate_pct,
    ROUND(AVG(readmission_within_30d::int) * 100
        - LAG(AVG(readmission_within_30d::int) * 100) OVER (ORDER BY DATE_TRUNC('month', admit_date)), 2
    ) AS month_over_month_change
FROM admissions
WHERE admit_date >= CURRENT_DATE - INTERVAL '2 years'
GROUP BY DATE_TRUNC('month', admit_date)
ORDER BY admission_month;
