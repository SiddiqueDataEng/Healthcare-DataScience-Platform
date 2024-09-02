-- ============================================================
-- Analytics Project 3: Hospital Revenue Analytics
-- Business Question: What is the revenue performance by service
--   line, payer mix, and DRG? Where are the leakage points?
-- ============================================================

-- 1. Revenue summary by hospital and service type (YTD)
SELECT
    h.hospital_name,
    b.service_type,
    COUNT(b.invoice_id)                                           AS invoice_count,
    ROUND(SUM(b.gross_amount), 2)                                 AS gross_revenue,
    ROUND(SUM(b.insurance_adjustment + b.contractual_adjustment), 2) AS total_adjustments,
    ROUND(SUM(b.insurance_paid), 2)                               AS insurance_collected,
    ROUND(SUM(b.patient_paid), 2)                                 AS patient_collected,
    ROUND(SUM(b.amount_due), 2)                                   AS outstanding_ar,
    ROUND(SUM(b.insurance_paid + b.patient_paid) /
          NULLIF(SUM(b.gross_amount), 0) * 100, 2)                AS collection_rate_pct,
    COUNT(CASE WHEN b.bad_debt_flag THEN 1 END)                  AS bad_debt_count,
    ROUND(SUM(CASE WHEN b.bad_debt_flag THEN b.amount_due ELSE 0 END), 2) AS bad_debt_amount
FROM billing b
JOIN hospitals h ON b.hospital_id = h.hospital_id
WHERE b.service_date >= DATE_TRUNC('year', CURRENT_DATE)
GROUP BY h.hospital_name, b.service_type
ORDER BY h.hospital_name, gross_revenue DESC;


-- 2. Payer mix analysis — revenue by insurance type
SELECT
    b.payment_method,
    COUNT(b.invoice_id)                                           AS invoice_count,
    ROUND(SUM(b.gross_amount), 2)                                 AS gross_revenue,
    ROUND(SUM(b.gross_amount) * 100 / SUM(SUM(b.gross_amount)) OVER(), 2) AS revenue_share_pct,
    ROUND(AVG(b.gross_amount), 2)                                 AS avg_invoice_amount,
    ROUND(SUM(b.insurance_paid + b.patient_paid) /
          NULLIF(SUM(b.gross_amount), 0) * 100, 2)                AS collection_rate_pct,
    ROUND(AVG(
        CASE WHEN b.payment_status NOT IN ('Paid','Written Off')
             THEN b.days_outstanding END
    ), 1)                                                          AS avg_days_outstanding
FROM billing b
GROUP BY b.payment_method
ORDER BY gross_revenue DESC;


-- 3. Revenue per admission (DRG profitability)
SELECT
    a.drg_code,
    a.drg_description,
    COUNT(a.admission_id)                                         AS admissions,
    ROUND(AVG(a.actual_cost), 2)                                  AS avg_actual_cost,
    ROUND(AVG(a.insurance_approved_cost), 2)                      AS avg_approved_revenue,
    ROUND(AVG(a.insurance_approved_cost - a.actual_cost), 2)      AS avg_margin,
    ROUND(AVG((a.insurance_approved_cost - a.actual_cost) /
              NULLIF(a.insurance_approved_cost, 0)) * 100, 2)     AS margin_pct,
    ROUND(AVG(a.length_of_stay), 1)                               AS avg_los,
    ROUND(AVG(a.actual_cost) / NULLIF(AVG(a.length_of_stay), 0), 2) AS cost_per_day
FROM admissions a
WHERE a.discharge_status NOT IN ('Still Admitted')
  AND a.actual_cost > 0
GROUP BY a.drg_code, a.drg_description
HAVING COUNT(*) >= 50
ORDER BY avg_margin DESC
LIMIT 25;


-- 4. Accounts receivable aging analysis
SELECT
    ar_bucket,
    COUNT(*) AS invoice_count,
    ROUND(SUM(amount_due), 2) AS total_ar,
    ROUND(SUM(amount_due) * 100 / SUM(SUM(amount_due)) OVER(), 2) AS pct_of_total_ar
FROM (
    SELECT
        invoice_id,
        amount_due,
        CASE
            WHEN days_outstanding <= 30   THEN '0-30 days'
            WHEN days_outstanding <= 60   THEN '31-60 days'
            WHEN days_outstanding <= 90   THEN '61-90 days'
            WHEN days_outstanding <= 120  THEN '91-120 days'
            ELSE '120+ days'
        END AS ar_bucket
    FROM billing
    WHERE payment_status NOT IN ('Paid','Written Off','Charity Care')
      AND amount_due > 0
) t
GROUP BY ar_bucket
ORDER BY MIN(days_outstanding);


-- 5. Monthly revenue trend with MoM and YoY
WITH monthly_rev AS (
    SELECT
        DATE_TRUNC('month', service_date) AS service_month,
        SUM(gross_amount) AS gross_rev,
        SUM(insurance_paid + patient_paid) AS collected_rev
    FROM billing
    GROUP BY DATE_TRUNC('month', service_date)
)
SELECT
    service_month,
    ROUND(gross_rev, 2) AS gross_revenue,
    ROUND(collected_rev, 2) AS collected_revenue,
    ROUND(collected_rev * 100 / NULLIF(gross_rev, 0), 2) AS collection_rate_pct,
    ROUND(gross_rev - LAG(gross_rev) OVER (ORDER BY service_month), 2) AS mom_change,
    ROUND((gross_rev - LAG(gross_rev, 12) OVER (ORDER BY service_month)) * 100 /
          NULLIF(LAG(gross_rev, 12) OVER (ORDER BY service_month), 0), 2) AS yoy_growth_pct
FROM monthly_rev
ORDER BY service_month;


-- 6. Revenue leakage: claim denials impact
SELECT
    ic.insurance_provider,
    COUNT(ic.claim_id)                                            AS total_claims,
    SUM(CASE WHEN ic.claim_status = 'Denied' THEN 1 ELSE 0 END) AS denied_claims,
    ROUND(AVG(CASE WHEN ic.claim_status = 'Denied' THEN 1.0 ELSE 0 END) * 100, 2)
                                                                  AS denial_rate_pct,
    ROUND(SUM(ic.denied_amount), 2)                               AS total_denied_amount,
    ROUND(SUM(CASE WHEN ic.appeal_flag AND ic.appeal_outcome = 'Approved'
              THEN ic.approved_amount ELSE 0 END), 2)             AS recovered_via_appeal,
    ic.denial_code,
    COUNT(CASE WHEN ic.denial_code IS NOT NULL THEN 1 END) AS denial_code_occurrences
FROM insurance_claims ic
GROUP BY ic.insurance_provider, ic.denial_code
HAVING COUNT(*) >= 10
ORDER BY total_denied_amount DESC
LIMIT 30;
