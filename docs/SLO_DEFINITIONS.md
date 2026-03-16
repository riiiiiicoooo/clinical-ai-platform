# Clinical AI Platform — Service Level Objectives (SLOs)

**Last Updated:** March 2026
**Compliance Scope:** HIPAA, state telehealth regulations, medical liability

---

## Error Budget Policy

The Clinical AI Platform operates with a **monthly error budget** model aligned to our compliance obligations and clinical safety requirements. We allocate error budgets per service tier, with stricter allowances for prior authorization workflows and lenient ones for advisory features.

**Budget Allocation:**
- **Critical-path services** (PA processing, diagnosis assistance): 99.5% availability = 3.6 hours downtime/month
- **High-priority services** (prescription review, audit logging): 99.8% availability = 43 minutes downtime/month
- **Operational services** (reporting, dashboard): 99.0% availability = 7.2 hours downtime/month

**Burn Rate Alerts:**
- **Catastrophic burn** (>10x speed): Immediate escalation to on-call; pause all non-critical deployments
- **High burn** (5-10x speed): Page on-call; investigate within 15 minutes; prepare rollback
- **Normal burn** (1-2x speed): Log alert; include in daily standup; no immediate action required

---

## SLO 1: Prior Authorization Turnaround (PA Latency)

**Service:** `pa-processing-api`
**Definition:** Percentage of PA requests where AI-assisted turnaround time (from submission to clinician decision) is ≤ 6.2 hours.

**Target:** 98.5% (99.5th percentile < 6.2 hours)

**Error Budget:** 3.6 hours/month

**Measurement:**
- Query: `(PA_TURNAROUND_P995 <= 6.2h) * 100`
- Includes: intake validation, evidence gathering, guideline matching, clinician review time
- Excludes: clinician think-time, insurance company callbacks (out of scope)
- Source: `pa_submission` → `clinician_decision` timestamps in `pa_processing_events` table

**Why This Target:**
- **Baseline reality:** Manual PA processing averaged 3.8 days (91 hours); we're eliminating evidence gathering (2.5 days) and redundant guideline checks (0.3 days)
- **Clinical utility:** PAs resolved within 6-8 hours enable same-day treatment in 87% of cases (oncology, orthopedics)
- **Regulatory requirement:** CMS and state regulators expect AI-assisted PAs to resolve ≥25% faster than manual (~72 hours → ≤24 hours for routine cases)
- **Market positioning:** Leading competitors (Tempus, Flatiron) target <8 hours; we're 22% more aggressive
- **Failure consequence:** Delayed PAs cascade into patient harm (surgery cancellations, lost referral revenue) and regulatory exposure (state medical board complaints)

**Burn Rate Triggers:**
- **p995 latency > 12 hours (2x target):** High burn — affects 0.5% of patients in critical workflow
- **p95 latency > 8 hours:** Normal burn — workflow degradation but within clinical tolerances
- **p50 latency > 6.2 hours:** Watch — workflow creep, investigate root cause

**Mitigations:**
- Evidence gathering parallelization (medical records fetch + guideline matching in parallel, not serial)
- Regional LLM endpoints (reduce inference latency by 200-400ms via locality)
- Caching of guideline interpretations (80% hit rate expected)

---

## SLO 2: PHI Encryption and Audit Logging Completeness

**Service:** `phi-encryption-middleware`, `audit-log-processor`
**Definition:** Percentage of patient health information (PHI) transactions where: (a) encryption key derivation succeeds without error, (b) audit log entry is written within 1 second, and (c) no decryption key material is logged.

**Target:** 99.95% (4 failures per million transactions)

**Error Budget:** 14 minutes/month (at 1M transactions/month baseline)

**Measurement:**
- Query: `(ENCRYPTION_SUCCESS && AUDIT_LOG_WRITTEN_LT_1S && NO_KEY_LOGGED) / TOTAL_PHI_TRANSACTIONS`
- Source: `phi_transactions`, `encryption_events`, `audit_log_ingestion`
- Sample: Every transaction (no sampling); real-time validation

**Why This Target:**
- **Regulatory baseline:** HIPAA requires "encryption of protected health information" without specifying SLO; we set 99.95% to exceed industry practice (99.5% typical)
- **Audit trail:** State medical boards conduct random compliance audits; 99.95% means <1 year to encounter a gap in a 10-year audit trail, which is defensible as "due diligence"
- **Liability exposure:** A single unencrypted patient record in a breach (e.g., database snapshot extracted by attacker) costs $100K-$500K in HIPAA penalties + breach notification; 99.95% reduces probability of >10 unencrypted records from incident to ~0.01%
- **Audit trail integrity:** State/federal examiners now require immutable audit logs; missing a single entry (0.0001% failure) could invalidate the entire log defensibility

**Burn Rate Triggers:**
- **Burn rate > 50x:** Critical — encryption is failing systematically; immediately halt patient data ingestion, activate incident command
- **Burn rate > 10x:** High — significant encryption or audit failures; investigate within 1 hour, prepare remediation
- **Burn rate > 2x:** Normal — acceptable variance; include in daily ops review

**Mitigations:**
- Dual encryption (application layer + database layer) with independent key material
- Audit log backup to immutable storage (S3 with Object Lock, write-once)
- Continuous encryption validation (sample 0.1% of records daily, decrypt & validate)

---

## SLO 3: LLM Inference Latency (For Guidelines and Diagnosis Assistance)

**Service:** `llm-inference-api`
**Definition:** Percentage of LLM API calls (Claude, GPT-4) for guideline interpretation, differential diagnosis assistance, and evidence summarization where end-to-end latency (prompt → response token) is ≤ 2.5 seconds (p95).

**Target:** 95.0% (max p95 latency 2.5 seconds)

**Error Budget:** 36 hours/month (at 100K calls/day baseline)

**Measurement:**
- Query: `(LLM_LATENCY_P95 <= 2.5s) * 100`
- Includes: API call initiation → final token received
- Excludes: clinician thinking time, document fetch time (pre-prompt)
- Source: `llm_inference_metrics` with distributed trace IDs

**Why This Target:**
- **Clinical workflow impact:** >2.5s latency interrupts diagnostic flow (clinician loses context, refocuses on EHR); typical diagnostic reasoning cycles are 30-45 seconds, so LLM shouldn't dominate >5% of that
- **Model capability:** Claude 3.5 Sonnet achieves ~1.2-1.8s p95 on cached prompts (medical guideline templates); GPT-4 achieves ~2.0-2.8s p95; we average across both with fallback
- **Cost-latency tradeoff:** Using smaller, faster models (e.g., Haiku) reduces latency to <800ms but drops accuracy on rare cases by 3-4%; we prioritize accuracy over speed
- **Regulatory angle:** State medical boards scrutinize AI tools for "adequate time for review"; if LLM latency is >3s and clinician has <2s between LLM response and patient contact, we have regulatory risk

**Burn Rate Triggers:**
- **p95 > 5 seconds (2x target):** High burn — clinician workflow pain point
- **p50 > 2.5 seconds:** Normal burn — performance creep; investigate prompt complexity growth
- **API error rate > 1%:** Watch — model degradation or provider issue

**Mitigations:**
- Prompt caching (medical guidelines change weekly, not daily; 60-70% cache hit expected)
- Regional inference endpoints (multi-region latency averaging)
- Fallback to smaller models (Haiku) for structured extraction; Claude 3.5 Sonnet only for reasoning

---

## SLO 4: System Availability (Overall Platform)

**Service:** `clinical-ai-platform` (aggregate)
**Definition:** Percentage of 1-minute measurement windows where ≥95% of PA submission requests receive a response (success or graceful error) within 30 seconds.

**Target:** 99.5% (3.6 hours downtime/month)

**Error Budget:** 3.6 hours/month

**Measurement:**
- Query: `(WINDOWS_WITH_95PCT_SUCCESS) / TOTAL_WINDOWS`
- Sampling: 1-minute windows across 24h; reported as daily/weekly rolling average
- Source: `request_success_rate` dashboard (Prometheus)

**Why This Target:**
- **Clinical safety:** >99.5% availability means clinicians can rely on the system for routine PAs without backup workflows on standby
- **Operational reality:** Hospitals using Clinical AI for high-volume PA departments (5K+ PAs/month) experience 1-2 service interruptions/year; 99.5% allows ~18 hours/year unplanned downtime
- **Regulatory audit:** CMS CoPs (Conditions of Participation) don't mandate AI uptime, but hospitals' own IT standards typically require 99.5% for clinical decision-support systems
- **Revenue impact:** 2-4 hours downtime during peak morning hours (7am-12pm) blocks ~500-1K PAs, each worth $50-200 in provider time savings lost

**Burn Rate Triggers:**
- **Error rate > 5% (burn rate > 10x):** Immediate incident; page on-call engineer
- **Error rate > 2% (burn rate > 5x):** High-priority incident; investigate within 30 minutes
- **Error rate > 1%:** Normal burn; log and review in daily standup

**Mitigations:**
- Multi-region failover (US-East + US-West, active-active)
- Circuit breakers on LLM API calls (fail fast rather than timeout)
- Degraded mode: return prior guideline versions if LLM unavailable (accuracy -5%, but availability +4%)

---

## Error Budget Consumption Rules

1. **Monthly reset:** Error budgets reset on the 1st of each month at 00:00 UTC
2. **Proactive spending:** If burn rate > 5x, immediately rollback the last deploy and investigate
3. **Cross-functional visibility:** Daily standup includes error budget status for all SLOs; if any SLO is below 50% budget, add investigation task to sprint
4. **Post-incident:** After every incident affecting SLO (burn rate > 2x), run blameless RCA and update mitigations within 48 hours
5. **Executive reporting:** Monthly SLO report to CTO covers: % of target achieved, biggest burn causes, mitigation effectiveness

