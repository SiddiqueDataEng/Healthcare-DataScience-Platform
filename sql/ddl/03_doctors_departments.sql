-- =============================================================
-- Table: departments
-- Description: Hospital departments / clinical service lines
-- =============================================================

CREATE TABLE IF NOT EXISTS departments (
    department_id       VARCHAR(15)     PRIMARY KEY,
    hospital_id         VARCHAR(10)     NOT NULL REFERENCES hospitals(hospital_id),
    department_name     VARCHAR(100)    NOT NULL,
    department_code     VARCHAR(20)     NOT NULL,
    department_type     VARCHAR(50),               -- Clinical | Administrative | Diagnostic | Support
    floor_number        INT,
    building            VARCHAR(50),
    head_doctor_id      VARCHAR(15),
    total_staff         INT,
    total_beds          INT,
    is_active           BOOLEAN         DEFAULT TRUE,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dept_hospital   ON departments(hospital_id);
CREATE INDEX IF NOT EXISTS idx_dept_name       ON departments(department_name);

-- Insert standard departments for each hospital
INSERT INTO departments (department_id, hospital_id, department_name, department_code, department_type, total_beds) VALUES
('DEP001','H001','Cardiology','CARD','Clinical',60),
('DEP002','H001','Neurology','NEUR','Clinical',45),
('DEP003','H001','Oncology','ONCO','Clinical',80),
('DEP004','H001','Orthopedics','ORTH','Clinical',50),
('DEP005','H001','Pediatrics','PEDI','Clinical',70),
('DEP006','H001','Emergency','EMER','Clinical',120),
('DEP007','H001','Radiology','RADI','Diagnostic',0),
('DEP008','H001','Dermatology','DERM','Clinical',20),
('DEP009','H001','ICU','ICU','Clinical',180),
('DEP010','H001','Surgery','SURG','Clinical',90),
('DEP011','H001','Nephrology','NEPH','Clinical',35),
('DEP012','H001','Pulmonology','PULM','Clinical',40),
('DEP013','H001','Gastroenterology','GAST','Clinical',30),
('DEP014','H001','Endocrinology','ENDO','Clinical',25),
('DEP015','H001','Psychiatry','PSYC','Clinical',55),
('DEP016','H002','Cardiology','CARD','Clinical',40),
('DEP017','H002','Neurology','NEUR','Clinical',35),
('DEP018','H002','Emergency','EMER','Clinical',80),
('DEP019','H002','ICU','ICU','Clinical',120),
('DEP020','H002','Surgery','SURG','Clinical',60);


-- =============================================================
-- Table: doctors
-- Description: Physician and clinical staff profiles
-- =============================================================

CREATE TABLE IF NOT EXISTS doctors (
    doctor_id           VARCHAR(15)     PRIMARY KEY,
    hospital_id         VARCHAR(10)     NOT NULL REFERENCES hospitals(hospital_id),
    department_id       VARCHAR(15)     REFERENCES departments(department_id),
    first_name          VARCHAR(100)    NOT NULL,
    last_name           VARCHAR(100)    NOT NULL,
    gender              CHAR(1),
    specialization      VARCHAR(100)    NOT NULL,
    sub_specialization  VARCHAR(100),
    qualification       VARCHAR(200),              -- MD | DO | PhD | MBBS
    medical_license_no  VARCHAR(50),
    npi_number          VARCHAR(20),               -- National Provider Identifier
    years_experience    INT,
    joining_date        DATE,
    employment_type     VARCHAR(30),               -- Full-Time | Part-Time | Contract | Locum
    salary              DECIMAL(12,2),
    shift_type          VARCHAR(20),               -- Day | Night | Rotating
    is_active           BOOLEAN         DEFAULT TRUE,
    created_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_doctors_hospital        ON doctors(hospital_id);
CREATE INDEX IF NOT EXISTS idx_doctors_department      ON doctors(department_id);
CREATE INDEX IF NOT EXISTS idx_doctors_specialization  ON doctors(specialization);
CREATE INDEX IF NOT EXISTS idx_doctors_active          ON doctors(is_active);

-- Sample Data
INSERT INTO doctors VALUES
('DR0001','H001','DEP001','Robert','Anderson','M','Cardiology','Interventional Cardiology','MD, FACC','TX-12345','1234567890',18,'2006-07-01','Full-Time',280000,'Day',TRUE,NOW(),NOW()),
('DR0002','H001','DEP002','Sarah','Martinez','F','Neurology','Stroke Neurology','MD, PhD','TX-23456','2345678901',12,'2012-03-15','Full-Time',250000,'Rotating',TRUE,NOW(),NOW()),
('DR0003','H001','DEP003','James','Wilson','M','Oncology','Medical Oncology','MD, FASCO','TX-34567','3456789012',22,'2002-08-20','Full-Time',320000,'Day',TRUE,NOW(),NOW()),
('DR0004','H001','DEP009','Emily','Thompson','F','Critical Care','ICU Medicine','MD, FCCP','TX-45678','4567890123',9,'2015-01-10','Full-Time',260000,'Rotating',TRUE,NOW(),NOW()),
('DR0005','H001','DEP006','Michael','Davis','M','Emergency Medicine','Trauma','MD, FACEP','TX-56789','5678901234',15,'2009-06-01','Full-Time',240000,'Rotating',TRUE,NOW(),NOW());

COMMENT ON TABLE doctors IS 'Physician and clinical staff directory. NPI numbers are public identifiers. Salary is sensitive and access-controlled.';
COMMENT ON COLUMN doctors.npi_number IS 'CMS National Provider Identifier - 10 digit public identifier';
