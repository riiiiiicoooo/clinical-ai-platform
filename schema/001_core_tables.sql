-- Core tables for Clinical AI Platform
-- Supabase PostgreSQL with encryption at rest (HIPAA compliant)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Organizations (multi-tenant)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    fhir_base_url TEXT,
    ehr_type TEXT DEFAULT 'epic',  -- epic, cerner, meditech
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id),
    clerk_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'clinician',
    npi TEXT,
    specialty TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Patients (PHI — encrypted fields)
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id),
    fhir_id TEXT NOT NULL,
    mrn_encrypted TEXT,  -- Encrypted MRN
    name_encrypted TEXT, -- Encrypted name
    dob_encrypted TEXT,  -- Encrypted DOB
    gender TEXT,
    payer_id TEXT,
    member_id_encrypted TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, fhir_id)
);

-- Encounters
CREATE TABLE encounters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id),
    patient_id UUID REFERENCES patients(id),
    fhir_id TEXT,
    encounter_type TEXT,
    encounter_class TEXT,
    provider_id UUID REFERENCES users(id),
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    status TEXT DEFAULT 'in-progress',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_encounters_patient ON encounters(patient_id);
CREATE INDEX idx_encounters_provider ON encounters(provider_id);
CREATE INDEX idx_encounters_date ON encounters(period_start DESC);
