-- =============================================================
-- Table: appointments
-- Description: Patient appointment scheduling and outcomes
-- Target: 10,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS appointments (
    appointment_id          VARCHAR(20)     PRIMARY KEY,
    patient_id              VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    doctor_id               VARCHAR(15)     NOT NULL REFERENCES doctors(doctor_id),
    hospital_id             VARCHAR(10)     NOT NULL REFERENCES hospitals(hospital_id),
    department_id           VARCHAR(15)     REFERENCES departments(department_id),
    appointment_date        DATE            NOT NULL,
    appointment_time        TIME,
    appointment_type        VARCHAR(50)     NOT NULL,  -- New Patient | Follow-Up | Consultation | Telehealth | Urgent
    visit_type              VARCHAR(30),               -- In-Person | Virtual | Phone
    reason_for_visit        VARCHAR(500),
    chief_complaint         VARCHAR(300),
    wait_time_minutes       INT,
    consultation_minutes    INT,
    appointment_status      VARCHAR(30)     NOT NULL,  -- Scheduled | Completed | Cancelled | No-Show | Rescheduled
    cancellation_reason     VARCHAR(200),
    no_show_reason          VARCHAR(200),
    followup_required       BOOLEAN         DEFAULT FALSE,
    followup_days           INT,
    followup_appointment_id VARCHAR(20),
    copay_amount            DECIMAL(10,2),
    insurance_verified      BOOLEAN         DEFAULT FALSE,
    referral_id             VARCHAR(20),
    referring_doctor_id     VARCHAR(15),
    notes                   TEXT,
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- Partition by appointment_date for performance at scale
-- CREATE TABLE appointments PARTITION BY RANGE (appointment_date);
-- CREATE TABLE appointments_2020 PARTITION OF appointments FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');
-- CREATE TABLE appointments_2021 PARTITION OF appointments FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');
-- CREATE TABLE appointments_2022 PARTITION OF appointments FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
-- CREATE TABLE appointments_2023 PARTITION OF appointments FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
-- CREATE TABLE appointments_2024 PARTITION OF appointments FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

-- Indexes
CREATE INDEX IF NOT EXISTS idx_appt_patient          ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appt_doctor           ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appt_hospital         ON appointments(hospital_id);
CREATE INDEX IF NOT EXISTS idx_appt_date             ON appointments(appointment_date);
CREATE INDEX IF NOT EXISTS idx_appt_status           ON appointments(appointment_status);
CREATE INDEX IF NOT EXISTS idx_appt_type             ON appointments(appointment_type);
CREATE INDEX IF NOT EXISTS idx_appt_patient_date     ON appointments(patient_id, appointment_date);

-- Composite index for no-show analysis
CREATE INDEX IF NOT EXISTS idx_appt_noshow_analysis  ON appointments(appointment_status, appointment_date, doctor_id);

COMMENT ON TABLE appointments IS '10M appointment records. Partitioned by appointment_date in production. Key table for no-show prediction and scheduling optimization.';
