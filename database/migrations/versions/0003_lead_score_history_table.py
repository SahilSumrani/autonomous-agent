"""lead_score_history_table

Revision ID: 0003_lead_score_history
Revises: 0002_browser_agent
Create Date: 2026-10-07 19:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003_lead_score_history'
down_revision: Union[str, None] = '0002_browser_agent'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lead_score_history',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('lead_id', sa.Uuid(as_uuid=True), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('previous_score', sa.Integer(), nullable=False),
        sa.Column('new_score', sa.Integer(), nullable=False),
        sa.Column('breakdown_json', sa.JSON(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_lead_score_history_lead_id', 'lead_score_history', ['lead_id'])
    op.create_index('ix_lead_score_history_created_at', 'lead_score_history', ['created_at'])


def downgrade() -> None:
    op.drop_table('lead_score_history')
