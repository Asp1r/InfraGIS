"""add media360 schema

Revision ID: 002_media360
Revises: 001_initial
Create Date: 2026-04-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_media360"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

mediasource_enum = postgresql.ENUM("raw360", "exported", name="mediasourcetype", create_type=True)
mediaassetkind_enum = postgresql.ENUM(
    "master_equirect", "hls", "thumbnail", "preview", name="mediaassetkind", create_type=True
)
mediaassetstatus_enum = postgresql.ENUM("pending", "ready", "failed", name="mediaassetstatus", create_type=True)
processingjobstage_enum = postgresql.ENUM(
    "queued", "processing", "ready", "failed", name="processingjobstage", create_type=True
)


def upgrade() -> None:
    # Core entity: uploaded media file and its source metadata.
    op.create_table(
        "media_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("source_type", mediasource_enum, nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("resolution", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Media derivatives/stateful outputs (master/hls/preview/etc.).
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("kind", mediaassetkind_enum, nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("codec", sa.String(length=128), nullable=True),
        sa.Column("bitrate", sa.Integer(), nullable=True),
        sa.Column("status", mediaassetstatus_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["media_id"], ["media_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_media_assets_media_id"), "media_assets", ["media_id"], unique=False)
    # Geospatial bindings to render media anchors on GIS map.
    op.create_table(
        "media_geo_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("layer_id", sa.Integer(), nullable=True),
        sa.Column("feature_id", sa.String(length=255), nullable=True),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("heading", sa.Float(), nullable=True),
        sa.Column("pitch", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["layer_id"], ["layers.id"]),
        sa.ForeignKeyConstraint(["media_id"], ["media_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_media_geo_links_media_id"), "media_geo_links", ["media_id"], unique=False)
    # Async processing lifecycle for conversion/transcoding pipeline.
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("stage", processingjobstage_enum, nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["media_id"], ["media_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_processing_jobs_media_id"), "processing_jobs", ["media_id"], unique=False)


def downgrade() -> None:
    # Drop child tables first, then root table and enum types.
    op.drop_index(op.f("ix_processing_jobs_media_id"), table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index(op.f("ix_media_geo_links_media_id"), table_name="media_geo_links")
    op.drop_table("media_geo_links")
    op.drop_index(op.f("ix_media_assets_media_id"), table_name="media_assets")
    op.drop_table("media_assets")
    op.drop_table("media_records")
    processingjobstage_enum.drop(op.get_bind(), checkfirst=True)
    mediaassetstatus_enum.drop(op.get_bind(), checkfirst=True)
    mediaassetkind_enum.drop(op.get_bind(), checkfirst=True)
    mediasource_enum.drop(op.get_bind(), checkfirst=True)
