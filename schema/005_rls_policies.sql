-- Row-Level Security policies for multi-tenant isolation and HIPAA compliance

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE encounters ENABLE ROW LEVEL SECURITY;
ALTER TABLE prior_auth_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE coding_suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_usage ENABLE ROW LEVEL SECURITY;

-- Tenant isolation: users can only see data from their organization
CREATE POLICY org_isolation_users ON users
    FOR ALL USING (org_id = current_setting('app.current_org_id')::UUID);

CREATE POLICY org_isolation_patients ON patients
    FOR ALL USING (org_id = current_setting('app.current_org_id')::UUID);

CREATE POLICY org_isolation_encounters ON encounters
    FOR ALL USING (org_id = current_setting('app.current_org_id')::UUID);

CREATE POLICY org_isolation_pa ON prior_auth_requests
    FOR ALL USING (org_id = current_setting('app.current_org_id')::UUID);

CREATE POLICY org_isolation_coding ON coding_suggestions
    FOR ALL USING (org_id = current_setting('app.current_org_id')::UUID);

CREATE POLICY org_isolation_claims ON claims
    FOR ALL USING (org_id = current_setting('app.current_org_id')::UUID);

-- Audit log: append-only (no update/delete)
CREATE POLICY audit_insert_only ON audit_log
    FOR INSERT WITH CHECK (TRUE);

CREATE POLICY audit_read ON audit_log
    FOR SELECT USING (
        current_setting('app.current_role') IN ('admin', 'system')
    );

-- No UPDATE or DELETE policies on audit_log = immutable
