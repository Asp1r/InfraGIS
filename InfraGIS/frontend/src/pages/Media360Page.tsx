import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiFetch, apiUpload, apiUrl } from "../api";
import { useAuth } from "../auth/AuthContext";
import type { MediaMapPoint, MediaPlayback, MediaRecord } from "../types";

type GeoDraft = {
  lon: string;
  lat: string;
  heading: string;
  pitch: string;
  layerId: string;
  axisLayerId: string;
  featureId: string;
};

const EMPTY_GEO: GeoDraft = {
  lon: "",
  lat: "",
  heading: "",
  pitch: "",
  layerId: "",
  axisLayerId: "",
  featureId: "",
};

export function Media360Page() {
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const [items, setItems] = useState<MediaRecord[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [savingGeo, setSavingGeo] = useState(false);
  const [playback, setPlayback] = useState<MediaPlayback | null>(null);
  const [geoDraft, setGeoDraft] = useState<GeoDraft>(EMPTY_GEO);
  const [points, setPoints] = useState<MediaMapPoint[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId],
  );

  const loadItems = useCallback(async () => {
    try {
      // Main list endpoint; also rehydrates selection from deep-link.
      const list = await apiFetch<MediaRecord[]>("/media360/items");
      setItems(list);
      const preferredId = Number(searchParams.get("mediaId"));
      if (list.length > 0 && Number.isFinite(preferredId) && list.some((item) => item.id === preferredId)) {
        setSelectedId(preferredId);
      } else if (list.length > 0 && !selectedId) {
        setSelectedId(list[0].id);
      }
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки media360");
    }
  }, [searchParams, selectedId]);

  const loadMapPoints = useCallback(async () => {
    try {
      // Auxiliary list used to show current geolink coverage in this page.
      const rows = await apiFetch<MediaMapPoint[]>("/media360/map-points");
      setPoints(rows);
    } catch {
      /* ignore for now */
    }
  }, []);

  const loadPlayback = useCallback(async (mediaId: number) => {
    try {
      // Backend resolves best ready playback asset for the selected media.
      const p = await apiFetch<MediaPlayback>(`/media360/items/${mediaId}/playback`);
      setPlayback(p);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка получения playback");
      setPlayback(null);
    }
  }, []);

  useEffect(() => {
    void loadItems();
    void loadMapPoints();
  }, [loadItems, loadMapPoints]);

  useEffect(() => {
    if (!selectedId) {
      setPlayback(null);
      return;
    }
    void loadPlayback(selectedId);
  }, [selectedId, loadPlayback]);

  async function onUpload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    setUploading(true);
    try {
      // Upload supports both raw .360 and already-exported videos.
      const created = (await apiUpload("/media360/upload", form)) as MediaRecord;
      setItems((prev) => [created, ...prev]);
      setSelectedId(created.id);
      setFile(null);
      setErr(null);
      void loadMapPoints();
    } catch (uploadErr) {
      setErr(uploadErr instanceof Error ? uploadErr.message : "Ошибка загрузки файла");
    } finally {
      setUploading(false);
    }
  }

  async function saveGeo() {
    if (!selected) return;
    const lon = Number(geoDraft.lon);
    const lat = Number(geoDraft.lat);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      setErr("Нужно указать валидные координаты");
      return;
    }
    setSavingGeo(true);
    try {
      // Create a geospatial anchor so media can be shown on GIS map.
      await apiFetch(`/media360/items/${selected.id}/geolink`, {
        method: "POST",
        body: JSON.stringify({
          lon,
          lat,
          heading: geoDraft.heading.trim() ? Number(geoDraft.heading) : null,
          pitch: geoDraft.pitch.trim() ? Number(geoDraft.pitch) : null,
          layer_id: geoDraft.layerId.trim() ? Number(geoDraft.layerId) : null,
          axis_layer_id: geoDraft.axisLayerId.trim() ? Number(geoDraft.axisLayerId) : null,
          feature_id: geoDraft.featureId.trim() ? geoDraft.featureId : null,
        }),
      });
      setGeoDraft(EMPTY_GEO);
      await loadItems();
      await loadMapPoints();
      setErr(null);
    } catch (geoErr) {
      setErr(geoErr instanceof Error ? geoErr.message : "Ошибка привязки к карте");
    } finally {
      setSavingGeo(false);
    }
  }

  async function simulateReady() {
    if (!selected) return;
    const pendingJob = selected.jobs.find((j) => j.stage !== "ready" && j.stage !== "failed");
    if (!pendingJob) return;
    try {
      // Dev helper endpoint: emulates worker completion for raw uploads.
      await apiFetch(`/media360/internal/jobs/${pendingJob.id}/simulate-ready`, { method: "POST" });
      await loadItems();
      await loadPlayback(selected.id);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка эмуляции обработки");
    }
  }

  return (
    <div className="page media360-grid">
      <section className="card">
        <h2 style={{ marginTop: 0 }}>GoPro Max 360</h2>
        <p style={{ marginTop: 0, color: "var(--muted)" }}>
          Загрузите `.360` или экспортированный `.mp4/.mov`. Для raw-файлов создаётся job обработки.
        </p>
        <form onSubmit={onUpload} style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="file"
            accept=".360,.mp4,.mov,.m4v,.webm,video/*"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <button className="btn btn-primary" type="submit" disabled={!file || uploading}>
            {uploading ? "Загрузка..." : "Загрузить"}
          </button>
        </form>
        {err && <div className="error-text">{err}</div>}

        <hr style={{ borderColor: "var(--border)", margin: "1rem 0" }} />
        <h3 style={{ marginTop: 0 }}>Записи</h3>
        <div style={{ display: "grid", gap: "0.4rem", maxHeight: 280, overflow: "auto" }}>
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              className="btn"
              style={{
                justifyContent: "space-between",
                borderColor: item.id === selectedId ? "var(--accent)" : "var(--border)",
              }}
              onClick={() => setSelectedId(item.id)}
            >
              <span>{item.original_filename}</span>
              <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>{item.source_type}</span>
            </button>
          ))}
          {items.length === 0 && <span style={{ color: "var(--muted)" }}>Пока нет загрузок</span>}
        </div>
      </section>

      <section className="card">
        <h3 style={{ marginTop: 0 }}>Просмотр</h3>
        {!selected && <p style={{ color: "var(--muted)" }}>Выберите файл слева.</p>}
        {selected && (
          <>
            <div style={{ marginBottom: "0.75rem" }}>
              <div><strong>ID:</strong> {selected.id}</div>
              <div><strong>Файл:</strong> {selected.original_filename}</div>
              <div><strong>Тип:</strong> {selected.source_type}</div>
            </div>
            {playback?.stream_url ? (
              <video controls style={{ width: "100%", borderRadius: 8 }} src={apiUrl(playback.stream_url)} />
            ) : (
              <div style={{ color: "var(--muted)", marginBottom: "0.5rem" }}>
                Playback пока недоступен: файл ожидает обработку.
              </div>
            )}
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
              {playback && (
                <a className="btn" href={apiUrl(playback.download_url)}>
                  Скачать исходник
                </a>
              )}
              {selected.source_type === "raw360" && user?.role === "admin" && (
                <button type="button" className="btn" onClick={simulateReady}>
                  Симулировать готовность
                </button>
              )}
            </div>
          </>
        )}
      </section>

      <section className="card">
        <h3 style={{ marginTop: 0 }}>Геопривязка</h3>
        {selected ? (
          <>
            <div style={{ display: "grid", gap: "0.5rem", gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
              <input placeholder="lon" value={geoDraft.lon} onChange={(e) => setGeoDraft((p) => ({ ...p, lon: e.target.value }))} />
              <input placeholder="lat" value={geoDraft.lat} onChange={(e) => setGeoDraft((p) => ({ ...p, lat: e.target.value }))} />
              <input placeholder="heading" value={geoDraft.heading} onChange={(e) => setGeoDraft((p) => ({ ...p, heading: e.target.value }))} />
              <input placeholder="pitch" value={geoDraft.pitch} onChange={(e) => setGeoDraft((p) => ({ ...p, pitch: e.target.value }))} />
              <input placeholder="layer id (optional)" value={geoDraft.layerId} onChange={(e) => setGeoDraft((p) => ({ ...p, layerId: e.target.value }))} />
              <input
                placeholder="axis layer id (optional)"
                value={geoDraft.axisLayerId}
                onChange={(e) => setGeoDraft((p) => ({ ...p, axisLayerId: e.target.value }))}
              />
              <input placeholder="feature id (optional)" value={geoDraft.featureId} onChange={(e) => setGeoDraft((p) => ({ ...p, featureId: e.target.value }))} />
            </div>
            <button
              type="button"
              className="btn btn-primary"
              style={{ marginTop: "0.75rem" }}
              onClick={saveGeo}
              disabled={savingGeo}
            >
              {savingGeo ? "Сохраняю..." : "Привязать к точке"}
            </button>
          </>
        ) : (
          <p style={{ color: "var(--muted)" }}>Сначала выберите файл для привязки.</p>
        )}
        <hr style={{ borderColor: "var(--border)", margin: "1rem 0" }} />
        <h4 style={{ marginTop: 0 }}>Точки 360 на карте</h4>
        <div style={{ maxHeight: 200, overflow: "auto", display: "grid", gap: "0.4rem" }}>
          {points.map((p) => (
            <div key={p.link_id} style={{ fontSize: "0.88rem", color: "var(--muted)" }}>
              #{p.media_id}: {p.lon.toFixed(5)}, {p.lat.toFixed(5)} ({p.original_filename})
              {p.axis_km !== null ? ` • км ${p.axis_km.toFixed(3)}` : ""}
            </div>
          ))}
          {points.length === 0 && <span style={{ color: "var(--muted)" }}>Точек пока нет</span>}
        </div>
      </section>
    </div>
  );
}
