-- Medical Coding tables

CREATE TABLE coding_suggestions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id),
    encounter_id UUID REFERENCES encounters(id),
    patient_id UUID REFERENCES patients(id),

    -- Code details
    code TEXT NOT NULL,
    code_system TEXT NOT NULL,  -- icd10, cpt
    display TEXT,
    confidence FLOAT DEFAULT 0,

    -- Source evidence
    source_text TEXT,
    nlp_extraction_id TEXT,

    -- Specificity
    specificity_status TEXT DEFAULT 'optimal',
    alternatives TEXT[] DEFAULT '{}',

    -- Review
    reviewed_by UUID REFERENCES users(id),
    review_action TEXT DEFAULT 'pending',
    original_code TEXT,
    modification_reason TEXT,
    reviewed_at TIMESTAMPTZ,

    -- Compliance
    cci_check_result TEXT DEFAULT 'pass',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_coding_encounter ON coding_suggestions(encounter_id);
CREATE INDEX idx_coding_review ON coding_suggestions(review_action);

-- Claims tracking
CREATE TABLE claims (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id),
    encounter_id UUID REFERENCES encounters(id),
    patient_id UUID REFERENCES patients(id),

    -- Claim details
    claim_number TEXT,
    payer_id TEXT,
    payer_name TEXT,
    billed_amount FLOAT DEFAULT 0,
    allowed_amount FLOAT,
    paid_amount FLOAT,

    -- Codes
    cpt_codes TEXT[] DEFAULT '{}',
    icd10_codes TEXT[] DEFAULT '{}',

    -- Status
    status TEXT DEFAULT 'submitted',
    denial_reason TEXT,
    denial_code TEXT,

    -- Prediction
    denial_risk_score INTEGER,
    predicted_at TIMESTAMPTZ,

    submitted_at TIMESTAMPTZ,
    adjudicated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_claims_status ON claims(status);
CREATE INDEX idx_claims_payer ON claims(payer_id);
CREATE INDEX idx_claims_submitted ON claims(submitted_at DESC);
