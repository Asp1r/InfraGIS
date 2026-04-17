"""road model hierarchy and diagnostics tables

Revision ID: 002_road_model
Revises: 001_initial
Create Date: 2026-04-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_road_model"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

layerkind_enum = postgresql.ENUM("road", "road_axis", "iri", "defects", name="layerkind", create_type=True)


def upgrade() -> None:
    bind = op.get_bind()
    layerkind_enum.create(bind, checkfirst=True)
    op.add_column("layers", sa.Column("kind", layerkind_enum, nullable=True))
    op.add_column("layers", sa.Column("parent_id", sa.Integer(), nullable=True))
    op.add_column("layers", sa.Column("axis_layer_id", sa.Integer(), nullable=True))
    op.execute("UPDATE layers SET kind='road' WHERE kind IS NULL")
    op.alter_column("layers", "kind", nullable=False)
    op.create_index(op.f("ix_layers_parent_id"), "layers", ["parent_id"], unique=False)
    op.create_index(op.f("ix_layers_axis_layer_id"), "layers", ["axis_layer_id"], unique=False)
    op.create_foreign_key(None, "layers", "layers", ["parent_id"], ["id"])
    op.create_foreign_key(None, "layers", "layers", ["axis_layer_id"], ["id"])

    op.create_table(
        "iri_measurements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("layer_id", sa.Integer(), nullable=False),
        sa.Column("axis_layer_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=True),
        sa.Column("lane", sa.String(length=32), nullable=True),
        sa.Column("km_start", sa.Float(), nullable=False),
        sa.Column("km_end", sa.Float(), nullable=False),
        sa.Column("iri_value", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["axis_layer_id"], ["layers.id"]),
        sa.ForeignKeyConstraint(["layer_id"], ["layers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_iri_measurements_layer_id"), "iri_measurements", ["layer_id"], unique=False)
    op.create_index(
        op.f("ix_iri_measurements_axis_layer_id"),
        "iri_measurements",
        ["axis_layer_id"],
        unique=False,
    )

    op.create_table(
        "defect_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("layer_id", sa.Integer(), nullable=False),
        sa.Column("axis_layer_id", sa.Integer(), nullable=False),
        sa.Column("defect_code", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("norm_ref", sa.String(length=255), nullable=True),
        sa.Column("km_start", sa.Float(), nullable=False),
        sa.Column("km_end", sa.Float(), nullable=False),
        sa.Column("extent_m", sa.Float(), nullable=True),
        sa.Column("area_m2", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["axis_layer_id"], ["layers.id"]),
        sa.ForeignKeyConstraint(["layer_id"], ["layers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_defect_records_layer_id"), "defect_records", ["layer_id"], unique=False)
    op.create_index(op.f("ix_defect_records_axis_layer_id"), "defect_records", ["axis_layer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_defect_records_axis_layer_id"), table_name="defect_records")
    op.drop_index(op.f("ix_defect_records_layer_id"), table_name="defect_records")
    op.drop_table("defect_records")
    op.drop_index(op.f("ix_iri_measurements_axis_layer_id"), table_name="iri_measurements")
    op.drop_index(op.f("ix_iri_measurements_layer_id"), table_name="iri_measurements")
    op.drop_table("iri_measurements")
    op.drop_constraint("layers_axis_layer_id_fkey", "layers", type_="foreignkey")
    op.drop_constraint("layers_parent_id_fkey", "layers", type_="foreignkey")
    op.drop_index(op.f("ix_layers_axis_layer_id"), table_name="layers")
    op.drop_index(op.f("ix_layers_parent_id"), table_name="layers")
    op.drop_column("layers", "axis_layer_id")
    op.drop_column("layers", "parent_id")
    op.drop_column("layers", "kind")
    layerkind_enum.drop(op.get_bind(), checkfirst=True)
