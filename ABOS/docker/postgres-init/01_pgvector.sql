-- Runs automatically when the PostgreSQL container starts for the first time.
-- Enables the pgvector extension needed for the Level-2 memory layer.

CREATE EXTENSION IF NOT EXISTS vector;
