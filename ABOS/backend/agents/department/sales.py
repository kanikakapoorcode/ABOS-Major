"""
Sales Department Agent

Handles: lead generation, CRM updates, outreach drafting,
pipeline analysis, win/loss analysis, deal qualification.
"""

from langchain_core.tools import tool
from backend.agents.department.base import BaseDepartmentAgent


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def search_leads(criteria: str) -> str:
    """
    Search and filter leads based on given criteria.
    Input: a natural-language or structured criteria description.
    Returns a list of matching lead summaries.
    """
    # TODO: integrate with actual CRM data source
    return f"[search_leads] Searched leads with criteria: '{criteria}'. Found 0 leads (stub)."


@tool
def draft_outreach(lead_info: str, tone: str = "professional") -> str:
    """
    Draft a personalized outreach message for a lead.
    Input: lead_info (name, company, context), tone (professional/friendly/urgent).
    Returns a draft outreach email or message.
    """
    # TODO: use LLM sub-call for personalized drafting
    return f"[draft_outreach] Draft outreach for: '{lead_info}' with tone '{tone}' (stub)."


@tool
def update_crm(lead_id: str, status: str, notes: str = "") -> str:
    """
    Update a CRM record with new status and notes.
    Input: lead_id, status (e.g. contacted/qualified/closed), optional notes.
    Returns confirmation of the update.
    """
    # TODO: integrate with CRM API
    return f"[update_crm] Updated lead '{lead_id}' to status '{status}' (stub)."


@tool
def analyze_pipeline(time_range: str = "last_30_days") -> str:
    """
    Analyze the sales pipeline and return a health summary.
    Input: time_range (e.g. last_30_days, last_quarter).
    Returns pipeline metrics and at-risk deal summary.
    """
    # TODO: query execution database for pipeline data
    return f"[analyze_pipeline] Pipeline analysis for '{time_range}' (stub)."


@tool
def qualify_deal(deal_info: str) -> str:
    """
    Score and qualify a deal based on BANT criteria (Budget, Authority, Need, Timeline).
    Input: deal_info describing the opportunity.
    Returns a qualification score and recommendation.
    """
    return f"[qualify_deal] Qualification for: '{deal_info}' (stub)."


# ── Agent ─────────────────────────────────────────────────────────────────────

class SalesAgent(BaseDepartmentAgent):
    name = "sales_agent"
    department = "sales"
    tools = [search_leads, draft_outreach, update_crm, analyze_pipeline, qualify_deal]

    def _get_system_prompt(self) -> str:
        return """\
You are the Sales Department Agent for ABOS.

Your responsibilities:
- Generate and qualify leads
- Draft personalized outreach communications
- Update CRM records with outcomes
- Analyze pipeline health and flag at-risk deals
- Provide win/loss analysis

You have access to tools for lead search, outreach drafting, CRM updates, and pipeline analysis.
Always be specific and data-driven. Return structured, actionable outputs.
If a tool is not yet integrated (returns a stub), acknowledge it and provide a reasoned recommendation.
"""


# Singleton instance used by the graph
sales_agent = SalesAgent()
