"""add is_read field to emails table

Revision ID: 20251203_is_read
Revises: 20251202_maildigest_pro
Create Date: 2025-12-03

Adds is_read boolean field to track which emails have been read/handled by syndic.
This allows filtering the digest to show only unread emails.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251203_is_read'
down_revision = '20251202_maildigest_pro'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add is_read field to emails table"""
    op.add_column('emails', sa.Column('is_read', sa.Boolean(), nullable=True, server_default='false'))


def downgrade() -> None:
    """Remove is_read field"""
    op.drop_column('emails', 'is_read')
