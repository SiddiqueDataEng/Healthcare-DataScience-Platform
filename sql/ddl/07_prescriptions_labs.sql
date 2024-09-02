-- =============================================================
-- Table: prescriptions
-- Description: Medication prescriptions and dispensing
-- Target: 20,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS prescriptions (
    prescription_id     VARCHAR(20)     PRIMARY KEY,
    patient_id          VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    doctor_id           VARCHAR(15)     NOT NULL REFERENCES doctors(doctor_id),
    admission_id        VARCHAR(20)     REFERENCES admissions(admission_id),
    hospital_id         VARCHAR(10)     REFERENCES hospitals(hospital_id),
    ndc_code            VARCHAR(15),               -- National Drug Code
    rxnorm_code         VARCHAR(15),               -- RxNorm code
    medication_name     VARCHAR(200)    NOT NULL,
    generic_name        VARCHAR(200),
    drug_class          VARCHAR(100),              -- ACE Inhibitor | Beta Blocker | Statin | etc.
    dosage              VARCHAR(100)    NOT NULL,  -- e.g., 10mg
    dosage_unit         VARCHAR(20),               -- mg | mcg | mL | units
    route               VARCHAR(30),               -- Oral | IV | IM | SC | Topical | Inhaled
    frequency           VARCHAR(50)     NOT NULL,  -- Once daily | BID | TID | QID | PRN
    start_date          DATE            NOT NULL,
    end_date            DATE,
    days_supply         INT,
    quantity_dispensed  DECIMAL(10,2),
    refill_count        INT             DEFAULT 0,
    max_refills         INT             DEFAULT 0,
    last_refill_date    DATE,
    pharmacy_id         VARCHAR(20),
    controlled_substance BOOLEAN        DEFAULT FALSE,
    dea_schedule        VARCHAR(5),                -- Schedule I-V
    diagnosis_code      VARCHAR(10),
    prior_auth_required BOOLEAN         DEFAULT FALSE,
    prior_auth_approved BOOLEAN,
    prescription_status VARCHAR(30)     DEFAULT 'Active', -- Active | Discontinued | Expired | On Hold
    discontinued_reason VARCHAR(200),
    adverse_reaction    BOOLEAN         DEFAULT FALSE,
    notes               TEXT,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- Common medications reference
CREATE TABLE IF NOT EXISTS medications_reference (
    ndc_code            VARCHAR(15)     PRIMARY KEY,
    medication_name     VARCHAR(200),
    generic_name        VARCHAR(200),
    drug_class          VARCHAR(100),
    controlled_schedule VARCHAR(5),
    avg_cost_per_unit   DECIMAL(10,4)
);

INSERT INTO medications_reference VALUES
('0069-4190-30','Lipitor 10mg','Atorvastatin','Statin',NULL,0.85),
('0006-0207-31','Zocor 20mg','Simvastatin','Statin',NULL,0.42),
('0071-0155-23','Norvasc 5mg','Amlodipine','Calcium Channel Blocker',NULL,0.35),
('0006-0014-54','Vasotec 10mg','Enalapril','ACE Inhibitor',NULL,0.28),
('0310-0271-30','Metformin 500mg','Metformin','Biguanide',NULL,0.10),
('0093-1075-01','Glucophage 1000mg','Metformin HCL','Biguanide',NULL,0.20),
('0002-4210-30','Humalog 100U/mL','Insulin Lispro','Insulin',NULL,1.20),
('0781-1516-42','Lisinopril 10mg','Lisinopril','ACE Inhibitor',NULL,0.08),
('0006-0952-31','Cozaar 50mg','Losartan','ARB',NULL,0.55),
('65162-0175-11','Metoprolol 50mg','Metoprolol Tartrate','Beta Blocker',NULL,0.15),
('0078-0359-34','Diovan 160mg','Valsartan','ARB',NULL,2.50),
('0025-1550-50','Plavix 75mg','Clopidogrel','Antiplatelet',NULL,1.80),
('0069-4190-66','Eliquis 5mg','Apixaban','Anticoagulant',NULL,8.50),
('0006-0107-28','Januvia 100mg','Sitagliptin','DPP-4 Inhibitor',NULL,12.00),
('0074-3799-60','Synthroid 100mcg','Levothyroxine','Thyroid',NULL,0.35),
('0245-0148-01','Amoxicillin 500mg','Amoxicillin','Antibiotic',NULL,0.25),
('0378-0268-05','Azithromycin 250mg','Azithromycin','Macrolide Antibiotic',NULL,0.90),
('0603-3533-32','Hydrocodone 5mg','Hydrocodone/APAP','Opioid','II',2.50),
('0093-0537-05','Oxycodone 10mg','Oxycodone HCL','Opioid','II',3.80),
('0405-0488-01','Alprazolam 0.5mg','Alprazolam','Benzodiazepine','IV',0.35);

CREATE INDEX IF NOT EXISTS idx_rx_patient        ON prescriptions(patient_id);
CREATE INDEX IF NOT EXISTS idx_rx_doctor         ON prescriptions(doctor_id);
CREATE INDEX IF NOT EXISTS idx_rx_medication     ON prescriptions(medication_name);
CREATE INDEX IF NOT EXISTS idx_rx_drug_class     ON prescriptions(drug_class);
CREATE INDEX IF NOT EXISTS idx_rx_start_date     ON prescriptions(start_date);
CREATE INDEX IF NOT EXISTS idx_rx_controlled     ON prescriptions(controlled_substance);
CREATE INDEX IF NOT EXISTS idx_rx_status         ON prescriptions(prescription_status);


-- =============================================================
-- Table: lab_results
-- Description: Laboratory test results
-- Target: 50,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS lab_results (
    result_id           VARCHAR(25)     PRIMARY KEY,
    patient_id          VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    admission_id        VARCHAR(20)     REFERENCES admissions(admission_id),
    ordering_doctor_id  VARCHAR(15)     REFERENCES doctors(doctor_id),
    hospital_id         VARCHAR(10)     REFERENCES hospitals(hospital_id),
    loinc_code          VARCHAR(15),               -- LOINC standard lab code
    test_name           VARCHAR(200)    NOT NULL,
    test_panel          VARCHAR(100),              -- CBC | CMP | Lipid Panel | etc.
    result_value        VARCHAR(50),               -- Stored as varchar for flexibility (can be numeric or text)
    result_numeric      DECIMAL(15,4),             -- Numeric value for analysis
    unit                VARCHAR(50),
    reference_range_low  DECIMAL(15,4),
    reference_range_high DECIMAL(15,4),
    reference_range_text VARCHAR(100),
    abnormal_flag       VARCHAR(10),               -- H | L | HH | LL | A | Normal
    critical_flag       BOOLEAN         DEFAULT FALSE,
    collection_datetime TIMESTAMP       NOT NULL,
    received_datetime   TIMESTAMP,
    resulted_datetime   TIMESTAMP,
    specimen_type       VARCHAR(50),               -- Blood | Urine | CSF | Tissue | Swab
    lab_method          VARCHAR(100),
    result_status       VARCHAR(20)     DEFAULT 'Final', -- Preliminary | Final | Corrected | Cancelled
    verified_by         VARCHAR(100),
    notes               TEXT,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- LOINC reference for common lab tests
CREATE TABLE IF NOT EXISTS loinc_reference (
    loinc_code          VARCHAR(15)     PRIMARY KEY,
    test_name           VARCHAR(200),
    long_name           VARCHAR(500),
    panel               VARCHAR(100),
    unit                VARCHAR(50),
    ref_range_low       DECIMAL(15,4),
    ref_range_high      DECIMAL(15,4),
    critical_low        DECIMAL(15,4),
    critical_high       DECIMAL(15,4)
);

INSERT INTO loinc_reference VALUES
('4548-4',  'HbA1c',                   'Hemoglobin A1c/Hemoglobin.total in Blood',    'Diabetes Panel', '%',    4.0,  5.7,   NULL, 14.0),
('2345-7',  'Glucose',                 'Glucose [Mass/volume] in Serum or Plasma',    'CMP',            'mg/dL',70.0, 99.0,  40.0, 500.0),
('2160-0',  'Creatinine',              'Creatinine [Mass/volume] in Serum or Plasma', 'CMP',            'mg/dL',0.7,  1.3,   NULL, 10.0),
('3094-0',  'BUN',                     'Urea nitrogen [Mass/volume] in Serum',        'CMP',            'mg/dL',7.0,  20.0,  NULL, 100.0),
('17861-6', 'Calcium',                 'Calcium [Mass/volume] in Serum or Plasma',    'CMP',            'mg/dL',8.5,  10.2,  6.0,  13.5),
('2823-3',  'Potassium',               'Potassium [Moles/volume] in Serum or Plasma', 'CMP',            'mEq/L',3.5,  5.1,   2.5,  6.5),
('2951-2',  'Sodium',                  'Sodium [Moles/volume] in Serum or Plasma',    'CMP',            'mEq/L',136.0,145.0, 120.0,160.0),
('2028-9',  'CO2',                     'Carbon dioxide, total [Moles/volume] Serum',  'CMP',            'mEq/L',22.0, 29.0,  NULL, NULL),
('1742-6',  'ALT',                     'Alanine aminotransferase [Enzymatic activity]','LFT',           'U/L',  7.0,  56.0,  NULL, 1000.0),
('1920-8',  'AST',                     'Aspartate aminotransferase [Enzymatic activity]','LFT',         'U/L',  10.0, 40.0,  NULL, 1000.0),
('14804-9', 'LDL Cholesterol',         'Cholesterol in LDL [Mass/volume] in Serum',  'Lipid Panel',    'mg/dL',NULL, 100.0, NULL, NULL),
('2085-9',  'HDL Cholesterol',         'Cholesterol in HDL [Mass/volume] in Serum',  'Lipid Panel',    'mg/dL',40.0, NULL,  NULL, NULL),
('2093-3',  'Total Cholesterol',       'Cholesterol [Mass/volume] in Serum',          'Lipid Panel',    'mg/dL',NULL, 200.0, NULL, NULL),
('6301-6',  'INR',                     'INR in Platelet poor plasma by Coagulation',  'Coagulation',    'INR',  0.8,  1.2,   NULL, 5.0),
('26464-8', 'WBC',                     'Leukocytes [#/volume] in Blood',              'CBC',            '10^3/uL',4.5,11.0, 2.0,  30.0),
('718-7',   'Hemoglobin',              'Hemoglobin [Mass/volume] in Blood',           'CBC',            'g/dL', 12.0, 17.5,  7.0,  NULL),
('777-3',   'Platelets',               'Platelets [#/volume] in Blood',               'CBC',            '10^3/uL',150.0,400.0,50.0,1000.0),
('10839-9', 'Troponin I',              'Troponin I.cardiac [Mass/volume] in Serum',   'Cardiac',        'ng/mL',NULL, 0.04,  NULL, NULL),
('33762-6', 'BNP',                     'Natriuretic peptide.B prohormone N-Term',     'Cardiac',        'pg/mL',NULL, 125.0, NULL, NULL),
('11579-0', 'TSH',                     'Thyrotropin [Units/volume] in Serum',         'Thyroid',        'mIU/L',0.4,  4.0,   NULL, NULL);

-- Partition by collection_datetime
CREATE INDEX IF NOT EXISTS idx_lab_patient        ON lab_results(patient_id);
CREATE INDEX IF NOT EXISTS idx_lab_admission      ON lab_results(admission_id);
CREATE INDEX IF NOT EXISTS idx_lab_loinc          ON lab_results(loinc_code);
CREATE INDEX IF NOT EXISTS idx_lab_test_name      ON lab_results(test_name);
CREATE INDEX IF NOT EXISTS idx_lab_collection     ON lab_results(collection_datetime);
CREATE INDEX IF NOT EXISTS idx_lab_abnormal       ON lab_results(abnormal_flag);
CREATE INDEX IF NOT EXISTS idx_lab_critical       ON lab_results(critical_flag);
CREATE INDEX IF NOT EXISTS idx_lab_panel          ON lab_results(test_panel);

COMMENT ON TABLE lab_results IS '50M lab records. Uses LOINC coding standard. Critical results trigger alerts. Key features for ML models.';
