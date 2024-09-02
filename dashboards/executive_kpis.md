# Healthcare Data Platform — Executive KPI Dashboard Specifications

## Dashboard 1: Executive Overview (CEO / CMO / CFO)

### Key Performance Indicators

| KPI | Formula | Target | Frequency |
|-----|---------|--------|-----------|
| **Bed Occupancy Rate** | Occupied Beds / Available Beds × 100 | 85% | Daily |
| **30-Day Readmission Rate** | 30d Readmissions / Total Discharges × 100 | < 15.6% | Monthly |
| **In-Hospital Mortality Rate** | Expired / Total Discharges × 100 | Benchmark | Monthly |
| **Net Revenue** | Gross Revenue – Adjustments – Bad Debt | Budget | Monthly |
| **Claim Approval Rate** | Approved Claims / Total Claims × 100 | > 88% | Weekly |
| **Avg Length of Stay** | Sum(LOS) / Count(Admissions) | DRG Benchmark | Daily |
| **Patient Satisfaction Score** | Avg(HCAHPS Overall Rating) | > 8.0 / 10 | Monthly |
| **ER Door-to-Doctor Time** | Avg(triage_datetime – arrival_datetime) | < 30 min | Daily |
| **Staff Utilization Rate** | Actual Hours / Scheduled Hours × 100 | 85-95% | Weekly |
| **Operating Margin** | (Revenue – Operating Costs) / Revenue × 100 | > 5% | Monthly |

---

## Dashboard 2: Clinical Quality (CMO / Medical Director)

```
┌─────────────────────────────────────────────────────────────────┐
│  CLINICAL QUALITY DASHBOARD                                      │
├─────────────────┬────────────────┬────────────────┬────────────┤
│ Readmission Rate│ Mortality Rate │ HCAHPS Score   │ Falls Rate │
│ 14.2%  ↓0.3%   │ 2.1%   →      │ 8.4 / 10  ↑    │ 0.8/1000  │
│ [Target: <15.6] │ [National: 2.3]│ [Target: >8.0] │ [Target<1] │
├─────────────────┴────────────────┴────────────────┴────────────┤
│                 QUALITY METRICS BY DEPARTMENT                    │
│  Cardiology ████████████████████ 92% | Avg LOS: 3.2d           │
│  Surgery    ████████████████░░░░ 78% | Avg LOS: 4.8d           │
│  Emergency  ██████████████████░░ 88% | Door-to-Doc: 22 min     │
│  ICU        ██████████████████░░ 87% | Ventilator days: 3.1    │
├─────────────────────────────────────────────────────────────────┤
│  TOP 5 HIGH-RISK READMISSION DRGs          30d Rate vs Benchmark│
│  1. Heart Failure (DRG 291)    22.4% |████████░░ National 20.0% │
│  2. Pneumonia (DRG 194)        16.8% |██████░░░░ National 16.1% │
│  3. Sepsis (DRG 871)           19.2% |███████░░░ National 18.5% │
│  4. COPD (DRG 190)             18.1% |██████░░░░ National 17.8% │
│  5. Hip/Knee (DRG 470)          4.2% |█░░░░░░░░░ National  4.7% │
└─────────────────────────────────────────────────────────────────┘
```

### SQL for Clinical Quality KPIs

```sql
-- Readmission Rate (CMS methodology)
SELECT
    DATE_TRUNC('month', admit_date) AS month,
    COUNT(*) AS total_discharges,
    SUM(readmission_within_30d::int) AS readmissions_30d,
    ROUND(AVG(readmission_within_30d::int) * 100, 2) AS readmission_rate_pct
FROM admissions
WHERE discharge_status NOT IN ('Still Admitted', 'Expired')
  AND admit_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY 1 ORDER BY 1;

-- Mortality Rate
SELECT
    DATE_TRUNC('month', admit_date) AS month,
    COUNT(*) AS total_admissions,
    SUM(CASE WHEN discharge_status = 'Expired' THEN 1 ELSE 0 END) AS deaths,
    ROUND(AVG(CASE WHEN discharge_status = 'Expired' THEN 1.0 ELSE 0 END) * 100, 2) AS mortality_rate_pct
FROM admissions
GROUP BY 1 ORDER BY 1;
```

---

## Dashboard 3: Financial Performance (CFO / Revenue Cycle)

### Revenue Cycle KPIs

| Metric | Definition | Target |
|--------|-----------|--------|
| Gross Revenue | Sum of all charges before adjustments | |
| Net Revenue | After contractual adjustments | |
| Collection Rate | Collected / Net Revenue × 100 | > 95% |
| Days in A/R | Outstanding AR / (Gross Revenue / 365) | < 50 days |
| Denial Rate | Denied Claims / Total Claims × 100 | < 5% |
| Clean Claim Rate | Claims requiring no follow-up / Total | > 90% |
| Bad Debt Rate | Bad Debt Write-offs / Gross Revenue | < 3% |
| Cost per Discharge | Total Operating Cost / Discharges | DRG based |

### Payer Mix Chart (Power BI / Tableau)

```
Commercial Insurance  ████████████████████ 48%  $48.2M
Medicare             ██████████████░░░░░░ 18%  $18.1M
Medicaid             ████████████░░░░░░░░ 12%  $12.0M
Self-Pay             ████░░░░░░░░░░░░░░░░  8%   $8.0M
Other Government     ████░░░░░░░░░░░░░░░░  6%   $6.0M
Other                ████░░░░░░░░░░░░░░░░  8%   $8.0M
```

---

## Dashboard 4: Operations (COO / Operations Director)

### Operational KPIs

| Area | KPI | Current | Target |
|------|-----|---------|--------|
| **Beds** | Occupancy Rate | 84.2% | 85% |
| **Beds** | Avg Bed Turnover Time | 68 min | < 60 min |
| **ED** | Door-to-Doctor | 24 min | < 30 min |
| **ED** | LWBS Rate | 1.8% | < 2% |
| **ED** | 72-hour Return Rate | 3.1% | < 3% |
| **OR** | OR Utilization | 78% | 80-85% |
| **Lab** | Turnaround Time (STAT) | 42 min | < 60 min |
| **Imaging** | Report Turnaround | 3.2 hrs | < 4 hrs |
| **Staff** | Agency/Overtime % | 8.2% | < 10% |

---

## Dashboard 5: Patient Satisfaction (Quality / Patient Experience)

### HCAHPS Score Tracker

```
Overall Hospital Rating:   8.4 / 10  ████████░░  ▲ +0.2 vs prior month
Likelihood to Recommend:   74% Promoters  18% Passive  8% Detractors
NPS Score:                 +66  (Industry avg: +58)

Domain Scores (1-4 scale: Never/Sometimes/Usually/Always)
Doctor Communication:      3.6  ████████████████████████████████████░░░░
Nurse Communication:       3.4  ████████████████████████████████░░░░░░░░
Staff Responsiveness:      3.2  ████████████████████████████░░░░░░░░░░░░
Pain Management:           3.1  ██████████████████████████░░░░░░░░░░░░░░
Medication Communication:  3.3  ███████████████████████████████░░░░░░░░░
Hospital Cleanliness:      3.7  ████████████████████████████████████████
Hospital Quietness:        2.9  ████████████████████████░░░░░░░░░░░░░░░░
Discharge Information:     3.5  ██████████████████████████████████░░░░░░
```

### Sentiment Analysis Results (from NLP pipeline)
- **Positive themes**: Staff kindness (42%), Clean facility (28%), Quick response (18%)
- **Negative themes**: Long wait times (45%), Communication gaps (32%), Pain management (15%)
- **Improvement opportunities**: Discharge planning, overnight noise, parking

---

## Dashboard 6: Disease Surveillance (Public Health / CMO)

### Disease Trend Monitor

```sql
-- Real-time disease volume tracker
SELECT
    d.disease_name,
    d.disease_category,
    COUNT(*) AS new_cases_this_week,
    COUNT(*) - LAG(COUNT(*)) OVER (PARTITION BY d.disease_name ORDER BY week) AS wow_change,
    ROUND(AVG(CASE d.severity WHEN 'Critical' THEN 1.0 ELSE 0 END) * 100, 1) AS critical_rate_pct
FROM diagnoses d
WHERE d.diagnosis_date >= CURRENT_DATE - 7
GROUP BY d.disease_name, d.disease_category,
         DATE_TRUNC('week', d.diagnosis_date) AS week
ORDER BY new_cases_this_week DESC
LIMIT 20;
```

---

## Dashboard Implementation Notes

### Power BI Setup
1. Connect to PostgreSQL via DirectQuery (real-time) or Import (scheduled refresh)
2. Set Row Level Security (RLS) to enforce HIPAA role-based access
3. Enable PHI field masking in report views
4. Schedule daily refresh at 06:00 AM

### Tableau Setup  
1. Use Live Connection to Snowflake for real-time dashboards
2. Implement Data Source Filters for hospital-level access control
3. Publish to Tableau Server with site-level permissions
4. Enable extract encryption for cached data

### Apache Superset Setup
1. Connect to PostgreSQL via SQLAlchemy URI
2. Create datasets with column-level security
3. Enable cache (Redis) for frequently-used aggregations
4. Set up row-level security for multi-hospital network

### Refresh Schedules
| Dashboard | Refresh | Source |
|-----------|---------|--------|
| Executive | Daily 6am | DW snapshot |
| Clinical Quality | Daily 6am | DW snapshot |
| Financial | Daily 7am | Billing system |
| Operations | Hourly | Near real-time |
| Patient Safety | Real-time | Streaming |
| Disease Surveillance | 4x/day | EMR feed |
