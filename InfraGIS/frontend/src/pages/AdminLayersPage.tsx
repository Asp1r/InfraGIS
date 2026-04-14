import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiFetch, apiUpload } from "../api";
import type { Layer } from "../types";

export function AdminLayersPage() {
  const [layers, setLayers] = useState<Layer[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    const list = await apiFetch<Layer[]>("/layers");
    setLayers(list);
  }, []);

  useEffect(() => {
    void load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!file && !sourceUrl.trim()) {
      setError("Укажите файл GeoJSON или URL");
      return;
    }
    setPending(true);
    try {
      const form = new FormData();
      form.append("name", name);
      if (description) form.append("description", description);
      if (file) form.append("file", file);
      if (sourceUrl.trim()) form.append("source_url", sourceUrl.trim());
      await apiUpload("/layers", form);
      setName("");
      setDescription("");
      setSourceUrl("");
      setFile(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setPending(false);
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
      <h2 style={{ marginTop: 0 }}>Слои данных</h2>
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Добавить слой (GeoJSON)</h3>
        <p style={{ color: "var(--muted)", fontSize: "0.875rem", marginTop: 0 }}>
          Загрузите файл <code>.geojson</code> или укажите прямой URL на GeoJSON. Если указаны оба, используется файл.
        </p>
        <form onSubmit={onCreate}>
          <div className="field">
            <label htmlFor="l-name">Название</label>
            <input id="l-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="l-desc">Описание</label>
            <textarea id="l-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="l-file">Файл</label>
            <input
              id="l-file"
              type="file"
              accept=".geojson,.json,application/geo+json,application/json"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="field">
            <label htmlFor="l-url">URL GeoJSON</label>
            <input
              id="l-url"
              type="url"
              placeholder="https://example.com/data.geojson"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
            />
          </div>
          {error && <p className="error-text">{error}</p>}
          <button type="submit" className="btn btn-primary" disabled={pending}>
            {pending ? "Загрузка…" : "Добавить"}
          </button>
        </form>
      </div>
      <table className="data">
        <thead>
          <tr>
            <th>ID</th>
            <th>Название</th>
            <th>Тип</th>
            <th>Создан</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {layers.map((l) => (
            <tr key={l.id}>
              <td>{l.id}</td>
              <td>{l.name}</td>
              <td>{l.source_type}</td>
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
