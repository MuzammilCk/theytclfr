# ytclfr V2 — Stage A: Signal Census
"""add_signal_manifests

Revision ID: 6c08e88f31be
Revises: 0006
Create Date: 2026-05-23 15:23:14.018194

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c08e88f31be'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('signal_manifests',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('job_id', sa.UUID(), nullable=False),
    sa.Column('audio_type', sa.String(length=30), nullable=False),
    sa.Column('language', sa.String(length=10), nullable=True),
    sa.Column('has_speech', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('has_music', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('has_burned_in_text', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('has_subtitle_track', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('has_faces', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('motion_density', sa.Float(), server_default='0.0', nullable=False),
    sa.Column('motion_score', sa.Float(), server_default='0.0', nullable=False),
    sa.Column('aspect_ratio', sa.String(length=20), server_default=sa.text("'unknown'"), nullable=False),
    sa.Column('content_format', sa.String(length=30), server_default=sa.text("'unknown'"), nullable=False),
    sa.Column('scene_cut_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('duration_seconds', sa.Float(), server_default='0.0', nullable=False),
    sa.Column('probing_confidence', sa.Float(), server_default='0.0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_signal_manifests_job_id', 'signal_manifests', ['job_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_signal_manifests_job_id', table_name='signal_manifests')
    op.drop_table('signal_manifests')
