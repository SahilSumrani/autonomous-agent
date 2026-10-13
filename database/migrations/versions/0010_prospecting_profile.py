"""prospecting_profile

Revision ID: 0010_prospecting_profile
Revises: 0009_prospecting_job_end_reason
Create Date: 2026-10-13 17:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010_prospecting_profile'
down_revision: Union[str, None] = '0009_prospecting_job_end_reason'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'prospecting_profiles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('services_offered', sa.JSON(), nullable=False),
        sa.Column('ideal_customer_keywords', sa.JSON(), nullable=False),
        sa.Column('excluded_keywords', sa.JSON(), nullable=False),
        sa.Column('sources_enabled', sa.JSON(), nullable=False),
        sa.Column('daily_limits_json', sa.JSON(), nullable=False),
        sa.Column('geography', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', name='uq_prospecting_profiles_organization_id')
    )
    op.create_index(
        'ix_prospecting_profiles_organization_id',
        'prospecting_profiles',
        ['organization_id'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index('ix_prospecting_profiles_organization_id', table_name='prospecting_profiles')
    op.drop_table('prospecting_profiles')
