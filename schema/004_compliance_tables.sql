-- HIPAA Compliance & Audit tables

-- Immutable audit log (HIPAA requirement: 6+ year retention)
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Who
    user_id TEXT NOT NULL,
    user_role TEXT,
    ip_address INET,
    session_id TEXT,

    -- What
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    phi_types_accessed TEXT[] DEFAULT '{}',

    -- Result
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,

    -- Context
    agent_name TEXT,
    reason TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Append-only: no UPDATE or DELETE allowed (enforced by RLS)
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_action ON audit_log(action);

-- Knowledge base for medical guidelines (pgvector)
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id),
    content TEXT NOT NULL,
    source_type TEXT NOT NULL,  -- guideline, policy, protocol, case
    title TEXT,
    source_url TEXT,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_knowledge_embedding ON knowledge_chunks
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_knowledge_source ON knowledge_chunks(source_type);

-- LLM usage tracking
CREATE TABLE llm_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id),
    agent_name TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost FLOAT DEFAULT 0,
    latency_ms FLOAT DEFAULT 0,
    cached BOOLEAN DEFAULT FALSE,
    task_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_llm_usage_agent ON llm_usage(agent_name);
CREATE INDEX idx_llm_usage_date ON llm_usage(created_at DESC);

-- Daily cost summary (materialized for dashboards)
CREATE TABLE daily_cost_summary (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES organizations(id),
    date DATE NOT NULL,
    agent_name TEXT NOT NULL,
    total_cost FLOAT DEFAULT 0,
    total_requests INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    avg_latency_ms FLOAT DEFAULT 0,
    UNIQUE(org_id, date, agent_name)
);
