"""SQLAlchemy Core tables mirroring migrations/versions/0001_baseline.py.

Deliberately decoupled from the migration: migrations own DDL history, this
module is the read/write contract repositories query against.
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR

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
