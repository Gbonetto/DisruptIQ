"""initial_schema_with_all_tables

Revision ID: 25fb31d17bc5
Revises: 
Create Date: 2025-11-05 23:52:07.562927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25fb31d17bc5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Create all database tables."""

    # NOTE: This is a placeholder migration for initial schema documentation
    # In production deployment with a live database, run:
    #   alembic revision --autogenerate -m "initial_schema"
    # to automatically generate the full table creation code

    # Tables that will be created on application startup via init_db():
    # - users: User authentication and management
    # - conversations: Chat conversation sessions
    # - messages: Individual chat messages with thoughts/sources
    # - coproprietes: Property/building management
    # - coproprietaires: Property owners/tenants
    # - professionnels (vendors): Service providers
    # - professionnels_coproprietes: Many-to-many junction table
    # - emails: Email management and digest
    # - documents: Document storage and RAG indexing

    print("✅ Alembic migrations initialized")
    print("   For production: Run with live database connection")
    print("   Tables are currently created by init_db() on startup")


def downgrade() -> None:
    """Downgrade schema."""
    # Placeholder - would drop all tables in reverse order
    pass
