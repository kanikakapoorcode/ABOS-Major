"""
Level-2 Explicit-Feedback Memory Layer

Implementation of Level-2 memory per the Governance-by-Design (2026) maturity model.
NOTE: The maturity framework is from existing literature. This is an implementation
of that model for adaptive workflow planning — not a claimed novel framework.

Two operations:
  1. retrieve() — called before planning to inject similar past feedback
  2. store_embedding() — called after feedback submission to persist the vector
"""

import logging
from typing import Any, Dict, List

from sqlalchemy import text

from backend.agents.memory.embeddings import embed_text
from backend.agents.state import ABOSState
from backend.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Number of similar feedback entries to retrieve
RETRIEVAL_TOP_K = 5

# Minimum similarity threshold (cosine distance — lower is more similar)
# pgvector uses <=> for cosine distance; 0 = identical, 2 = opposite
SIMILARITY_THRESHOLD = 1.0


async def retrieve_similar_feedback(goal_description: str) -> List[Dict[str, Any]]:
    """
    Embed the goal description and retrieve the top-K most similar
    past feedback entries from pgvector.

    Returns a list of dicts with keys: rating, correction, suggested_agent
    """
    query_embedding = await embed_text(goal_description)

    # Skip retrieval if embedding failed (all zeros)
    if all(v == 0.0 for v in query_embedding):
        logger.warning("[Memory] Embedding failed — skipping memory retrieval.")
        return []

    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    sql = text("""
        SELECT
            f.rating,
            f.correction,
            f.suggested_agent,
            1 - (f.embedding <=> :embedding ::vector) AS similarity
        FROM feedback f
        WHERE f.embedding IS NOT NULL
          AND (f.embedding <=> :embedding ::vector) < :threshold
        ORDER BY f.embedding <=> :embedding ::vector
        LIMIT :top_k
    """)

    results = []
    try:
        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                sql,
                {
                    "embedding": embedding_str,
                    "threshold": SIMILARITY_THRESHOLD,
                    "top_k": RETRIEVAL_TOP_K,
                },
            )
            for row in rows.mappings():
                results.append({
                    "rating": row["rating"],
                    "correction": row["correction"],
                    "suggested_agent": row["suggested_agent"],
                    "similarity": round(float(row["similarity"]), 4),
                })
    except Exception as e:
        logger.error(f"[Memory] Retrieval failed: {e}")

    logger.info(f"[Memory] Retrieved {len(results)} similar feedback entries.")
    return results


async def store_feedback_embedding(feedback_id: str, text: str) -> None:
    """
    Compute and persist the embedding for a feedback correction.
    Called by Celery after a feedback entry is created.
    """
    embedding = await embed_text(text)

    if all(v == 0.0 for v in embedding):
        logger.warning(f"[Memory] Skipping embedding store for feedback {feedback_id} — embed failed.")
        return

    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

    sql = text("""
        UPDATE feedback
        SET embedding = :embedding ::vector
        WHERE id = :feedback_id
    """)

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(sql, {"embedding": embedding_str, "feedback_id": feedback_id})
            await session.commit()
        logger.info(f"[Memory] Stored embedding for feedback {feedback_id}.")
    except Exception as e:
        logger.error(f"[Memory] Failed to store embedding for feedback {feedback_id}: {e}")


async def memory_retrieval_node(state: ABOSState) -> Dict[str, Any]:
    """
    LangGraph node: Memory Retrieval.

    Runs before the planner. Retrieves similar past feedback
    and injects it into state for the planner to use.

    Reads:  goal_description
    Writes: retrieved_memory, logs
    """
    logger.info(f"[Memory] Retrieving for goal_id={state['goal_id']}")

    feedback = await retrieve_similar_feedback(state["goal_description"])

    return {
        "retrieved_memory": feedback,
        "logs": [f"Memory: retrieved {len(feedback)} similar past feedback entries."],
    }
