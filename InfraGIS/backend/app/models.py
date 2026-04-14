import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    viewer = "viewer"


class LayerSourceType(str, enum.Enum):
    uploaded_geojson = "uploaded_geojson"
    url_geojson = "url_geojson"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.viewer,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    layers: Mapped[list["Layer"]] = relationship("Layer", back_populates="creator")


class Layer(Base):
    __tablename__ = "layers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[LayerSourceType] = mapped_column(
        Enum(LayerSourceType, name="layersourcetype", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    creator: Mapped["User | None"] = relationship("User", back_populates="layers")
