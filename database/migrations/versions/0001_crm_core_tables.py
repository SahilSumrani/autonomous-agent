"""crm_core_tables

Revision ID: 0001_crm_core
Revises: 
Create Date: 2026-10-07 18:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_crm_core'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    # 2. users
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='MEMBER'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('organization_id', 'email', name='uq_user_org_email')
    )
    op.create_index('ix_users_organization_id', 'users', ['organization_id'])
    op.create_index('ix_users_email', 'users', ['email'])

    # 3. companies
    op.create_table(
        'companies',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('normalized_name', sa.String(length=255), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('normalized_domain', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('website_url', sa.String(length=1024), nullable=True),
        sa.Column('linkedin_url', sa.String(length=1024), nullable=True),
        sa.Column('instagram_url', sa.String(length=1024), nullable=True),
        sa.Column('reddit_url', sa.String(length=1024), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='UNKNOWN'),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_companies_organization_id', 'companies', ['organization_id'])
    op.create_index('ix_companies_normalized_name', 'companies', ['normalized_name'])
    op.create_index('ix_companies_normalized_domain', 'companies', ['normalized_domain'])
    op.create_index('ix_companies_industry', 'companies', ['industry'])
    op.create_index('ix_companies_org_domain', 'companies', ['organization_id', 'normalized_domain'])
    op.create_index('ix_companies_org_name', 'companies', ['organization_id', 'normalized_name'])

    # 4. contacts
    op.create_table(
        'contacts',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.Uuid(as_uuid=True), sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('job_title', sa.String(length=150), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('instagram_username', sa.String(length=100), nullable=True),
        sa.Column('instagram_url', sa.String(length=1024), nullable=True),
        sa.Column('reddit_username', sa.String(length=100), nullable=True),
        sa.Column('reddit_url', sa.String(length=1024), nullable=True),
        sa.Column('linkedin_url', sa.String(length=1024), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_contacts_organization_id', 'contacts', ['organization_id'])
    op.create_index('ix_contacts_company_id', 'contacts', ['company_id'])
    op.create_index('ix_contacts_email', 'contacts', ['email'])
    op.create_index('ix_contacts_instagram_username', 'contacts', ['instagram_username'])
    op.create_index('ix_contacts_reddit_username', 'contacts', ['reddit_username'])
    op.create_index('ix_contacts_linkedin_url', 'contacts', ['linkedin_url'])
    op.create_index('ix_contacts_org_email', 'contacts', ['organization_id', 'email'])

    # 5. lead_sources
    op.create_table(
        'lead_sources',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=False),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_lead_sources_organization_id', 'lead_sources', ['organization_id'])
    op.create_index('ix_lead_sources_source_type', 'lead_sources', ['source_type'])
    op.create_index('ix_lead_sources_external_id', 'lead_sources', ['external_id'])

    # 6. leads
    op.create_table(
        'leads',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.Uuid(as_uuid=True), sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('contact_id', sa.Uuid(as_uuid=True), sa.ForeignKey('contacts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_id', sa.Uuid(as_uuid=True), sa.ForeignKey('lead_sources.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='NEW'),
        sa.Column('lead_type', sa.String(length=50), nullable=False, server_default='COMPANY'),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('profile_url', sa.String(length=1024), nullable=True),
        sa.Column('content_url', sa.String(length=1024), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('intent_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('qualification_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('overall_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recommended_service', sa.String(length=150), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('intent_score >= 0 AND intent_score <= 100', name='chk_lead_intent_score'),
        sa.CheckConstraint('qualification_score >= 0 AND qualification_score <= 100', name='chk_lead_qualification_score'),
        sa.CheckConstraint('overall_score >= 0 AND overall_score <= 100', name='chk_lead_overall_score'),
    )
    op.create_index('ix_leads_organization_id', 'leads', ['organization_id'])
    op.create_index('ix_leads_company_id', 'leads', ['company_id'])
    op.create_index('ix_leads_contact_id', 'leads', ['contact_id'])
    op.create_index('ix_leads_source_id', 'leads', ['source_id'])
    op.create_index('ix_leads_status', 'leads', ['status'])
    op.create_index('ix_leads_lead_type', 'leads', ['lead_type'])
    op.create_index('ix_leads_profile_url', 'leads', ['profile_url'])
    op.create_index('ix_leads_overall_score', 'leads', ['overall_score'])
    op.create_index('ix_leads_last_seen_at', 'leads', ['last_seen_at'])
    op.create_index('ix_leads_org_status', 'leads', ['organization_id', 'status'])
    op.create_index('ix_leads_org_score', 'leads', ['organization_id', 'overall_score'])
    op.create_index('ix_leads_org_profile', 'leads', ['organization_id', 'profile_url'])

    # 7. lead_signals
    op.create_table(
        'lead_signals',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('lead_id', sa.Uuid(as_uuid=True), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('signal_type', sa.String(length=100), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='chk_signal_confidence'),
    )
    op.create_index('ix_lead_signals_lead_id', 'lead_signals', ['lead_id'])
    op.create_index('ix_lead_signals_signal_type', 'lead_signals', ['signal_type'])

    # 8. pipeline_events
    op.create_table(
        'pipeline_events',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('lead_id', sa.Uuid(as_uuid=True), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('old_status', sa.String(length=50), nullable=True),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('actor_type', sa.String(length=50), nullable=False, server_default='SYSTEM'),
        sa.Column('actor_id', sa.String(length=255), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_pipeline_events_lead_id', 'pipeline_events', ['lead_id'])
    op.create_index('ix_pipeline_events_new_status', 'pipeline_events', ['new_status'])
    op.create_index('ix_pipeline_events_created_at', 'pipeline_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('pipeline_events')
    op.drop_table('lead_signals')
    op.drop_table('leads')
    op.drop_table('lead_sources')
    op.drop_table('contacts')
    op.drop_table('companies')
    op.drop_table('users')
    op.drop_table('organizations')
