import math
from typing import Any


def _to_xy_m(lon: float, lat: float, lat_ref_rad: float) -> tuple[float, float]:
    # Local equirectangular projection to metric XY for small-distance operations.
    radius = 6371008.8
    x = math.radians(lon) * radius * math.cos(lat_ref_rad)
    y = math.radians(lat) * radius
    return x, y


def _iter_segments(geometry: dict[str, Any]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    # Normalize axis geometry to a flat segment list for projection/search.
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    lines: list[list[list[float]]]
    if gtype == "LineString":
        lines = [coords]
    elif gtype == "MultiLineString":
        lines = coords
    else:
        raise ValueError("Axis geometry must be LineString or MultiLineString")
    if not isinstance(lines, list):
        raise ValueError("Invalid axis coordinates")

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for line in lines:
        if not isinstance(line, list) or len(line) < 2:
            continue
        for idx in range(1, len(line)):
            a = line[idx - 1]
            b = line[idx]
            if not isinstance(a, list) or not isinstance(b, list) or len(a) < 2 or len(b) < 2:
                continue
            segments.append(((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))))
    if not segments:
        raise ValueError("Axis does not contain valid segments")
    return segments


def project_point_to_axis_km(geometry: dict[str, Any], lon: float, lat: float) -> float:
    # Project arbitrary point to nearest axis segment and return chainage in kilometers.
    segments = _iter_segments(geometry)
    lat_ref = math.radians(lat)
    px, py = _to_xy_m(lon, lat, lat_ref)

    traversed_m = 0.0
    best_dist_sq = float("inf")
    best_chainage_m = 0.0
    for (lon1, lat1), (lon2, lat2) in segments:
        x1, y1 = _to_xy_m(lon1, lat1, lat_ref)
        x2, y2 = _to_xy_m(lon2, lat2, lat_ref)
        dx, dy = x2 - x1, y2 - y1
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq <= 0.0:
            continue
        t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
        # Clamp projection to finite segment [A, B] to keep chainage on route geometry.
        t_clamped = max(0.0, min(1.0, t))
        proj_x = x1 + t_clamped * dx
        proj_y = y1 + t_clamped * dy
        dist_sq = (px - proj_x) ** 2 + (py - proj_y) ** 2
        seg_len_m = math.sqrt(seg_len_sq)
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_chainage_m = traversed_m + t_clamped * seg_len_m
        traversed_m += seg_len_m
    return round(best_chainage_m / 1000.0, 6)

