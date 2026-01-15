"""add knowledge entries

Revision ID: fb717c637cde
Revises: 14e14b69890a
Create Date: 2026-01-04 17:00:57.341104+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'fb717c637cde'
down_revision: Union[str, None] = '14e14b69890a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension is installed for VECTOR type
    # op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    op.create_table('knowledge_entries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('entry_type', sa.String(length=50), nullable=False),
        sa.Column('error_signature', sa.String(length=500), nullable=False),
        sa.Column('tech_stack', sa.String(length=100), nullable=True),
        # sa.Column('context_embedding', Vector(768), nullable=True),
        sa.Column('solution_pattern', sa.Text(), nullable=False),
        sa.Column('solution_description', sa.Text(), nullable=True),
        sa.Column('solution_compressed', sa.LargeBinary(), nullable=True),
        sa.Column('success_count', sa.Integer(), nullable=False),
        sa.Column('failure_count', sa.Integer(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('visibility', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_knowledge_entries_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_entries'))
    )
    op.create_index('idx_ke_confidence_desc', 'knowledge_entries', [sa.literal_column('confidence DESC')], unique=False)
    op.create_index('idx_ke_visibility', 'knowledge_entries', ['visibility'], unique=False)
    op.create_index(op.f('ix_knowledge_entries_entry_type'), 'knowledge_entries', ['entry_type'], unique=False)
    op.create_index(op.f('ix_knowledge_entries_error_signature'), 'knowledge_entries', ['error_signature'], unique=False)
    op.create_index(op.f('ix_knowledge_entries_tech_stack'), 'knowledge_entries', ['tech_stack'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_knowledge_entries_tech_stack'), table_name='knowledge_entries')
    op.drop_index(op.f('ix_knowledge_entries_error_signature'), table_name='knowledge_entries')
    op.drop_index(op.f('ix_knowledge_entries_entry_type'), table_name='knowledge_entries')
    op.drop_index('idx_ke_visibility', table_name='knowledge_entries')
    op.drop_index('idx_ke_confidence_desc', table_name='knowledge_entries')
    op.drop_table('knowledge_entries')
