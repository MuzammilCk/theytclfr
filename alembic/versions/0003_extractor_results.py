"""Creates the extractor_results table.

Revision ID: 0003
Down revision: 0002
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'extractor_results',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('extractor_type', sa.String(length=16), nullable=False),
        sa.Column('segments_json', sa.JSON(), nullable=False),
        sa.Column('total_duration_seconds', sa.Float(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_extractor_results_job_extractor', 'extractor_results', ['job_id', 'extractor_type'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_extractor_results_job_extractor', table_name='extractor_results')
    op.drop_table('extractor_results')
