from app.services.chainage import build_chainage_points


def test_chainage_for_linestring():
    geometry = {"type": "LineString", "coordinates": [[37.0, 55.0], [37.1, 55.0], [37.2, 55.0]]}
    points, total_km = build_chainage_points(geometry)
    assert len(points) == 3
    assert total_km > 0
    assert points[0]["km"] == 0
    assert points[-1]["km"] == total_km


def test_chainage_for_multilinestring():
    geometry = {
        "type": "MultiLineString",
        "coordinates": [
            [[37.0, 55.0], [37.1, 55.0]],
            [[37.1, 55.0], [37.2, 55.0]],
        ],
    }
    points, total_km = build_chainage_points(geometry)
    assert len(points) == 4
    assert total_km > 0
