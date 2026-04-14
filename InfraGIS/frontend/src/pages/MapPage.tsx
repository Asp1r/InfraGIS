import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api";
import type { Layer } from "../types";
import { MapView } from "../components/MapView";

const layerColors = ["#3d8bfd", "#22c55e", "#eab308", "#a855f7", "#f97316", "#ec4899"];

export function MapPage() {
  const [layers, setLayers] = useState<Layer[]>([]);
  const [enabled, setEnabled] = useState<Set<number>>(new Set());
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await apiFetch<Layer[]>("/layers");
      setLayers(list);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки слоёв");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function toggle(id: number) {
    setEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const colorById = useMemo(() => {
    const m = new Map<number, string>();
    layers.forEach((l, i) => m.set(l.id, layerColors[i % layerColors.length]));
    return m;
  }, [layers]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 52px)" }}>
      <aside
        style={{
          padding: "0.75rem 1rem",
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
          display: "flex",
          flexWrap: "wrap",
          gap: "1rem",
          alignItems: "center",
        }}
      >
        <span style={{ color: "var(--muted)", fontSize: "0.875rem" }}>Слои</span>
        {layers.length === 0 && <span style={{ color: "var(--muted)" }}>Нет доступных слоёв</span>}
        {layers.map((l) => (
          <label
            key={l.id}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
              cursor: "pointer",
              fontSize: "0.9rem",
            }}
          >
            <input type="checkbox" checked={enabled.has(l.id)} onChange={() => toggle(l.id)} />
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                background: colorById.get(l.id),
                display: "inline-block",
              }}
            />
            {l.name}
          </label>
        ))}
        {err && <span className="error-text">{err}</span>}
      </aside>
      <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
        <MapView enabledLayerIds={enabled} layerColors={colorById} />
      </div>
    </div>
  );
}
