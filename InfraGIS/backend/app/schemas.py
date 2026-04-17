from datetime import datetime

from pydantic import BaseModel, Field

from app.models import (
    LayerKind,
    LayerSourceType,
    MediaAssetKind,
    MediaAssetStatus,
    MediaSourceType,
    ProcessingJobStage,
    UserRole,
)


# Auth token payload returned by login endpoint.
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class UserPublic(BaseModel):
    id: int
    login: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    login: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    role: UserRole = UserRole.viewer


class LayerBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class LayerCreateUrl(LayerBase):
    source_url: str = Field(min_length=1, max_length=2048)
    parent_id: int | None = None
    kind: LayerKind = LayerKind.road
    axis_layer_id: int | None = None


class LayerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class LayerOut(BaseModel):
    id: int
    name: str
    description: str | None
    source_type: LayerSourceType
    kind: LayerKind
    parent_id: int | None
    axis_layer_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RoadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class AxisChainagePoint(BaseModel):
    index: int
    lon: float
    lat: float
    km: float


class AxisUploadOut(LayerOut):
    total_km: float
    points: list[AxisChainagePoint]


class LayerTreeNode(LayerOut):
    # Recursive tree node used by /layers/tree response.
    children: list["LayerTreeNode"] = []


class IriMeasurementCreate(BaseModel):
    layer_id: int
    axis_layer_id: int
    direction: str | None = Field(default=None, max_length=32)
    lane: str | None = Field(default=None, max_length=32)
    km_start: float = Field(ge=0)
    km_end: float = Field(ge=0)
    iri_value: float = Field(ge=0)


class IriMeasurementOut(BaseModel):
    id: int
    layer_id: int
    axis_layer_id: int
    direction: str | None
    lane: str | None
    km_start: float
    km_end: float
    iri_value: float
    created_at: datetime

    model_config = {"from_attributes": True}


class DefectRecordCreate(BaseModel):
    layer_id: int
    axis_layer_id: int
    defect_code: str = Field(min_length=1, max_length=128)
    severity: str | None = Field(default=None, max_length=32)
    norm_ref: str | None = Field(default=None, max_length=255)
    km_start: float = Field(ge=0)
    km_end: float = Field(ge=0)
    extent_m: float | None = Field(default=None, ge=0)
    area_m2: float | None = Field(default=None, ge=0)


class DefectRecordOut(BaseModel):
    id: int
    layer_id: int
    axis_layer_id: int
    defect_code: str
    severity: str | None
    norm_ref: str | None
    km_start: float
    km_end: float
    extent_m: float | None
    area_m2: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaAssetOut(BaseModel):
    # Derived or source asset info (master, hls, thumbnail, preview).
    id: int
    kind: MediaAssetKind
    storage_key: str
    codec: str | None
    bitrate: int | None
    status: MediaAssetStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ProcessingJobOut(BaseModel):
    # Processing lifecycle state for raw -> ready conversion flow.
    id: int
    media_id: int
    stage: ProcessingJobStage
    progress: int
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaGeoLinkOut(BaseModel):
    # Persisted geospatial anchor for a media record.
    id: int
    media_id: int
    layer_id: int | None
    axis_layer_id: int | None
    feature_id: str | None
    lon: float
    lat: float
    axis_km: float | None
    heading: float | None
    pitch: float | None
    captured_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaGeoLinkCreate(BaseModel):
    # Input payload for creating map anchor (lon/lat required).
    layer_id: int | None = None
    axis_layer_id: int | None = None
    feature_id: str | None = Field(default=None, max_length=255)
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    heading: float | None = None
    pitch: float | None = None
    captured_at: datetime | None = None


class MediaRecordOut(BaseModel):
    # Aggregate DTO used by media list/details endpoints.
    id: int
    owner_id: int
    source_type: MediaSourceType
    original_filename: str
    storage_key: str
    duration: int | None
    resolution: str | None
    created_at: datetime
    assets: list[MediaAssetOut] = []
    geo_links: list[MediaGeoLinkOut] = []
    jobs: list[ProcessingJobOut] = []

    model_config = {"from_attributes": True}


class MediaPlaybackOut(BaseModel):
    # Playback contract consumed by frontend player.
    media_id: int
    source_type: MediaSourceType
    stream_url: str | None
    download_url: str
    poster_url: str | None = None
    status: MediaAssetStatus


class MediaMapPointOut(BaseModel):
    # Lightweight point payload for rendering markers on map.
    link_id: int
    media_id: int
    layer_id: int | None
    axis_layer_id: int | None
    feature_id: str | None
    lon: float
    lat: float
    axis_km: float | None
    heading: float | None
    pitch: float | None
    captured_at: datetime | None
    source_type: MediaSourceType
    original_filename: str


class MediaAxisRecalculateOut(BaseModel):
    # Summary payload for bulk axis_km refresh operation.
    axis_layer_id: int
    scanned: int
    recalculated: int
    changed: int


LayerTreeNode.model_rebuild()
