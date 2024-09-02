-- ============================================================
-- Analytics Project 2: Disease Trend Analysis
-- Business Question: How are disease prevalence rates changing
--   over time across demographics and geographies?
-- ============================================================

-- 1. Disease prevalence trend by year
SELECT
    EXTRACT(YEAR FROM d.diagnosis_date)                           AS year,
    d.disease_category,
    d.disease_name,
    COUNT(DISTINCT d.patient_id)                                  AS unique_patients,
    COUNT(d.diagnosis_id)                                         AS total_diagnoses,
    ROUND(COUNT(DISTINCT d.patient_id) * 100.0 /
          MAX(pop.total_patients), 2)                             AS prevalence_rate_pct
FROM diagnoses d
CROSS JOIN (SELECT COUNT(DISTINCT patient_id) AS total_patients FROM patients) pop
WHERE d.diagnosis_type = 'Primary'
  AND EXTRACT(YEAR FROM d.diagnosis_date) BETWEEN 2019 AND 2024
GROUP BY EXTRACT(YEAR FROM d.diagnosis_date), d.disease_category, d.disease_name
ORDER BY year, total_diagnoses DESC;


-- 2. Top 10 diseases with fastest growing prevalence (YoY)
WITH yearly_counts AS (
    SELECT
        disease_name,
        EXTRACT(YEAR FROM diagnosis_date) AS yr,
        COUNT(DISTINCT patient_id) AS patient_count
    FROM diagnoses
    WHERE diagnosis_type = 'Primary'
      AND EXTRACT(YEAR FROM diagnosis_date) IN (2022, 2023, 2024)
    GROUP BY disease_name, EXTRACT(YEAR FROM diagnosis_date)
),
yoy AS (
    SELECT
        disease_name,
        MAX(CASE WHEN yr = 2022 THEN patient_count END) AS cnt_2022,
        MAX(CASE WHEN yr = 2023 THEN patient_count END) AS cnt_2023,
        MAX(CASE WHEN yr = 2024 THEN patient_count END) AS cnt_2024
    FROM yearly_counts
    GROUP BY disease_name
)
SELECT
    disease_name,
    cnt_2022,
    cnt_2023,
    cnt_2024,
    ROUND((cnt_2023 - cnt_2022) * 100.0 / NULLIF(cnt_2022, 0), 1) AS growth_2022_to_2023_pct,
    ROUND((cnt_2024 - cnt_2023) * 100.0 / NULLIF(cnt_2023, 0), 1) AS growth_2023_to_2024_pct,
    ROUND((cnt_2024 - cnt_2022) * 100.0 / NULLIF(cnt_2022, 0), 1) AS cagr_2022_to_2024_pct
FROM yoy
WHERE cnt_2022 IS NOT NULL AND cnt_2024 IS NOT NULL
ORDER BY growth_2023_to_2024_pct DESC NULLS LAST
LIMIT 10;


-- 3. Disease burden by demographics
SELECT
    p.ethnicity,
    p.gender,
    CASE
        WHEN DATE_PART('year', AGE(CURRENT_DATE, p.dob::date)) < 35 THEN 'Under 35'
        WHEN DATE_PART('year', AGE(CURRENT_DATE, p.dob::date)) < 50 THEN '35-49'
        WHEN DATE_PART('year', AGE(CURRENT_DATE, p.dob::date)) < 65 THEN '50-64'
        ELSE '65+'
    END AS age_group,
    d.disease_name,
    COUNT(DISTINCT d.patient_id)                                  AS affected_patients,
    ROUND(AVG(CASE d.severity
        WHEN 'Mild'     THEN 1
        WHEN 'Moderate' THEN 2
        WHEN 'Severe'   THEN 3
        WHEN 'Critical' THEN 4
        ELSE NULL END), 2)                                        AS avg_severity_score
FROM diagnoses d
JOIN patients p ON d.patient_id = p.patient_id
WHERE d.chronic_flag = TRUE
GROUP BY p.ethnicity, p.gender, age_group, d.disease_name
HAVING COUNT(DISTINCT d.patient_id) >= 10
ORDER BY affected_patients DESC
LIMIT 50;


-- 4. Chronic disease co-occurrence matrix (comorbidity pairs)
WITH chronic_patients AS (
    SELECT DISTINCT
        patient_id,
        disease_name
    FROM diagnoses
    WHERE chronic_flag = TRUE
      AND status IN ('Active','Chronic')
),
pairs AS (
    SELECT
        a.disease_name AS disease_1,
        b.disease_name AS disease_2,
        COUNT(DISTINCT a.patient_id) AS co_occurrence_count
    FROM chronic_patients a
    JOIN chronic_patients b ON a.patient_id = b.patient_id
        AND a.disease_name < b.disease_name
    GROUP BY a.disease_name, b.disease_name
)
SELECT
    disease_1,
    disease_2,
    co_occurrence_count,
    RANK() OVER (ORDER BY co_occurrence_count DESC) AS rank_by_frequency
FROM pairs
ORDER BY co_occurrence_count DESC
LIMIT 20;


-- 5. Geographic disease hotspots by state
SELECT
    p.address_state,
    d.disease_name,
    COUNT(DISTINCT d.patient_id)                                  AS patient_count,
    ROUND(COUNT(DISTINCT d.patient_id) * 100.0 /
          COUNT(DISTINCT p.patient_id) OVER (PARTITION BY p.address_state), 2)
                                                                  AS state_prevalence_pct
FROM diagnoses d
JOIN patients p ON d.patient_id = p.patient_id
WHERE d.chronic_flag = TRUE
  AND d.disease_name IN (
      'Essential Hypertension', 'Type 2 Diabetes Mellitus',
      'Heart Failure, Unspecified', 'COPD with Exacerbation'
  )
GROUP BY p.address_state, d.disease_name
ORDER BY p.address_state, patient_count DESC;


-- 6. Seasonal disease patterns
SELECT
    EXTRACT(MONTH FROM d.diagnosis_date)                          AS month,
    TO_CHAR(d.diagnosis_date, 'Month')                            AS month_name,
    d.disease_name,
    COUNT(*)                                                       AS diagnoses_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY d.disease_name), 2) AS pct_of_annual
FROM diagnoses d
WHERE d.disease_name IN ('Pneumonia', 'COVID-19', 'Severe Persistent Asthma',
                          'COPD with Exacerbation', 'Major Depressive Disorder')
  AND EXTRACT(YEAR FROM d.diagnosis_date) = 2024
GROUP BY EXTRACT(MONTH FROM d.diagnosis_date), TO_CHAR(d.diagnosis_date, 'Month'), d.disease_name
ORDER BY d.disease_name, month;
