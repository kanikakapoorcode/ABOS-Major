"""
Safe Migration Script: Migrate Cold-Start Agent Profiles
=========================================================

PURPOSE:
  Resets unexecuted agent profiles (total_executions == 0) from legacy default values (1.0)
  to honest neutral cold-start priors (success_rate = 0.5, confidence_score = 0.2, avg_latency_ms = 0.0).

SCIENTIFIC INTEGRITY SAFEGUARD:
  Profiles with total_executions > 0 containing real historical evidence are STRICTLY PRESERVED
  and NEVER overwritten.

Usage:
  poetry run python scripts/migrate_cold_start_profiles.py
"""

import asyncio
import logging
import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from backend.db.session import AsyncSessionLocal
from backend.db.models.agent_profile import AgentProfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("migration")


async def migrate_profiles():
    logger.info("Starting safe cold-start profile migration...")

    async with AsyncSessionLocal() as session:
        # Load all agent profiles
        result = await session.execute(select(AgentProfile))
        profiles = list(result.scalars().all())

        if not profiles:
            logger.info("No agent profiles found in database. Nothing to migrate.")
            return

        migrated_count = 0
        preserved_count = 0

        for p in profiles:
            if p.total_executions == 0:
                old_sr = p.success_rate
                old_conf = p.confidence_score
                p.success_rate = 0.5
                p.confidence_score = 0.2
                p.avg_latency_ms = 0.0
                migrated_count += 1
                logger.info(
                    f"[MIGRATED] Agent '{p.agent_name}' ({p.department}): "
                    f"total_executions=0 | SR {old_sr} -> 0.5 | Conf {old_conf} -> 0.2 | Latency -> 0.0ms (Prior = 0.41)"
                )
            else:
                preserved_count += 1
                logger.info(
                    f"[PRESERVED] Agent '{p.agent_name}' ({p.department}): "
                    f"total_executions={p.total_executions} | SR={p.success_rate:.2f} | Latency={p.avg_latency_ms:.1f}ms | Conf={p.confidence_score:.2f} (Real History Preserved)"
                )

        if migrated_count > 0:
            await session.commit()
            logger.info(f"Successfully committed migration for {migrated_count} cold-start profiles.")
        else:
            logger.info("No cold-start profiles needed migration.")

        logger.info(f"Migration Summary: {migrated_count} reset to neutral prior, {preserved_count} preserved with real history.")


if __name__ == "__main__":
    asyncio.run(migrate_profiles())
