import json
import uuid
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Layer, LayerSourceType, User
from app.schemas import LayerCreateUrl, LayerOut, LayerUpdate

router = APIRouter(prefix="/layers", tags=["layers"])


def _validate_geojson(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("GeoJSON must be a JSON object")
    t = data.get("type")
    if t not in ("FeatureCollection", "Feature", "Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon", "GeometryCollection"):
        raise ValueError("Invalid GeoJSON type")


@router.get("", response_model=list[LayerOut])
def list_layers(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Layer]:
    return db.query(Layer).order_by(Layer.id).all()


@router.post("", response_model=LayerOut, status_code=status.HTTP_201_CREATED)
async def create_layer_multipart(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    source_url: Annotated[str | None, Form()] = None,
    file: UploadFile | None = File(None),
) -> Layer:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    settings.upload_path.mkdir(parents=True, exist_ok=True)

    if file is not None and file.filename:
        raw = await file.read()
        if len(raw) > max_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
        try:
            data = json.loads(raw.decode("utf-8"))
            _validate_geojson(data)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid GeoJSON: {e}") from e
        fname = f"{uuid.uuid4().hex}.geojson"
        fpath = settings.upload_path / fname
        fpath.write_bytes(raw)
        layer = Layer(
            name=name,
            description=description,
            source_type=LayerSourceType.uploaded_geojson,
            file_path=str(fpath),
            source_url=None,
            created_by=admin.id,
        )
        db.add(layer)
        db.commit()
        db.refresh(layer)
        return layer

    if source_url:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(source_url)
                r.raise_for_status()
                data = r.json()
                _validate_geojson(data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not fetch or parse GeoJSON from URL: {e}",
            ) from e
        layer = Layer(
            name=name,
            description=description,
            source_type=LayerSourceType.url_geojson,
            file_path=None,
            source_url=source_url,
            created_by=admin.id,
        )
        db.add(layer)
        db.commit()
        db.refresh(layer)
        return layer

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Provide either a GeoJSON file or source_url",
    )


@router.post("/from-url", response_model=LayerOut, status_code=status.HTTP_201_CREATED)
async def create_layer_json(
    body: LayerCreateUrl,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Layer:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(body.source_url)
            r.raise_for_status()
            data = r.json()
            _validate_geojson(data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not fetch or parse GeoJSON from URL: {e}",
        ) from e
    layer = Layer(
        name=body.name,
        description=body.description,
        source_type=LayerSourceType.url_geojson,
        file_path=None,
        source_url=body.source_url,
        created_by=admin.id,
    )
    db.add(layer)
    db.commit()
    db.refresh(layer)
    return layer


@router.patch("/{layer_id}", response_model=LayerOut)
def update_layer(
    layer_id: int,
    body: LayerUpdate,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Layer:
    layer = db.get(Layer, layer_id)
    if layer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
    if body.name is not None:
        layer.name = body.name
    if body.description is not None:
        layer.description = body.description
    db.commit()
    db.refresh(layer)
    return layer


@router.delete("/{layer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_layer(
    layer_id: int,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    layer = db.get(Layer, layer_id)
    if layer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
    if layer.file_path:
        p = Path(layer.file_path)
        if p.is_file():
            p.unlink(missing_ok=True)
    db.delete(layer)
    db.commit()


@router.get("/{layer_id}/geojson")
async def get_layer_geojson(
    layer_id: int,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    layer = db.get(Layer, layer_id)
    if layer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
    if layer.source_type == LayerSourceType.uploaded_geojson and layer.file_path:
        p = Path(layer.file_path)
        if not p.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer file missing")
        return json.loads(p.read_text(encoding="utf-8"))
    if layer.source_type == LayerSourceType.url_geojson and layer.source_url:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(layer.source_url)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch layer: {e}",
            ) from e
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Layer has no data source")
