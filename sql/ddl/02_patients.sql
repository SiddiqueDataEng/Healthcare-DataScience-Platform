-- =============================================================
-- Table: patients
-- Description: Patient demographics and registration
-- PHI table - all fields marked PHI require encryption/masking
-- =============================================================

CREATE TABLE IF NOT EXISTS patients (
    patient_id          VARCHAR(15)     PRIMARY KEY,
    first_name          VARCHAR(100)    NOT NULL,       -- PHI
    last_name           VARCHAR(100)    NOT NULL,       -- PHI
    gender              CHAR(1)         NOT NULL,       -- M | F | O (Other)
    dob                 DATE            NOT NULL,       -- PHI
    age                 INT             GENERATED ALWAYS AS (
                            DATE_PART('year', AGE(CURRENT_DATE, dob))::INT
                        ) STORED,
    ssn_hash            VARCHAR(64),                   -- SHA-256 hash of SSN (PHI - never store raw)
    ethnicity           VARCHAR(50),
    race                VARCHAR(50),
    blood_group         VARCHAR(5),                    -- A+|A-|B+|B-|AB+|AB-|O+|O-
    marital_status      VARCHAR(20),                   -- Single|Married|Divorced|Widowed
    occupation          VARCHAR(100),
    education_level     VARCHAR(50),
    annual_income_band  VARCHAR(20),                   -- <25K|25-50K|50-75K|75-100K|100K+
    email_hash          VARCHAR(64),                   -- PHI - hashed
    phone_hash          VARCHAR(64),                   -- PHI - hashed
    address_city        VARCHAR(100),                  -- PHI
    address_state       VARCHAR(100),
    address_country     VARCHAR(100)    DEFAULT 'USA',
    address_zip         VARCHAR(10),                   -- PHI
    hospital_id         VARCHAR(10)     REFERENCES hospitals(hospital_id),
    primary_physician_id VARCHAR(15),
    insurance_provider  VARCHAR(100),
    insurance_plan_type VARCHAR(50),                   -- HMO|PPO|EPO|Medicare|Medicaid|None
    registration_date   DATE            NOT NULL,
    last_visit_date     DATE,
    deceased_flag       BOOLEAN         DEFAULT FALSE,
    deceased_date       DATE,
    consent_research    BOOLEAN         DEFAULT FALSE,
    consent_marketing   BOOLEAN         DEFAULT FALSE,
    gdpr_erasure_flag   BOOLEAN         DEFAULT FALSE,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- Partitioning hint: partition by registration_date year in production
-- CREATE TABLE patients PARTITION BY RANGE (registration_date);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_patients_hospital     ON patients(hospital_id);
CREATE INDEX IF NOT EXISTS idx_patients_dob          ON patients(dob);
CREATE INDEX IF NOT EXISTS idx_patients_deceased     ON patients(deceased_flag);
CREATE INDEX IF NOT EXISTS idx_patients_registration ON patients(registration_date);
CREATE INDEX IF NOT EXISTS idx_patients_state        ON patients(address_state);
CREATE INDEX IF NOT EXISTS idx_patients_blood_group  ON patients(blood_group);
CREATE INDEX IF NOT EXISTS idx_patients_insurance    ON patients(insurance_provider);

-- Sample Data
INSERT INTO patients (patient_id, first_name, last_name, gender, dob, ethnicity, blood_group, marital_status, occupation, address_city, address_state, hospital_id, registration_date, deceased_flag) VALUES
('P0000001','John','Smith','M','1982-06-21','Caucasian','O+','Married','Engineer','Houston','Texas','H001','2020-04-01',FALSE),
('P0000002','Maria','Garcia','F','1975-11-14','Hispanic','A+','Single','Teacher','Dallas','Texas','H002','2019-08-15',FALSE),
('P0000003','David','Johnson','M','1990-03-08','African American','B+','Married','Accountant','Los Angeles','California','H003','2021-01-22',FALSE),
('P0000004','Jennifer','Williams','F','1968-09-30','Caucasian','AB+','Divorced','Nurse','Chicago','Illinois','H004','2018-06-10',FALSE),
('P0000005','Michael','Brown','M','1955-12-05','Caucasian','O-','Widowed','Retired','Boston','Massachusetts','H005','2017-03-28',FALSE);

COMMENT ON TABLE patients IS 'Central patient registry. Contains PHI - subject to HIPAA/GDPR controls. Minimum necessary access applies.';
COMMENT ON COLUMN patients.ssn_hash IS 'SHA-256 hash of SSN. Never store raw SSN in database.';
COMMENT ON COLUMN patients.gdpr_erasure_flag IS 'When TRUE, patient has requested GDPR erasure. PHI fields must be zeroed out.';
