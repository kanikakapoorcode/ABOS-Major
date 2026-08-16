"""
Research & Analytics Department Agent

Handles: data queries, trend analysis, KPI reporting,
market research, segment comparison, churn signal analysis.
"""

from langchain_core.tools import tool
from backend.agents.department.base import BaseDepartmentAgent


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def query_data(query: str, data_source: str = "default") -> str:
    """
    Run a structured data query against a specified data source.
    Input: natural-language or SQL-like query, data_source name.
    Returns: query results as a structured summary.
    """
    # TODO: integrate with analytics data source / data warehouse
    return f"[query_data] Query: '{query}' on source '{data_source}' (stub)."


@tool
def analyze_trends(metric: str, time_range: str = "last_90_days") -> str:
    """
    Identify and describe trends for a given metric over a time period.
    Input: metric name (e.g. 'monthly_revenue', 'churn_rate'), time_range.
    Returns: trend direction, magnitude, and notable inflection points.
    """
    return f"[analyze_trends] Trend analysis for '{metric}' over '{time_range}' (stub)."


@tool
def generate_report(report_type: str, parameters: str = "") -> str:
    """
    Generate a structured business report.
    Input: report_type (e.g. monthly_kpi, quarterly_review, churn_analysis), parameters.
    Returns: a formatted report with key findings and recommendations.
    """
    # TODO: use LLM sub-call for narrative generation
    return f"[generate_report] Report '{report_type}' with params '{parameters}' (stub)."


@tool
def compare_segments(segment_a: str, segment_b: str, metric: str) -> str:
    """
    Compare two customer or product segments on a specified metric.
    Input: segment_a, segment_b (names or filter criteria), metric.
    Returns: comparison table with statistical summary.
    """
    return f"[compare_segments] Comparing '{segment_a}' vs '{segment_b}' on '{metric}' (stub)."


@tool
def detect_churn_signals(time_range: str = "last_30_days", threshold: float = 0.7) -> str:
    """
    Identify customers showing behavioural signals of churn risk.
    Input: time_range, threshold (churn probability cutoff).
    Returns: list of at-risk customer IDs with risk scores.
    """
    return f"[detect_churn_signals] Churn detection for '{time_range}', threshold={threshold} (stub)."


# ── Agent ─────────────────────────────────────────────────────────────────────

class ResearchAgent(BaseDepartmentAgent):
    name = "research_agent"
    department = "research"
    tools = [query_data, analyze_trends, generate_report, compare_segments, detect_churn_signals]

    def _get_system_prompt(self) -> str:
        return """\
You are the Research & Analytics Department Agent for ABOS.

Your responsibilities:
- Run data queries and surface relevant insights
- Identify trends in business metrics
- Generate structured KPI and performance reports
- Compare customer or product segments
- Detect early churn signals and at-risk customers

Be precise, data-driven, and concise. Structure outputs clearly.
If a tool is not yet integrated (returns a stub), acknowledge it and provide a reasoned recommendation based on the available information.
"""


# Singleton instance used by the graph
research_agent = ResearchAgent()
