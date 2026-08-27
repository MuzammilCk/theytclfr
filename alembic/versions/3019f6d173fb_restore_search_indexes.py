"""restore search indexes

Revision ID: 3019f6d173fb
Revises: ddb75e991d39
Create Date: 2026-05-28 16:02:13.373685

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3019f6d173fb'
down_revision: Union[str, None] = 'ddb75e991d39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_aligned_segments_embedding_hnsw
        ON aligned_segments USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_aligned_segments_text_gin
        ON aligned_segments USING gin (to_tsvector('english', text))
    """)


def downgrade() -> None:
    op.drop_index('ix_aligned_segments_embedding_hnsw', table_name='aligned_segments')
    op.drop_index('ix_aligned_segments_text_gin', table_name='aligned_segments')
