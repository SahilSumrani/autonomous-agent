"""website_research_tables

Revision ID: 0004_website_research
Revises: 0003_lead_score_history
Create Date: 2026-10-07 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004_website_research'
down_revision: Union[str, None] = '0003_lead_score_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'website_research',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.Uuid(as_uuid=True), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.Uuid(as_uuid=True), sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('website_url', sa.String(512), nullable=False),
        sa.Column('status', sa.String(64), nullable=False, server_default='PENDING'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pages_analyzed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pages_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('technology_stack', sa.JSON(), nullable=False),
        sa.Column('cms', sa.String(128), nullable=True),
        sa.Column('frontend_framework', sa.String(128), nullable=True),
        sa.Column('backend_technology', sa.String(128), nullable=True),
        sa.Column('analytics_tools', sa.JSON(), nullable=False),
        sa.Column('payment_provider', sa.String(128), nullable=True),
        sa.Column('hosting_provider', sa.String(128), nullable=True),
        sa.Column('cdn', sa.String(128), nullable=True),
        sa.Column('ecommerce_platform', sa.String(128), nullable=True),
        sa.Column('website_health_score', sa.Integer(), nullable=True),
        sa.Column('performance_score', sa.Integer(), nullable=True),
        sa.Column('mobile_score', sa.Integer(), nullable=True),
        sa.Column('ux_score', sa.Integer(), nullable=True),
        sa.Column('seo_score', sa.Integer(), nullable=True),
        sa.Column('conversion_score', sa.Integer(), nullable=True),
        sa.Column('accessibility_score', sa.Integer(), nullable=True),
        sa.Column('opportunity_score', sa.Integer(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('positive_findings', sa.JSON(), nullable=False),
        sa.Column('negative_findings', sa.JSON(), nullable=False),
        sa.Column('recommendations', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_website_research_org_id', 'website_research', ['organization_id'])
    op.create_index('ix_website_research_lead_id', 'website_research', ['lead_id'])
    op.create_index('ix_website_research_company_id', 'website_research', ['company_id'])
    op.create_index('ix_website_research_status', 'website_research', ['status'])
    op.create_index('ix_website_research_opp_score', 'website_research', ['opportunity_score'])

    op.create_table(
        'website_page_research',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('research_id', sa.Uuid(as_uuid=True), sa.ForeignKey('website_research.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(1024), nullable=False),
        sa.Column('page_type', sa.String(64), nullable=False, server_default='OTHER'),
        sa.Column('title', sa.String(512), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('content_summary', sa.Text(), nullable=True),
        sa.Column('visible_text', sa.Text(), nullable=True),
        sa.Column('links_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('has_cta', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_contact_form', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_phone', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_email', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_pricing', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_product_catalog', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_checkout', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_social_proof', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_testimonials', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_reviews', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('mobile_observations', sa.JSON(), nullable=False),
        sa.Column('ux_observations', sa.JSON(), nullable=False),
        sa.Column('seo_observations', sa.JSON(), nullable=False),
        sa.Column('performance_observations', sa.JSON(), nullable=False),
        sa.Column('conversion_observations', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_website_page_research_research_id', 'website_page_research', ['research_id'])
    op.create_index('ix_website_page_research_org_id', 'website_page_research', ['organization_id'])
    op.create_index('ix_website_page_research_page_type', 'website_page_research', ['page_type'])


def downgrade() -> None:
    op.drop_table('website_page_research')
    op.drop_table('website_research')
