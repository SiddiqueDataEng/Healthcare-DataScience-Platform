-- =============================================================
-- Analytical Views — pre-built views for BI tools and analytics
-- =============================================================

-- 1. Patient 360 View — single view of patient across all domains
CREATE OR REPLACE VIEW vw_patient_360 AS
SELECT
    p.patient_id,
    p.gender,
    p.ethnicity,
    p.blood_group,
    p.address_state,
    p.insurance_plan_type,
    DATE_PART('year', AGE(CURRENT_DATE, p.dob::date))::INT    AS age,
    p.deceased_flag,
    p.registration_date,
    -- Admission stats
    COUNT(DISTINCT a.admission_id)                             AS total_admissions,
    SUM(a.readmission_within_30d::int)                        AS readmissions_30d,
    ROUND(AVG(a.length_of_stay), 1)                           AS avg_los,
    MAX(a.admit_date::date)                                    AS last_admission_date,
    -- Appointment stats
    COUNT(DISTINCT apt.appointment_id)                        AS total_appointments,
    SUM(CASE WHEN apt.appointment_status = 'No-Show' THEN 1 ELSE 0 END) AS no_show_count,
    -- Diagnosis stats
    COUNT(DISTINCT dx.icd10_code)                             AS unique_diagnoses,
    COUNT(DISTINCT CASE WHEN dx.chronic_flag THEN dx.icd10_code END) AS chronic_conditions,
    -- Financial stats
    ROUND(SUM(b.gross_amount), 2)                             AS total_gross_charges,
    ROUND(SUM(b.patient_paid), 2)                             AS total_patient_payments,
    -- Lab stats
    COUNT(DISTINCT lr.result_id)                              AS total_lab_results,
    SUM(CASE WHEN lr.critical_flag THEN 1 ELSE 0 END)        AS critical_lab_count,
    -- Satisfaction
    ROUND(AVG(pf.overall_rating), 2)                         AS avg_satisfaction_score
FROM patients p
LEFT JOIN admissions    a   ON p.patient_id = a.patient_id
LEFT JOIN appointments  apt ON p.patient_id = apt.patient_id
LEFT JOIN diagnoses     dx  ON p.patient_id = dx.patient_id
LEFT JOIN billing       b   ON p.patient_id = b.patient_id
LEFT JOIN lab_results   lr  ON p.patient_id = lr.patient_id
LEFT JOIN patient_feedback pf ON p.patient_id = pf.patient_id
GROUP BY
    p.patient_id, p.gender, p.ethnicity, p.blood_group,
    p.address_state, p.insurance_plan_type, p.dob,
    p.deceased_flag, p.registration_date;


-- 2. Daily Operational Dashboard View
CREATE OR REPLACE VIEW vw_daily_operations AS
SELECT
    CURRENT_DATE                                               AS report_date,
    h.hospital_id,
    h.hospital_name,
    -- Bed occupancy (today)
    COUNT(bu.bed_id)                                          AS total_beds,
    SUM(CASE WHEN bu.occupancy_status = 'Occupied' THEN 1 ELSE 0 END) AS occupied_beds,
    ROUND(SUM(CASE WHEN bu.occupancy_status = 'Occupied' THEN 1.0 ELSE 0 END)
          / NULLIF(COUNT(bu.bed_id), 0) * 100, 2)            AS bed_occupancy_pct,
    SUM(CASE WHEN bu.occupancy_status = 'Available' THEN 1 ELSE 0 END) AS available_beds,
    -- Today's admissions
    (SELECT COUNT(*) FROM admissions a2
     WHERE a2.hospital_id = h.hospital_id
       AND a2.admit_date::date = CURRENT_DATE)                AS admissions_today,
    -- Today's discharges
    (SELECT COUNT(*) FROM admissions a3
     WHERE a3.hospital_id = h.hospital_id
       AND a3.discharge_date::date = CURRENT_DATE)            AS discharges_today,
    -- ED visits today
    (SELECT COUNT(*) FROM emergency_visits ev
     WHERE ev.hospital_id = h.hospital_id
       AND ev.arrival_datetime::date = CURRENT_DATE)          AS ed_visits_today,
    -- Avg ED wait time today
    (SELECT ROUND(AVG(ev.wait_time_minutes), 1)
     FROM emergency_visits ev
     WHERE ev.hospital_id = h.hospital_id
       AND ev.arrival_datetime::date = CURRENT_DATE)          AS avg_ed_wait_minutes_today
FROM hospitals h
LEFT JOIN bed_utilization bu ON h.hospital_id = bu.hospital_id
GROUP BY h.hospital_id, h.hospital_name;


-- 3. Revenue Cycle KPIs View
CREATE OR REPLACE VIEW vw_revenue_cycle_kpis AS
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', billing_date) AS bill_month,
        hospital_id,
        SUM(gross_amount)               AS gross_revenue,
        SUM(insurance_adjustment + contractual_adjustment) AS adjustments,
        SUM(insurance_paid + patient_paid) AS collected,
        SUM(amount_due)                 AS outstanding_ar,
        COUNT(invoice_id)               AS invoice_count,
        SUM(CASE WHEN bad_debt_flag THEN amount_due ELSE 0 END) AS bad_debt,
        ROUND(AVG(days_outstanding), 1) AS avg_days_outstanding
    FROM billing
    GROUP BY DATE_TRUNC('month', billing_date), hospital_id
)
SELECT
    bill_month,
    hospital_id,
    ROUND(gross_revenue, 2)                                   AS gross_revenue,
    ROUND(adjustments, 2)                                     AS adjustments,
    ROUND(gross_revenue - adjustments, 2)                    AS net_revenue,
    ROUND(collected, 2)                                       AS collected,
    ROUND(collected / NULLIF(gross_revenue - adjustments, 0) * 100, 2) AS collection_rate_pct,
    ROUND(outstanding_ar, 2)                                  AS outstanding_ar,
    ROUND(outstanding_ar / (gross_revenue / 30), 1)          AS days_in_ar,
    invoice_count,
    ROUND(bad_debt, 2)                                        AS bad_debt,
    ROUND(bad_debt / NULLIF(gross_revenue, 0) * 100, 2)      AS bad_debt_rate_pct,
    avg_days_outstanding
FROM monthly
ORDER BY bill_month DESC, hospital_id;


-- 4. ICU Risk Score View (for real-time alerting)
CREATE OR REPLACE VIEW vw_icu_active_alerts AS
SELECT
    iv.patient_id,
    iv.hospital_id,
    iv.bed_id,
    iv.timestamp,
    iv.heart_rate,
    iv.blood_pressure_sys,
    iv.spo2,
    iv.temperature,
    iv.respiration_rate,
    iv.on_ventilator,
    iv.alarm_triggered,
    iv.alarm_type,
    iv.alarm_severity,
    iv.critical_vitals_flag,
    -- Simple SOFA-like score components
    CASE WHEN iv.spo2 < 88 THEN 4
         WHEN iv.spo2 < 92 THEN 3
         WHEN iv.spo2 < 96 THEN 1
         ELSE 0 END AS resp_score,
    CASE WHEN iv.mean_arterial_pressure < 50 THEN 4
         WHEN iv.mean_arterial_pressure < 65 THEN 3
         WHEN iv.mean_arterial_pressure < 75 THEN 1
         ELSE 0 END AS cv_score,
    CASE WHEN iv.heart_rate > 150 OR iv.heart_rate < 40 THEN 3
         WHEN iv.heart_rate > 130 OR iv.heart_rate < 50 THEN 2
         ELSE 0 END AS hr_score
FROM icu_vitals iv
WHERE iv.critical_vitals_flag = TRUE
  AND iv.timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 hour';


-- 5. Hospital Performance Scorecard
CREATE OR REPLACE VIEW vw_hospital_scorecard AS
SELECT
    h.hospital_id,
    h.hospital_name,
    h.hospital_type,
    h.state,
    -- Quality
    ROUND(AVG(a.readmission_within_30d::int) * 100, 2)      AS readmission_rate_30d_pct,
    ROUND(AVG(CASE WHEN a.discharge_status = 'Expired' THEN 1.0 ELSE 0 END) * 100, 2) AS mortality_rate_pct,
    ROUND(AVG(a.length_of_stay), 1)                          AS avg_los_days,
    -- Operations
    ROUND(AVG(ev.wait_time_minutes), 1)                      AS avg_ed_wait_minutes,
    ROUND(AVG(ev.left_without_seen::int) * 100, 2)           AS lwbs_rate_pct,
    -- Financial
    ROUND(AVG(b.gross_amount), 2)                            AS avg_charge_per_service,
    -- Satisfaction
    ROUND(AVG(pf.overall_rating), 2)                         AS avg_patient_rating,
    ROUND(AVG(pf.likelihood_recommend), 2)                   AS avg_nps_score,
    -- Volume
    COUNT(DISTINCT a.admission_id)                           AS total_admissions,
    COUNT(DISTINCT ev.visit_id)                              AS total_ed_visits,
    COUNT(DISTINCT p.patient_id)                             AS total_patients
FROM hospitals h
LEFT JOIN admissions      a   ON h.hospital_id = a.hospital_id AND a.admit_date >= CURRENT_DATE - 365
LEFT JOIN emergency_visits ev ON h.hospital_id = ev.hospital_id AND ev.arrival_datetime >= CURRENT_DATE - 365
LEFT JOIN billing         b   ON h.hospital_id = b.hospital_id AND b.billing_date >= CURRENT_DATE - 365
LEFT JOIN patient_feedback pf ON h.hospital_id = pf.hospital_id AND pf.survey_date >= CURRENT_DATE - 365
LEFT JOIN patients        p   ON h.hospital_id = p.hospital_id
GROUP BY h.hospital_id, h.hospital_name, h.hospital_type, h.state;


-- 6. Lab Critical Values Alert View
CREATE OR REPLACE VIEW vw_critical_lab_alerts AS
SELECT
    lr.result_id,
    lr.patient_id,
    lr.hospital_id,
    lr.ordering_doctor_id,
    lr.test_name,
    lr.result_numeric,
    lr.unit,
    lr.reference_range_text,
    lr.abnormal_flag,
    lr.collection_datetime,
    lr.resulted_datetime,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - lr.resulted_datetime)) / 3600 AS hours_since_result,
    -- Identify specific critical conditions
    CASE
        WHEN lr.test_name = 'Potassium' AND lr.result_numeric > 6.5 THEN 'Critical Hyperkalemia'
        WHEN lr.test_name = 'Potassium' AND lr.result_numeric < 2.5 THEN 'Critical Hypokalemia'
        WHEN lr.test_name = 'Sodium' AND lr.result_numeric > 160     THEN 'Critical Hypernatremia'
        WHEN lr.test_name = 'Sodium' AND lr.result_numeric < 120     THEN 'Critical Hyponatremia'
        WHEN lr.test_name = 'Glucose' AND lr.result_numeric > 500    THEN 'Critical Hyperglycemia'
        WHEN lr.test_name = 'Glucose' AND lr.result_numeric < 40     THEN 'Critical Hypoglycemia'
        WHEN lr.test_name = 'Troponin I' AND lr.result_numeric > 2.0 THEN 'Elevated Troponin - STEMI Risk'
        WHEN lr.test_name = 'INR' AND lr.result_numeric > 5.0        THEN 'Critical Coagulopathy'
        WHEN lr.test_name = 'Hemoglobin' AND lr.result_numeric < 7.0 THEN 'Critical Anemia'
        WHEN lr.test_name = 'Platelets' AND lr.result_numeric < 50   THEN 'Critical Thrombocytopenia'
        ELSE 'Other Critical Value'
    END AS critical_reason
FROM lab_results lr
WHERE lr.critical_flag = TRUE
  AND lr.result_status IN ('Final', 'Preliminary')
  AND lr.resulted_datetime >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
ORDER BY lr.resulted_datetime DESC;
