-- ============================================================
-- Analytics Project 5: Bed Occupancy & Emergency Analytics
-- ============================================================

-- 1. Real-time bed occupancy by hospital and ward
SELECT
    h.hospital_name,
    bu.ward,
    bu.bed_type,
    h.total_beds,
    COUNT(bu.bed_id)                                              AS total_managed_beds,
    SUM(CASE WHEN bu.occupancy_status = 'Occupied' THEN 1 ELSE 0 END)
                                                                  AS occupied_beds,
    SUM(CASE WHEN bu.occupancy_status = 'Available' THEN 1 ELSE 0 END)
                                                                  AS available_beds,
    SUM(CASE WHEN bu.occupancy_status = 'Housekeeping' THEN 1 ELSE 0 END)
                                                                  AS in_housekeeping,
    ROUND(
        SUM(CASE WHEN bu.occupancy_status = 'Occupied' THEN 1 ELSE 0 END)::NUMERIC
        / NULLIF(COUNT(bu.bed_id), 0) * 100, 2
    )                                                             AS occupancy_rate_pct
FROM bed_utilization bu
JOIN hospitals h ON bu.hospital_id = h.hospital_id
GROUP BY h.hospital_name, bu.ward, bu.bed_type, h.total_beds
ORDER BY h.hospital_name, occupancy_rate_pct DESC;


-- 2. Hourly bed occupancy pattern (avg across all hospitals)
SELECT
    EXTRACT(HOUR FROM bu.occupancy_start)                         AS hour_of_day,
    bu.ward,
    ROUND(AVG(
        CASE WHEN bu.occupancy_status = 'Occupied' THEN 1.0 ELSE 0 END
    ) * 100, 2)                                                   AS avg_occupancy_pct,
    COUNT(*)                                                       AS observations
FROM bed_utilization bu
WHERE bu.occupancy_start IS NOT NULL
GROUP BY EXTRACT(HOUR FROM bu.occupancy_start), bu.ward
ORDER BY bu.ward, hour_of_day;


-- 3. Average bed turnover time (discharge to next patient)
SELECT
    h.hospital_name,
    bu.ward,
    ROUND(AVG(bu.cleaning_minutes), 1)                           AS avg_cleaning_minutes,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY bu.cleaning_minutes)
                                                                  AS median_cleaning_minutes,
    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY bu.cleaning_minutes)
                                                                  AS p90_cleaning_minutes,
    COUNT(*)                                                       AS turnover_events
FROM bed_utilization bu
JOIN hospitals h ON bu.hospital_id = h.hospital_id
WHERE bu.cleaning_minutes IS NOT NULL
GROUP BY h.hospital_name, bu.ward
ORDER BY avg_cleaning_minutes DESC;


-- 4. Emergency Department performance metrics
SELECT
    h.hospital_name,
    EXTRACT(YEAR FROM ev.arrival_datetime)                        AS year,
    EXTRACT(MONTH FROM ev.arrival_datetime)                       AS month,
    COUNT(ev.visit_id)                                            AS total_ed_visits,
    ROUND(AVG(ev.wait_time_minutes), 1)                           AS avg_wait_minutes,
    ROUND(AVG(ev.door_to_doc_minutes), 1)                         AS avg_door_to_doc_minutes,
    ROUND(AVG(ev.total_ed_minutes), 1)                            AS avg_total_ed_minutes,
    SUM(ev.admitted_flag::int)                                    AS admitted_count,
    ROUND(AVG(ev.admitted_flag::int) * 100, 2)                    AS admission_rate_pct,
    SUM(ev.left_without_seen::int)                                AS lwbs_count,
    ROUND(AVG(ev.left_without_seen::int) * 100, 2)                AS lwbs_rate_pct,
    SUM(ev.return_within_72h::int)                                AS return_72h_count
FROM emergency_visits ev
JOIN hospitals h ON ev.hospital_id = h.hospital_id
GROUP BY h.hospital_name, EXTRACT(YEAR FROM ev.arrival_datetime), EXTRACT(MONTH FROM ev.arrival_datetime)
ORDER BY h.hospital_name, year, month;


-- 5. ED volume by hour and day (capacity planning)
SELECT
    TO_CHAR(arrival_datetime, 'Dy')                               AS day_of_week,
    EXTRACT(DOW FROM arrival_datetime)                            AS dow_num,
    EXTRACT(HOUR FROM arrival_datetime)                           AS hour_of_day,
    COUNT(*)                                                       AS visit_count,
    ROUND(AVG(wait_time_minutes), 1)                              AS avg_wait_minutes,
    ROUND(AVG(total_ed_minutes), 1)                               AS avg_ed_minutes,
    SUM(CASE WHEN triage_level <= 2 THEN 1 ELSE 0 END)           AS high_acuity_count
FROM emergency_visits
GROUP BY day_of_week, dow_num, EXTRACT(HOUR FROM arrival_datetime)
ORDER BY dow_num, hour_of_day;


-- 6. ED triage level distribution and acuity trends
SELECT
    EXTRACT(YEAR FROM arrival_datetime)                           AS year,
    triage_level,
    triage_level_desc,
    COUNT(*)                                                       AS visit_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY EXTRACT(YEAR FROM arrival_datetime)), 2)
                                                                   AS pct_of_visits,
    ROUND(AVG(wait_time_minutes), 1)                              AS avg_wait_minutes,
    ROUND(AVG(door_to_doc_minutes), 1)                            AS avg_door_to_doc,
    ROUND(AVG(admitted_flag::int) * 100, 2)                       AS admission_rate_pct
FROM emergency_visits
GROUP BY EXTRACT(YEAR FROM arrival_datetime), triage_level, triage_level_desc
ORDER BY year, triage_level;
