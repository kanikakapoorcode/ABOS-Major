"""
Customer Support Department Agent

Handles: ticket triage, response drafting, escalation decisions,
sentiment analysis, CSAT improvement.

Tool implementations use MockSimulator for controlled stochastic variance.
See mock_simulator.py and SOURCE_OF_TRUTH.md §5 for parameter rationale.
"""

import random
from langchain_core.tools import tool

from backend.agents.department.base import BaseDepartmentAgent
from backend.agents.department.mock_simulator import get_simulator, ToolExecutionError


# ── Mock data helpers ─────────────────────────────────────────────────────────

def _mock_triage(ticket_content: str) -> dict:
    types = ["billing", "technical", "general", "complaint", "feature_request"]
    priorities = ["low", "medium", "high", "critical"]
    weights = [0.15, 0.40, 0.25, 0.15, 0.05]
    priority_weights = [0.20, 0.45, 0.25, 0.10]
    return {
        "ticket_preview": ticket_content[:100],
        "type": random.choices(types, weights=weights)[0],
        "priority": random.choices(priorities, weights=priority_weights)[0],
        "estimated_resolution_hours": random.choice([1, 2, 4, 8, 24, 48]),
        "requires_escalation": random.random() < 0.15,
        "tags": random.sample(
            ["billing", "bug", "account", "slow", "error", "refund", "login"], k=random.randint(1, 3)
        ),
    }


def _mock_response(ticket_id: str, ticket_content: str, tone: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "tone": tone,
        "subject": f"Re: Your support request #{ticket_id}",
        "body": (
            f"Dear Customer,\n\n"
            f"Thank you for reaching out. I've reviewed your request and I'm happy to help. "
            f"Based on what you've described, here is what we recommend:\n\n"
            f"[Recommended action based on ticket context]\n\n"
            f"Please let us know if this resolves your issue or if you need further assistance.\n\n"
            f"Best regards,\nSupport Team"
        ),
        "estimated_send_time": "2026-08-16T10:00:00Z",
        "word_count": 62,
    }


def _mock_escalate(ticket_id: str, reason: str) -> dict:
    teams = ["tier2_technical", "billing_specialist", "account_manager", "engineering"]
    return {
        "ticket_id": ticket_id,
        "reason": reason,
        "escalated_to": random.choice(teams),
        "escalation_id": f"ESC-{random.randint(10000, 99999)}",
        "sla_hours": random.choice([4, 8, 24]),
        "confirmation": f"Ticket {ticket_id} escalated successfully.",
    }


def _mock_sentiment(text: str) -> dict:
    sentiments = ["positive", "neutral", "negative"]
    weights = [0.25, 0.35, 0.40]
    sentiment = random.choices(sentiments, weights=weights)[0]
    score = {
        "positive": round(random.uniform(0.60, 0.95), 3),
        "neutral": round(random.uniform(0.40, 0.65), 3),
        "negative": round(random.uniform(0.55, 0.90), 3),
    }[sentiment]
    return {
        "input_preview": text[:100],
        "sentiment": sentiment,
        "score": score,
        "magnitude": round(random.uniform(0.3, 1.0), 3),
        "key_phrases": random.sample(
            ["frustrated", "waiting", "resolved", "happy", "confused", "urgent", "thanks"],
            k=random.randint(2, 4),
        ),
    }


def _mock_csat(time_range: str) -> dict:
    avg = round(random.uniform(3.1, 4.8), 2)
    total = random.randint(80, 500)
    low_count = int(total * random.uniform(0.05, 0.25))
    themes = random.sample(
        [
            "slow response time",
            "unclear instructions",
            "billing confusion",
            "bug not resolved",
            "agent not helpful",
            "long wait time",
        ],
        k=random.randint(2, 4),
    )
    return {
        "time_range": time_range,
        "avg_csat_score": avg,
        "total_responses": total,
        "low_rated_count": low_count,
        "low_rated_pct": round(low_count / total * 100, 1),
        "top_complaint_themes": themes,
        "summary": (
            f"Average CSAT: {avg}/5.0 over {time_range}. "
            f"{low_count} low-rated tickets ({round(low_count/total*100,1)}%). "
            f"Top themes: {', '.join(themes[:2])}."
        ),
    }


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
async def triage_ticket(ticket_content: str) -> dict:
    """
    Classify a support ticket by type and priority.
    Input: raw ticket content (subject + body).
    Returns: type, priority, estimated resolution time, escalation flag, tags.
    """
    return await get_simulator().run("triage_ticket", _mock_triage(ticket_content))


@tool
async def draft_response(ticket_id: str, ticket_content: str, tone: str = "empathetic") -> dict:
    """
    Draft a customer-facing response for a support ticket.
    Input: ticket_id, ticket_content, tone (empathetic/formal/technical).
    Returns: structured response with subject, body, and estimated send time.
    """
    return await get_simulator().run(
        "draft_response", _mock_response(ticket_id, ticket_content, tone)
    )


@tool
async def escalate(ticket_id: str, reason: str) -> dict:
    """
    Escalate a ticket to a specialist team.
    Input: ticket_id, reason for escalation.
    Returns: escalation ID, assigned team, SLA hours, confirmation.
    """
    return await get_simulator().run("escalate", _mock_escalate(ticket_id, reason))


@tool
async def analyze_sentiment(text: str) -> dict:
    """
    Analyze the sentiment of a customer message or ticket batch.
    Input: text content or ticket summary.
    Returns: sentiment label, score, magnitude, and key phrases.
    """
    return await get_simulator().run("analyze_sentiment", _mock_sentiment(text))


@tool
async def get_csat_summary(time_range: str = "last_30_days") -> dict:
    """
    Retrieve CSAT summary for a time range.
    Input: time_range (e.g. last_30_days, last_quarter).
    Returns: avg score, total responses, low-rated count, top complaint themes.
    """
    return await get_simulator().run("get_csat_summary", _mock_csat(time_range))


# ── Agents ─────────────────────────────────────────────────────────────────────

class SupportTier1FastAgent(BaseDepartmentAgent):
    name = "support_tier1_fast"
    department = "support"
    tools = [triage_ticket, draft_response, escalate]

    def _get_system_prompt(self) -> str:
        return """\
You are the Tier-1 Fast Customer Support Agent for ABOS.

Your focus:
- Rapid ticket triage and initial classification
- Standard customer response drafting
- Direct escalation to specialist teams when flagged

Deliver swift customer support resolution.
"""


class SupportTier2SpecialistAgent(BaseDepartmentAgent):
    name = "support_tier2_specialist"
    department = "support"
    tools = [triage_ticket, draft_response, escalate, analyze_sentiment, get_csat_summary]

    def _get_system_prompt(self) -> str:
        return """\
You are the Tier-2 Specialist Customer Support Agent for ABOS.

Your focus:
- Comprehensive ticket triage and sentiment analysis
- Empathetic, detailed response drafting for complex tickets
- Root-cause escalation analysis and CSAT summary synthesis

Perform thorough investigation and detailed resolution for high-priority support issues.
"""


class SupportAgent(SupportTier1FastAgent):
    name = "support_agent"


# Agent candidate instances
support_tier1_fast = SupportTier1FastAgent()
support_tier2_specialist = SupportTier2SpecialistAgent()
support_agent = support_tier1_fast  # Default alias for backward compatibility / baseline primary
