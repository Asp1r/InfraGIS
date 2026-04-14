import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../api";

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

type Props = {
  enabledLayerIds: Set<number>;
  layerColors: Map<number, string>;
};

export function MapView({ enabledLayerIds, layerColors }: Props) {
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
              "fill-opacity": 0.25,
            },
          });
          map.addLayer({
            id: lineLayerId(id),
            type: "line",
            source: sid,
            paint: {
              "line-color": color,
              "line-width": 2,
            },
          });
        } catch {
          /* ignore failed fetch */
        }
      }
    };
    void run();
  }, [mapReady, enabledLayerIds, layerColors]);

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
