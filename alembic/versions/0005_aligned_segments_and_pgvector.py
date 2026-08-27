"""aligned_segments and pgvector

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-24 10:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable the pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create the aligned_segments table
    op.create_table(
        'aligned_segments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('start_seconds', sa.Float(), nullable=False),
        sa.Column('end_seconds', sa.Float(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Create a standard B-tree index on job_id
    op.create_index('ix_aligned_segments_job_id', 'aligned_segments', ['job_id'])

    # 4. Create the HNSW pgvector index using raw SQL
    # We must first ensure we only run this if it's not sqlite, but context says Postgres
    # Actually wait, test suite says "Use SQLite dialect guards for vector/GIN raw SQL executions"
    # So I need to add guards!
    
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        op.execute(
            "CREATE INDEX ix_aligned_segments_embedding_hnsw "
            "ON aligned_segments "
            "USING hnsw (embedding vector_cosine_ops)"
        )

        # 5. Create the GIN index for full-text search
        op.execute(
            "CREATE INDEX ix_aligned_segments_text_gin "
            "ON aligned_segments "
            "USING GIN (to_tsvector('english', text))"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        op.execute("DROP INDEX IF EXISTS ix_aligned_segments_text_gin")
        op.execute("DROP INDEX IF EXISTS ix_aligned_segments_embedding_hnsw")
    
    op.drop_index('ix_aligned_segments_job_id', table_name='aligned_segments')
    op.drop_table('aligned_segments')
    
    if bind.dialect.name != 'sqlite':
        op.execute("DROP EXTENSION IF EXISTS vector")
