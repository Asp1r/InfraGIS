"""media geolink axis chainage fields

Revision ID: 005_media_geolink_axis_chainage
Revises: 004_media360_hardening
Create Date: 2026-04-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_media_geolink_axis_chainage"
down_revision: Union[str, None] = "004_media360_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("media_geo_links", sa.Column("axis_layer_id", sa.Integer(), nullable=True))
    op.add_column("media_geo_links", sa.Column("axis_km", sa.Float(), nullable=True))
    op.create_index(op.f("ix_media_geo_links_axis_layer_id"), "media_geo_links", ["axis_layer_id"], unique=False)
    op.create_foreign_key(None, "media_geo_links", "layers", ["axis_layer_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("media_geo_links_axis_layer_id_fkey", "media_geo_links", type_="foreignkey")
    op.drop_index(op.f("ix_media_geo_links_axis_layer_id"), table_name="media_geo_links")
    op.drop_column("media_geo_links", "axis_km")
    op.drop_column("media_geo_links", "axis_layer_id")

