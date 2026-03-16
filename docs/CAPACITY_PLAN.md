# Clinical AI Platform — Capacity Plan

**Last Updated:** March 2026
**Baseline Workload:** 50K PA submissions/month, 150K daily active clinicians

---

## Current State (50K PA/month)

### Infrastructure

| Component | Current | Headroom | Notes |
|-----------|---------|----------|-------|
| **LLM API (Claude + GPT-4)** | 50K req/month | 150K tokens budget/month from suppliers | Running at ~33% of contracted token capacity |
| **Database (PostgreSQL primary)** | 15 GB used, 20 GB allocated | 25% headroom | PA processing table: 8GB; audit logs: 5GB; indexes: 2GB |
| **API servers (FastAPI)** | 4 x t3.xlarge (4 CPU, 16GB RAM each) | ~40% CPU utilization avg | Peak hours hit 70% CPU |
| **Redis cache** | 1 x r6g.xlarge (4 CPU, 32GB) | 45% memory utilization | Guideline template cache mostly warm |
| **Webhook inbound (insurance callbacks)** | SQS: <5K msgs/day | 95% headroom | Async callback queue for insurance company responses |

### Cost

| Category | Monthly | Annual |
|----------|---------|--------|
| LLM API (token overages) | $12K | $144K |
| Compute (EC2 + ECS) | $4.2K | $50K |
| Database (RDS multi-AZ) | $2.1K | $25K |
| Storage (S3 for encrypted archives) | $0.8K | $10K |
| **Total** | **$19.1K** | **$229K** |

### Performance Baseline

| Metric | Value | SLO |
|--------|-------|-----|
| PA turnaround (p95) | 4.2 hours | 6.2 hours ✓ |
| PA turnaround (p99) | 8.1 hours | — |
| LLM inference latency (p95) | 1.8 seconds | 2.5 seconds ✓ |
| API error rate | 0.08% | <0.5% ✓ |
| Database query latency (p95) | 45ms | — |
| Audit log ingestion lag (p95) | 200ms | <1s ✓ |

### What Breaks First at Current Load

1. **RDS connection pool** — Peak hours (7am-12pm) hit 90% active connections; additional 20% load causes timeout errors on new connections
2. **LLM token budget** — If usage grows linearly, token budget exhausts in ~4.5 months at current spending trajectory
3. **Redis memory** — Guideline cache eviction starts at 85% memory; ~10% of requests fall through to database
4. **PA submission queue** — SQS batch processing latency exceeds 500ms when >200 concurrent submissions

---

## 2x Scenario (100K PA/month)

### What Changes

- **Clinician base:** 300K daily active users (hospitals expanding programs)
- **PA mix:** More complex cases (oncology +15%, neurology +8%) = longer guideline matching
- **Third-party integrations:** EHRs (Epic, Cerner) start submitting bulk batch jobs

### Infrastructure Changes

| Component | 1x → 2x | Action | Timeline |
|-----------|---------|--------|----------|
| **LLM API** | 50K → 100K req/month | Upgrade contract to 300K token budget/month + negotiate 15% volume discount | Month 1 |
| **API servers** | 4 → 8 instances (t3.xlarge) | Autoscaling: add 2 instances when CPU > 65% for 2 min | Week 1 |
| **Database** | 20GB → 45GB | RDS multi-AZ upgrade to r6g.2xlarge (8 CPU, 64GB) | Month 1 |
| **Redis** | 32GB → 64GB | r6g.2xlarge + add read replica for guideline reads | Month 1 |
| **Webhook processing** | SQS + SNS | Add Kafka topic for insurance callbacks; batch processing instead of per-message | Month 2 |

### Cost Impact

| Category | 1x | 2x | Delta | % increase |
|----------|----|----|-------|-----------|
| LLM API | $12K | $24K | +$12K | +100% |
| Compute | $4.2K | $7.8K | +$3.6K | +86% |
| Database | $2.1K | $5.2K | +$3.1K | +148% |
| Storage | $0.8K | $1.2K | +$0.4K | +50% |
| **Total** | **$19.1K** | **$38.2K** | **+$19.1K** | **+100%** |

### Performance at 2x

| Metric | 1x Baseline | 2x Expected | Impact |
|--------|------------|-------------|--------|
| PA turnaround (p95) | 4.2h | 5.8h | Still within SLO (6.2h) ✓ |
| PA turnaround (p99) | 8.1h | 10.5h | Exceeds SLO — need optimization |
| LLM latency (p95) | 1.8s | 2.1s | Still within SLO ✓ |
| API error rate | 0.08% | 0.15% | Still acceptable |
| Database query latency (p95) | 45ms | 120ms | Acceptable (warm cache still ~70% hit rate) |

### What Breaks First at 2x

1. **PA turnaround (p99)** — Complex case matching (oncology, neurology) requires longer LLM context; p99 exceeds 10 hours
2. **Database read throughput** — Guideline cache hit rate drops from 70% to 55%; RDS becomes bottleneck
3. **LLM API rate limits** — Insurance company batches (500-1K PAs/job) cause token budget spikes; risk of being rate-limited mid-day
4. **Webhook delivery guarantees** — SQS doesn't guarantee ordering for insurance callbacks; Kafka needed for ordering guarantees

### Scaling Triggers for 2x

- **CPU utilization > 70% for 5+ min:** Autoscale (+2 API servers)
- **RDS connections > 85% of pool:** Promote read replica to primary, migrate read-heavy queries
- **LLM token consumption > 75% daily budget:** Alert ops, prepare fallback to smaller model
- **Cache hit rate < 60%:** Add Redis read replica, consider upgrading to r6g.3xlarge
- **PA turnaround p95 > 5.5h:** Optimize guideline matching (parallel checks instead of sequential)

---

## 10x Scenario (500K PA/month)

### Market Reality at 10x

- **Adoption:** Top-50 hospitals (Mayo, Cleveland Clinic, Partners) all using platform
- **Clinician base:** 1.5M daily active clinicians
- **PA types:** Rare disease cases now 8% of volume (require specialized knowledge bases)
- **International:** Canadian and UK healthcare systems requesting integration

### What's Fundamentally Broken at 10x

1. **Latency math doesn't work** — At 500K PA/month, concurrent submissions hit 200-300 during peak; even with perfect caching, orchestrating 10 guideline checks + LLM reasoning + audit logging takes >3 seconds baseline. PA turnaround p95 would be 12+ hours, SLO failure.

2. **LLM token budget becomes prohibitive** — 500K PA × 3K tokens/request avg = 1.5B tokens/month. At $0.015/token (bulk pricing), cost alone is $22.5K/month. Adding insurance callbacks, batch verification, and audit traces pushes to $35K-40K/month.

3. **Data explosion** — 500K PA/month × ~5 KB per PA (submission + decision + evidence) = 2.5GB/month or 30GB/year. Audit logs alone (PII, key decision points) would be 5GB/month or 60GB/year. RDS storage becomes costly ($5K+/month for 500GB+ allocation).

4. **Compliance complexity** — At 10x volume, probability of encountering a regulatory edge case (cross-state PA, specialty mismatch, rare drug interaction) reaches ~5% of volume. Current rule-based compliance filters won't scale; need learned models for edge detection.

### Architectural Changes Needed for 10x

| Problem | 1x/2x Solution | 10x Solution |
|---------|---|---|
| **LLM latency** | Batch caching + regional endpoints | Retrieval-augmented generation (RAG) over fine-tuned 7B model (Mistral) instead of Claude; 10x cheaper, <500ms latency |
| **Token budget** | Raise budget with supplier | Build internal guideline interpretation layer (rules engine) for 70% of routine cases; LLM only for complex/rare cases (30%) |
| **Storage** | RDS multi-AZ + S3 archive | Data warehouse (BigQuery/Snowflake) for analytics; operational database (RDS) only holds last 30 days of PAs; older PAs archived to cold storage |
| **Compliance** | Static rule enforcement | Machine learning model for regulatory edge case detection (trained on regulator complaint patterns); continuous monitoring |
| **Availability** | Multi-region failover | Distributed consensus (Raft) across 3 regions; no single point of failure |

### Cost at 10x (Realistic Projection)

| Category | 1x | 10x | Ratio |
|----------|----|----|-------|
| LLM API (token-based) | $12K | $25K | 2.08x (due to fine-tuned model fallback) |
| Compute | $4.2K | $35K | 8.3x (3 regions, more instances per region) |
| Database | $2.1K | $18K | 8.6x (DW infrastructure) |
| Storage (warm + cold) | $0.8K | $8K | 10x |
| Data warehouse | $0 | $15K | ∞ (new component) |
| **Total** | **$19.1K** | **$101K** | **5.3x** |

**Key insight:** Cost scales sub-linearly (5.3x cost for 10x volume) due to economics of scale on compute and bulk LLM pricing. However, architectural rework is non-trivial (6-month engineering effort).

### Scaling Triggers for 10x

- **LLM token daily spend > $800** (current ~$400): Activate fine-tuned model pilot for top 5 common PA types
- **RDS database size > 200GB:** Migrate OLTP to separate DW; keep only hot data in RDS
- **API latency p95 > 6s:** Consider distributed caching layer (Memcached cluster across regions)
- **PA turnaround p95 approaching SLO (>6h):** Pre-launch fallback to rules engine for routine cases
- **Incident frequency > 2/month affecting SLO:** Architecture review; consider moving to event-driven processing (Kafka) instead of request-response

---

## Capacity Planning Roadmap

| Quarter | Trigger Level | Action | Investment |
|---------|---|---|---|
| Q2 2026 | Monitor 2x | Pre-stage 2x infrastructure (RDS upgrade, Redis expansion); negotiate LLM contract expansion | $5K (infrastructure only) |
| Q3 2026 | Approach 2x (80K PA/month) | Activate autoscaling; deploy Kafka for webhooks | $8K infrastructure + 200 eng hours |
| Q4 2026 | Hit 2x (100K PA/month) | Full 2x rollout; optimize guideline caching; SLO review | Ongoing |
| Q1 2027 | Plan 5x (250K PA/month) | Architecture review for RAG/fine-tuned model; cost modeling | 400 eng hours |
| Q2 2027+ | 5x+ territory | Execute 10x roadmap; internal guideline interpretation layer; DW migration | $80K infra + 1200 eng hours over 6 months |

