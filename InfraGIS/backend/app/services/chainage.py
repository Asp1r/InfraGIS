import math
from typing import Any


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    # Геодезическая длина между двумя вершинами на сфере Земли (WGS84, приближенно).
    radius_m = 6371008.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * radius_m * math.asin(math.sqrt(a))


def _as_lines(geometry: dict[str, Any]) -> list[list[list[float]]]:
    # Для линейной привязки ось дороги допускаем только как LineString/MultiLineString.
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "LineString":
        if not isinstance(coords, list) or len(coords) < 2:
            raise ValueError("LineString must contain at least two coordinates")
        return [coords]
    if gtype == "MultiLineString":
        if not isinstance(coords, list) or not coords:
            raise ValueError("MultiLineString must contain lines")
        for line in coords:
            if not isinstance(line, list) or len(line) < 2:
                raise ValueError("Each line in MultiLineString must contain at least two coordinates")
        return coords
    raise ValueError("Geometry for chainage must be LineString or MultiLineString")


def build_chainage_points(geometry: dict[str, Any]) -> tuple[list[dict[str, float | int]], float]:
    # Возвращаем кумулятивный километраж по каждой вершине оси и суммарную длину.
    lines = _as_lines(geometry)
    points: list[dict[str, float | int]] = []
    total_m = 0.0
    idx = 0

    for line in lines:
        for i, coord in enumerate(line):
            if not isinstance(coord, list) or len(coord) < 2:
                raise ValueError("Invalid coordinate in geometry")
            lon = float(coord[0])
            lat = float(coord[1])
            if points and i > 0:
                # Километраж растет от начала оси по каждому линейному сегменту.
                prev = line[i - 1]
                total_m += _haversine_m(float(prev[0]), float(prev[1]), lon, lat)
            points.append(
                {
                    "index": idx,
                    "lon": lon,
                    "lat": lat,
                    "km": round(total_m / 1000.0, 6),
                }
            )
            idx += 1

    return points, round(total_m / 1000.0, 6)

