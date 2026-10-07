"""outreach_intelligence_tables

Revision ID: 0005_outreach_intelligence
Revises: 0004_website_research
Create Date: 2026-10-07 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005_outreach_intelligence'
down_revision: Union[str, None] = '0004_website_research'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. outreach_campaigns
    op.create_table(
        'outreach_campaigns',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('channel', sa.String(50), nullable=False, server_default='INSTAGRAM_DM'),
        sa.Column('status', sa.String(50), nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_outreach_campaigns_org_id', 'outreach_campaigns', ['organization_id'])
    op.create_index('ix_outreach_campaigns_status', 'outreach_campaigns', ['status'])

    # 2. outreach_drafts
    op.create_table(
        'outreach_drafts',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.Uuid(as_uuid=True), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('campaign_id', sa.Uuid(as_uuid=True), sa.ForeignKey('outreach_campaigns.id', ondelete='SET NULL'), nullable=True),
        sa.Column('channel', sa.String(50), nullable=False, server_default='INSTAGRAM_DM'),
        sa.Column('variant', sa.String(10), nullable=False, server_default='A'),
        sa.Column('subject', sa.String(512), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('personalization_level', sa.String(50), nullable=False, server_default='DEEP'),
        sa.Column('angle', sa.String(100), nullable=False),
        sa.Column('recommended_service', sa.String(100), nullable=False),
        sa.Column('quality_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='DRAFT'),
        sa.Column('cta_text', sa.String(512), nullable=True),
        sa.Column('cta_category', sa.String(50), nullable=True),
        sa.Column('suggested_follow_up_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('follow_up_reason', sa.String(512), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_outreach_drafts_org_id', 'outreach_drafts', ['organization_id'])
    op.create_index('ix_outreach_drafts_lead_id', 'outreach_drafts', ['lead_id'])
    op.create_index('ix_outreach_drafts_campaign_id', 'outreach_drafts', ['campaign_id'])
    op.create_index('ix_outreach_drafts_channel', 'outreach_drafts', ['channel'])
    op.create_index('ix_outreach_drafts_quality_score', 'outreach_drafts', ['quality_score'])
    op.create_index('ix_outreach_drafts_status', 'outreach_drafts', ['status'])
    op.create_index('ix_outreach_drafts_org_lead', 'outreach_drafts', ['organization_id', 'lead_id'])
    op.create_index('ix_outreach_drafts_org_status', 'outreach_drafts', ['organization_id', 'status'])

    # 3. outreach_evidences
    op.create_table(
        'outreach_evidences',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('draft_id', sa.Uuid(as_uuid=True), sa.ForeignKey('outreach_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('claim', sa.String(512), nullable=False),
        sa.Column('source_url', sa.String(2048), nullable=True),
        sa.Column('evidence_text', sa.Text(), nullable=False),
        sa.Column('evidence_type', sa.String(100), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.9'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_outreach_evidences_draft_id', 'outreach_evidences', ['draft_id'])
    op.create_index('ix_outreach_evidences_org_id', 'outreach_evidences', ['organization_id'])

    # 4. outreach_approvals
    op.create_table(
        'outreach_approvals',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.Uuid(as_uuid=True), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('draft_id', sa.Uuid(as_uuid=True), sa.ForeignKey('outreach_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('requested_by', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('reviewed_by', sa.String(255), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_outreach_approvals_org_id', 'outreach_approvals', ['organization_id'])
    op.create_index('ix_outreach_approvals_lead_id', 'outreach_approvals', ['lead_id'])
    op.create_index('ix_outreach_approvals_draft_id', 'outreach_approvals', ['draft_id'])
    op.create_index('ix_outreach_approvals_status', 'outreach_approvals', ['status'])

    # 5. outreach_attempts
    op.create_table(
        'outreach_attempts',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.Uuid(as_uuid=True), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('draft_id', sa.Uuid(as_uuid=True), sa.ForeignKey('outreach_drafts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('recipient', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='RECORDED'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_outreach_attempts_org_id', 'outreach_attempts', ['organization_id'])
    op.create_index('ix_outreach_attempts_lead_id', 'outreach_attempts', ['lead_id'])
    op.create_index('ix_outreach_attempts_draft_id', 'outreach_attempts', ['draft_id'])
    op.create_index('ix_outreach_attempts_channel', 'outreach_attempts', ['channel'])
    op.create_index('ix_outreach_attempts_recipient', 'outreach_attempts', ['recipient'])
    op.create_index('ix_outreach_attempts_status', 'outreach_attempts', ['status'])


def downgrade() -> None:
    op.drop_table('outreach_attempts')
    op.drop_table('outreach_approvals')
    op.drop_table('outreach_evidences')
    op.drop_table('outreach_drafts')
    op.drop_table('outreach_campaigns')
