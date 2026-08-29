"""
Sales Department Agent

Handles: lead generation, CRM updates, outreach drafting,
pipeline analysis, win/loss analysis, deal qualification.

Tool implementations use MockSimulator for controlled stochastic variance.
See mock_simulator.py and SOURCE_OF_TRUTH.md §5 for parameter rationale.
"""

import random
from langchain_core.tools import tool

from backend.agents.department.base import BaseDepartmentAgent
from backend.agents.department.mock_simulator import get_simulator, ToolExecutionError


# ── Mock data helpers ─────────────────────────────────────────────────────────
# These produce realistic-enough structured output for the planner to chain
# downstream steps. Values are randomised per call so consecutive steps
# see varied data — important for evaluation validity.

def _mock_leads(criteria: str) -> dict:
    count = random.randint(3, 20)
    leads = [
        {
            "id": f"lead_{i:03d}",
            "name": f"Contact {i}",
            "company": f"Company {chr(65 + i % 26)}",
            "last_activity_days_ago": random.randint(30, 120),
            "score": round(random.uniform(0.4, 0.95), 2),
        }
        for i in range(count)
    ]
    return {
        "criteria": criteria,
        "total_found": count,
        "leads": leads,
        "summary": f"Found {count} leads matching '{criteria}'.",
    }


def _mock_outreach(lead_info: str, tone: str) -> dict:
    return {
        "lead_info": lead_info,
        "tone": tone,
        "subject": f"Re-connecting — exploring how we can help",
        "body": (
            f"Hi [Name],\n\nI noticed it's been a while since we last connected. "
            f"Given your role at [Company], I thought it worth reaching out again. "
            f"Would you be open to a brief call this week?\n\nBest,\n[Sender]"
        ),
        "word_count": 48,
    }


def _mock_crm_update(lead_id: str, status: str, notes: str) -> dict:
    return {
        "lead_id": lead_id,
        "updated_status": status,
        "notes_saved": bool(notes),
        "timestamp": "2026-08-16T10:00:00Z",
        "confirmation": f"CRM record {lead_id} updated to '{status}'.",
    }


def _mock_pipeline(time_range: str) -> dict:
    total = random.randint(20, 60)
    at_risk = random.randint(3, max(4, total // 5))
    return {
        "time_range": time_range,
        "total_deals": total,
        "total_value_usd": random.randint(200_000, 2_000_000),
        "at_risk_count": at_risk,
        "avg_days_in_stage": random.randint(10, 45),
        "win_rate_pct": round(random.uniform(18, 42), 1),
        "summary": (
            f"Pipeline has {total} active deals. "
            f"{at_risk} flagged as at-risk (no activity > 14 days)."
        ),
    }


def _mock_qualify(deal_info: str) -> dict:
    score = round(random.uniform(30, 95), 1)
    return {
        "deal_info": deal_info,
        "bant_score": score,
        "budget_confirmed": random.choice([True, False]),
        "authority_confirmed": random.choice([True, False]),
        "need_confirmed": True,
        "timeline_confirmed": random.choice([True, False]),
        "recommendation": "Proceed" if score >= 60 else "Nurture",
        "summary": f"BANT score: {score}/100. Recommendation: {'Proceed' if score >= 60 else 'Nurture'}.",
    }


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
async def search_leads(criteria: str) -> dict:
    """
    Search and filter leads based on given criteria.
    Input: a natural-language or structured criteria description.
    Returns: structured list of matching leads with scores and activity data.
    """
    return await get_simulator().run("search_leads", _mock_leads(criteria))


@tool
async def draft_outreach(lead_info: str, tone: str = "professional") -> dict:
    """
    Draft a personalized outreach message for a lead.
    Input: lead_info (name, company, context), tone (professional/friendly/urgent).
    Returns: structured outreach draft with subject and body.
    """
    return await get_simulator().run("draft_outreach", _mock_outreach(lead_info, tone))


@tool
async def update_crm(lead_id: str, status: str, notes: str = "") -> dict:
    """
    Update a CRM record with new status and notes.
    Input: lead_id, status (contacted/qualified/closed/lost), optional notes.
    Returns: confirmation of the update with timestamp.
    """
    return await get_simulator().run("update_crm", _mock_crm_update(lead_id, status, notes))


@tool
async def analyze_pipeline(time_range: str = "last_30_days") -> dict:
    """
    Analyze the sales pipeline and return a health summary.
    Input: time_range (e.g. last_30_days, last_quarter).
    Returns: pipeline metrics including deal count, value, at-risk count, win rate.
    """
    return await get_simulator().run("analyze_pipeline", _mock_pipeline(time_range))


@tool
async def qualify_deal(deal_info: str) -> dict:
    """
    Score and qualify a deal based on BANT criteria (Budget, Authority, Need, Timeline).
    Input: deal_info describing the opportunity.
    Returns: BANT score, per-criterion flags, and a Proceed/Nurture recommendation.
    """
    return await get_simulator().run("qualify_deal", _mock_qualify(deal_info))


# ── Agents ─────────────────────────────────────────────────────────────────────

class SalesOutreachFastAgent(BaseDepartmentAgent):
    name = "sales_outreach_fast"
    department = "sales"
    tools = [search_leads, draft_outreach, update_crm]

    def _get_system_prompt(self) -> str:
        return """\
You are the Fast Sales Outreach Agent for ABOS.

Your focus:
- Rapid single-pass lead query and filtering
- Concise personalized outreach drafting
- Quick CRM record updates

Process steps efficiently with concise, data-driven outputs.
"""


class SalesEnterpriseThoroughAgent(BaseDepartmentAgent):
    name = "sales_enterprise_thorough"
    department = "sales"
    tools = [search_leads, draft_outreach, update_crm, analyze_pipeline, qualify_deal]

    def _get_system_prompt(self) -> str:
        return """\
You are the Thorough Enterprise Sales Agent for ABOS.

Your focus:
- Comprehensive lead search & multi-stage criteria evaluation
- Detailed BANT deal qualification (Budget, Authority, Need, Timeline)
- In-depth sales pipeline health analysis and risk mitigation

Perform thorough, data-driven qualification and detailed multi-step validation.
"""


class SalesAgent(SalesOutreachFastAgent):
    name = "sales_agent"


# Agent candidate instances
sales_outreach_fast = SalesOutreachFastAgent()
sales_enterprise_thorough = SalesEnterpriseThoroughAgent()
sales_agent = sales_outreach_fast  # Default alias for backward compatibility / baseline primary
