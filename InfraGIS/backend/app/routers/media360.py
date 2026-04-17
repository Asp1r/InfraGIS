import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import (
    Layer,
    LayerKind,
    LayerSourceType,
    MediaAsset,
    MediaAssetKind,
    MediaAssetStatus,
    MediaGeoLink,
    MediaRecord,
    MediaSourceType,
    ProcessingJob,
    ProcessingJobStage,
    User,
)
from app.schemas import (
    MediaAxisRecalculateOut,
    MediaGeoLinkCreate,
    MediaGeoLinkOut,
    MediaMapPointOut,
    MediaPlaybackOut,
    MediaRecordOut,
    ProcessingJobOut,
)
from app.services.linear_reference import project_point_to_axis_km

router = APIRouter(prefix="/media360", tags=["media360"])

# Allowed upload extensions for initial MVP ingestion path.
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}
RAW360_EXTENSIONS = {".360"}
# Upload chunk size keeps memory bounded for large files.
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def _media_storage_path(storage_key: str) -> Path:
    # "processed/" prefix is reserved for derived/transcoded assets.
    if storage_key.startswith("processed/"):
        return (settings.media_processed_path / storage_key.removeprefix("processed/")).resolve()
    return (settings.media_upload_path / storage_key).resolve()


def _assert_media_access(user: User, media: MediaRecord) -> None:
    # Admin can view any media; viewers are scoped to ownership.
    if user.role.value == "admin":
        return
    if media.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _infer_source_type(filename: str) -> MediaSourceType:
    suffix = Path(filename).suffix.lower()
    if suffix in RAW360_EXTENSIONS:
        return MediaSourceType.raw360
    if suffix in VIDEO_EXTENSIONS:
        return MediaSourceType.exported
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file type. Allowed: .360, .mp4, .mov, .m4v, .webm",
    )


async def _save_upload_file(file: UploadFile, destination: Path, max_bytes: int) -> int:
    # Stream upload to disk in chunks to avoid loading big files into RAM.
    written = 0
    with destination.open("wb") as out:
        while True:
            chunk = await file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                # Drop partial file if size exceeds configured limit.
                out.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
            out.write(chunk)
    return written


def _load_axis_geometry(db: Session, axis_layer_id: int) -> dict[str, Any]:
    # Load axis source as GeoJSON regardless of storage mode (uploaded file or URL).
    axis_layer = db.get(Layer, axis_layer_id)
    if axis_layer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Axis layer not found")
    if axis_layer.kind != LayerKind.road_axis:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="axis_layer_id must point to road_axis")

    if axis_layer.source_type == LayerSourceType.uploaded_geojson and axis_layer.file_path:
        p = Path(axis_layer.file_path)
        if not p.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Axis file missing")
        return json.loads(p.read_text(encoding="utf-8"))
    if axis_layer.source_type == LayerSourceType.url_geojson and axis_layer.source_url:
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.get(axis_layer.source_url)
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to load axis: {exc}") from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Axis layer has no data source")


def _resolve_axis_layer_id(db: Session, layer_id: int | None, axis_layer_id: int | None) -> int | None:
    # Priority: explicit axis_layer_id from payload, then derive from linked thematic layer.
    if axis_layer_id is not None:
        return axis_layer_id
    if layer_id is None:
        return None
    layer = db.get(Layer, layer_id)
    if layer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
    if layer.kind == LayerKind.road_axis:
        return layer.id
    return layer.axis_layer_id


@router.post("/axis/{axis_layer_id}/recalculate-km", response_model=MediaAxisRecalculateOut)
def recalculate_axis_km(
    axis_layer_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    media_id: int | None = None,
) -> MediaAxisRecalculateOut:
    # Admin maintenance endpoint: recompute chainage for existing media anchors.
    geometry = _load_axis_geometry(db, axis_layer_id)
    links = db.query(MediaGeoLink).order_by(MediaGeoLink.id).all()
    scanned = 0
    recalculated = 0
    changed = 0
    for link in links:
        if media_id is not None and link.media_id != media_id:
            continue
        # Reuse same resolution logic as single geolink creation.
        resolved_axis_id = _resolve_axis_layer_id(db, link.layer_id, link.axis_layer_id)
        if resolved_axis_id != axis_layer_id:
            continue
        scanned += 1
        km = project_point_to_axis_km(geometry, link.lon, link.lat)
        recalculated += 1
        if link.axis_km is None or abs(link.axis_km - km) > 1e-9 or link.axis_layer_id != axis_layer_id:
            changed += 1
        link.axis_layer_id = axis_layer_id
        link.axis_km = km
    db.commit()
    return MediaAxisRecalculateOut(
        axis_layer_id=axis_layer_id,
        scanned=scanned,
        recalculated=recalculated,
        changed=changed,
    )


@router.post("/upload", response_model=MediaRecordOut, status_code=status.HTTP_201_CREATED)
async def upload_media(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
    duration: Annotated[int | None, Form()] = None,
    resolution: Annotated[str | None, Form()] = None,
) -> MediaRecord:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is required")
    source_type = _infer_source_type(file.filename)
    max_bytes = settings.media_max_upload_mb * 1024 * 1024

    # Ensure storage dirs exist for source files and derived assets.
    settings.media_upload_path.mkdir(parents=True, exist_ok=True)
    settings.media_processed_path.mkdir(parents=True, exist_ok=True)
    file_ext = Path(file.filename).suffix.lower()
    filename = f"{uuid.uuid4().hex}{file_ext}"
    output_path = settings.media_upload_path / filename
    await _save_upload_file(file, output_path, max_bytes)

    media = MediaRecord(
        owner_id=user.id,
        source_type=source_type,
        original_filename=file.filename,
        storage_key=filename,
        duration=duration,
        resolution=resolution,
    )
    db.add(media)
    db.flush()

    # Exported videos are considered ready for immediate playback.
    if source_type == MediaSourceType.exported:
        db.add(
            MediaAsset(
                media_id=media.id,
                kind=MediaAssetKind.master_equirect,
                storage_key=filename,
                codec=None,
                bitrate=None,
                status=MediaAssetStatus.ready,
            )
        )
        db.add(
            ProcessingJob(
                media_id=media.id,
                stage=ProcessingJobStage.ready,
                progress=100,
                error=None,
            )
        )
    # Raw .360 files enter queued state until a converter/worker processes them.
    else:
        db.add(
            MediaAsset(
                media_id=media.id,
                kind=MediaAssetKind.master_equirect,
                storage_key=filename,
                codec=None,
                bitrate=None,
                status=MediaAssetStatus.pending,
            )
        )
        db.add(
            ProcessingJob(
                media_id=media.id,
                stage=ProcessingJobStage.queued,
                progress=0,
                error="Queued for conversion from raw .360 to web playback format",
            )
        )

    db.commit()
    db.refresh(media)
    return (
        db.query(MediaRecord)
        .options(
            selectinload(MediaRecord.assets),
            selectinload(MediaRecord.geo_links),
            selectinload(MediaRecord.jobs),
        )
        .filter(MediaRecord.id == media.id)
        .first()
    )


@router.get("/items", response_model=list[MediaRecordOut])
def list_items(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: MediaAssetStatus | None = None,
) -> list[MediaRecord]:
    q = db.query(MediaRecord).options(
        selectinload(MediaRecord.assets),
        selectinload(MediaRecord.geo_links),
        selectinload(MediaRecord.jobs),
    )
    if user.role.value != "admin":
        q = q.filter(MediaRecord.owner_id == user.id)
    if status_filter is not None:
        q = q.join(MediaAsset, MediaAsset.media_id == MediaRecord.id).filter(MediaAsset.status == status_filter)
        # Avoid duplicates when a record has multiple assets with same status.
        q = q.distinct()
    return q.order_by(MediaRecord.id.desc()).all()


@router.get("/items/{media_id}", response_model=MediaRecordOut)
def get_item(
    media_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MediaRecord:
    media = (
        db.query(MediaRecord)
        .options(
            selectinload(MediaRecord.assets),
            selectinload(MediaRecord.geo_links),
            selectinload(MediaRecord.jobs),
        )
        .filter(MediaRecord.id == media_id)
        .first()
    )
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    _assert_media_access(user, media)
    return media


@router.post("/items/{media_id}/geolink", response_model=MediaGeoLinkOut)
def create_geo_link(
    media_id: int,
    body: MediaGeoLinkCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MediaGeoLink:
    media = db.get(MediaRecord, media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    _assert_media_access(user, media)
    if body.layer_id is not None and db.get(Layer, body.layer_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
    resolved_axis_layer_id = _resolve_axis_layer_id(db, body.layer_id, body.axis_layer_id)
    axis_km: float | None = None
    if resolved_axis_layer_id is not None:
        # Compute km along axis so each 360 frame is linearly referenced.
        geometry = _load_axis_geometry(db, resolved_axis_layer_id)
        axis_km = project_point_to_axis_km(geometry, body.lon, body.lat)
    link = MediaGeoLink(
        media_id=media_id,
        layer_id=body.layer_id,
        axis_layer_id=resolved_axis_layer_id,
        feature_id=body.feature_id,
        lon=body.lon,
        lat=body.lat,
        axis_km=axis_km,
        heading=body.heading,
        pitch=body.pitch,
        captured_at=body.captured_at,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.get("/items/{media_id}/playback", response_model=MediaPlaybackOut)
def get_playback(
    media_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MediaPlaybackOut:
    media = (
        db.query(MediaRecord)
        .options(selectinload(MediaRecord.assets))
        .filter(MediaRecord.id == media_id)
        .first()
    )
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    _assert_media_access(user, media)

    # Only stream-capable assets should be returned as playback source.
    ready_asset = next(
        (
            a
            for a in media.assets
            if a.status == MediaAssetStatus.ready and a.kind in (MediaAssetKind.master_equirect, MediaAssetKind.hls)
        ),
        None,
    )
    if ready_asset is not None:
        return MediaPlaybackOut(
            media_id=media.id,
            source_type=media.source_type,
            stream_url=f"/media360/assets/{ready_asset.id}",
            download_url=f"/media360/download/{media.id}",
            status=MediaAssetStatus.ready,
        )
    return MediaPlaybackOut(
        media_id=media.id,
        source_type=media.source_type,
        stream_url=None,
        download_url=f"/media360/download/{media.id}",
        status=MediaAssetStatus.pending,
    )


@router.get("/jobs/{job_id}", response_model=ProcessingJobOut)
def get_job(
    job_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProcessingJob:
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    media = db.get(MediaRecord, job.media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    _assert_media_access(user, media)
    return job


@router.get("/map-points", response_model=list[MediaMapPointOut])
def list_map_points(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    layer_id: int | None = None,
    axis_layer_id: int | None = None,
) -> list[MediaMapPointOut]:
    q = db.query(MediaGeoLink, MediaRecord).join(MediaRecord, MediaRecord.id == MediaGeoLink.media_id)
    # Viewers only see points for media they own.
    if user.role.value != "admin":
        q = q.filter(MediaRecord.owner_id == user.id)
    if layer_id is not None:
        q = q.filter(MediaGeoLink.layer_id == layer_id)
    if axis_layer_id is not None:
        q = q.filter(MediaGeoLink.axis_layer_id == axis_layer_id)
    rows = q.order_by(MediaGeoLink.id.desc()).all()
    return [
        MediaMapPointOut(
            link_id=link.id,
            media_id=media.id,
            layer_id=link.layer_id,
            axis_layer_id=link.axis_layer_id,
            feature_id=link.feature_id,
            lon=link.lon,
            lat=link.lat,
            axis_km=link.axis_km,
            heading=link.heading,
            pitch=link.pitch,
            captured_at=link.captured_at,
            source_type=media.source_type,
            original_filename=media.original_filename,
        )
        for link, media in rows
    ]


@router.get("/download/{media_id}")
def download_source(
    media_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    media = db.get(MediaRecord, media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    _assert_media_access(user, media)
    source_path = _media_storage_path(media.storage_key)
    if not source_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file not found")
    return FileResponse(path=str(source_path), filename=media.original_filename)


@router.get("/assets/{asset_id}")
def get_asset_file(
    asset_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    media = db.get(MediaRecord, asset.media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    _assert_media_access(user, media)
    file_path = _media_storage_path(asset.storage_key)
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset file not found")
    return FileResponse(path=str(file_path))


@router.delete("/items/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    media_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    media = (
        db.query(MediaRecord)
        .options(
            selectinload(MediaRecord.assets),
            selectinload(MediaRecord.jobs),
            selectinload(MediaRecord.geo_links),
        )
        .filter(MediaRecord.id == media_id)
        .first()
    )
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    _assert_media_access(user, media)
    for asset in media.assets:
        path = _media_storage_path(asset.storage_key)
        if path.is_file():
            path.unlink(missing_ok=True)
    source_path = _media_storage_path(media.storage_key)
    if source_path.is_file():
        source_path.unlink(missing_ok=True)
    db.delete(media)
    db.commit()


@router.post("/internal/jobs/{job_id}/simulate-ready", response_model=ProcessingJobOut)
def simulate_ready(
    job_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ProcessingJob:
    # Internal helper endpoint for local/dev flow; restricted to admins.
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    media = db.get(MediaRecord, job.media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    source_path = _media_storage_path(media.storage_key)
    if not source_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file missing")
    settings.media_processed_path.mkdir(parents=True, exist_ok=True)
    processed_key = f"processed/{media.id}.mp4"
    processed_path = _media_storage_path(processed_key)
    shutil.copyfile(source_path, processed_path)

    ready_asset = (
        db.query(MediaAsset)
        .filter(MediaAsset.media_id == media.id, MediaAsset.kind == MediaAssetKind.master_equirect)
        .first()
    )
    if ready_asset is None:
        ready_asset = MediaAsset(
            media_id=media.id,
            kind=MediaAssetKind.master_equirect,
            storage_key=processed_key,
            status=MediaAssetStatus.ready,
        )
        db.add(ready_asset)
    else:
        ready_asset.storage_key = processed_key
        ready_asset.status = MediaAssetStatus.ready

    job.stage = ProcessingJobStage.ready
    job.progress = 100
    job.error = None
    # Track timestamps even in simulated processing flow.
    if job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job
