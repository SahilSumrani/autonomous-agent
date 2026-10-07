"""browser_agent_tables

Revision ID: 0002_browser_agent
Revises: 0001_crm_core
Create Date: 2026-10-07 19:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_browser_agent'
down_revision: Union[str, None] = '0001_crm_core'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. agent_sessions
    op.create_table(
        'agent_sessions',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('browser_id', sa.String(length=255), nullable=False),
        sa.Column('current_url', sa.String(length=2048), nullable=True),
        sa.Column('current_domain', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='IDLE'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_agent_sessions_organization_id', 'agent_sessions', ['organization_id'])
    op.create_index('ix_agent_sessions_user_id', 'agent_sessions', ['user_id'])
    op.create_index('ix_agent_sessions_browser_id', 'agent_sessions', ['browser_id'])
    op.create_index('ix_agent_sessions_current_domain', 'agent_sessions', ['current_domain'])
    op.create_index('ix_agent_sessions_status', 'agent_sessions', ['status'])
    op.create_index('ix_agent_sessions_org_status', 'agent_sessions', ['organization_id', 'status'])

    # 2. agent_events
    op.create_table(
        'agent_events',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('session_id', sa.Uuid(as_uuid=True), sa.ForeignKey('agent_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=True),
        sa.Column('tool', sa.String(length=100), nullable=True),
        sa.Column('input_summary', sa.Text(), nullable=True),
        sa.Column('output_summary', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='SUCCESS'),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_agent_events_session_id', 'agent_events', ['session_id'])
    op.create_index('ix_agent_events_event_type', 'agent_events', ['event_type'])
    op.create_index('ix_agent_events_tool', 'agent_events', ['tool'])
    op.create_index('ix_agent_events_created_at', 'agent_events', ['created_at'])

    # 3. action_approvals
    op.create_table(
        'action_approvals',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('session_id', sa.Uuid(as_uuid=True), sa.ForeignKey('agent_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.Uuid(as_uuid=True), sa.ForeignKey('leads.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False, server_default='DM'),
        sa.Column('target_url', sa.String(length=2048), nullable=True),
        sa.Column('recipient', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', sa.String(length=255), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
    )
    op.create_index('ix_action_approvals_session_id', 'action_approvals', ['session_id'])
    op.create_index('ix_action_approvals_lead_id', 'action_approvals', ['lead_id'])
    op.create_index('ix_action_approvals_status', 'action_approvals', ['status'])
    op.create_index('ix_action_approvals_recipient', 'action_approvals', ['recipient'])
    op.create_index('ix_action_approvals_requested_at', 'action_approvals', ['requested_at'])


def downgrade() -> None:
    op.drop_table('action_approvals')
    op.drop_table('agent_events')
    op.drop_table('agent_sessions')
