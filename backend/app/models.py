import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    viewer = "viewer"


class LayerSourceType(str, enum.Enum):
    uploaded_geojson = "uploaded_geojson"
    url_geojson = "url_geojson"


class LayerKind(str, enum.Enum):
    road = "road"
    road_axis = "road_axis"
    iri = "iri"
    defects = "defects"


class MediaSourceType(str, enum.Enum):
    raw360 = "raw360"
    exported = "exported"


class MediaAssetKind(str, enum.Enum):
    master_equirect = "master_equirect"
    hls = "hls"
    thumbnail = "thumbnail"
    preview = "preview"


class MediaAssetStatus(str, enum.Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class ProcessingJobStage(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


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
    media_records: Mapped[list["MediaRecord"]] = relationship("MediaRecord", back_populates="owner")


class Layer(Base):
    __tablename__ = "layers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[LayerSourceType] = mapped_column(
        Enum(LayerSourceType, name="layersourcetype", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=LayerSourceType.uploaded_geojson,
    )
    kind: Mapped[LayerKind] = mapped_column(
        Enum(LayerKind, name="layerkind", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=LayerKind.road,
    )
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("layers.id"), nullable=True, index=True)
    axis_layer_id: Mapped[int | None] = mapped_column(ForeignKey("layers.id"), nullable=True, index=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    creator: Mapped["User | None"] = relationship("User", back_populates="layers")
    parent: Mapped["Layer | None"] = relationship(
        "Layer",
        foreign_keys=[parent_id],
        remote_side=[id],
        back_populates="children",
    )
    children: Mapped[list["Layer"]] = relationship(
        "Layer",
        foreign_keys=[parent_id],
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    axis_layer: Mapped["Layer | None"] = relationship("Layer", foreign_keys=[axis_layer_id], remote_side=[id])
    iri_measurements: Mapped[list["IriMeasurement"]] = relationship(
        "IriMeasurement",
        foreign_keys="IriMeasurement.layer_id",
        back_populates="layer",
        cascade="all, delete-orphan",
    )
    defect_records: Mapped[list["DefectRecord"]] = relationship(
        "DefectRecord",
        foreign_keys="DefectRecord.layer_id",
        back_populates="layer",
        cascade="all, delete-orphan",
    )
    media_links: Mapped[list["MediaGeoLink"]] = relationship(
        "MediaGeoLink",
        foreign_keys="MediaGeoLink.layer_id",
        back_populates="layer",
    )


class IriMeasurement(Base):
    __tablename__ = "iri_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    layer_id: Mapped[int] = mapped_column(ForeignKey("layers.id"), nullable=False, index=True)
    axis_layer_id: Mapped[int] = mapped_column(ForeignKey("layers.id"), nullable=False, index=True)
    direction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lane: Mapped[str | None] = mapped_column(String(32), nullable=True)
    km_start: Mapped[float] = mapped_column(nullable=False)
    km_end: Mapped[float] = mapped_column(nullable=False)
    iri_value: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    layer: Mapped["Layer"] = relationship("Layer", foreign_keys=[layer_id], back_populates="iri_measurements")
    axis_layer: Mapped["Layer"] = relationship("Layer", foreign_keys=[axis_layer_id])


class DefectRecord(Base):
    __tablename__ = "defect_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    layer_id: Mapped[int] = mapped_column(ForeignKey("layers.id"), nullable=False, index=True)
    axis_layer_id: Mapped[int] = mapped_column(ForeignKey("layers.id"), nullable=False, index=True)
    defect_code: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    norm_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    km_start: Mapped[float] = mapped_column(nullable=False)
    km_end: Mapped[float] = mapped_column(nullable=False)
    extent_m: Mapped[float | None] = mapped_column(nullable=True)
    area_m2: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    layer: Mapped["Layer"] = relationship("Layer", foreign_keys=[layer_id], back_populates="defect_records")
    axis_layer: Mapped["Layer"] = relationship("Layer", foreign_keys=[axis_layer_id])


class MediaRecord(Base):
    __tablename__ = "media_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_type: Mapped[MediaSourceType] = mapped_column(
        Enum(MediaSourceType, name="mediasourcetype", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Owner relationship is used by access checks in API handlers.
    owner: Mapped["User"] = relationship("User", back_populates="media_records")
    assets: Mapped[list["MediaAsset"]] = relationship(
        "MediaAsset", back_populates="media", cascade="all, delete-orphan"
    )
    geo_links: Mapped[list["MediaGeoLink"]] = relationship(
        "MediaGeoLink", back_populates="media", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["ProcessingJob"]] = relationship(
        "ProcessingJob", back_populates="media", cascade="all, delete-orphan"
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"
    # One asset per kind (e.g. one master_equirect) for each media record.
    __table_args__ = (UniqueConstraint("media_id", "kind", name="uq_media_assets_media_id_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media_records.id"), nullable=False, index=True)
    kind: Mapped[MediaAssetKind] = mapped_column(
        Enum(MediaAssetKind, name="mediaassetkind", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    codec: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[MediaAssetStatus] = mapped_column(
        Enum(MediaAssetStatus, name="mediaassetstatus", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MediaAssetStatus.pending,
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    media: Mapped["MediaRecord"] = relationship("MediaRecord", back_populates="assets")


class MediaGeoLink(Base):
    __tablename__ = "media_geo_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media_records.id"), nullable=False, index=True)
    layer_id: Mapped[int | None] = mapped_column(ForeignKey("layers.id"), nullable=True)
    # Road axis used for linear referencing of this media anchor.
    axis_layer_id: Mapped[int | None] = mapped_column(ForeignKey("layers.id"), nullable=True, index=True)
    feature_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lon: Mapped[float] = mapped_column(nullable=False)
    lat: Mapped[float] = mapped_column(nullable=False)
    # Calculated chainage along axis (km from axis start).
    axis_km: Mapped[float | None] = mapped_column(nullable=True)
    heading: Mapped[float | None] = mapped_column(nullable=True)
    pitch: Mapped[float | None] = mapped_column(nullable=True)
    captured_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Geospatial links connect media to optional layer/feature context on map.
    media: Mapped["MediaRecord"] = relationship("MediaRecord", back_populates="geo_links")
    layer: Mapped["Layer | None"] = relationship(
        "Layer",
        foreign_keys=[layer_id],
        back_populates="media_links",
    )
    # Separate relation to the axis layer allows direct filtering and bulk recalculation.
    axis_layer: Mapped["Layer | None"] = relationship("Layer", foreign_keys=[axis_layer_id])


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media_records.id"), nullable=False, index=True)
    stage: Mapped[ProcessingJobStage] = mapped_column(
        Enum(ProcessingJobStage, name="processingjobstage", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ProcessingJobStage.queued,
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    media: Mapped["MediaRecord"] = relationship("MediaRecord", back_populates="jobs")
