"""conversation_intelligence_tables

Revision ID: 0006_conversation_intelligence
Revises: 0005_outreach_intelligence
Create Date: 2026-10-07 22:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0006_conversation_intelligence'
down_revision: Union[str, None] = '0005_outreach_intelligence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. conversation_threads
    op.create_table(
        'conversation_threads',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.Uuid(as_uuid=True), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(50), nullable=False, server_default='INSTAGRAM_DM'),
        sa.Column('external_thread_ref', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='ACTIVE'),
        sa.Column('current_intent', sa.String(50), nullable=True),
        sa.Column('sentiment', sa.String(50), nullable=True),
        sa.Column('sales_stage', sa.String(50), nullable=False, server_default='CONTACTED'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_conversation_threads_org_id', 'conversation_threads', ['organization_id'])
    op.create_index('ix_conversation_threads_lead_id', 'conversation_threads', ['lead_id'])
    op.create_index('ix_conversation_threads_status', 'conversation_threads', ['status'])
    op.create_index('ix_conversation_threads_sales_stage', 'conversation_threads', ['sales_stage'])
    op.create_index('ix_conversation_threads_ext_ref', 'conversation_threads', ['external_thread_ref'])
    op.create_index('ix_conversation_threads_org_lead', 'conversation_threads', ['organization_id', 'lead_id'])
    op.create_index('ix_conversation_threads_org_status', 'conversation_threads', ['organization_id', 'status'])

    # 2. conversation_messages
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('thread_id', sa.Uuid(as_uuid=True), sa.ForeignKey('conversation_threads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('direction', sa.String(20), nullable=False, server_default='INBOUND'),
        sa.Column('author_type', sa.String(20), nullable=False, server_default='PROSPECT'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sanitized_content', sa.Text(), nullable=False),
        sa.Column('source_url', sa.String(2048), nullable=True),
        sa.Column('external_message_ref', sa.String(255), nullable=True),
        sa.Column('delivery_status', sa.String(50), nullable=False, server_default='RECEIVED'),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_conversation_messages_org_id', 'conversation_messages', ['organization_id'])
    op.create_index('ix_conversation_messages_thread_id', 'conversation_messages', ['thread_id'])
    op.create_index('ix_conversation_messages_org_thread', 'conversation_messages', ['organization_id', 'thread_id'])
    op.create_index('ix_conversation_messages_ext_ref', 'conversation_messages', ['external_message_ref'])

    # 3. conversation_reply_drafts
    op.create_table(
        'conversation_reply_drafts',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('thread_id', sa.Uuid(as_uuid=True), sa.ForeignKey('conversation_threads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('in_reply_to_message_id', sa.Uuid(as_uuid=True), sa.ForeignKey('conversation_messages.id', ondelete='SET NULL'), nullable=True),
        sa.Column('variant', sa.String(20), nullable=False, server_default='DIRECT'),
        sa.Column('objective', sa.String(50), nullable=False, server_default='ANSWER'),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('quality_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='DRAFT'),
        sa.Column('evidence_text', sa.Text(), nullable=True),
        sa.Column('risk_flags', sa.JSON(), nullable=True),
        sa.Column('requires_human_approval', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_conversation_reply_drafts_org_id', 'conversation_reply_drafts', ['organization_id'])
    op.create_index('ix_conversation_reply_drafts_thread_id', 'conversation_reply_drafts', ['thread_id'])
    op.create_index('ix_conversation_reply_drafts_org_thread', 'conversation_reply_drafts', ['organization_id', 'thread_id'])
    op.create_index('ix_conversation_reply_drafts_status', 'conversation_reply_drafts', ['status'])

    # 4. conversation_approvals
    op.create_table(
        'conversation_approvals',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('thread_id', sa.Uuid(as_uuid=True), sa.ForeignKey('conversation_threads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reply_id', sa.Uuid(as_uuid=True), sa.ForeignKey('conversation_reply_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('reviewer_id', sa.String(255), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_conversation_approvals_org_id', 'conversation_approvals', ['organization_id'])
    op.create_index('ix_conversation_approvals_thread_id', 'conversation_approvals', ['thread_id'])
    op.create_index('ix_conversation_approvals_reply_id', 'conversation_approvals', ['reply_id'])
    op.create_index('ix_conversation_approvals_status', 'conversation_approvals', ['status'])
    op.create_index('ix_conversation_approvals_org_thread', 'conversation_approvals', ['organization_id', 'thread_id'])


def downgrade() -> None:
    op.drop_table('conversation_approvals')
    op.drop_table('conversation_reply_drafts')
    op.drop_table('conversation_messages')
    op.drop_table('conversation_threads')
