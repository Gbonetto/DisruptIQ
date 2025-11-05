"""Add server_default to is_indexed columns

Revision ID: 20251105_add_is_indexed_default
Revises:
Create Date: 2025-11-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251105_add_is_indexed_default'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    Add server_default='false' to is_indexed columns in coproprietaires and coproprietes tables
    This fixes import errors where is_indexed NULL values caused IntegrityError
    """
    # Add server default for coproprietaires.is_indexed
    op.alter_column(
        'coproprietaires',
        'is_indexed',
        server_default=sa.text('false'),
        existing_type=sa.Boolean(),
        existing_nullable=False
    )

    # Add server default for coproprietes.is_indexed
    op.alter_column(
        'coproprietes',
        'is_indexed',
        server_default=sa.text('false'),
        existing_type=sa.Boolean(),
        existing_nullable=False
    )

    # Update any existing NULL values to false (safety measure)
    op.execute("UPDATE coproprietaires SET is_indexed = false WHERE is_indexed IS NULL")
    op.execute("UPDATE coproprietes SET is_indexed = false WHERE is_indexed IS NULL")


def downgrade():
    """
    Remove server_default from is_indexed columns
    """
    # Remove server default for coproprietaires.is_indexed
    op.alter_column(
        'coproprietaires',
        'is_indexed',
        server_default=None,
        existing_type=sa.Boolean(),
        existing_nullable=False
    )

    # Remove server default for coproprietes.is_indexed
    op.alter_column(
        'coproprietes',
        'is_indexed',
        server_default=None,
        existing_type=sa.Boolean(),
        existing_nullable=False
    )
