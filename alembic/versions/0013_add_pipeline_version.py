"""add pipeline version

Revision ID: 0013
Revises: e330ec026969
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0013'
down_revision: Union[str, None] = '3019f6d173fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add pipeline_version and schema_version
    op.add_column('final_outputs', sa.Column('pipeline_version', sa.String(length=10), server_default='v2', nullable=False))
    op.add_column('final_outputs', sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False))
    
    # Backfill script
    op.execute("""
        UPDATE final_outputs 
        SET pipeline_version = CASE 
            WHEN content_type LIKE 'v3_%' THEN 'v3'
            ELSE 'v2'
        END,
        content_type = REPLACE(REPLACE(content_type, 'v3_', ''), 'v2_', '')
    """)

def downgrade() -> None:
    op.drop_column('final_outputs', 'schema_version')
    op.drop_column('final_outputs', 'pipeline_version')
