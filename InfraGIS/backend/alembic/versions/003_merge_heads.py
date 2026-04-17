"""merge road and media heads

Revision ID: 003_merge_heads
Revises: 002_road_model, 002_media360
Create Date: 2026-04-17
"""

from typing import Sequence, Union

from alembic import op

revision: str = "003_merge_heads"
down_revision: Union[str, Sequence[str], None] = ("002_road_model", "002_media360")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge revision: schema changes are applied by parent branches.
    pass


def downgrade() -> None:
    # Merge revision: nothing to rollback directly.
    pass
