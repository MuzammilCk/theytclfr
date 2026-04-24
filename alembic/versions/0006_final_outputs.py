"""final outputs

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-24 10:36:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'final_outputs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('content_type', sa.String(length=64), nullable=False),
        sa.Column('overall_confidence', sa.Float(), nullable=False),
        sa.Column('output_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_final_outputs_job_id', 'final_outputs', ['job_id'], unique=True)
    op.create_index('ix_final_outputs_content_type', 'final_outputs', ['content_type'])


def downgrade() -> None:
    op.drop_index('ix_final_outputs_content_type', table_name='final_outputs')
    op.drop_index('ix_final_outputs_job_id', table_name='final_outputs')
    op.drop_table('final_outputs')
