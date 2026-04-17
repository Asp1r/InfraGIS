import csv
import io
import json
import zipfile
from typing import Any

import shapefile


def _line_from_feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    # Собираем только линейные геометрии, чтобы нормализовать вход в ось дороги.
    lines: list[list[list[float]]] = []
    for feature in features:
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        if not isinstance(geometry, dict):
            continue
        gtype = geometry.get("type")
        coords = geometry.get("coordinates")
        if gtype == "LineString" and isinstance(coords, list):
            lines.append(coords)
        elif gtype == "MultiLineString" and isinstance(coords, list):
            for item in coords:
                if isinstance(item, list):
                    lines.append(item)
    if not lines:
        raise ValueError("No line geometry found")
    if len(lines) == 1:
        return {"type": "LineString", "coordinates": lines[0]}
    return {"type": "MultiLineString", "coordinates": lines}


def parse_axis_geojson(raw: bytes) -> dict[str, Any]:
    # Нормализует разные GeoJSON-формы (Feature/FeatureCollection) к линейной геометрии.
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid GeoJSON") from exc

    if not isinstance(data, dict):
        raise ValueError("GeoJSON must be a JSON object")

    gtype = data.get("type")
    if gtype in {"LineString", "MultiLineString"}:
        return {"type": gtype, "coordinates": data.get("coordinates")}
    if gtype == "Feature":
        geometry = data.get("geometry")
        if not isinstance(geometry, dict):
            raise ValueError("Feature must contain geometry")
        return parse_axis_geojson(json.dumps(geometry).encode("utf-8"))
    if gtype == "FeatureCollection":
        features = data.get("features")
        if not isinstance(features, list):
            raise ValueError("FeatureCollection must contain feature list")
        return _line_from_feature_collection(features)
    raise ValueError("Only LineString/MultiLineString geometry is supported for road axis")


def parse_axis_csv(raw: bytes) -> dict[str, Any]:
    # CSV-ось: ожидаем lon/lat, порядок точек берем из order/seq/index (если есть).
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV must contain header")

    field_map = {name.lower().strip(): name for name in reader.fieldnames}
    lon_key = next((field_map[k] for k in ("lon", "lng", "x", "longitude") if k in field_map), None)
    lat_key = next((field_map[k] for k in ("lat", "y", "latitude") if k in field_map), None)
    order_key = next((field_map[k] for k in ("order", "seq", "point_order", "index") if k in field_map), None)

    if not lon_key or not lat_key:
        raise ValueError("CSV must contain lon/lat columns")

    rows = []
    for idx, row in enumerate(reader):
        try:
            lon = float(row[lon_key])
            lat = float(row[lat_key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid coordinate at row {idx + 2}") from exc
        order = idx
        if order_key:
            try:
                order = int(float(row[order_key]))
            except (TypeError, ValueError):
                order = idx
        rows.append((order, [lon, lat]))

    if len(rows) < 2:
        raise ValueError("CSV must contain at least two points")

    rows.sort(key=lambda x: x[0])
    return {"type": "LineString", "coordinates": [coord for _, coord in rows]}


def parse_axis_shapefile_zip(raw: bytes) -> dict[str, Any]:
    # Для Shapefile принимаем ZIP с обязательными .shp/.shx/.dbf.
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = {n.lower(): n for n in zf.namelist()}
        shp_name = next((names[n] for n in names if n.endswith(".shp")), None)
        shx_name = next((names[n] for n in names if n.endswith(".shx")), None)
        dbf_name = next((names[n] for n in names if n.endswith(".dbf")), None)

        if not shp_name or not shx_name or not dbf_name:
            raise ValueError("Shapefile ZIP must include .shp, .shx and .dbf")

        with zf.open(shp_name) as shp, zf.open(shx_name) as shx, zf.open(dbf_name) as dbf:
            reader = shapefile.Reader(
                shp=io.BytesIO(shp.read()),
                shx=io.BytesIO(shx.read()),
                dbf=io.BytesIO(dbf.read()),
            )
            lines: list[list[list[float]]] = []
            for shape in reader.shapes():
                # Ось дороги допускаем только в типах polyline.
                if shape.shapeTypeName not in {"POLYLINE", "POLYLINEZ", "POLYLINEM"}:
                    continue
                points = [[float(pt[0]), float(pt[1])] for pt in shape.points]
                if len(points) >= 2:
                    lines.append(points)

    if not lines:
        raise ValueError("Shapefile does not contain polyline geometry")
    if len(lines) == 1:
        return {"type": "LineString", "coordinates": lines[0]}
    return {"type": "MultiLineString", "coordinates": lines}

