-- =============================================================
-- Table: wearable_data
-- Description: IoT wearable device telemetry
-- Target: 500,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS wearable_data (
    device_event_id     BIGSERIAL       PRIMARY KEY,
    patient_id          VARCHAR(15)     NOT NULL,
    device_id           VARCHAR(50)     NOT NULL,
    device_type         VARCHAR(50),               -- Smartwatch | Fitness Band | CGM | ECG Patch | BP Monitor
    device_brand        VARCHAR(50),               -- Apple | Fitbit | Garmin | Dexcom | Withings
    timestamp           TIMESTAMP       NOT NULL,
    -- Activity Metrics
    steps               INT,
    steps_goal          INT             DEFAULT 10000,
    calories_burned     DECIMAL(8,2),
    active_minutes      INT,
    sedentary_minutes   INT,
    distance_km         DECIMAL(8,4),
    floors_climbed      INT,
    -- Cardiovascular
    heart_rate          INT,                       -- bpm
    heart_rate_zone     VARCHAR(20),               -- Rest|Fat Burn|Cardio|Peak
    heart_rate_variability DECIMAL(8,4),           -- HRV in ms
    resting_hr          INT,
    -- Sleep
    sleep_hours         DECIMAL(5,2),
    deep_sleep_hours    DECIMAL(5,2),
    rem_sleep_hours     DECIMAL(5,2),
    light_sleep_hours   DECIMAL(5,2),
    sleep_score         INT,                       -- 0-100
    -- Metabolic
    spo2                DECIMAL(5,2),
    skin_temperature    DECIMAL(5,2),
    stress_level        INT,                       -- 1-100
    -- Continuous Glucose (CGM)
    blood_glucose       DECIMAL(6,2),              -- mg/dL (CGM devices)
    -- Menstrual (where applicable)
    -- Geolocation (opt-in only, aggregated to city level for privacy)
    location_city       VARCHAR(100),
    location_state      VARCHAR(100),
    -- Data quality
    battery_level       INT,                       -- %
    sync_method         VARCHAR(20),               -- Auto | Manual
    data_quality        VARCHAR(20)    DEFAULT 'Good'
) PARTITION BY RANGE (timestamp);

CREATE TABLE IF NOT EXISTS wearable_data_2024_q1 PARTITION OF wearable_data
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE IF NOT EXISTS wearable_data_2024_q2 PARTITION OF wearable_data
    FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE IF NOT EXISTS wearable_data_2024_q3 PARTITION OF wearable_data
    FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE IF NOT EXISTS wearable_data_2024_q4 PARTITION OF wearable_data
    FOR VALUES FROM ('2024-10-01') TO ('2025-01-01');

CREATE INDEX IF NOT EXISTS idx_wear_patient_ts  ON wearable_data(patient_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_wear_device      ON wearable_data(device_id);
CREATE INDEX IF NOT EXISTS idx_wear_type        ON wearable_data(device_type);


-- =============================================================
-- Table: emergency_visits
-- Description: Emergency Department triage and visit records
-- Target: 5,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS emergency_visits (
    visit_id            VARCHAR(20)     PRIMARY KEY,
    patient_id          VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    hospital_id         VARCHAR(10)     NOT NULL REFERENCES hospitals(hospital_id),
    arrival_datetime    TIMESTAMP       NOT NULL,
    arrival_mode        VARCHAR(50),               -- Walk-In | EMS | Police | Transfer | Helicopter
    triage_datetime     TIMESTAMP,
    triage_level        INT,                       -- 1=Immediate | 2=Emergent | 3=Urgent | 4=Less Urgent | 5=Non-Urgent (ESI)
    triage_level_desc   VARCHAR(30),
    chief_complaint     VARCHAR(300),
    wait_time_minutes   INT,                       -- Triage to first physician contact
    door_to_doc_minutes INT,                       -- Arrival to physician minutes
    physician_id        VARCHAR(15)     REFERENCES doctors(doctor_id),
    primary_diagnosis   VARCHAR(10),               -- ICD-10
    secondary_diagnosis VARCHAR(10),
    disposition         VARCHAR(50),               -- Discharged | Admitted | Transferred | AMA | Expired | LWBS
    discharge_datetime  TIMESTAMP,
    total_ed_minutes    INT             GENERATED ALWAYS AS (
                            CASE
                                WHEN discharge_datetime IS NOT NULL
                                THEN EXTRACT(EPOCH FROM (discharge_datetime - arrival_datetime))::INT / 60
                                ELSE NULL
                            END
                        ) STORED,
    admitted_flag       BOOLEAN         DEFAULT FALSE,
    admission_id        VARCHAR(20)     REFERENCES admissions(admission_id),
    left_without_seen   BOOLEAN         DEFAULT FALSE,
    left_without_treatment BOOLEAN      DEFAULT FALSE,
    return_within_72h   BOOLEAN         DEFAULT FALSE,
    pain_score_arrival  INT,                       -- 0-10
    pain_score_discharge INT,
    procedures_performed TEXT[],
    medications_given   TEXT[],
    labs_ordered        BOOLEAN         DEFAULT FALSE,
    imaging_ordered     BOOLEAN         DEFAULT FALSE,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_er_patient        ON emergency_visits(patient_id);
CREATE INDEX IF NOT EXISTS idx_er_hospital       ON emergency_visits(hospital_id);
CREATE INDEX IF NOT EXISTS idx_er_arrival        ON emergency_visits(arrival_datetime);
CREATE INDEX IF NOT EXISTS idx_er_triage         ON emergency_visits(triage_level);
CREATE INDEX IF NOT EXISTS idx_er_disposition    ON emergency_visits(disposition);
CREATE INDEX IF NOT EXISTS idx_er_admitted       ON emergency_visits(admitted_flag);


-- =============================================================
-- Table: insurance_claims
-- Description: Insurance claims submission and adjudication
-- Target: 5,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS insurance_claims (
    claim_id                VARCHAR(20)     PRIMARY KEY,
    patient_id              VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    admission_id            VARCHAR(20)     REFERENCES admissions(admission_id),
    hospital_id             VARCHAR(10)     REFERENCES hospitals(hospital_id),
    insurance_provider      VARCHAR(100)    NOT NULL,
    insurance_plan_type     VARCHAR(50),             -- HMO | PPO | Medicare | Medicaid | Tricare
    group_number            VARCHAR(50),
    member_id               VARCHAR(50),
    claim_type              VARCHAR(30),             -- Inpatient | Outpatient | Emergency | Pharmacy
    primary_icd10           VARCHAR(10),
    primary_cpt             VARCHAR(10),
    service_date_from       DATE,
    service_date_to         DATE,
    submission_date         DATE            NOT NULL,
    claim_amount            DECIMAL(12,2)   NOT NULL,
    approved_amount         DECIMAL(12,2),
    denied_amount           DECIMAL(12,2),
    patient_responsibility  DECIMAL(12,2),
    deductible_applied      DECIMAL(10,2),
    copay_amount            DECIMAL(10,2),
    coinsurance_amount      DECIMAL(10,2),
    claim_status            VARCHAR(30)     NOT NULL, -- Submitted | Pending | Approved | Denied | Partially Approved | Appeal | Paid
    denial_reason           VARCHAR(300),
    denial_code             VARCHAR(20),             -- CARC/RARC codes
    appeal_flag             BOOLEAN         DEFAULT FALSE,
    appeal_date             DATE,
    appeal_outcome          VARCHAR(50),
    processing_days         INT             GENERATED ALWAYS AS (
                                CASE
                                    WHEN claim_status IN ('Approved','Denied','Paid','Partially Approved')
                                        AND submission_date IS NOT NULL
                                    THEN (CURRENT_DATE - submission_date)::INT
                                    ELSE NULL
                                END
                            ) STORED,
    fraud_flag              BOOLEAN         DEFAULT FALSE,
    fraud_score             DECIMAL(5,4),           -- ML fraud probability 0-1
    audited_flag            BOOLEAN         DEFAULT FALSE,
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_claims_patient      ON insurance_claims(patient_id);
CREATE INDEX IF NOT EXISTS idx_claims_hospital     ON insurance_claims(hospital_id);
CREATE INDEX IF NOT EXISTS idx_claims_provider     ON insurance_claims(insurance_provider);
CREATE INDEX IF NOT EXISTS idx_claims_status       ON insurance_claims(claim_status);
CREATE INDEX IF NOT EXISTS idx_claims_fraud        ON insurance_claims(fraud_flag);
CREATE INDEX IF NOT EXISTS idx_claims_submission   ON insurance_claims(submission_date);
CREATE INDEX IF NOT EXISTS idx_claims_denial       ON insurance_claims(denial_code);


-- =============================================================
-- Table: billing
-- Description: Patient billing and payment records
-- Target: 15,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS billing (
    invoice_id          VARCHAR(20)     PRIMARY KEY,
    patient_id          VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    admission_id        VARCHAR(20)     REFERENCES admissions(admission_id),
    claim_id            VARCHAR(20)     REFERENCES insurance_claims(claim_id),
    hospital_id         VARCHAR(10)     REFERENCES hospitals(hospital_id),
    service_type        VARCHAR(100)    NOT NULL,  -- Room & Board | Surgery | Lab | Imaging | Pharmacy | ER | ICU | Therapy
    service_date        DATE            NOT NULL,
    billing_date        DATE            NOT NULL,
    cpt_code            VARCHAR(10),
    revenue_code        VARCHAR(10),               -- UB-04 revenue codes
    description         VARCHAR(300),
    quantity            DECIMAL(10,2)   DEFAULT 1,
    unit_price          DECIMAL(12,2),
    gross_amount        DECIMAL(12,2)   NOT NULL,
    insurance_adjustment DECIMAL(12,2)  DEFAULT 0,
    contractual_adjustment DECIMAL(12,2) DEFAULT 0,
    insurance_paid      DECIMAL(12,2)   DEFAULT 0,
    patient_paid        DECIMAL(12,2)   DEFAULT 0,
    amount_due          DECIMAL(12,2),
    payment_method      VARCHAR(50),               -- Insurance | Self-Pay | Credit Card | Payment Plan | Charity | Medicare | Medicaid
    payment_status      VARCHAR(30)     NOT NULL,  -- Pending | Partial | Paid | Written Off | Collections | Sent to Collections
    due_date            DATE,
    paid_date           DATE,
    days_outstanding    INT             GENERATED ALWAYS AS (
                            CASE
                                WHEN payment_status NOT IN ('Paid','Written Off')
                                THEN (CURRENT_DATE - billing_date)::INT
                                ELSE NULL
                            END
                        ) STORED,
    collection_agency   VARCHAR(100),
    bad_debt_flag       BOOLEAN         DEFAULT FALSE,
    charity_care_flag   BOOLEAN         DEFAULT FALSE,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_billing_patient     ON billing(patient_id);
CREATE INDEX IF NOT EXISTS idx_billing_admission   ON billing(admission_id);
CREATE INDEX IF NOT EXISTS idx_billing_hospital    ON billing(hospital_id);
CREATE INDEX IF NOT EXISTS idx_billing_status      ON billing(payment_status);
CREATE INDEX IF NOT EXISTS idx_billing_service     ON billing(service_type);
CREATE INDEX IF NOT EXISTS idx_billing_date        ON billing(billing_date);


-- =============================================================
-- Table: patient_feedback
-- Description: Patient satisfaction surveys (HCAHPS-style)
-- =============================================================

CREATE TABLE IF NOT EXISTS patient_feedback (
    feedback_id             VARCHAR(20)     PRIMARY KEY,
    patient_id              VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    admission_id            VARCHAR(20)     REFERENCES admissions(admission_id),
    hospital_id             VARCHAR(10)     REFERENCES hospitals(hospital_id),
    doctor_id               VARCHAR(15)     REFERENCES doctors(doctor_id),
    survey_type             VARCHAR(50),             -- Inpatient | Outpatient | ER | Telehealth
    survey_date             DATE            NOT NULL,
    -- HCAHPS Core Measures (1-10 scale)
    overall_rating          INT,                     -- Overall hospital rating (0-10)
    likelihood_recommend    INT,                     -- NPS question (0-10)
    doctor_communication    INT,                     -- 1-4: Never/Sometimes/Usually/Always
    nurse_communication     INT,
    staff_responsiveness    INT,
    pain_management         INT,
    medication_communication INT,
    discharge_information   INT,
    hospital_cleanliness    INT,
    hospital_quietness      INT,
    -- Open-ended
    comments                TEXT,
    improvement_suggestions TEXT,
    -- Derived scores
    nps_category            VARCHAR(15)     GENERATED ALWAYS AS (
                                CASE
                                    WHEN likelihood_recommend >= 9 THEN 'Promoter'
                                    WHEN likelihood_recommend >= 7 THEN 'Passive'
                                    ELSE 'Detractor'
                                END
                            ) STORED,
    -- NLP analysis
    sentiment_score         DECIMAL(5,4),
    nlp_topics              TEXT[],
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_patient    ON patient_feedback(patient_id);
CREATE INDEX IF NOT EXISTS idx_feedback_hospital   ON patient_feedback(hospital_id);
CREATE INDEX IF NOT EXISTS idx_feedback_doctor     ON patient_feedback(doctor_id);
CREATE INDEX IF NOT EXISTS idx_feedback_date       ON patient_feedback(survey_date);
CREATE INDEX IF NOT EXISTS idx_feedback_rating     ON patient_feedback(overall_rating);


-- =============================================================
-- Table: staff_schedule
-- Description: Staff scheduling and shift management
-- =============================================================

CREATE TABLE IF NOT EXISTS staff_schedule (
    schedule_id         VARCHAR(20)     PRIMARY KEY,
    employee_id         VARCHAR(15)     NOT NULL,
    hospital_id         VARCHAR(10)     REFERENCES hospitals(hospital_id),
    department_id       VARCHAR(15)     REFERENCES departments(department_id),
    employee_type       VARCHAR(50),               -- Physician | Nurse | PA | NP | Tech | Admin
    shift_type          VARCHAR(20)     NOT NULL,  -- Day | Evening | Night | On-Call
    shift_date          DATE            NOT NULL,
    start_time          TIME            NOT NULL,
    end_time            TIME            NOT NULL,
    scheduled_hours     DECIMAL(5,2),
    actual_start_time   TIME,
    actual_end_time     TIME,
    actual_hours        DECIMAL(5,2),
    overtime_hours      DECIMAL(5,2)    DEFAULT 0,
    status              VARCHAR(20)     DEFAULT 'Scheduled', -- Scheduled | Completed | Called Off | No-Show | Swapped
    call_off_reason     VARCHAR(200),
    replacement_id      VARCHAR(15),
    patients_assigned   INT,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_staff_employee      ON staff_schedule(employee_id);
CREATE INDEX IF NOT EXISTS idx_staff_hospital      ON staff_schedule(hospital_id);
CREATE INDEX IF NOT EXISTS idx_staff_department    ON staff_schedule(department_id);
CREATE INDEX IF NOT EXISTS idx_staff_date          ON staff_schedule(shift_date);
CREATE INDEX IF NOT EXISTS idx_staff_type          ON staff_schedule(shift_type);


-- =============================================================
-- Table: bed_utilization
-- Description: Real-time bed occupancy tracking
-- =============================================================

CREATE TABLE IF NOT EXISTS bed_utilization (
    bed_id              VARCHAR(20)     PRIMARY KEY,
    hospital_id         VARCHAR(10)     NOT NULL REFERENCES hospitals(hospital_id),
    department_id       VARCHAR(15)     REFERENCES departments(department_id),
    ward                VARCHAR(50)     NOT NULL,
    room_number         VARCHAR(10),
    bed_number          VARCHAR(10),
    bed_type            VARCHAR(30),               -- Medical | Surgical | ICU | CCU | NICU | Maternity | Psych
    is_isolation_room   BOOLEAN         DEFAULT FALSE,
    patient_id          VARCHAR(15),               -- NULL if unoccupied
    admission_id        VARCHAR(20),
    occupancy_status    VARCHAR(20)     NOT NULL,  -- Occupied | Available | Housekeeping | Maintenance | Blocked
    occupancy_start     TIMESTAMP,
    occupancy_end       TIMESTAMP,
    hours_occupied      DECIMAL(8,2)    GENERATED ALWAYS AS (
                            CASE
                                WHEN occupancy_start IS NOT NULL AND occupancy_end IS NOT NULL
                                THEN EXTRACT(EPOCH FROM (occupancy_end - occupancy_start)) / 3600
                                ELSE NULL
                            END
                        ) STORED,
    -- Turnover tracking
    cleaning_start      TIMESTAMP,
    cleaning_end        TIMESTAMP,
    cleaning_minutes    INT             GENERATED ALWAYS AS (
                            CASE
                                WHEN cleaning_start IS NOT NULL AND cleaning_end IS NOT NULL
                                THEN EXTRACT(EPOCH FROM (cleaning_end - cleaning_start))::INT / 60
                                ELSE NULL
                            END
                        ) STORED,
    last_updated        TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bed_hospital        ON bed_utilization(hospital_id);
CREATE INDEX IF NOT EXISTS idx_bed_ward            ON bed_utilization(ward);
CREATE INDEX IF NOT EXISTS idx_bed_status          ON bed_utilization(occupancy_status);
CREATE INDEX IF NOT EXISTS idx_bed_patient         ON bed_utilization(patient_id);
CREATE INDEX IF NOT EXISTS idx_bed_type            ON bed_utilization(bed_type);

COMMENT ON TABLE bed_utilization IS 'Real-time bed occupancy. Updated by admissions/discharge events. Key for capacity management and operational efficiency dashboards.';
