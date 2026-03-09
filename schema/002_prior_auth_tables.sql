-- Prior Authorization tables

CREATE TABLE prior_auth_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id),
    patient_id UUID REFERENCES patients(id),
    encounter_id UUID REFERENCES encounters(id),
    provider_id UUID REFERENCES users(id),

    -- Service details
    cpt_code TEXT NOT NULL,
    cpt_description TEXT,
    icd10_codes TEXT[] DEFAULT '{}',
    quantity INTEGER DEFAULT 1,
    urgency TEXT DEFAULT 'routine',

    -- Payer info
    payer_id TEXT NOT NULL,
    payer_name TEXT,

    -- Generated content (encrypted)
    clinical_summary_encrypted TEXT,
    medical_necessity_encrypted TEXT,
    supporting_docs TEXT[] DEFAULT '{}',
    missing_docs TEXT[] DEFAULT '{}',

    -- Status tracking
    status TEXT DEFAULT 'draft',
    auth_number TEXT,
    denial_reason TEXT,
    appeal_text_encrypted TEXT,

    -- Submission tracking
    submission_method TEXT,
    tracking_id TEXT,
    submitted_at TIMESTAMPTZ,
    decided_at TIMESTAMPTZ,

    -- Metrics
    generation_time_ms FLOAT,
    total_cost FLOAT DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pa_patient ON prior_auth_requests(patient_id);
CREATE INDEX idx_pa_status ON prior_auth_requests(status);
CREATE INDEX idx_pa_payer ON prior_auth_requests(payer_id);
CREATE INDEX idx_pa_created ON prior_auth_requests(created_at DESC);

-- PA status history (audit trail)
CREATE TABLE pa_status_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pa_id UUID REFERENCES prior_auth_requests(id),
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_by UUID REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
