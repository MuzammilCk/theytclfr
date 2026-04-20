"""initial_schema

Revision ID: 0001
Revises: 
Create Date: 2026-04-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('youtube_url', sa.String(length=2048), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('video_title', sa.String(length=512), nullable=True),
    sa.Column('channel_name', sa.String(length=256), nullable=True),
    sa.Column('duration_seconds', sa.Float(), nullable=True),
    sa.Column('thumbnail_url', sa.String(length=2048), nullable=True),
    sa.Column('local_media_path', sa.String(length=2048), nullable=True),
    sa.Column('metadata_raw', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_jobs_status_created_at', 'jobs', ['status', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_jobs_status_created_at', table_name='jobs')
    op.drop_table('jobs')
