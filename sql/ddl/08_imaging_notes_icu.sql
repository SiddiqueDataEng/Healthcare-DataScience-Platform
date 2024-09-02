-- =============================================================
-- Table: imaging_records
-- Description: Medical imaging metadata (images stored in object storage)
-- Target: 3,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS imaging_records (
    image_id            VARCHAR(20)     PRIMARY KEY,
    patient_id          VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    admission_id        VARCHAR(20)     REFERENCES admissions(admission_id),
    ordering_doctor_id  VARCHAR(15)     REFERENCES doctors(doctor_id),
    radiologist_id      VARCHAR(15)     REFERENCES doctors(doctor_id),
    hospital_id         VARCHAR(10)     REFERENCES hospitals(hospital_id),
    image_type          VARCHAR(50)     NOT NULL,  -- X-Ray | MRI | CT Scan | PET Scan | Ultrasound | Mammogram | DEXA
    modality            VARCHAR(20),               -- DICOM modality code: CR|MR|CT|PT|US|MG
    body_part           VARCHAR(100),              -- Chest | Brain | Abdomen | Spine | Knee | Pelvis
    laterality          VARCHAR(10),               -- Left | Right | Bilateral | NA
    image_date          TIMESTAMP       NOT NULL,
    study_instance_uid  VARCHAR(100)    UNIQUE,    -- DICOM Study Instance UID
    accession_number    VARCHAR(50),
    findings            TEXT,                      -- Radiology findings (NLP source)
    impression          TEXT,                      -- Radiologist impression/conclusion
    recommendations     TEXT,
    follow_up_required  BOOLEAN         DEFAULT FALSE,
    critical_finding    BOOLEAN         DEFAULT FALSE,
    critical_flag_time  TIMESTAMP,                -- When radiologist flagged critical
    pathology_noted     VARCHAR(500),
    image_quality       VARCHAR(20),               -- Excellent | Good | Fair | Poor | Non-diagnostic
    contrast_used       BOOLEAN         DEFAULT FALSE,
    contrast_type       VARCHAR(50),
    radiation_dose      DECIMAL(8,4),             -- mGy
    image_count         INT,                      -- Number of DICOM images in study
    image_storage_path  VARCHAR(500),             -- S3/blob path to DICOM files
    ai_interpretation   TEXT,                     -- AI/ML model findings
    ai_confidence_score DECIMAL(5,4),            -- 0.0000 to 1.0000
    pacs_system         VARCHAR(50),
    report_status       VARCHAR(30)    DEFAULT 'Final', -- Draft | Preliminary | Final | Addendum
    report_datetime     TIMESTAMP,
    created_at          TIMESTAMP      DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_img_patient      ON imaging_records(patient_id);
CREATE INDEX IF NOT EXISTS idx_img_admission    ON imaging_records(admission_id);
CREATE INDEX IF NOT EXISTS idx_img_type         ON imaging_records(image_type);
CREATE INDEX IF NOT EXISTS idx_img_date         ON imaging_records(image_date);
CREATE INDEX IF NOT EXISTS idx_img_critical     ON imaging_records(critical_finding);
CREATE INDEX IF NOT EXISTS idx_img_modality     ON imaging_records(modality);
CREATE INDEX IF NOT EXISTS idx_img_body_part    ON imaging_records(body_part);


-- =============================================================
-- Table: clinical_notes
-- Description: Unstructured clinical notes - PRIMARY NLP SOURCE
-- Target: 10,000,000 records
-- =============================================================

CREATE TABLE IF NOT EXISTS clinical_notes (
    note_id             VARCHAR(20)     PRIMARY KEY,
    patient_id          VARCHAR(15)     NOT NULL REFERENCES patients(patient_id),
    admission_id        VARCHAR(20)     REFERENCES admissions(admission_id),
    doctor_id           VARCHAR(15)     REFERENCES doctors(doctor_id),
    hospital_id         VARCHAR(10)     REFERENCES hospitals(hospital_id),
    note_datetime       TIMESTAMP       NOT NULL,
    note_type           VARCHAR(50)     NOT NULL,  -- Admission H&P | Progress Note | Discharge Summary | Consultation | Operative | Nursing | Radiology | Pathology
    department          VARCHAR(100),
    clinical_text       TEXT            NOT NULL,  -- Full unstructured note text
    -- NLP-extracted fields (populated by NLP pipeline)
    extracted_icd10_codes   TEXT[],               -- Array of predicted ICD-10 codes
    extracted_medications   TEXT[],               -- Extracted medication names
    extracted_entities      JSONB,                -- NER output: {symptoms:[], conditions:[], procedures:[]}
    sentiment_score         DECIMAL(5,4),         -- -1.0 to 1.0
    urgency_score           DECIMAL(5,4),         -- 0.0 to 1.0
    risk_score              DECIMAL(5,4),         -- 0.0 to 1.0
    summary                 TEXT,                 -- AI-generated summary
    key_findings            TEXT[],
    nlp_processed           BOOLEAN       DEFAULT FALSE,
    nlp_processed_at        TIMESTAMP,
    nlp_model_version       VARCHAR(50),
    word_count              INT,
    is_signed               BOOLEAN       DEFAULT FALSE,
    signed_by               VARCHAR(100),
    signed_at               TIMESTAMP,
    is_amended              BOOLEAN       DEFAULT FALSE,
    amendment_reason        TEXT,
    created_at              TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);

-- Sample clinical notes
INSERT INTO clinical_notes (note_id, patient_id, doctor_id, hospital_id, note_datetime, note_type, clinical_text, word_count) VALUES
('NOTE001','P0000001','DR0001','H001','2024-01-15 09:30:00','Admission H&P',
'CHIEF COMPLAINT: Chest pain and shortness of breath for 2 days.

HISTORY OF PRESENT ILLNESS:
Patient is a 43-year-old male with known history of hypertension and type 2 diabetes presenting with 2 days of progressive chest discomfort described as pressure-like, 7/10 in severity, radiating to the left arm. Associated with mild shortness of breath and diaphoresis. Denies nausea, vomiting, or syncope. Patient has been non-compliant with medications for past month.

PAST MEDICAL HISTORY:
1. Type 2 Diabetes Mellitus (diagnosed 2018) - HbA1c 8.9% last month
2. Essential Hypertension - uncontrolled
3. Hyperlipidemia
4. Former smoker - 15 pack-year history, quit 3 years ago

MEDICATIONS:
- Metformin 1000mg BID
- Lisinopril 10mg daily (non-compliant)
- Atorvastatin 40mg at bedtime

PHYSICAL EXAMINATION:
Vital Signs: BP 158/96, HR 88, RR 18, SpO2 96%, Temp 98.6°F
General: Alert, anxious-appearing male in mild distress
Cardiovascular: Regular rate and rhythm, no murmurs
Respiratory: Clear to auscultation bilaterally

ASSESSMENT AND PLAN:
1. Rule out acute coronary syndrome - Serial troponins, ECG, cardiology consult
2. Hypertension - resume Lisinopril, add amlodipine
3. Diabetes - endocrinology consult for medication optimization
4. Smoking cessation counseling provided',
185),
('NOTE002','P0000002','DR0002','H002','2024-02-20 14:15:00','Progress Note',
'PATIENT: 49-year-old female with hypertension and migraine.

SUBJECTIVE: Patient reports improvement in headache severity from 8/10 to 4/10 since starting topiramate. Still experiencing aura before episodes. Blood pressure at home readings averaging 145/88 per patient diary.

OBJECTIVE: BP 142/86, HR 72, well-appearing. Neurological exam intact. No focal deficits.

ASSESSMENT: 
1. Migraine with aura - partially controlled on topiramate 50mg BID
2. Hypertension - suboptimal control

PLAN:
1. Increase topiramate to 75mg BID in 2 weeks
2. Increase lisinopril to 20mg daily
3. Follow up in 4 weeks
4. MRI brain ordered to rule out secondary causes
5. Patient instructed to keep headache diary',
115);

CREATE INDEX IF NOT EXISTS idx_notes_patient        ON clinical_notes(patient_id);
CREATE INDEX IF NOT EXISTS idx_notes_admission      ON clinical_notes(admission_id);
CREATE INDEX IF NOT EXISTS idx_notes_doctor         ON clinical_notes(doctor_id);
CREATE INDEX IF NOT EXISTS idx_notes_datetime       ON clinical_notes(note_datetime);
CREATE INDEX IF NOT EXISTS idx_notes_type           ON clinical_notes(note_type);
CREATE INDEX IF NOT EXISTS idx_notes_nlp_processed  ON clinical_notes(nlp_processed);
-- Full text search index
CREATE INDEX IF NOT EXISTS idx_notes_fts            ON clinical_notes USING gin(to_tsvector('english', clinical_text));


-- =============================================================
-- Table: icu_vitals
-- Description: ICU monitoring data - every 5 seconds per patient
-- Target: 2,000,000,000 records (streaming + partitioned)
-- =============================================================

CREATE TABLE IF NOT EXISTS icu_vitals (
    event_id                BIGSERIAL       PRIMARY KEY,
    patient_id              VARCHAR(15)     NOT NULL,
    admission_id            VARCHAR(20),
    hospital_id             VARCHAR(10),
    bed_id                  VARCHAR(15),
    timestamp               TIMESTAMP       NOT NULL,
    -- Vital Signs
    heart_rate              INT,                       -- bpm
    blood_pressure_sys      INT,                       -- mmHg
    blood_pressure_dia      INT,                       -- mmHg
    mean_arterial_pressure  INT,                       -- mmHg
    spo2                    DECIMAL(5,2),              -- %
    respiration_rate        INT,                       -- breaths/min
    temperature             DECIMAL(5,2),              -- Celsius
    temperature_site        VARCHAR(20),               -- Oral|Rectal|Axillary|Tympanic|Rectal
    -- Advanced Monitoring
    end_tidal_co2           DECIMAL(5,2),              -- mmHg
    central_venous_pressure INT,                       -- mmHg
    intracranial_pressure   INT,                       -- mmHg
    cardiac_output          DECIMAL(5,2),              -- L/min
    -- Ventilator Parameters
    on_ventilator           BOOLEAN        DEFAULT FALSE,
    fio2                    DECIMAL(5,2),              -- %
    peep                    INT,                       -- cmH2O
    tidal_volume            INT,                       -- mL
    plateau_pressure        INT,                       -- cmH2O
    -- Alarms
    alarm_triggered         BOOLEAN        DEFAULT FALSE,
    alarm_type              VARCHAR(50),
    alarm_severity          VARCHAR(20),               -- Info | Warning | Critical
    -- Alert flags
    critical_vitals_flag    BOOLEAN        DEFAULT FALSE,
    device_id               VARCHAR(50),
    data_quality_flag       VARCHAR(20)    DEFAULT 'Good'  -- Good | Poor | Artifact | Missing
)
PARTITION BY RANGE (timestamp);

-- Create monthly partitions (example for 2024)
CREATE TABLE IF NOT EXISTS icu_vitals_2024_01 PARTITION OF icu_vitals
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE IF NOT EXISTS icu_vitals_2024_02 PARTITION OF icu_vitals
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
CREATE TABLE IF NOT EXISTS icu_vitals_2024_03 PARTITION OF icu_vitals
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');
CREATE TABLE IF NOT EXISTS icu_vitals_2024_04 PARTITION OF icu_vitals
    FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');
CREATE TABLE IF NOT EXISTS icu_vitals_2024_05 PARTITION OF icu_vitals
    FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');
CREATE TABLE IF NOT EXISTS icu_vitals_2024_06 PARTITION OF icu_vitals
    FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');

CREATE INDEX IF NOT EXISTS idx_icu_patient_ts   ON icu_vitals(patient_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_icu_alarm        ON icu_vitals(alarm_triggered, timestamp);
CREATE INDEX IF NOT EXISTS idx_icu_critical     ON icu_vitals(critical_vitals_flag, timestamp);

COMMENT ON TABLE icu_vitals IS '2B records. Partitioned by month. Ingested via Kafka streaming. Source for ICU mortality prediction ML model.';
COMMENT ON TABLE clinical_notes IS '10M unstructured notes. Full-text search enabled. Primary source for NLP pipelines: NER, ICD prediction, summarization.';
