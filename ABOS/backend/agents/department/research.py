"""
Research & Analytics Department Agent

Handles: data queries, trend analysis, KPI reporting,
market research, segment comparison, churn signal analysis.

Tool implementations use MockSimulator for controlled stochastic variance.
See mock_simulator.py and SOURCE_OF_TRUTH.md §5 for parameter rationale.
"""

import random
from langchain_core.tools import tool

from backend.agents.department.base import BaseDepartmentAgent
from backend.agents.department.mock_simulator import get_simulator, ToolExecutionError


# ── Mock data helpers ─────────────────────────────────────────────────────────

def _mock_query(query: str, data_source: str) -> dict:
    row_count = random.randint(10, 500)
    return {
        "query": query,
        "data_source": data_source,
        "rows_returned": row_count,
        "columns": ["id", "value", "date", "segment", "metric"],
        "sample_rows": [
            {
                "id": f"row_{i}",
                "value": round(random.uniform(100, 10000), 2),
                "date": f"2026-{random.randint(1,8):02d}-{random.randint(1,28):02d}",
                "segment": random.choice(["enterprise", "smb", "startup"]),
                "metric": random.choice(["revenue", "engagement", "churn_risk"]),
            }
            for i in range(min(5, row_count))
        ],
        "summary": f"Query returned {row_count} rows from '{data_source}'.",
    }


def _mock_trends(metric: str, time_range: str) -> dict:
    directions = ["upward", "downward", "flat", "volatile"]
    direction = random.choices(directions, weights=[0.35, 0.30, 0.20, 0.15])[0]
    change_pct = round(random.uniform(-25, 40), 1)
    return {
        "metric": metric,
        "time_range": time_range,
        "trend_direction": direction,
        "change_pct": change_pct,
        "peak_period": f"2026-{random.randint(1,8):02d}",
        "trough_period": f"2026-{random.randint(1,8):02d}",
        "inflection_points": random.randint(0, 3),
        "summary": (
            f"{metric} shows a {direction} trend over {time_range} "
            f"({'+' if change_pct >= 0 else ''}{change_pct}% change). "
            f"{random.randint(0,3)} notable inflection points detected."
        ),
    }


def _mock_report(report_type: str, parameters: str) -> dict:
    kpis = {
        "monthly_revenue": round(random.uniform(80_000, 500_000), 2),
        "new_customers": random.randint(20, 200),
        "churn_rate_pct": round(random.uniform(1.5, 8.0), 2),
        "avg_deal_size_usd": round(random.uniform(2000, 25000), 2),
        "nps_score": random.randint(20, 72),
        "support_csat": round(random.uniform(3.2, 4.9), 2),
    }
    return {
        "report_type": report_type,
        "parameters": parameters,
        "period": "2026-08",
        "kpis": kpis,
        "highlights": [
            f"Revenue {'up' if random.random() > 0.4 else 'down'} {round(random.uniform(2,15),1)}% MoM",
            f"Churn rate {'increased' if random.random() > 0.5 else 'decreased'} this period",
            f"NPS score: {kpis['nps_score']}",
        ],
        "recommendations": [
            "Focus retention efforts on SMB segment",
            "Invest in onboarding improvements to reduce early churn",
        ],
        "summary": f"{report_type} report generated. Revenue: ${kpis['monthly_revenue']:,.2f}. Churn: {kpis['churn_rate_pct']}%.",
    }


def _mock_compare(segment_a: str, segment_b: str, metric: str) -> dict:
    val_a = round(random.uniform(1000, 50000), 2)
    val_b = round(random.uniform(1000, 50000), 2)
    diff_pct = round((val_a - val_b) / val_b * 100, 1)
    return {
        "metric": metric,
        "segment_a": {"name": segment_a, "value": val_a, "sample_size": random.randint(50, 500)},
        "segment_b": {"name": segment_b, "value": val_b, "sample_size": random.randint(50, 500)},
        "difference_pct": diff_pct,
        "statistical_significance": random.choice(["p<0.05", "p<0.01", "p=0.08 (not significant)"]),
        "summary": (
            f"{segment_a} vs {segment_b} on {metric}: "
            f"{segment_a} is {abs(diff_pct):.1f}% "
            f"{'higher' if diff_pct > 0 else 'lower'}."
        ),
    }


def _mock_churn(time_range: str, threshold: float) -> dict:
    total_customers = random.randint(200, 2000)
    at_risk_count = int(total_customers * random.uniform(0.05, 0.20))
    signals = random.sample(
        [
            "no login in 30+ days",
            "support ticket spike",
            "declining usage",
            "contract renewal approaching",
            "negative sentiment in tickets",
            "reduced feature adoption",
        ],
        k=random.randint(2, 4),
    )
    return {
        "time_range": time_range,
        "threshold": threshold,
        "total_customers_analyzed": total_customers,
        "at_risk_count": at_risk_count,
        "at_risk_pct": round(at_risk_count / total_customers * 100, 1),
        "top_risk_signals": signals,
        "high_value_at_risk": random.randint(2, max(3, at_risk_count // 5)),
        "sample_at_risk_ids": [f"cust_{random.randint(1000,9999)}" for _ in range(5)],
        "summary": (
            f"{at_risk_count} customers ({round(at_risk_count/total_customers*100,1)}%) "
            f"flagged as churn risk. Top signals: {', '.join(signals[:2])}."
        ),
    }


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
async def query_data(query: str, data_source: str = "default") -> dict:
    """
    Run a structured data query against a specified data source.
    Input: natural-language or structured query description, data_source name.
    Returns: row count, column list, sample rows, and query summary.
    """
    return await get_simulator().run("query_data", _mock_query(query, data_source))


@tool
async def analyze_trends(metric: str, time_range: str = "last_90_days") -> dict:
    """
    Identify and describe trends for a given metric over a time period.
    Input: metric name (e.g. monthly_revenue, churn_rate), time_range.
    Returns: trend direction, change percentage, inflection points.
    """
    return await get_simulator().run("analyze_trends", _mock_trends(metric, time_range))


@tool
async def generate_report(report_type: str, parameters: str = "") -> dict:
    """
    Generate a structured business report.
    Input: report_type (monthly_kpi, quarterly_review, churn_analysis), parameters.
    Returns: KPI dict, highlights, recommendations, and executive summary.
    """
    return await get_simulator().run("generate_report", _mock_report(report_type, parameters))


@tool
async def compare_segments(segment_a: str, segment_b: str, metric: str) -> dict:
    """
    Compare two customer or product segments on a specified metric.
    Input: segment_a name, segment_b name, metric to compare.
    Returns: values per segment, difference percentage, statistical significance.
    """
    return await get_simulator().run(
        "compare_segments", _mock_compare(segment_a, segment_b, metric)
    )


@tool
async def detect_churn_signals(time_range: str = "last_30_days", threshold: float = 0.7) -> dict:
    """
    Identify customers showing behavioural signals of churn risk.
    Input: time_range, threshold (churn probability cutoff 0.0-1.0).
    Returns: at-risk count, percentage, top signals, high-value customers at risk.
    """
    return await get_simulator().run(
        "detect_churn_signals", _mock_churn(time_range, threshold)
    )


# ── Agents ─────────────────────────────────────────────────────────────────────

class ResearchKPIQuickAgent(BaseDepartmentAgent):
    name = "research_kpi_quick"
    department = "research"
    tools = [query_data, analyze_trends, generate_report]

    def _get_system_prompt(self) -> str:
        return """\
You are the Quick KPI Research Agent for ABOS.

Your focus:
- Rapid data querying across primary metrics
- Fast trend direction extraction
- Direct executive summary report generation

Surface key metrics quickly and concisely.
"""


class ResearchDeepAnalystAgent(BaseDepartmentAgent):
    name = "research_deep_analyst"
    department = "research"
    tools = [query_data, analyze_trends, generate_report, compare_segments, detect_churn_signals]

    def _get_system_prompt(self) -> str:
        return """\
You are the Deep Analytics Research Agent for ABOS.

Your focus:
- Comprehensive multi-source data queries & statistical trend analysis
- Multi-segment comparative analysis (enterprise vs SMB vs startup)
- Early churn signal detection and risk-scored customer prioritization

Perform thorough statistical analysis, segment comparisons, and deep metric synthesis.
"""


class ResearchAgent(ResearchKPIQuickAgent):
    name = "research_agent"


# Agent candidate instances
research_kpi_quick = ResearchKPIQuickAgent()
research_deep_analyst = ResearchDeepAnalystAgent()
research_agent = research_kpi_quick  # Default alias for backward compatibility / baseline primary
