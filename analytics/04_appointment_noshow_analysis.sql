-- ============================================================
-- Analytics Project 4: Appointment No-Show Analysis
-- Business Question: What factors predict no-shows? 
--   What is the revenue impact?
-- ============================================================

-- 1. No-show rate by specialty and appointment type
SELECT
    d.specialization,
    a.appointment_type,
    a.visit_type,
    COUNT(*)                                                      AS total_appointments,
    SUM(CASE WHEN a.appointment_status = 'No-Show' THEN 1 ELSE 0 END) AS no_shows,
    ROUND(AVG(CASE WHEN a.appointment_status = 'No-Show' THEN 1.0 ELSE 0 END) * 100, 2)
                                                                  AS no_show_rate_pct,
    ROUND(AVG(CASE WHEN a.appointment_status = 'Cancelled' THEN 1.0 ELSE 0 END) * 100, 2)
                                                                  AS cancellation_rate_pct
FROM appointments a
JOIN doctors d ON a.doctor_id = d.doctor_id
GROUP BY d.specialization, a.appointment_type, a.visit_type
HAVING COUNT(*) >= 50
ORDER BY no_show_rate_pct DESC;


-- 2. No-show rate by day of week and time of day
SELECT
    TO_CHAR(a.appointment_date, 'Day')                            AS day_of_week,
    EXTRACT(DOW FROM a.appointment_date)                          AS dow_num,
    CASE
        WHEN a.appointment_time < '09:00' THEN 'Early Morning (before 9am)'
        WHEN a.appointment_time < '12:00' THEN 'Morning (9am-12pm)'
        WHEN a.appointment_time < '14:00' THEN 'Lunch (12pm-2pm)'
        WHEN a.appointment_time < '17:00' THEN 'Afternoon (2pm-5pm)'
        ELSE 'Evening (after 5pm)'
    END AS time_slot,
    COUNT(*)                                                       AS total_appointments,
    SUM(CASE WHEN a.appointment_status = 'No-Show' THEN 1 ELSE 0 END) AS no_shows,
    ROUND(AVG(CASE WHEN a.appointment_status = 'No-Show' THEN 1.0 ELSE 0 END) * 100, 2)
                                                                   AS no_show_rate_pct
FROM appointments a
GROUP BY day_of_week, dow_num, time_slot
ORDER BY dow_num, time_slot;


-- 3. No-show rate by patient demographics
SELECT
    CASE
        WHEN DATE_PART('year', AGE(CURRENT_DATE, p.dob::date)) < 18 THEN 'Under 18'
        WHEN DATE_PART('year', AGE(CURRENT_DATE, p.dob::date)) < 35 THEN '18-34'
        WHEN DATE_PART('year', AGE(CURRENT_DATE, p.dob::date)) < 50 THEN '35-49'
        WHEN DATE_PART('year', AGE(CURRENT_DATE, p.dob::date)) < 65 THEN '50-64'
        ELSE '65+'
    END AS age_group,
    p.gender,
    p.insurance_plan_type,
    COUNT(a.appointment_id)                                       AS total_appointments,
    ROUND(AVG(CASE WHEN a.appointment_status = 'No-Show' THEN 1.0 ELSE 0 END) * 100, 2)
                                                                   AS no_show_rate_pct
FROM appointments a
JOIN patients p ON a.patient_id = p.patient_id
GROUP BY age_group, p.gender, p.insurance_plan_type
HAVING COUNT(*) >= 20
ORDER BY no_show_rate_pct DESC
LIMIT 30;


-- 4. Lead time impact on no-show rate
-- (How far in advance was the appointment scheduled?)
SELECT
    lead_time_bucket,
    COUNT(*)                                                      AS appointments,
    ROUND(AVG(CASE WHEN appointment_status = 'No-Show' THEN 1.0 ELSE 0 END) * 100, 2)
                                                                  AS no_show_rate_pct
FROM (
    SELECT
        appointment_id,
        appointment_status,
        CASE
            WHEN created_at::date = appointment_date THEN 'Same day'
            WHEN appointment_date - created_at::date <= 3 THEN '1-3 days'
            WHEN appointment_date - created_at::date <= 7 THEN '4-7 days'
            WHEN appointment_date - created_at::date <= 14 THEN '8-14 days'
            WHEN appointment_date - created_at::date <= 30 THEN '15-30 days'
            ELSE '30+ days'
        END AS lead_time_bucket
    FROM appointments
) t
GROUP BY lead_time_bucket
ORDER BY no_show_rate_pct DESC;


-- 5. Patient no-show history (repeat offenders)
WITH patient_history AS (
    SELECT
        patient_id,
        COUNT(*) AS total_appointments,
        SUM(CASE WHEN appointment_status = 'No-Show' THEN 1 ELSE 0 END) AS no_show_count,
        ROUND(AVG(CASE WHEN appointment_status = 'No-Show' THEN 1.0 ELSE 0 END) * 100, 2) AS no_show_rate
    FROM appointments
    GROUP BY patient_id
    HAVING COUNT(*) >= 3
)
SELECT
    CASE
        WHEN no_show_rate = 0    THEN 'Never No-Show'
        WHEN no_show_rate < 20   THEN 'Low Risk (<20%)'
        WHEN no_show_rate < 50   THEN 'Medium Risk (20-50%)'
        WHEN no_show_rate < 75   THEN 'High Risk (50-75%)'
        ELSE 'Very High Risk (75%+)'
    END AS risk_segment,
    COUNT(*) AS patient_count,
    ROUND(AVG(total_appointments), 1) AS avg_appointments,
    ROUND(AVG(no_show_count), 1) AS avg_no_shows,
    ROUND(AVG(no_show_rate), 2) AS avg_no_show_rate
FROM patient_history
GROUP BY risk_segment
ORDER BY avg_no_show_rate DESC;


-- 6. Financial impact of no-shows
SELECT
    EXTRACT(YEAR FROM a.appointment_date) AS year,
    COUNT(CASE WHEN a.appointment_status = 'No-Show' THEN 1 END) AS no_show_count,
    -- Estimated revenue loss: avg copay + lost slot opportunity
    ROUND(COUNT(CASE WHEN a.appointment_status = 'No-Show' THEN 1 END)
          * AVG(a.copay_amount), 2)                               AS estimated_copay_lost,
    -- Average revenue per completed appointment * no shows = opportunity cost
    ROUND(COUNT(CASE WHEN a.appointment_status = 'No-Show' THEN 1 END) * 185.0, 2)
                                                                   AS estimated_revenue_impact
FROM appointments a
GROUP BY EXTRACT(YEAR FROM a.appointment_date)
ORDER BY year;
