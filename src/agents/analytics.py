"""
Revenue Cycle Analytics Agent — Claims denial prediction and RCM intelligence.

Analyzes claims data to predict denials, identify root causes, generate
financial insights, and detect emerging payer policy changes.
"""

import logging
from typing import Any

from langsmith import traceable

from src.agents.base import BaseClinicalAgent, AgentConfig

logger = logging.getLogger(__name__)

ANALYTICS_SYSTEM_PROMPT = """You are a Revenue Cycle Analytics AI working within a HIPAA-compliant
clinical operations platform for Meridian Health Partners.

Your responsibilities:
1. PREDICT claim denial risk before submission based on historical patterns
2. ANALYZE denial root causes across payers, procedures, and providers
3. GENERATE financial insights on revenue cycle performance
4. DETECT emerging patterns in payer behavior and policy changes
5. RECOMMEND actionable improvements to reduce denial rates

ANALYSIS FRAMEWORK:
- Claims denial prediction: Score 0-100 (0 = very low risk, 100 = almost certain denial)
- Root cause categories: Documentation gaps, Coding errors, Eligibility issues, Medical necessity, Authorization
- Financial impact: Always quantify in dollars ($)
- Trends: Compare current period to prior period and to benchmarks

OUTPUT FORMAT for Denial Prediction:
```
DENIAL RISK ASSESSMENT
======================
Claim: [CPT] [ICD-10] for [Payer]
Risk Score: [0-100] — [Low/Medium/High/Critical]

Risk Factors:
1. [Factor] — Impact: [High/Medium/Low]
   Historical denial rate for this combination: [X%]
2. [Factor]

Recommended Actions:
- [Specific action to reduce denial risk]
- [Additional documentation needed]

Similar Historical Claims:
- [X] submitted, [Y] denied ([Z%] denial rate)
```

OUTPUT FORMAT for RCM Analysis:
```
REVENUE CYCLE ANALYSIS
======================
Period: [Date range]

Key Metrics:
- Clean Claim Rate: [X%] (benchmark: 95%+)
- Denial Rate: [X%] (benchmark: <5%)
- Days in AR: [X] days (benchmark: <35)
- Net Collection Rate: [X%] (benchmark: >96%)

Top Denial Drivers:
1. [Category]: [X%] of denials — $[amount]
2. [Category]: [X%] of denials — $[amount]

Trend Analysis:
- [Key trend observation]
- [Emerging pattern]

Recommendations:
1. [Specific, actionable recommendation with expected impact]
2. [Recommendation]
```"""


class AnalyticsAgent(BaseClinicalAgent):
    """
    Revenue cycle analytics and denial prediction agent.

    Capabilities:
    - Pre-submission claim denial risk scoring
    - Denial root cause analysis
    - Revenue cycle KPI monitoring
    - Payer behavior trend detection
    - Financial impact quantification
    """

    def __init__(self, model_router, audit_logger):
        config = AgentConfig(
            name="rcm_analytics",
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0.2,
            daily_budget=40.0,
            per_request_limit=0.25,
            tools=["claims_database", "denial_history", "payer_rules", "financial_reports"],
            requires_phi_access=False,  # Works with de-identified aggregate data
            audit_level="summary",
        )
        super().__init__(config, model_router, audit_logger)

    def get_system_prompt(self) -> str:
        return ANALYTICS_SYSTEM_PROMPT

    @traceable(name="analytics.build_context")
    async def build_context(self, request: dict, patient_data: dict) -> str:
        """Build analytics-specific prompt with claims and RCM data."""
        task_type = request.get("task_type", "denial_prediction")

        if task_type == "denial_prediction":
            claim = request.get("claim_data", {})
            return f"""Assess denial risk for this claim before submission:

CLAIM DETAILS:
- CPT Code: {claim.get('cpt_code', 'Unknown')}
- ICD-10 Codes: {', '.join(claim.get('icd10_codes', []))}
- Payer: {claim.get('payer_name', 'Unknown')}
- Plan Type: {claim.get('plan_type', 'Unknown')}
- Billed Amount: ${claim.get('billed_amount', 0):.2f}
- Provider Specialty: {claim.get('specialty', 'Unknown')}

HISTORICAL PATTERNS:
- This CPT+Payer combination: {claim.get('historical_denial_rate', 'N/A')}% denial rate
- This provider's overall denial rate: {claim.get('provider_denial_rate', 'N/A')}%
- Documentation completeness score: {claim.get('doc_completeness', 'N/A')}%

DOCUMENTATION FLAGS:
{chr(10).join(f"  - {f}" for f in claim.get('flags', [])) or "  None"}
"""

        elif task_type == "root_cause_analysis":
            period = request.get("period", "last_30_days")
            denial_data = request.get("denial_data", {})
            return f"""Analyze denial root causes for the period: {period}

DENIAL SUMMARY:
- Total claims: {denial_data.get('total_claims', 0)}
- Total denials: {denial_data.get('total_denials', 0)}
- Denial rate: {denial_data.get('denial_rate', 0):.1f}%
- Total denied amount: ${denial_data.get('denied_amount', 0):,.2f}

BY DENIAL REASON:
{chr(10).join(f"  - {r['reason']}: {r['count']} claims (${r['amount']:,.2f})" for r in denial_data.get('by_reason', []))}

BY PAYER:
{chr(10).join(f"  - {p['payer']}: {p['denial_rate']:.1f}% denial rate ({p['count']} denials)" for p in denial_data.get('by_payer', []))}

BY PROCEDURE:
{chr(10).join(f"  - CPT {p['cpt']}: {p['denial_rate']:.1f}% denial rate ({p['count']} denials)" for p in denial_data.get('by_procedure', []))}

Provide root cause analysis with actionable recommendations.
"""

        else:  # rcm_dashboard
            return f"""Generate revenue cycle performance summary:

{request.get('financial_data', 'No financial data provided')}
"""
