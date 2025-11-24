"""add emergency workflows table

Revision ID: 20251123_emergency_wf
Revises: 20251105_2352_25fb31d17bc5
Create Date: 2025-11-23

V1: Emergency workflow management for water leak incidents
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251123_emergency_wf'
down_revision = '25fb31d17bc5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create emergency_workflows table"""
    op.create_table(
        'emergency_workflows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('workflow_type', sa.String(length=100), nullable=False),
        sa.Column('workflow_name', sa.String(length=255), nullable=False),
        sa.Column('checklist', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_emergency_workflows_id'), 'emergency_workflows', ['id'], unique=False)
    op.create_index(op.f('ix_emergency_workflows_tenant_id'), 'emergency_workflows', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_emergency_workflows_workflow_type'), 'emergency_workflows', ['workflow_type'], unique=False)
    op.create_index(op.f('ix_emergency_workflows_is_active'), 'emergency_workflows', ['is_active'], unique=False)


def downgrade() -> None:
    """Drop emergency_workflows table"""
    op.drop_index(op.f('ix_emergency_workflows_is_active'), table_name='emergency_workflows')
    op.drop_index(op.f('ix_emergency_workflows_workflow_type'), table_name='emergency_workflows')
    op.drop_index(op.f('ix_emergency_workflows_tenant_id'), table_name='emergency_workflows')
    op.drop_index(op.f('ix_emergency_workflows_id'), table_name='emergency_workflows')
    op.drop_table('emergency_workflows')
