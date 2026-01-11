"""Add agent_runs and agent_steps tables

Revision ID: 20260111_1310_add_agent_runs
Revises: 20260104_1700_add_knowledge_entries
Create Date: 2026-01-11 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = '20260111_1310_add_agent_runs'
down_revision: Union[str, None] = 'fb717c637cde'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create agent_runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_path', sa.String(1024), nullable=False),
        sa.Column('branch_name', sa.String(255)),
        sa.Column('parent_run_id', UUID(as_uuid=True), sa.ForeignKey('agent_runs.id', ondelete='SET NULL')),
        sa.Column('parent_step', sa.Integer),
        sa.Column('user_request', sa.Text),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('current_step', sa.Integer, nullable=False, default=0),
        sa.Column('error_message', sa.Text),
        sa.Column('run_metadata', JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
    )
    
    # Create indexes for agent_runs
    op.create_index('ix_agent_runs_user_id', 'agent_runs', ['user_id'])
    op.create_index('ix_agent_runs_parent_run_id', 'agent_runs', ['parent_run_id'])
    op.create_index('ix_agent_runs_user_status', 'agent_runs', ['user_id', 'status'])
    op.create_index('ix_agent_runs_user_created', 'agent_runs', ['user_id', 'created_at'])
    
    # Create agent_steps table
    op.create_table(
        'agent_steps',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', UUID(as_uuid=True), sa.ForeignKey('agent_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_number', sa.Integer, nullable=False),
        sa.Column('agent', sa.String(50), nullable=False),
        sa.Column('phase', sa.String(50)),
        sa.Column('action', sa.String(100)),
        sa.Column('content', JSONB),
        sa.Column('tokens_used', sa.Integer, nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Create indexes for agent_steps
    op.create_index('ix_agent_steps_run_id', 'agent_steps', ['run_id'])
    op.create_index('ix_agent_steps_run_number', 'agent_steps', ['run_id', 'step_number'])


def downgrade() -> None:
    # Drop agent_steps first (foreign key dependency)
    op.drop_index('ix_agent_steps_run_number', 'agent_steps')
    op.drop_index('ix_agent_steps_run_id', 'agent_steps')
    op.drop_table('agent_steps')
    
    # Drop agent_runs
    op.drop_index('ix_agent_runs_user_created', 'agent_runs')
    op.drop_index('ix_agent_runs_user_status', 'agent_runs')
    op.drop_index('ix_agent_runs_parent_run_id', 'agent_runs')
    op.drop_index('ix_agent_runs_user_id', 'agent_runs')
    op.drop_table('agent_runs')
