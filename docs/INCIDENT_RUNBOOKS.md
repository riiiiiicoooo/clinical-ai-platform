# Clinical AI Platform — Incident Runbooks

**Last Updated:** March 2026
**Severity Levels:** P0 (patient harm risk), P1 (SLO breach + clinician impact), P2 (degraded service)

---

## Incident Runbook 1: Unencrypted PHI Exposure in Database Logs or Backups

**Likelihood:** Medium (1-2x per year across portfolio)
**Severity:** P0 (HIPAA violation, regulatory reporting required)
**Detection Symptoms:** Audit log alert, security scan flag, or external party report

### Detection

**Automated triggers:**
- Log scan shows plaintext SSN, DOB, or medical record number in database slow-query logs
- `phi-encryption-audit` job detects unencrypted values in `PHI_TRANSACTIONS` table (should be all encrypted)
- S3 backup scan finds unencrypted snapshot containing patient identifiers

**Manual triggers:**
- Security researcher finds unencrypted data in snapshot (e.g., via AWS forensics API)
- Compliance team reports: "We found patient names in the audit log"

### Diagnosis (First 15 minutes)

1. **Confirm the scope:**
   ```sql
   SELECT COUNT(*), MAX(created_at) FROM audit_logs
   WHERE log_content LIKE '%[0-9]{3}-[0-9]{2}-[0-9]{4}%'
   AND created_at > NOW() - INTERVAL '24 hours';
   ```
   Determine: How many patients? How long has this been happening?

2. **Check encryption status:**
   ```sql
   SELECT * FROM phi_transactions
   WHERE encryption_status = 'UNENCRYPTED'
   OR decryption_failed = TRUE
   ORDER BY created_at DESC LIMIT 100;
   ```

3. **Determine exposure vector:**
   - Database logs (recoverable via log rotation; most contained)
   - S3 backups (more permanent; requires AWS forensics)
   - CloudWatch logs (visible to anyone with CloudWatch access; highest risk)
   - Slow query logs (only visible to database admin; moderate risk)

4. **Check if PHI reached external systems:**
   ```sql
   SELECT * FROM outbound_api_calls
   WHERE (response_body LIKE '%SSN%' OR request_body LIKE '%[0-9]{3}-[0-9]{2}%')
   AND created_at > NOW() - INTERVAL '24 hours';
   ```
   (This should be empty for compliant systems; if not, breach escalates to BREACH_NOTIFICATION_REQUIRED)

### Remediation (First 1 hour)

**Immediate:**
1. **Isolate:** Disable affected logging stream or database replica
2. **Purge:** Delete unencrypted logs from CloudWatch (logs older than 90 days can be archived)
   - Use AWS CLI: `aws logs delete-log-group --log-group-name /aws/rds/instance/...`
3. **Rotate keys:** If encryption key was used to encrypt sensitive data, rotate encryption keys immediately
4. **Notification:** Page incident commander and compliance officer (even if not during business hours)

**Within 1 hour:**
1. **Run RCA:** Why did encryption fail? Review code changes in last 48 hours
2. **Fix:** Deploy fix to prevent recurrence (e.g., force encryption at application layer, add validation)
3. **Audit trail:** Generate immutable report of what was exposed, when, and why

**Within 24 hours:**
1. **Determine if breach notification required:**
   - Per HIPAA: Breach = unauthorized acquisition + reasonable likelihood of compromise
   - If unencrypted data reached CloudWatch (accessible to engineers): Likely breach
   - If unencrypted data was in slow query logs (database admin only): Probably not breach (limited access)
   - Consult legal/compliance
2. **If breach notification required:** Notify affected individuals within 60 days
3. **Regulator notification:** State medical board + HHS if >500 individuals affected

### Communication Template

**Internal (Slack #incident-ops):**
```
🚨 P0: Unencrypted PHI in [LOCATION: database logs / S3 backups / CloudWatch]

Scope: ~[N] patients, [TIME RANGE]
Exposure vector: [logs / backups / external system]
Status: Contained (logs deleted) | Ongoing (still investigating)

Actions:
- [ ] Confirm scope and exposure
- [ ] Disable logging/delete unencrypted data
- [ ] Rotate encryption keys
- [ ] Determine breach notification requirement
- [ ] Deploy fix to prevent recurrence

ETA to all-clear: [TIME]
On-call: [NAME], [SLACK HANDLE]
```

**External (if breach notification required):**
```
Subject: Notice of Privacy Incident — Clinical AI Platform

Dear [PATIENT NAME],

We are writing to inform you of a security incident that may have affected your health
information. On [DATE], we discovered that some patient data may have been exposed due to
[BRIEF EXPLANATION: encryption configuration issue, log exposure, etc.].

We have taken the following steps to protect you:
- Immediately isolated and removed the exposed data
- Updated our security controls to prevent this in the future
- Notified law enforcement [if applicable]

What you can do:
- Monitor your credit reports at [CREDIT MONITORING LINK]
- Do not respond to unsolicited contacts requesting your health information
- Contact us at [COMPLIANCE EMAIL] with questions

We regret this incident and are committed to protecting your privacy.
```

---

## Incident Runbook 2: LLM Model Regression — Incorrect Medical Guidance

**Likelihood:** Medium (1-2x per year due to model updates or prompt changes)
**Severity:** P0 (patient harm risk if incorrect diagnosis/drug interaction advice given)
**Detection Symptoms:** Clinician complaint, audit log shows unusual recommendations, model evaluation alert

### Detection

**Automated triggers:**
- Model evaluation job compares current model output against baseline on held-out test set; accuracy drops >3%
- Guardrail alert: PII detection, hallucination check, or confidence score fails for >0.5% of outputs
- Clinician feedback: Multiple reports of same incorrect diagnosis (e.g., "model keeps missing drug interactions for [DRUG CLASS]")

**Manual triggers:**
- "I saw the AI recommend [DANGEROUS ACTION] to a patient" (internal report)
- Hospital compliance officer flags: "We're seeing higher than expected overrides for [DIAGNOSIS]"

### Diagnosis (First 30 minutes)

1. **Determine what changed:**
   ```sql
   SELECT * FROM prompt_versions
   WHERE status = 'DEPLOYED'
   AND deployed_at > NOW() - INTERVAL '72 hours'
   ORDER BY deployed_at DESC;
   ```
   Check if prompt changed recently (new guideline, new example, new system message).

2. **Isolate impact:**
   - Run model evaluation on last 100 recommendations: Are they systematically wrong?
   - Example: "Model is now recommending ACE inhibitors for all hypertension, ignoring contraindications"
   - Use: `SELECT recommendation_type, outcome_override_rate FROM audit_logs WHERE model_version = 'CURRENT' AND created_at > NOW() - INTERVAL '24 hours' GROUP BY recommendation_type;`

3. **Identify root cause:**
   - Did we deploy a new model version? (Check `model_deployments` table)
   - Did a prompt change? (Check `prompt_versions` table)
   - Did guardrails change? (Check `guardrail_config` table)

4. **Scope the harm:**
   - How many patients saw the incorrect guidance?
   - Did any clinicians act on it (i.e., was the override rate unusually high)?
   - Were there any adverse events reported?

### Remediation (First 2 hours)

**Immediate (within 15 min):**
1. **Rollback:** Revert to last known-good model version or prompt
   ```bash
   kubectl rollout undo deployment/llm-inference-api
   kubectl rollout undo deployment/prompt-server
   ```

2. **Verify:** Confirm rollback successful by running model eval on sample of cases
   ```sql
   SELECT * FROM model_evaluations WHERE model_version = 'PREVIOUS' LIMIT 20;
   ```

3. **Pause deployment:** Block any further model/prompt changes until RCA complete

**Within 1 hour:**
1. **Determine if harm occurred:**
   - Query override rate before/after change: Did clinicians override more during bad period?
   - Example: `SELECT COUNT(*) FROM recommendations WHERE overridden = TRUE AND created_at BETWEEN 'BAD_START' AND 'BAD_END';`
   - If override rate spiked (>15% above baseline), adverse event risk is elevated

2. **Notify clinicians (if necessary):**
   - If >50 patients saw potentially harmful advice, send alert: "Clinical AI provided incorrect guidance on [TOPIC] between [TIME]. Please review [N] recommendations."

3. **Escalate to medical director:**
   - Compliance officer reviews all overridden recommendations during bad period
   - Medical director determines if patient follow-up required

**Within 24 hours:**
1. **Root cause analysis:**
   - If prompt change: What was the intent? Why did it break? Who approved it?
   - If model change: Did we do sufficient testing before deploying?
   - If guardrails: Why didn't they catch the bad output?

2. **Fix:**
   - Revert to previous prompt/model permanently (don't re-try same change)
   - Add guardrail for this specific error (e.g., "Flag any recommendation without contraindication check")
   - Add test case to model eval: "Verify ACE inhibitor recommendations have contraindication analysis"

3. **Deploy guard:**
   - Add confidence threshold gate: If model confidence on this recommendation type drops >5%, require human review
   - Or: Disable this recommendation type temporarily while investigating

### Communication Template

**Internal (Slack #incident-ops):**
```
🚨 P0: Model Regression — Incorrect Guidance on [TOPIC]

Timeline:
- [TIME 1]: Prompt/model deployed
- [TIME 2]: Issue detected (alert / user report)
- [TIME 3]: Rollback initiated

Impact:
- ~[N] recommendations affected
- [M] clinicians saw incorrect guidance
- [K] overrides suggest clinicians caught the error
- Estimated harm: LOW (clinicians caught it) / MEDIUM / HIGH (need follow-up)

Actions:
- [x] Rollback deployed
- [ ] Determine if patient follow-up required
- [ ] Update guardrails to prevent recurrence
- [ ] RCA complete

Next: Medical director review at [TIME]
```

**External (if patient harm possible):**
```
Subject: Important Update on Clinical AI Recommendations

[To clinical teams using the platform]

We identified an issue with our AI model between [TIME] that may have provided
incorrect guidance on [TOPIC]. We have immediately rolled back to our previous
verified model and added safeguards.

Please review any AI recommendations for [TOPIC] provided between [TIME] and
confirm they align with your clinical judgment before implementing.

We have flagged the following recommendations for human review: [LIST]

We take patient safety seriously and are enhancing our quality assurance process.
```

---

## Incident Runbook 3: Audit Log Loss or Integrity Compromise

**Likelihood:** Low (1x per year across portfolio, usually from human error)
**Severity:** P1 (regulatory/compliance violation, not patient harm but legal exposure)
**Detection Symptoms:** Audit log gap (no entries for 1+ hours), failed write to immutable storage, or integrity check failure

### Detection

**Automated triggers:**
- `audit-log-health-check` job finds gap: No entries in audit logs for >1 hour (should have 100+ per hour)
- S3 Object Lock validation fails: Audit log backup file was modified or deleted (should be immutable)
- WAL (Write-Ahead Log) archive fails: PostgreSQL cannot write to immutable backup destination

**Manual triggers:**
- Compliance officer: "I'm trying to audit activity from [TIME RANGE] but there are no logs"
- Security team: "S3 audit log bucket doesn't have expected files"

### Diagnosis (First 30 minutes)

1. **Verify logging is still working:**
   ```sql
   SELECT COUNT(*), MAX(created_at) FROM audit_logs
   WHERE created_at > NOW() - INTERVAL '1 minute';
   ```
   If count is normal (>10), logging is working; issue is historical.

2. **Identify the gap:**
   ```sql
   SELECT
     DATE_TRUNC('hour', created_at) as hour,
     COUNT(*) as entry_count
   FROM audit_logs
   WHERE created_at > NOW() - INTERVAL '7 days'
   GROUP BY DATE_TRUNC('hour', created_at)
   ORDER BY hour DESC;
   ```
   Look for hours with 0 or very low counts.

3. **Check backup integrity:**
   ```bash
   aws s3api head-object --bucket clinical-ai-audit-logs --key audit-2026-03-16.json.gz
   # Should show: ObjectLock configuration = GOVERNANCE or COMPLIANCE
   # If not, object lock was not applied
   ```

4. **Determine root cause:**
   - Database crash during that hour? (Check RDS event logs)
   - Logging service failed? (Check application error logs)
   - S3 backup failed? (Check `audit-log-archiver` service logs)
   - Manual deletion? (Check AWS CloudTrail for S3 DELETE operations)

### Remediation (First 2 hours)

**Immediate:**
1. **Stop the bleeding:**
   - If logging is failing, restart audit log processor:
     ```bash
     kubectl rollout restart deployment/audit-log-processor
     ```
   - If S3 backup is failing, check credentials and retry:
     ```bash
     aws s3 cp audit-log-backup.tar.gz s3://clinical-ai-audit-logs/ \
       --sse-c-algorithm AES256 --sse-c-key [KEY]
     ```

2. **Attempt recovery:**
   - Check if logs exist in PostgreSQL WAL (write-ahead log): `pg_wal/` directory
   - If WAL still exists, can replay to recover missing audit entries:
     ```bash
     pg_dump --wal-method=stream > audit_recovery.sql
     ```
   - Restore from point-in-time backup if available

3. **Notify compliance:**
   - Page compliance officer (even if during off-hours)
   - Prepare scope of loss: How many hours? Which patient interactions?

**Within 4 hours:**
1. **Determine if regulatory notification required:**
   - Per HIPAA: Must maintain audit logs of PHI access
   - If logs for >1 hour are unrecoverable: Regulatory violation
   - Consult legal on reporting requirements

2. **Implement recovery:**
   - Replay WAL to recover missing audit entries (if possible)
   - Restore S3 backup from previous day (if Object Lock is working)
   - Update immutable backup system to prevent recurrence

3. **Investigation:**
   - Why did audit logging fail? (code bug, infrastructure issue, permissions)
   - Why didn't we catch it sooner? (monitoring gap)

### Remediation Specifics

**If logs were deleted (security incident):**
```bash
# Check CloudTrail for who deleted what
aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceType,AttributeValue=AWS::S3::Object \
  --max-results 50 | grep DeleteObject

# If deletion found, escalate to security + compliance
```

**If logs are unrecoverable:**
- Generate incident report documenting:
  - Start time of loss
  - End time of loss
  - Estimated number of missing audit entries
  - Root cause
  - Preventive measures implemented
- File with state medical board + HHS (if required by law)

### Communication Template

**Internal (Slack #incident-ops):**
```
🚨 P1: Audit Log Loss — Gap from [TIME] to [TIME]

Scope:
- Missing entries: ~[N] audit events
- Affected patients: [ESTIMATE]
- Recovery status: Attempting recovery from WAL / Recovered from backup / Unrecoverable

Root cause:
- [ ] Database crash
- [ ] Application service failure
- [ ] S3 backup failure
- [ ] Manual deletion (security incident)

Actions:
- [x] Logging resumed
- [ ] Recover missing entries
- [ ] Regulatory notification assessment
- [ ] Root cause fix deployed

Regulatory impact: [ASSESS NOW]
On-call: [NAME]
```

**If regulatory notification required:**
```
Subject: Notice of Audit Log Integrity Incident

[To HHS / State Medical Board, per HIPAA Breach Notification Rule]

We are notifying you of a compliance incident affecting our Clinical AI Platform.

Incident: Audit logging was interrupted for [DURATION], resulting in
[N] missing audit entries for patient health information access.

Affected individuals: [COUNT]

Remediation:
- Restored audit logging systems
- Implemented Object Lock on all future audit logs
- Enhanced monitoring to detect gaps within 5 minutes

We regret this lapse and have strengthened our controls.
```

---

## Incident Commander Checklist

For any P0 incident involving Clinical AI:

- [ ] Page incident commander within 5 minutes of detection
- [ ] Page medical director within 10 minutes (for patient harm assessment)
- [ ] Page compliance officer within 15 minutes (for regulatory assessment)
- [ ] Create incident channel: `#incident-YYYYMMDD-BRIEF-DESCRIPTION`
- [ ] Establish timeline: When did it start? When detected? When fixed?
- [ ] Document: What was the impact? How many patients? How many clinicians?
- [ ] Assess harm: Did patient receive incorrect guidance? Did clinician override?
- [ ] Determine notifications: Patient notification? Regulatory notification? Hospital notification?
- [ ] RCA: Root cause analysis due within 24 hours
- [ ] Prevention: What control prevents recurrence?
- [ ] Post-incident review: Schedule with all stakeholders within 72 hours

