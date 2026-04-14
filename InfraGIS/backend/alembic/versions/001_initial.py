"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

userrole_enum = postgresql.ENUM("admin", "viewer", name="userrole", create_type=True)
layersource_enum = postgresql.ENUM(
    "uploaded_geojson", "url_geojson", name="layersourcetype", create_type=True
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    userrole_enum.create(op.get_bind(), checkfirst=True)
    layersource_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("login", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", userrole_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_login"), "users", ["login"], unique=True)
    op.create_table(
        "layers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", layersource_enum, nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("layers")
    op.drop_index(op.f("ix_users_login"), table_name="users")
    op.drop_table("users")
    layersource_enum.drop(op.get_bind(), checkfirst=True)
    userrole_enum.drop(op.get_bind(), checkfirst=True)
