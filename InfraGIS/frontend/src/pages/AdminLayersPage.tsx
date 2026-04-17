import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch, apiUpload } from "../api";
import type { AxisUploadResult, Layer, LayerTreeNode } from "../types";

export function AdminLayersPage() {
  const [layersTree, setLayersTree] = useState<LayerTreeNode[]>([]);
  const [roadName, setRoadName] = useState("");
  const [roadDescription, setRoadDescription] = useState("");
  const [selectedRoadId, setSelectedRoadId] = useState<number | null>(null);
  const [axisName, setAxisName] = useState("Ось дороги");
  const [axisDescription, setAxisDescription] = useState("");
  const [axisSourceUrl, setAxisSourceUrl] = useState("");
  const [axisFile, setAxisFile] = useState<File | null>(null);
  const [axisInfo, setAxisInfo] = useState<AxisUploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    const list = await apiFetch<LayerTreeNode[]>("/layers/tree");
    setLayersTree(list);
  }, []);

  const roads = useMemo(() => layersTree.filter((n) => n.kind === "road"), [layersTree]);

  useEffect(() => {
    void load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [load]);

  useEffect(() => {
    if (!selectedRoadId && roads.length > 0) {
      setSelectedRoadId(roads[0].id);
    }
  }, [roads, selectedRoadId]);

  async function onCreateRoad(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await apiFetch<Layer>("/layers/roads", {
        method: "POST",
        body: JSON.stringify({ name: roadName, description: roadDescription || null }),
      });
      setRoadName("");
      setRoadDescription("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setPending(false);
    }
  }

  async function onUploadAxis(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setAxisInfo(null);
    if (!selectedRoadId) {
      setError("Выберите дорогу");
      return;
    }
    if (!axisFile && !axisSourceUrl.trim()) {
      setError("Загрузите файл оси или укажите URL GeoJSON");
      return;
    }
    setPending(true);
    try {
      const form = new FormData();
      form.append("name", axisName);
      if (axisDescription) form.append("description", axisDescription);
      if (axisFile) form.append("file", axisFile);
      if (axisSourceUrl.trim()) form.append("source_url", axisSourceUrl.trim());
      const res = (await apiUpload(`/layers/${selectedRoadId}/axis`, form)) as AxisUploadResult;
      setAxisInfo(res);
      setAxisDescription("");
      setAxisSourceUrl("");
      setAxisFile(null);
      await ensureDiagnosticsChildren(selectedRoadId, res.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setPending(false);
    }
  }

  async function ensureDiagnosticsChildren(roadId: number, axisLayerId: number) {
    const all = await apiFetch<Layer[]>("/layers");
    const hasIri = all.some((l) => l.parent_id === roadId && l.kind === "iri");
    const hasDefects = all.some((l) => l.parent_id === roadId && l.kind === "defects");
    if (!hasIri) {
      const form = new FormData();
      form.append("name", "IRI");
      form.append("description", "Продольная ровность");
      form.append("kind", "iri");
      form.append("parent_id", String(roadId));
      form.append("axis_layer_id", String(axisLayerId));
      await apiUpload("/layers", form);
    }
    if (!hasDefects) {
      const form = new FormData();
      form.append("name", "Дефекты");
      form.append("description", "Дефекты ОДМ/ГОСТ");
      form.append("kind", "defects");
      form.append("parent_id", String(roadId));
      form.append("axis_layer_id", String(axisLayerId));
      await apiUpload("/layers", form);
    }
  }

  async function removeLayer(id: number) {
    if (!confirm("Удалить слой?")) return;
    setError(null);
    try {
      await apiFetch(`/layers/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  return (
    <div className="page">
      <h2 style={{ marginTop: 0 }}>Дерево дорожных слоев</h2>
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Создать дорогу</h3>
        <form onSubmit={onCreateRoad}>
          <div className="field">
            <label htmlFor="road-name">Название дороги</label>
            <input id="road-name" value={roadName} onChange={(e) => setRoadName(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="road-desc">Описание</label>
            <textarea
              id="road-desc"
              rows={2}
              value={roadDescription}
              onChange={(e) => setRoadDescription(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={pending}>
            {pending ? "Сохранение…" : "Создать дорогу"}
          </button>
        </form>
      </div>

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Загрузка оси дороги</h3>
        <p style={{ color: "var(--muted)", fontSize: "0.875rem", marginTop: 0 }}>
          Поддерживаются <code>.geojson</code>, <code>.csv</code> и ZIP Shapefile.
        </p>
        <form onSubmit={onUploadAxis}>
          <div className="field">
            <label htmlFor="road-select">Дорога</label>
            <select
              id="road-select"
              value={selectedRoadId ?? ""}
              onChange={(e) => setSelectedRoadId(Number(e.target.value))}
              required
            >
              {roads.length === 0 && <option value="">Нет дорог</option>}
              {roads.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} (ID {r.id})
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="a-name">Название слоя оси</label>
            <input id="a-name" value={axisName} onChange={(e) => setAxisName(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="a-desc">Описание</label>
            <textarea id="a-desc" rows={2} value={axisDescription} onChange={(e) => setAxisDescription(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="a-file">Файл оси</label>
            <input
              id="a-file"
              type="file"
              accept=".geojson,.json,.csv,.zip,application/geo+json,application/json,text/csv,application/zip"
              onChange={(e) => setAxisFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="field">
            <label htmlFor="a-url">URL GeoJSON</label>
            <input
              id="a-url"
              type="url"
              placeholder="https://example.com/axis.geojson"
              value={axisSourceUrl}
              onChange={(e) => setAxisSourceUrl(e.target.value)}
            />
          </div>
          {axisInfo && (
            <p style={{ marginTop: 0 }}>
              Ось загружена: {axisInfo.name}, протяженность {axisInfo.total_km.toFixed(3)} км, точек {axisInfo.points.length}
            </p>
          )}
          {error && <p className="error-text">{error}</p>}
          <button type="submit" className="btn btn-primary" disabled={pending}>
            {pending ? "Загрузка…" : "Загрузить ось"}
          </button>
        </form>
      </div>
      <table className="data">
        <thead>
          <tr>
            <th>ID</th>
            <th>Название</th>
            <th>Вид</th>
            <th>Родитель</th>
            <th>Создан</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {layersTree.flatMap((root) => [root, ...root.children]).map((l) => (
            <tr key={l.id}>
              <td>{l.id}</td>
              <td>{l.name}</td>
              <td>{l.kind}</td>
              <td>{l.parent_id ?? "-"}</td>
              <td>{new Date(l.created_at).toLocaleString()}</td>
              <td>
                <button type="button" className="btn btn-ghost" onClick={() => removeLayer(l.id)}>
                  Удалить
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
