"""Add typed kural_no column and B-tree index."""

import sqlalchemy as sa
from alembic import op

revision = "c71a9d3e2f40"  # pragma: allowlist secret
down_revision = "5bf755981045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("kural_no", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        UPDATE documents
        SET kural_no = (metadata ->> 'kural_no')::integer
        WHERE metadata ? 'kural_no'
          AND metadata ->> 'kural_no' ~ '^[0-9]+$'
        """
    )

    op.create_index(
        "ix_documents_kural_no",
        "documents",
        ["kural_no"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_documents_kural_no",
        table_name="documents",
    )
    op.drop_column("documents", "kural_no")
