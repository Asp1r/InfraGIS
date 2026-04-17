import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../api";
import type { MediaMapPoint } from "../types";

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    },
  },
  layers: [
    {
      id: "osm",
      type: "raster",
      source: "osm",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

function sourceId(id: number) {
  return `layer-src-${id}`;
}
function lineLayerId(id: number) {
  return `layer-line-${id}`;
}
function fillLayerId(id: number) {
  return `layer-fill-${id}`;
}
function mediaSourceId() {
  // Dedicated map source for 360 media point markers.
  return "media360-points-src";
}
function mediaLayerId() {
  // Dedicated map layer id for click/hover handlers.
  return "media360-points-layer";
}

type Props = {
  enabledLayerIds: Set<number>;
  layerColors: Map<number, string>;
  layerKinds: Map<number, string>;
  mediaPoints: MediaMapPoint[];
};

export function MapView({ enabledLayerIds, layerColors, layerKinds, mediaPoints }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: [37.62, 55.75],
      zoom: 5,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.on("load", () => setMapReady(true));
    mapRef.current = map;
    return () => {
      setMapReady(false);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const removeLayer = (id: number) => {
      const lid = lineLayerId(id);
      const fid = fillLayerId(id);
      const sid = sourceId(id);
      if (map.getLayer(lid)) map.removeLayer(lid);
      if (map.getLayer(fid)) map.removeLayer(fid);
      if (map.getSource(sid)) map.removeSource(sid);
    };

    const prevIds = new Set(
      Object.keys(map.getStyle().sources ?? {})
        .filter((k) => k.startsWith("layer-src-"))
        .map((k) => parseInt(k.replace("layer-src-", ""), 10)),
    );

    for (const id of prevIds) {
      if (!enabledLayerIds.has(id)) removeLayer(id);
    }

    const run = async () => {
      // Lazily fetch and attach selected GIS layers as GeoJSON sources.
      for (const id of enabledLayerIds) {
        const sid = sourceId(id);
        if (map.getSource(sid)) continue;
        try {
          const geo = await apiFetch<GeoJSON.GeoJSON>(`/layers/${id}/geojson`);
          if (!mapRef.current || mapRef.current !== map) return;
          if (!enabledLayerIds.has(id)) return;
          if (map.getSource(sid)) return;
          map.addSource(sid, { type: "geojson", data: geo });
          const color = layerColors.get(id) ?? "#3d8bfd";
          map.addLayer({
            id: fillLayerId(id),
            type: "fill",
            source: sid,
            filter: ["==", ["geometry-type"], "Polygon"],
            paint: {
              "fill-color": color,
              "fill-opacity": layerKinds.get(id) === "road_axis" ? 0.05 : 0.25,
            },
          });
          map.addLayer({
            id: lineLayerId(id),
            type: "line",
            source: sid,
            paint: {
              "line-color": layerKinds.get(id) === "road_axis" ? "#ef4444" : color,
              "line-width": layerKinds.get(id) === "road_axis" ? 4 : 2,
            },
          });
        } catch {
          /* ignore failed fetch */
        }
      }
    };
    void run();
  }, [mapReady, enabledLayerIds, layerColors, layerKinds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const srcId = mediaSourceId();
    const lyrId = mediaLayerId();
    // Rebuild marker source whenever media points change.
    const data: GeoJSON.FeatureCollection<GeoJSON.Point> = {
      type: "FeatureCollection",
      features: mediaPoints.map((point) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [point.lon, point.lat] },
        properties: {
          media_id: point.media_id,
          original_filename: point.original_filename,
          axis_km: point.axis_km,
        },
      })),
    };

    if (!map.getSource(srcId)) {
      map.addSource(srcId, { type: "geojson", data });
    } else {
      (map.getSource(srcId) as maplibregl.GeoJSONSource).setData(data);
    }

    if (!map.getLayer(lyrId)) {
      map.addLayer({
        id: lyrId,
        type: "circle",
        source: srcId,
        paint: {
          "circle-radius": 6,
          "circle-color": "#f97316",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        },
      });
    }

    const onClick = (event: maplibregl.MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      if (!feature) return;
      const mediaId = feature.properties?.media_id;
      const filename = feature.properties?.original_filename;
      const axisKm = feature.properties?.axis_km;
      if (typeof mediaId !== "number" && typeof mediaId !== "string") return;
      const id = String(mediaId);
      const label = typeof filename === "string" ? filename : `media-${id}`;
      // Deep-link into media module focused on clicked record.
      const kmText = typeof axisKm === "number" ? `<br/><strong>Км:</strong> ${axisKm.toFixed(3)}` : "";
      new maplibregl.Popup()
        .setLngLat(event.lngLat)
        .setHTML(
          `<strong>360:</strong> ${label}${kmText}<br/><a href="/media360?mediaId=${id}">Открыть модуль</a>`,
        )
        .addTo(map);
    };

    map.on("click", lyrId, onClick);
    map.on("mouseenter", lyrId, () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", lyrId, () => {
      map.getCanvas().style.cursor = "";
    });

    return () => {
      map.off("click", lyrId, onClick);
      if (map.getLayer(lyrId)) map.removeLayer(lyrId);
      if (map.getSource(srcId)) map.removeSource(srcId);
    };
  }, [mapReady, mediaPoints]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "absolute",
        inset: 0,
      }}
    />
  );
}
