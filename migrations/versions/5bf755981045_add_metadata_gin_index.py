"""Add GIN index for document metadata."""

from alembic import op

revision = "5bf755981045"
down_revision = "d03_integer_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_metadata_gin",
        "documents",
        ["metadata"],
        postgresql_using="gin",
        postgresql_ops={"metadata": "jsonb_path_ops"},
    )


def downgrade() -> None:
    op.drop_index(
        "ix_documents_metadata_gin",
        table_name="documents",
    )
