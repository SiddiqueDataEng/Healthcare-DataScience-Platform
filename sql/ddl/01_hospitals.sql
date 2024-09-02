-- =============================================================
-- Table: hospitals
-- Description: Master table for hospital network nodes
-- =============================================================

CREATE TABLE IF NOT EXISTS hospitals (
    hospital_id         VARCHAR(10)     PRIMARY KEY,
    hospital_name       VARCHAR(200)    NOT NULL,
    hospital_type       VARCHAR(50)     NOT NULL,   -- Public | Private | Non-Profit | Teaching | Specialty
    city                VARCHAR(100)    NOT NULL,
    state               VARCHAR(100)    NOT NULL,
    country             VARCHAR(100)    NOT NULL     DEFAULT 'USA',
    zip_code            VARCHAR(10),
    latitude            DECIMAL(9,6),
    longitude           DECIMAL(9,6),
    phone               VARCHAR(20),
    website             VARCHAR(200),
    total_beds          INT             NOT NULL,
    icu_beds            INT,
    nicu_beds           INT,
    er_beds             INT,
    trauma_center       BOOLEAN         DEFAULT FALSE,
    trauma_level        VARCHAR(10),                -- Level I | Level II | Level III
    accreditation       VARCHAR(50),               -- JCI | DNV | ACHC | None
    established_year    INT,
    ceo_name            VARCHAR(100),
    network_id          VARCHAR(10),               -- parent health network
    is_active           BOOLEAN         DEFAULT TRUE,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_hospitals_state     ON hospitals(state);
CREATE INDEX IF NOT EXISTS idx_hospitals_type      ON hospitals(hospital_type);
CREATE INDEX IF NOT EXISTS idx_hospitals_network   ON hospitals(network_id);

-- Sample Data
INSERT INTO hospitals VALUES
('H001','City General Hospital','Public','Houston','Texas','USA','77001',29.7604,-95.3698,'713-555-0101','www.citygeneralhouston.org',1200,180,40,120,TRUE,'Level I','JCI',1952,'Dr. Patricia Moore','NET001',TRUE,NOW(),NOW()),
('H002','St. Mary Medical Center','Non-Profit','Dallas','Texas','USA','75201',32.7767,-96.7970,'214-555-0202','www.stmarymedical.org',850,120,30,80,TRUE,'Level II','DNV',1968,'Dr. James Wright','NET001',TRUE,NOW(),NOW()),
('H003','Pacific Coast Hospital','Private','Los Angeles','California','USA','90001',34.0522,-118.2437,'213-555-0303','www.pacificcoasthosp.com',1500,250,60,150,TRUE,'Level I','JCI',1945,'Dr. Susan Chen','NET002',TRUE,NOW(),NOW()),
('H004','Midwest Regional Medical','Public','Chicago','Illinois','USA','60601',41.8781,-87.6298,'312-555-0404','www.midwestregional.org',1100,160,45,100,TRUE,'Level I','JCI',1960,'Dr. Robert Johnson','NET003',TRUE,NOW(),NOW()),
('H005','Northeast University Hospital','Teaching','Boston','Massachusetts','USA','02101',42.3601,-71.0589,'617-555-0505','www.northeastuniv.edu',2000,320,80,200,TRUE,'Level I','JCI',1899,'Dr. Emily Clarke','NET004',TRUE,NOW(),NOW());

COMMENT ON TABLE hospitals IS 'Hospital network master reference table. Each row represents a physical hospital facility.';
COMMENT ON COLUMN hospitals.hospital_id IS 'Unique hospital identifier (H001-H999)';
COMMENT ON COLUMN hospitals.hospital_type IS 'Legal and operational classification of the hospital';
COMMENT ON COLUMN hospitals.trauma_level IS 'ACS trauma center designation level';
