"""Let shared curriculum content exist alongside tenant-scoped content

Revision ID: 020_shared_curriculum_rls
Revises: 019_real_pgvector_embeddings
Create Date: 2026-08-10 00:00:00.000000

Multi-tenancy put row-level security on processed_content:

    USING (organization_id = current_setting('app.current_organization_id')::uuid)

Right for a school's own uploads. Wrong for NCERT textbooks, which belong to no
school and should be retrievable by every student in the product. Under that
policy alone a row with organization_id IS NULL compares NULL = NULL, which is
NULL, which is false — so shared content is not merely unowned, it is invisible
to everyone, forever. Ingesting the curriculum was impossible.

This adds a second policy so a NULL organization means "shared", readable by
all. Policies for the same command are OR'd, so tenant isolation is untouched:
a row owned by school A is still visible only to school A.

Writes are deliberately not opened up. The existing FOR ALL policy has no
WITH CHECK, so PostgreSQL applies its USING clause as the insert check, and a
non-owner still cannot create a NULL-organization row. Only the table owner —
which is what migrations and the ingestion job connect as — can publish shared
curriculum. A tenant cannot promote its own content to global.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '020_shared_curriculum_rls'
down_revision = '019_real_pgvector_embeddings'
branch_labels = None
depends_on = None

POLICY = "processed_content_shared_read_policy"


def upgrade():
    """Make organization-less content readable by everyone."""
    op.execute(f"DROP POLICY IF EXISTS {POLICY} ON processed_content")
    op.execute(
        f"""
        CREATE POLICY {POLICY} ON processed_content
        FOR SELECT
        USING (organization_id IS NULL)
        """
    )


def downgrade():
    """Return to tenant-only visibility, hiding shared curriculum again."""
    op.execute(f"DROP POLICY IF EXISTS {POLICY} ON processed_content")
