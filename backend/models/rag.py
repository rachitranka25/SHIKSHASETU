"""
RAG (Retrieval-Augmented Generation) models.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..core.config import settings
from ..database import Base


def utcnow():
    """Get current UTC time as naive datetime (for TIMESTAMP WITHOUT TIME ZONE)."""
    return datetime.utcnow()


class DocumentChunk(Base):
    """Stores text chunks from uploaded documents for RAG."""

    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id = Column(
        UUID(as_uuid=True),
        ForeignKey("processed_content.id"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_size = Column(Integer)
    chunk_metadata = Column(
        JSONB
    )  # page number, section, etc. (renamed from 'metadata' to avoid SQLAlchemy reserved word)
    created_at = Column(TIMESTAMP, default=utcnow)


class Embedding(Base):
    """Stores vector embeddings for semantic search using pgvector."""

    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=False, index=True
    )
    content_id = Column(
        UUID(as_uuid=True),
        ForeignKey("processed_content.id"),
        nullable=False,
        index=True,
    )
    # Declared, not commented out: migration 019 makes this a real
    # vector(1024) with an HNSW cosine index. It was `double precision[]`
    # before, which meant rag.py's `embedding <=> :vector::vector` query
    # failed with "operator does not exist" on every search.
    #
    # The width is fixed in the migration and must match
    # settings.EMBEDDING_DIMENSION; changing embedding models needs a new
    # migration, not just a config edit.
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION))
    embedding_model = Column(String(100), default=settings.EMBEDDING_MODEL_ID)
    embedding_version = Column(
        Integer, default=2
    )  # Version 2 = E5-large (1024-dim), Version 1 = MiniLM (384-dim)
    created_at = Column(TIMESTAMP, default=utcnow)


class ChatHistory(Base):
    """Stores Q&A chat history for context-aware conversations."""

    __tablename__ = "chat_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_id = Column(
        UUID(as_uuid=True),
        ForeignKey("processed_content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    context_chunks = Column(ARRAY(UUID(as_uuid=True)))  # IDs of chunks used
    confidence_score = Column(Float)
    created_at = Column(TIMESTAMP, default=utcnow, index=True)
