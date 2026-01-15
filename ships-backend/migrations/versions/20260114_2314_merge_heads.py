"""merge_heads

Revision ID: 69153e2bd29c
Revises: fb717c637cde, 52b309dd2ad8
Create Date: 2026-01-14 23:14:25.227120+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69153e2bd29c'
down_revision: Union[str, None] = ('fb717c637cde', '52b309dd2ad8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
