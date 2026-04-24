"""Add s3_video_uri column to jobs table.

Revision ID: 0004
Down revision: 0003

Phase 10: Distributed scaling — stores the S3 URI for videos
uploaded by the ingestion worker so extraction workers on
different nodes can download them.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("s3_video_uri", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "s3_video_uri")
