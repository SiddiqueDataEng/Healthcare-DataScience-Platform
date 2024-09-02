-- =============================================================
-- Table: diagnoses
-- Description: ICD-10 coded clinical diagnoses
-- Target: 15,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS diagnoses (
    diagnosis_id        VARCHAR(20)     PRIMARY KEY,
    patient_id          VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    admission_id        VARCHAR(20)     REFERENCES admissions(admission_id),
    appointment_id      VARCHAR(20)     REFERENCES appointments(appointment_id),
    doctor_id           VARCHAR(15)     REFERENCES doctors(doctor_id),
    hospital_id         VARCHAR(10)     REFERENCES hospitals(hospital_id),
    icd10_code          VARCHAR(10)     NOT NULL,   -- e.g., E11.9, I10, J18.9
    icd10_category      VARCHAR(5),                -- First 3 chars of ICD-10
    disease_name        VARCHAR(300)    NOT NULL,
    disease_category    VARCHAR(100),              -- Cardiovascular | Respiratory | Endocrine | etc.
    diagnosis_date      DATE            NOT NULL,
    diagnosis_type      VARCHAR(30),               -- Primary | Secondary | Comorbidity | Complication
    severity            VARCHAR(20),               -- Mild | Moderate | Severe | Critical
    chronic_flag        BOOLEAN         DEFAULT FALSE,
    acute_flag          BOOLEAN         DEFAULT FALSE,
    status              VARCHAR(30),               -- Active | Resolved | Chronic | In Remission
    onset_date          DATE,
    resolution_date     DATE,
    hcc_code            VARCHAR(10),               -- Hierarchical Condition Category (risk scoring)
    snomed_code         VARCHAR(20),               -- SNOMED CT code
    confirmed_flag      BOOLEAN         DEFAULT TRUE,
    notes               TEXT,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- Reference table for ICD-10 codes
CREATE TABLE IF NOT EXISTS icd10_reference (
    icd10_code          VARCHAR(10)     PRIMARY KEY,
    icd10_description   VARCHAR(500)    NOT NULL,
    icd10_category      VARCHAR(5),
    category_description VARCHAR(200),
    chapter             VARCHAR(200),
    is_billable         BOOLEAN         DEFAULT TRUE,
    hcc_code            VARCHAR(10)
);

-- Load key ICD-10 codes
INSERT INTO icd10_reference VALUES
('E11.9',  'Type 2 diabetes mellitus without complications',                          'E11','Diabetes mellitus','Endocrine',TRUE,'19'),
('E11.65', 'Type 2 diabetes with hyperglycemia',                                     'E11','Diabetes mellitus','Endocrine',TRUE,'19'),
('I10',    'Essential (primary) hypertension',                                        'I10','Hypertension','Cardiovascular',TRUE,'85'),
('I21.9',  'Acute myocardial infarction, unspecified',                               'I21','AMI','Cardiovascular',TRUE,'86'),
('I50.9',  'Heart failure, unspecified',                                              'I50','Heart failure','Cardiovascular',TRUE,'85'),
('I63.9',  'Cerebral infarction, unspecified',                                        'I63','Stroke','Cardiovascular',TRUE,'100'),
('J18.9',  'Pneumonia, unspecified organism',                                         'J18','Pneumonia','Respiratory',TRUE,'114'),
('J44.1',  'Chronic obstructive pulmonary disease with acute exacerbation',          'J44','COPD','Respiratory',TRUE,'111'),
('J45.50', 'Severe persistent asthma, uncomplicated',                                 'J45','Asthma','Respiratory',TRUE,NULL),
('N18.3',  'Chronic kidney disease, stage 3 (moderate)',                             'N18','CKD','Genitourinary',TRUE,'137'),
('N18.6',  'End-stage renal disease',                                                 'N18','CKD','Genitourinary',TRUE,'136'),
('C34.10', 'Malignant neoplasm of upper lobe, bronchus or lung, unspecified side',   'C34','Lung Cancer','Neoplasm',TRUE,'9'),
('C50.919','Malignant neoplasm of unspecified site of unspecified female breast',     'C50','Breast Cancer','Neoplasm',TRUE,'10'),
('U07.1',  'COVID-19',                                                                'U07','COVID-19','Infectious',TRUE,NULL),
('A41.9',  'Sepsis, unspecified organism',                                            'A41','Sepsis','Infectious',TRUE,'2'),
('F32.9',  'Major depressive disorder, single episode, unspecified',                 'F32','Depression','Mental Health',TRUE,'59'),
('F41.1',  'Generalized anxiety disorder',                                            'F41','Anxiety','Mental Health',TRUE,NULL),
('M54.5',  'Low back pain',                                                            'M54','Back Pain','Musculoskeletal',TRUE,NULL),
('K21.0',  'Gastro-esophageal reflux disease with esophagitis',                      'K21','GERD','Digestive',TRUE,NULL),
('G43.909','Migraine, unspecified, not intractable, without status migrainosus',     'G43','Migraine','Neurological',TRUE,NULL);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_diag_patient         ON diagnoses(patient_id);
CREATE INDEX IF NOT EXISTS idx_diag_admission        ON diagnoses(admission_id);
CREATE INDEX IF NOT EXISTS idx_diag_icd10           ON diagnoses(icd10_code);
CREATE INDEX IF NOT EXISTS idx_diag_date            ON diagnoses(diagnosis_date);
CREATE INDEX IF NOT EXISTS idx_diag_chronic         ON diagnoses(chronic_flag);
CREATE INDEX IF NOT EXISTS idx_diag_type            ON diagnoses(diagnosis_type);
CREATE INDEX IF NOT EXISTS idx_diag_category        ON diagnoses(disease_category);


-- =============================================================
-- Table: procedures
-- Description: CPT-coded clinical procedures
-- Target: 8,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS procedures (
    procedure_id        VARCHAR(20)     PRIMARY KEY,
    patient_id          VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    admission_id        VARCHAR(20)     REFERENCES admissions(admission_id),
    doctor_id           VARCHAR(15)     REFERENCES doctors(doctor_id),
    hospital_id         VARCHAR(10)     REFERENCES hospitals(hospital_id),
    cpt_code            VARCHAR(10)     NOT NULL,
    procedure_name      VARCHAR(300)    NOT NULL,
    procedure_category  VARCHAR(100),
    procedure_date      TIMESTAMP       NOT NULL,
    duration_minutes    INT,
    anesthesia_type     VARCHAR(50),               -- General | Local | Regional | Sedation | None
    outcome             VARCHAR(50),               -- Successful | Complication | Abandoned | Pending
    complication_flag   BOOLEAN         DEFAULT FALSE,
    complication_details TEXT,
    performing_doctor_id VARCHAR(15),
    assisting_doctor_id  VARCHAR(15),
    operating_room      VARCHAR(20),
    facility_fee        DECIMAL(10,2),
    physician_fee       DECIMAL(10,2),
    notes               TEXT,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- CPT Reference
CREATE TABLE IF NOT EXISTS cpt_reference (
    cpt_code            VARCHAR(10)     PRIMARY KEY,
    cpt_description     VARCHAR(500),
    cpt_category        VARCHAR(100),
    avg_duration_min    INT,
    avg_facility_fee    DECIMAL(10,2),
    rvu                 DECIMAL(8,2)    -- Relative Value Unit
);

INSERT INTO cpt_reference VALUES
('99213','Office visit, established patient, 20-29 minutes','E&M',25,150.00,1.30),
('99214','Office visit, established patient, 30-39 minutes','E&M',35,200.00,1.92),
('99232','Subsequent hospital care, 25 minutes','E&M',25,180.00,1.39),
('93000','Electrocardiogram, routine ECG','Cardiology',15,100.00,0.17),
('93306','Echocardiography, transthoracic','Cardiology',45,800.00,4.55),
('93458','Left heart catheterization','Cardiology',90,5000.00,10.22),
('27447','Total knee replacement','Orthopedics',120,15000.00,22.37),
('27130','Total hip replacement','Orthopedics',100,15000.00,22.62),
('47562','Laparoscopic cholecystectomy','Surgery',60,5000.00,18.62),
('45378','Colonoscopy, diagnostic','Gastroenterology',30,2500.00,3.69),
('71046','Chest X-Ray, 2 views','Radiology',15,200.00,0.32),
('70553','MRI Brain w/o and with contrast','Radiology',60,2500.00,6.35),
('74178','CT abdomen and pelvis w/ contrast','Radiology',45,2000.00,5.05),
('36415','Collection of venous blood','Lab',5,25.00,0.17),
('90837','Psychotherapy, 60 minutes','Psychiatry',60,200.00,1.78);

CREATE INDEX IF NOT EXISTS idx_proc_patient       ON procedures(patient_id);
CREATE INDEX IF NOT EXISTS idx_proc_admission     ON procedures(admission_id);
CREATE INDEX IF NOT EXISTS idx_proc_cpt           ON procedures(cpt_code);
CREATE INDEX IF NOT EXISTS idx_proc_date          ON procedures(procedure_date);
CREATE INDEX IF NOT EXISTS idx_proc_outcome       ON procedures(outcome);

COMMENT ON TABLE diagnoses IS '15M diagnosis records using ICD-10 coding standard. Supports disease trend analysis, risk scoring, and ML feature engineering.';
COMMENT ON TABLE procedures IS '8M CPT-coded procedure records. Drives revenue analytics and surgical outcome analysis.';
