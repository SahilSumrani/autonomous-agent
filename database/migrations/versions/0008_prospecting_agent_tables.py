"""prospecting_agent_tables

Revision ID: 0008_prospecting_agent_tables
Revises: 0007_deduplication_constraints
Create Date: 2026-10-08 16:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0008_prospecting_agent_tables'
down_revision: Union[str, None] = '0007_deduplication_constraints'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. prospecting_jobs table
    op.create_table(
        'prospecting_jobs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='CREATED'),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='WEBSITE'),
        sa.Column('query', sa.String(length=1000), nullable=True),
        sa.Column('target_service', sa.String(length=255), nullable=True),
        sa.Column('target_industries', sa.JSON(), nullable=True),
        sa.Column('target_geography', sa.String(length=255), nullable=True),
        sa.Column('max_candidates', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_pages', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('max_scrolls', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('max_time_seconds', sa.Integer(), nullable=False, server_default='1800'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('statistics', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_prospecting_jobs_organization_id', 'prospecting_jobs', ['organization_id'])
    op.create_index('ix_prospecting_jobs_session_id', 'prospecting_jobs', ['session_id'])
    op.create_index('ix_prospecting_jobs_status', 'prospecting_jobs', ['status'])
    op.create_index('ix_prospecting_jobs_source', 'prospecting_jobs', ['source'])
    op.create_index('ix_prospecting_jobs_org_status', 'prospecting_jobs', ['organization_id', 'status'])

    # 2. prospect_candidates table
    op.create_table(
        'prospect_candidates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=True),
        sa.Column('canonical_url', sa.String(length=2048), nullable=True),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('username_or_handle', sa.String(length=255), nullable=True),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('business_category', sa.String(length=100), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('discovery_evidence', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DISCOVERED'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('dedup_key', sa.String(length=512), nullable=False),
        sa.Column('linked_lead_id', sa.Uuid(), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['prospecting_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linked_lead_id'], ['leads.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'dedup_key', name='uq_prospect_candidates_job_dedup'),
    )
    op.create_index('ix_prospect_candidates_job_id', 'prospect_candidates', ['job_id'])
    op.create_index('ix_prospect_candidates_organization_id', 'prospect_candidates', ['organization_id'])
    op.create_index('ix_prospect_candidates_platform', 'prospect_candidates', ['platform'])
    op.create_index('ix_prospect_candidates_username_or_handle', 'prospect_candidates', ['username_or_handle'])
    op.create_index('ix_prospect_candidates_domain', 'prospect_candidates', ['domain'])
    op.create_index('ix_prospect_candidates_status', 'prospect_candidates', ['status'])
    op.create_index('ix_prospect_candidates_dedup_key', 'prospect_candidates', ['dedup_key'])
    op.create_index('ix_prospect_candidates_linked_lead_id', 'prospect_candidates', ['linked_lead_id'])
    op.create_index('ix_prospect_candidates_job_status', 'prospect_candidates', ['job_id', 'status'])

    # 3. prospect_observations table
    op.create_table(
        'prospect_observations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=True),
        sa.Column('candidate_id', sa.Uuid(), nullable=True),
        sa.Column('session_id', sa.Uuid(), nullable=True),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('page_title', sa.String(length=512), nullable=True),
        sa.Column('visible_text', sa.Text(), nullable=True),
        sa.Column('headings', sa.JSON(), nullable=True),
        sa.Column('links', sa.JSON(), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['prospecting_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['candidate_id'], ['prospect_candidates.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['agent_sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_prospect_observations_job_id', 'prospect_observations', ['job_id'])
    op.create_index('ix_prospect_observations_candidate_id', 'prospect_observations', ['candidate_id'])
    op.create_index('ix_prospect_observations_session_id', 'prospect_observations', ['session_id'])
    op.create_index('ix_prospect_observations_organization_id', 'prospect_observations', ['organization_id'])
    op.create_index('ix_prospect_observations_content_hash', 'prospect_observations', ['content_hash'])
    op.create_index('ix_prospect_observations_created_at', 'prospect_observations', ['created_at'])


def downgrade() -> None:
    op.drop_table('prospect_observations')
    op.drop_table('prospect_candidates')
    op.drop_table('prospecting_jobs')
