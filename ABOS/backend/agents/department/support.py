"""
Customer Support Department Agent

Handles: ticket triage, response drafting, escalation decisions,
sentiment analysis, CSAT improvement.
"""

from langchain_core.tools import tool
from backend.agents.department.base import BaseDepartmentAgent


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def triage_ticket(ticket_content: str) -> str:
    """
    Classify a support ticket by type and priority.
    Input: raw ticket content (subject + body).
    Returns: type (billing/technical/general/complaint), priority (low/medium/high/critical).
    """
    # TODO: integrate with support desk API
    return f"[triage_ticket] Triaged ticket: '{ticket_content[:80]}...' (stub)."


@tool
def draft_response(ticket_id: str, ticket_content: str, tone: str = "empathetic") -> str:
    """
    Draft a customer-facing response for a support ticket.
    Input: ticket_id, ticket_content, tone (empathetic/formal/technical).
    Returns a draft response message.
    """
    # TODO: use LLM sub-call for response drafting
    return f"[draft_response] Draft response for ticket '{ticket_id}' (stub)."


@tool
def escalate(ticket_id: str, reason: str) -> str:
    """
    Escalate a ticket to a human agent or specialist team.
    Input: ticket_id, reason for escalation.
    Returns confirmation and escalation path.
    """
    # TODO: integrate with escalation workflow
    return f"[escalate] Ticket '{ticket_id}' escalated. Reason: '{reason}' (stub)."


@tool
def analyze_sentiment(text: str) -> str:
    """
    Analyze the sentiment of a customer message or ticket batch.
    Input: text or comma-separated ticket IDs.
    Returns: sentiment score (positive/neutral/negative) and confidence.
    """
    return f"[analyze_sentiment] Sentiment analysis for: '{text[:80]}' (stub)."


@tool
def get_csat_summary(time_range: str = "last_30_days") -> str:
    """
    Retrieve CSAT (Customer Satisfaction Score) summary for a time range.
    Input: time_range (e.g. last_30_days, last_quarter).
    Returns: average CSAT score, low-rated ticket count, common complaint themes.
    """
    return f"[get_csat_summary] CSAT summary for '{time_range}' (stub)."


# ── Agent ─────────────────────────────────────────────────────────────────────

class SupportAgent(BaseDepartmentAgent):
    name = "support_agent"
    department = "support"
    tools = [triage_ticket, draft_response, escalate, analyze_sentiment, get_csat_summary]

    def _get_system_prompt(self) -> str:
        return """\
You are the Customer Support Department Agent for ABOS.

Your responsibilities:
- Triage and classify incoming support tickets
- Draft empathetic, accurate customer responses
- Identify tickets requiring human escalation
- Analyze customer sentiment and satisfaction trends
- Recommend CSAT improvement actions

Always prioritize customer experience. Be clear, concise, and actionable.
If a tool is not yet integrated (returns a stub), acknowledge it and provide a reasoned recommendation.
"""


# Singleton instance used by the graph
support_agent = SupportAgent()
