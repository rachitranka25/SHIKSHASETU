"""Store embeddings as pgvector and build a real HNSW index

Revision ID: 019_real_pgvector_embeddings
Revises: 018_add_chat_conversations
Create Date: 2026-08-09 00:00:00.000000

Semantic search has never been able to run.

backend/services/rag.py queries with the pgvector cosine operator:

    1 - (e.embedding <=> :vector::vector) AS similarity

but embeddings.embedding is `double precision[]`, so every such query dies on

    operator does not exist: double precision[] <=> vector

The intent was there and got stubbed out. Migration 010 has the column change
commented out with a note that it "requires recreating the column". Migration
012 skips HNSW creation entirely — "Bypassing HNSW index creation due to
missing pgvector extension" — substitutes a plain btree on content_id named
idx_embeddings_content_id_hnsw, and then prints that it created three HNSW
indexes. The name and the log both describe something that was never built.

The reason underneath was environmental: pgvector was not installed for the
running PostgreSQL, so the migrations degraded rather than failing. Degrading
silently is what let the mismatch survive this long, so this migration does the
opposite and refuses to run without the extension.

Safe as a conversion: all three RAG tables are empty. Should that stop being
true, the USING clause below round-trips through text and preserves values.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '019_real_pgvector_embeddings'
down_revision = '018_add_chat_conversations'
branch_labels = None
depends_on = None

# Must match settings.EMBEDDING_DIMENSION. BAAI/bge-m3 emits 1024 dimensions.
# pgvector requires a fixed width on the column, so this cannot read config at
# runtime — changing embedding models means a new migration.
EMBEDDING_DIM = 1024


def upgrade():
    """Convert the embedding column to vector(1024) and index it for cosine search."""

    # Fail loudly rather than degrade. A silent fallback is what produced the
    # btree-named-hnsw that this migration is here to replace.
    connection = op.get_bind()
    has_vector = connection.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    ).scalar()

    if not has_vector:
        raise RuntimeError(
            "pgvector is not enabled on this database, so embeddings cannot be "
            "stored as vectors and semantic search cannot work.\n"
            "Install it for the *running* server version, then:\n"
            "    CREATE EXTENSION vector;\n"
            "See the pgvector notes in README.md — Homebrew builds the extension "
            "only for the PostgreSQL versions it currently supports, so the "
            "install can succeed while leaving your server without it."
        )

    # The btree that migration 012 created in place of an HNSW index. Its name
    # claims otherwise, so drop it before anything starts trusting it.
    op.execute("DROP INDEX IF EXISTS idx_embeddings_content_id_hnsw")

    # float8[] -> vector. The text round-trip is what pgvector accepts as a
    # conversion; with rows present it preserves every component.
    op.execute(
        f"""
        ALTER TABLE embeddings
        ALTER COLUMN embedding TYPE vector({EMBEDDING_DIM})
        USING embedding::text::vector({EMBEDDING_DIM})
        """
    )

    # A real HNSW index, for the operator rag.py actually uses.
    # Cosine only: the query is `1 - (embedding <=> query)`, and an index built
    # for a different operator class would simply never be chosen.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw_cosine
        ON embeddings USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Retrieval is almost always scoped to one document, and that filter runs
    # before the vector scan.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_content_id_btree
        ON embeddings (content_id)
        """
    )


def downgrade():
    """Return the column to a float array and restore the previous indexes."""
    op.execute("DROP INDEX IF EXISTS idx_embeddings_hnsw_cosine")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_content_id_btree")

    op.execute(
        """
        ALTER TABLE embeddings
        ALTER COLUMN embedding TYPE double precision[]
        USING embedding::text::double precision[]
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_content_id_hnsw
        ON embeddings (content_id)
        """
    )
