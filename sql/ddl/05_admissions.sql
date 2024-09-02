-- =============================================================
-- Table: admissions
-- Description: Inpatient admissions and discharge tracking
-- Target: 2,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS admissions (
    admission_id            VARCHAR(20)     PRIMARY KEY,
    patient_id              VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    hospital_id             VARCHAR(10)     NOT NULL REFERENCES hospitals(hospital_id),
    department_id           VARCHAR(15)     REFERENCES departments(department_id),
    attending_doctor_id     VARCHAR(15)     REFERENCES doctors(doctor_id),
    admit_date              TIMESTAMP       NOT NULL,
    discharge_date          TIMESTAMP,
    length_of_stay          INT             GENERATED ALWAYS AS (
                                CASE
                                    WHEN discharge_date IS NOT NULL
                                    THEN EXTRACT(DAY FROM discharge_date - admit_date)::INT
                                    ELSE NULL
                                END
                            ) STORED,
    ward                    VARCHAR(50),               -- General | ICU | CCU | NICU | Surgical | Maternity
    room_number             VARCHAR(10),
    bed_number              VARCHAR(10),
    admission_type          VARCHAR(30)     NOT NULL,  -- Emergency | Elective | Urgent | Maternity | Transfer
    admission_source        VARCHAR(50),               -- ER | Direct | Transfer | Clinic | EMS
    discharge_status        VARCHAR(50),               -- Discharged Home | Transferred | AMA | Expired | Hospice
    discharge_destination   VARCHAR(100),
    primary_diagnosis_id    VARCHAR(20),
    drg_code                VARCHAR(10),               -- Diagnosis Related Group
    drg_description         VARCHAR(200),
    icu_hours               INT,
    ventilator_hours        INT,
    surgery_performed       BOOLEAN         DEFAULT FALSE,
    readmission_flag        BOOLEAN         DEFAULT FALSE,
    readmission_within_30d  BOOLEAN         DEFAULT FALSE,
    readmission_within_90d  BOOLEAN         DEFAULT FALSE,
    prior_admission_id      VARCHAR(20),
    expected_los_days       INT,
    actual_cost             DECIMAL(12,2),
    insurance_approved_cost DECIMAL(12,2),
    case_manager_id         VARCHAR(15),
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_adm_patient            ON admissions(patient_id);
CREATE INDEX IF NOT EXISTS idx_adm_hospital           ON admissions(hospital_id);
CREATE INDEX IF NOT EXISTS idx_adm_admit_date         ON admissions(admit_date);
CREATE INDEX IF NOT EXISTS idx_adm_discharge_status   ON admissions(discharge_status);
CREATE INDEX IF NOT EXISTS idx_adm_type               ON admissions(admission_type);
CREATE INDEX IF NOT EXISTS idx_adm_readmission        ON admissions(readmission_within_30d);
CREATE INDEX IF NOT EXISTS idx_adm_drg                ON admissions(drg_code);
CREATE INDEX IF NOT EXISTS idx_adm_ward               ON admissions(ward);
CREATE INDEX IF NOT EXISTS idx_adm_patient_date       ON admissions(patient_id, admit_date DESC);

COMMENT ON TABLE admissions IS '2M inpatient admissions. Core table for LOS prediction, readmission analysis, and revenue analytics. DRG code drives reimbursement.';
COMMENT ON COLUMN admissions.drg_code IS 'CMS Diagnosis Related Group - drives Medicare/Medicaid reimbursement rates';
COMMENT ON COLUMN admissions.readmission_within_30d IS 'CMS quality metric - 30-day all-cause readmission. Affects hospital reimbursement.';
