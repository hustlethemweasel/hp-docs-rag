"""SQLAlchemy Core tables mirroring migrations/versions/0001_baseline.py.

Deliberately decoupled from the migration: migrations own DDL history, this
module is the read/write contract repositories query against.
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

EMBEDDING_DIM = 640

metadata = sa.MetaData()

documents_table = sa.Table(
    "documents",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("filename", sa.Text, nullable=False),
    sa.Column("sha256", sa.String(64), nullable=False),
    sa.Column("page_count", sa.Integer, nullable=False),
)

chunks_table = sa.Table(
    "chunks",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("document_id", sa.Integer, nullable=False),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
    sa.Column("tsv", TSVECTOR, nullable=False),
    sa.Column("page_start", sa.Integer, nullable=False),
    sa.Column("page_end", sa.Integer, nullable=False),
    sa.Column("section", sa.Text),
    sa.Column("chunk_type", sa.Text, nullable=False),
    sa.Column("figure_ref", sa.Text),
    sa.Column("token_count", sa.Integer, nullable=False),
    sa.Column("chunk_index", sa.Integer, nullable=False),
)

conversations_table = sa.Table(
    "conversations",
    metadata,
    sa.Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("user_id", UUID(as_uuid=True), nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

messages_table = sa.Table(
    "messages",
    metadata,
    sa.Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("conversation_id", UUID(as_uuid=True), nullable=False),
    sa.Column(
        "role", sa.Enum("user", "assistant", name="message_role"), nullable=False
    ),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("sources", JSONB),
    sa.Column("provider", sa.Text),
    sa.Column("model", sa.Text),
    sa.Column("latency_ms", sa.Integer),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
