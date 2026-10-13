"""prospecting_job_end_reason

Revision ID: 0009_prospecting_job_end_reason
Revises: 0008_prospecting_agent_tables
Create Date: 2026-10-13 17:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009_prospecting_job_end_reason'
down_revision: Union[str, None] = '0008_prospecting_agent_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'prospecting_jobs',
        sa.Column('end_reason', sa.String(length=50), nullable=True)
    )
    op.create_index(
        'ix_prospecting_jobs_end_reason',
        'prospecting_jobs',
        ['end_reason'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_prospecting_jobs_end_reason', table_name='prospecting_jobs')
    op.drop_column('prospecting_jobs', 'end_reason')
