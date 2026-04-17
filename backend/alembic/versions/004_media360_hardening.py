"""media360 hardening constraints

Revision ID: 004_media360_hardening
Revises: 003_merge_heads
Create Date: 2026-04-17
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004_media360_hardening"
down_revision: Union[str, None] = "003_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Prevent duplicate assets with same kind for a single media record.
    op.create_unique_constraint(
        "uq_media_assets_media_id_kind",
        "media_assets",
        ["media_id", "kind"],
    )


def downgrade() -> None:
    # Rollback unique constraint if migration is reverted.
    op.drop_constraint("uq_media_assets_media_id_kind", "media_assets", type_="unique")
