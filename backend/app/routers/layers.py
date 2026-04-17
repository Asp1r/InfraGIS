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
from app.models import DefectRecord, IriMeasurement, Layer, LayerKind, LayerSourceType, User
from app.schemas import (
    AxisUploadOut,
    DefectRecordCreate,
    DefectRecordOut,
    IriMeasurementCreate,
    IriMeasurementOut,
    LayerCreateUrl,
    LayerOut,
    LayerTreeNode,
    LayerUpdate,
    RoadCreate,
)
from app.services.chainage import build_chainage_points
from app.services.import_axis import parse_axis_csv, parse_axis_geojson, parse_axis_shapefile_zip

router = APIRouter(prefix="/layers", tags=["layers"])


def _validate_geojson(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("GeoJSON must be a JSON object")
    t = data.get("type")
    if t not in ("FeatureCollection", "Feature", "Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon", "GeometryCollection"):
        raise ValueError("Invalid GeoJSON type")


def _build_tree(nodes: list[Layer]) -> list[LayerTreeNode]:
    # Формируем дерево слоев в памяти по parent_id.
    by_id: dict[int, LayerTreeNode] = {
        layer.id: LayerTreeNode.model_validate(layer, from_attributes=True) for layer in nodes
    }
    roots: list[LayerTreeNode] = []
    for node in by_id.values():
        if node.parent_id and node.parent_id in by_id:
            by_id[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


async def _download_geojson(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
    _validate_geojson(data)
    return data


def _ensure_axis_layer(db: Session, axis_layer_id: int) -> Layer:
    # Центральная проверка: ссылка axis_layer_id должна указывать именно на слой оси.
    axis = db.get(Layer, axis_layer_id)
    if axis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Axis layer not found")
    if axis.kind != LayerKind.road_axis:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Layer is not a road axis")
    return axis


def _normalize_axis_geometry(filename: str | None, raw: bytes) -> dict[str, Any]:
    # Выбор парсера оси по расширению исходного файла.
    name = (filename or "").lower()
    if name.endswith(".geojson") or name.endswith(".json"):
        return parse_axis_geojson(raw)
    if name.endswith(".csv"):
        return parse_axis_csv(raw)
    if name.endswith(".zip"):
        return parse_axis_shapefile_zip(raw)
    raise ValueError("Unsupported axis format. Use GeoJSON, CSV or zipped Shapefile")


@router.get("", response_model=list[LayerOut])
def list_layers(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Layer]:
    return db.query(Layer).order_by(Layer.id).all()


@router.get("/tree", response_model=list[LayerTreeNode])
def list_layers_tree(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[LayerTreeNode]:
    layers = db.query(Layer).order_by(Layer.id).all()
    return _build_tree(layers)


@router.post("/roads", response_model=LayerOut, status_code=status.HTTP_201_CREATED)
def create_road(
    body: RoadCreate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Layer:
    layer = Layer(
        name=body.name,
        description=body.description,
        kind=LayerKind.road,
        source_type=LayerSourceType.uploaded_geojson,
        created_by=admin.id,
    )
    db.add(layer)
    db.commit()
    db.refresh(layer)
    return layer


@router.post("", response_model=LayerOut, status_code=status.HTTP_201_CREATED)
async def create_layer_multipart(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    kind: Annotated[LayerKind, Form()] = LayerKind.road,
    parent_id: Annotated[int | None, Form()] = None,
    axis_layer_id: Annotated[int | None, Form()] = None,
    source_url: Annotated[str | None, Form()] = None,
    file: UploadFile | None = File(None),
) -> Layer:
    # Универсальная точка создания слоя: road/axis/iri/defects с optional geometry source.
    max_bytes = settings.max_upload_mb * 1024 * 1024
    settings.upload_path.mkdir(parents=True, exist_ok=True)

    if kind in (LayerKind.iri, LayerKind.defects) and not axis_layer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="axis_layer_id is required")
    if axis_layer_id:
        _ensure_axis_layer(db, axis_layer_id)

    if file is not None and file.filename:
        raw = await file.read()
        if len(raw) > max_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
        try:
            data = (
                _normalize_axis_geometry(file.filename, raw)
                if kind == LayerKind.road_axis
                else json.loads(raw.decode("utf-8"))
            )
            if kind != LayerKind.road_axis:
                _validate_geojson(data)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid GeoJSON: {e}") from e
        fname = f"{uuid.uuid4().hex}.geojson"
        fpath = settings.upload_path / fname
        # Храним ось всегда в нормализованном GeoJSON для единообразного чтения на карте.
        fpath.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        layer = Layer(
            name=name,
            description=description,
            kind=kind,
            source_type=LayerSourceType.uploaded_geojson,
            file_path=str(fpath),
            source_url=None,
            parent_id=parent_id,
            axis_layer_id=axis_layer_id,
            created_by=admin.id,
        )
        db.add(layer)
        db.commit()
        db.refresh(layer)
        return layer

    if source_url:
        try:
            if kind == LayerKind.road_axis:
                data = await _download_geojson(source_url)
                data = parse_axis_geojson(json.dumps(data).encode("utf-8"))
            else:
                data = await _download_geojson(source_url)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not fetch or parse GeoJSON from URL: {e}",
            ) from e
        layer = Layer(
            name=name,
            description=description,
            kind=kind,
            source_type=LayerSourceType.url_geojson,
            file_path=None,
            source_url=source_url,
            parent_id=parent_id,
            axis_layer_id=axis_layer_id,
            created_by=admin.id,
        )
        db.add(layer)
        db.commit()
        db.refresh(layer)
        return layer

    if kind in (LayerKind.road, LayerKind.iri, LayerKind.defects):
        layer = Layer(
            name=name,
            description=description,
            kind=kind,
            source_type=LayerSourceType.uploaded_geojson,
            file_path=None,
            source_url=None,
            parent_id=parent_id,
            axis_layer_id=axis_layer_id,
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


@router.post("/{road_id}/axis", response_model=AxisUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_road_axis(
    road_id: int,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()] = "Ось дороги",
    description: Annotated[str | None, Form()] = None,
    source_url: Annotated[str | None, Form()] = None,
    file: UploadFile | None = File(None),
) -> AxisUploadOut:
    # Специализированный endpoint: загрузка оси внутрь конкретной дороги + расчет chainage.
    road = db.get(Layer, road_id)
    if road is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Road layer not found")
    if road.kind != LayerKind.road:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent layer must be kind=road")

    if not file and not source_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide file or source_url")

    if file and file.filename:
        raw = await file.read()
        try:
            geometry = _normalize_axis_geometry(file.filename, raw)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    else:
        try:
            geometry = await _download_geojson(source_url or "")
            geometry = parse_axis_geojson(json.dumps(geometry).encode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid axis URL: {exc}") from exc

    points, total_km = build_chainage_points(geometry)
    fname = f"{uuid.uuid4().hex}.geojson"
    fpath = settings.upload_path / fname
    fpath.write_text(json.dumps(geometry, ensure_ascii=False), encoding="utf-8")
    layer = Layer(
        name=name,
        description=description,
        kind=LayerKind.road_axis,
        source_type=LayerSourceType.uploaded_geojson,
        file_path=str(fpath),
        source_url=source_url,
        parent_id=road.id,
        created_by=admin.id,
    )
    db.add(layer)
    db.commit()
    db.refresh(layer)
    return AxisUploadOut(
        **LayerOut.model_validate(layer, from_attributes=True).model_dump(),
        total_km=total_km,
        points=points,
    )


@router.post("/from-url", response_model=LayerOut, status_code=status.HTTP_201_CREATED)
async def create_layer_json(
    body: LayerCreateUrl,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Layer:
    if body.kind in (LayerKind.iri, LayerKind.defects) and not body.axis_layer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="axis_layer_id is required")
    if body.axis_layer_id:
        _ensure_axis_layer(db, body.axis_layer_id)

    try:
        if body.kind == LayerKind.road_axis:
            data = await _download_geojson(body.source_url)
            data = parse_axis_geojson(json.dumps(data).encode("utf-8"))
        else:
            data = await _download_geojson(body.source_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not fetch or parse GeoJSON from URL: {e}",
        ) from e
    layer = Layer(
        name=body.name,
        description=body.description,
        kind=body.kind,
        source_type=LayerSourceType.url_geojson,
        file_path=None,
        source_url=body.source_url,
        parent_id=body.parent_id,
        axis_layer_id=body.axis_layer_id,
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


@router.post("/iri-records", response_model=IriMeasurementOut, status_code=status.HTTP_201_CREATED)
def create_iri_record(
    body: IriMeasurementCreate,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> IriMeasurement:
    # IRI-показатели привязываем к тематическому слою IRI и к конкретной оси дороги.
    layer = db.get(Layer, body.layer_id)
    if layer is None or layer.kind != LayerKind.iri:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="layer_id must point to iri layer")
    _ensure_axis_layer(db, body.axis_layer_id)
    if body.km_end < body.km_start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="km_end must be >= km_start")
    item = IriMeasurement(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/iri-records/{layer_id}", response_model=list[IriMeasurementOut])
def list_iri_records(
    layer_id: int,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[IriMeasurement]:
    return db.query(IriMeasurement).filter(IriMeasurement.layer_id == layer_id).order_by(IriMeasurement.id).all()


@router.post("/defect-records", response_model=DefectRecordOut, status_code=status.HTTP_201_CREATED)
def create_defect_record(
    body: DefectRecordCreate,
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> DefectRecord:
    # Дефекты храним как линейно-привязанные записи (km_start/km_end) с нормативной ссылкой.
    layer = db.get(Layer, body.layer_id)
    if layer is None or layer.kind != LayerKind.defects:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="layer_id must point to defects layer")
    _ensure_axis_layer(db, body.axis_layer_id)
    if body.km_end < body.km_start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="km_end must be >= km_start")
    item = DefectRecord(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/defect-records/{layer_id}", response_model=list[DefectRecordOut])
def list_defect_records(
    layer_id: int,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DefectRecord]:
    return db.query(DefectRecord).filter(DefectRecord.layer_id == layer_id).order_by(DefectRecord.id).all()


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
    if layer.kind in (LayerKind.iri, LayerKind.defects):
        # Тематические слои могут быть без геометрии на этапе 1 — возвращаем пустую коллекцию.
        return {"type": "FeatureCollection", "features": []}
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Layer has no data source")
