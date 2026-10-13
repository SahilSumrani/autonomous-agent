"""deduplication_constraints

Revision ID: 0007_deduplication_constraints
Revises: 0006_conversation_intelligence
Create Date: 2026-10-08 14:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0007_deduplication_constraints'
down_revision: Union[str, None] = '0006_conversation_intelligence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Deduplicate any existing duplicate leads before adding unique constraint
    op.execute("""
        DELETE FROM leads
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY organization_id, profile_url
                    ORDER BY created_at ASC
                ) as rnum
                FROM leads
                WHERE profile_url IS NOT NULL
            ) t
            WHERE t.rnum > 1
        );
    """)

    # 2. Unique constraint for companies (org_id, normalized_domain)
    op.create_unique_constraint('uq_companies_org_domain', 'companies', ['organization_id', 'normalized_domain'])

    # 3. Unique constraint for contacts (org_id, email)
    op.create_unique_constraint('uq_contacts_org_email', 'contacts', ['organization_id', 'email'])

    # 4. Unique constraint for leads (org_id, profile_url)
    op.create_unique_constraint('uq_leads_org_profile_url', 'leads', ['organization_id', 'profile_url'])


def downgrade() -> None:
    op.drop_constraint('uq_leads_org_profile_url', 'leads', type_='unique')
    op.drop_constraint('uq_contacts_org_email', 'contacts', type_='unique')
    op.drop_constraint('uq_companies_org_domain', 'companies', type_='unique')
