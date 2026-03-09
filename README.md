# Clinical AI Platform — Prior Authorization & Revenue Cycle Intelligence

**An AI-powered clinical operations platform that automates prior authorization, medical coding, and claims denial prevention for mid-size healthcare organizations.**

Built for **Meridian Health Partners** — a 38-provider multi-specialty group (orthopedics, cardiology, internal medicine) across 6 locations in the greater Charlotte, NC metro. Meridian processes ~4,200 prior authorization requests/month, manages $62M in annual claims volume, and employs 14 revenue cycle staff.

---

## The Problem

Meridian Health Partners was drowning in administrative overhead:

- **Prior authorization backlog**: 4,200 PA requests/month with average 3.8-day turnaround. Staff spending 11 hours/day on phone/fax with payers. 23% of patients abandoned recommended treatment due to PA delays.
- **Claims denial rate at 18.4%**: $11.4M in annual denials. Only 31% of appeals successful. Root causes: documentation gaps (42%), coding errors (28%), eligibility issues (19%), medical necessity failures (11%).
- **Medical coding bottleneck**: 3 FTE coders processing 850 encounters/week. Average 22 minutes per chart. Error rate 8.7% on initial submission. Under-coding estimated at $1.2M/year in missed revenue.
- **Clinician burnout**: Physicians spending 2.4 hours/day on documentation and PA-related tasks. Two providers left in 12 months citing administrative burden.
- **Fragmented systems**: Epic EHR, separate billing system (Athena), manual fax-based PA workflow, Excel-based denial tracking. No unified view of revenue cycle health.

**Total estimated annual cost of inefficiency: $4.8M** (staff overtime, denied claims, under-coding, provider turnover, patient leakage).

---

## The Solution

We built a HIPAA-compliant AI platform that sits alongside their Epic EHR via SMART on FHIR, automating three critical workflows:

### 1. Prior Authorization Engine
- **Clinical data extraction**: FHIR API pulls patient demographics, diagnoses, medications, lab results, and encounter history from Epic
- **Payer criteria matching**: AI maps clinical documentation against payer-specific coverage policies (loaded from CMS PA API and manual policy ingestion)
- **Auto-generation**: Produces complete PA request packages with supporting clinical evidence, medical necessity justification, and correct CPT/ICD-10 codes
- **Submission**: Electronic submission via payer PA APIs (CMS-mandated FHIR endpoints) with real-time status tracking
- **Appeals**: Analyzes denial reasons, identifies supporting documentation, generates appeal letters with clinical justification and precedent references

### 2. Medical Coding Intelligence
- **NLP extraction**: SciSpaCy + MedCAT pipeline extracts clinical concepts from encounter notes — conditions, procedures, medications, lab values
- **Concept normalization**: Maps extracted entities to SNOMED CT, then cross-references to ICD-10-CM and CPT codes via UMLS
- **Specificity optimization**: Recommends most specific codes (higher specificity = better reimbursement). Catches under-coded encounters.
- **Bundling validation**: Checks CCI (Correct Coding Initiative) edits for procedure bundling/unbundling rules and modifier application
- **Audit trail**: Every coding suggestion linked to source documentation for compliance

### 3. Revenue Cycle Analytics
- **Denial prediction**: ML model scores claims pre-submission based on historical denial patterns, payer-specific rules, and documentation completeness
- **Root cause analysis**: Aggregates denial data to identify systematic issues — which payers, which procedures, which documentation gaps
- **Financial dashboard**: Real-time revenue cycle KPIs — clean claim rate, days in AR, denial rate by payer, net collection rate
- **Trend detection**: Identifies emerging denial patterns before they become systemic (e.g., new payer policy changes causing spike)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Epic EHR (SMART on FHIR)                     │
│            Patient, Encounter, Condition, MedicationRequest           │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ FHIR R4 API (OAuth 2.0 / TLS 1.3)
                           │
┌──────────────────────────▼───────────────────────────────────────────┐
│                      FHIR Integration Layer                          │
│   Patient Sync │ Encounter Listener │ Document Watcher │ Lab Feed    │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────────┐
│                     Clinical NLP Pipeline                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
│  │  SciSpaCy   │→ │   MedCAT     │→ │  Concept Normalization     │  │
│  │  (NER)      │  │ (SNOMED CT)  │  │  (ICD-10, CPT, RxNorm)    │  │
│  └─────────────┘  └──────────────┘  └────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼──────────────┐
│  Prior Auth    │ │   Medical    │ │  Revenue Cycle      │
│  Engine        │ │   Coding     │ │  Analytics          │
│                │ │   Agent      │ │                     │
│ • PA generation│ │ • Code       │ │ • Denial prediction │
│ • Criteria     │ │   suggestion │ │ • Root cause        │
│   matching     │ │ • Specificity│ │ • Financial KPIs    │
│ • Submission   │ │   check      │ │ • Trend detection   │
│ • Appeals      │ │ • CCI edits  │ │                     │
└────────────────┘ └──────────────┘ └─────────────────────┘
          │                │                │
┌─────────▼────────────────▼────────────────▼─────────────────────────┐
│                    Compliance & Guardrails Layer                      │
│   PHI Detection │ Audit Logger │ RBAC │ Encryption │ BAA Tracker     │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────────┐
│                       Data Layer                                      │
│  Supabase PostgreSQL (encrypted)  │  Redis (session/cache)           │
│  pgvector (medical knowledge)     │  S3 (document storage, encrypted)│
└──────────────────────────────────────────────────────────────────────┘
```

---

## Key Pivot

**Original approach**: Build a general-purpose clinical documentation assistant (ambient note-taking + coding). After discovery with Meridian, we realized:

1. Ambient documentation market is saturated (Nuance DAX, Abridge, DeepScribe all have strong products)
2. The real pain wasn't documentation *creation* — it was what happened *after* the note: PA requests, coding, claims submission, denials
3. Prior authorization was consuming more staff time than documentation itself (11 hrs/day vs 2.4 hrs/day)
4. CMS Interoperability Rule (CMS-0057-F) mandating payer PA APIs by Jan 2027 created a narrow window where early movers gain massive advantage

**Pivot**: From "clinical documentation AI" → "post-encounter operations intelligence" — focusing on the PA → coding → claims → denial loop where ROI is immediately measurable in dollars recovered.

---

## Results (6-Month Post-Launch)

| Metric | Before | After | Impact |
|--------|--------|-------|--------|
| PA turnaround time | 3.8 days | 6.2 hours | **93% faster** |
| PA auto-approval rate | 0% (all manual) | 67% auto-submitted | **Staff redeployed** |
| Claims denial rate | 18.4% | 9.1% | **51% reduction** |
| Appeal success rate | 31% | 72% | **132% improvement** |
| Coding accuracy | 91.3% | 97.8% | **6.5pt increase** |
| Revenue recovered (annualized) | — | $2.1M | **From denied claims** |
| Coder throughput | 38/day | 94/day | **147% increase** |
| Clinician admin time | 2.4 hrs/day | 0.8 hrs/day | **67% reduction** |

---

## My Role

**Principal Product Manager** — Led end-to-end from discovery through production launch.

- **Discovery & Research (Weeks 1-4)**: Conducted 22 stakeholder interviews across clinical, billing, coding, and IT teams. Shadowed PA coordinators for 3 days. Mapped the complete revenue cycle workflow. Identified prior auth as the highest-ROI automation target ($3.2M estimated annual impact).
- **Regulatory Deep Dive (Weeks 2-6)**: Worked with Meridian's compliance officer to define HIPAA technical safeguards checklist. Evaluated BAA requirements for LLM providers. Designed PHI handling architecture (tokenization for processing, encryption at rest/transit, audit logging). Documented compliance requirements that became engineering guardrails.
- **Architecture & Design (Weeks 4-8)**: Designed SMART on FHIR integration pattern with Epic. Made critical tech decisions: SciSpaCy + MedCAT for NLP (lightweight, deployable, no PHI sent to external APIs), Claude Enterprise for complex reasoning tasks (BAA-signed), Supabase for HIPAA-compliant data layer. Defined three-agent architecture (PA, Coding, RCM Analytics).
- **Sprint Leadership (Weeks 6-20)**: Ran 2-week sprints with 1 lead dev + 3 offshore engineers. Prioritized PA engine first (highest urgency), then coding intelligence, then analytics. Managed scope aggressively — cut ambient documentation feature entirely after pivot. Unblocked EHR integration delays by negotiating directly with Epic's App Orchard team.
- **Launch & Iteration (Weeks 16-24)**: Phased rollout — orthopedics first (highest PA volume), then cardiology, then internal medicine. Monitored coding accuracy daily for first 4 weeks. Adjusted payer criteria matching rules based on denial feedback loop. Achieved 97.8% coding accuracy by week 20.

---

## Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | FastAPI + Python 3.11 | Healthcare NLP ecosystem is Python-native; async for FHIR API calls |
| **NLP** | SciSpaCy + MedCAT | Medical NER + concept normalization without sending PHI externally |
| **Medical Ontologies** | SNOMED CT, ICD-10-CM, CPT, RxNorm, LOINC | Standard medical vocabularies for concept mapping |
| **LLM** | Claude Enterprise (BAA) | Complex clinical reasoning, appeal letter generation, PA justification |
| **EHR Integration** | SMART on FHIR (R4) | Standard API for Epic integration; OAuth 2.0 auth |
| **Database** | Supabase PostgreSQL | HIPAA-compliant, encrypted at rest, RLS for tenant isolation |
| **Vector Search** | pgvector | Medical knowledge base for similar case retrieval |
| **Cache** | Redis | Session management, FHIR token cache, rate limiting |
| **Document Storage** | S3 (encrypted) | PA documents, appeal letters, audit exports |
| **Auth** | Clerk + SMART on FHIR OAuth | App auth + EHR single sign-on |
| **Observability** | LangSmith | LLM call tracing, cost tracking, quality monitoring |
| **Compliance** | Custom audit engine | HIPAA audit logging, PHI access tracking, encryption verification |
| **CI/CD** | GitHub Actions | Automated testing, HIPAA compliance checks, deployment |
| **Infrastructure** | Docker + AWS ECS | Container orchestration; HIPAA-eligible AWS services |
| **Workflows** | Trigger.dev | Long-running PA processing, batch coding jobs |

---

## Project Structure

```
clinical-ai-platform/
├── src/
│   ├── main.py                     # FastAPI application entry
│   ├── api/
│   │   ├── routes.py               # REST API endpoints
│   │   ├── models.py               # Pydantic request/response models
│   │   └── websocket.py            # Real-time status updates
│   ├── agents/
│   │   ├── base.py                 # Base clinical agent
│   │   ├── prior_auth.py           # Prior authorization agent
│   │   ├── coding.py               # Medical coding agent
│   │   └── analytics.py            # Revenue cycle analytics agent
│   ├── fhir/
│   │   ├── client.py               # FHIR R4 API client
│   │   ├── resources.py            # FHIR resource models
│   │   └── smart_auth.py           # SMART on FHIR OAuth
│   ├── nlp/
│   │   ├── pipeline.py             # Clinical NLP pipeline
│   │   ├── ner.py                  # Medical named entity recognition
│   │   ├── concept_linker.py       # SNOMED CT / UMLS concept linking
│   │   └── abbreviation.py         # Clinical abbreviation resolver
│   ├── prior_auth/
│   │   ├── engine.py               # PA request generation engine
│   │   ├── criteria_matcher.py     # Payer criteria matching
│   │   ├── submission.py           # Electronic PA submission
│   │   └── appeals.py              # Denial appeal generation
│   ├── coding/
│   │   ├── suggester.py            # ICD-10/CPT code suggestion
│   │   ├── specificity.py          # Code specificity optimizer
│   │   ├── bundling.py             # CCI edit checker
│   │   └── audit.py                # Coding audit trail
│   ├── guardrails/
│   │   ├── phi_detector.py         # PHI detection and masking
│   │   ├── clinical_safety.py      # Clinical content safety checks
│   │   └── compliance_engine.py    # HIPAA compliance enforcement
│   ├── compliance/
│   │   ├── audit_logger.py         # HIPAA audit logging
│   │   ├── encryption.py           # Encryption utilities
│   │   ├── rbac.py                 # Role-based access control
│   │   └── baa_tracker.py          # BAA status tracking
│   ├── providers/
│   │   ├── base.py                 # LLM provider base
│   │   ├── anthropic.py            # Claude Enterprise (BAA)
│   │   └── router.py               # Model routing
│   ├── memory/
│   │   ├── session.py              # Redis session store
│   │   ├── patient_context.py      # Patient context aggregation
│   │   └── knowledge.py            # Medical knowledge base (pgvector)
│   ├── config/
│   │   └── settings.py             # Application configuration
│   └── middleware/
│       ├── auth.py                 # Authentication middleware
│       ├── audit.py                # Audit logging middleware
│       └── rate_limit.py           # Rate limiting
├── schema/
│   ├── 001_core_tables.sql         # Core data model
│   ├── 002_prior_auth_tables.sql   # PA-specific tables
│   ├── 003_coding_tables.sql       # Medical coding tables
│   ├── 004_compliance_tables.sql   # Audit and compliance
│   └── 005_rls_policies.sql        # Row-level security
├── evals/
│   └── evaluators.py               # LangSmith evaluation suite
├── n8n/
│   ├── pa_status_monitor.json      # PA status polling workflow
│   └── denial_alert.json           # Denial spike alerting
├── trigger-jobs/
│   └── pa_processing.ts            # Long-running PA job
├── .github/
│   └── workflows/
│       └── ci.yml                  # CI with HIPAA checks
├── docker-compose.yml              # Local development
├── Makefile                        # Build commands
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
└── .gitignore                      # Git exclusions
```

---

## GitHub

[github.com/riiiiiicoooo/clinical-ai-platform](https://github.com/riiiiiicoooo/clinical-ai-platform)
