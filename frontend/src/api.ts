const base = import.meta.env.VITE_API_URL ?? "";

function authHeader(): HeadersInit {
  const t = localStorage.getItem("infragis_token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function apiUpload(path: string, form: FormData): Promise<unknown> {
  const t = localStorage.getItem("infragis_token");
  const headers: HeadersInit = {};
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${base}${path}`, { method: "POST", headers, body: form });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export function apiUrl(path: string): string {
  return `${base}${path}`;
}

export async function createRoad(name: string, description?: string): Promise<unknown> {
  return apiFetch("/layers/roads", {
    method: "POST",
    body: JSON.stringify({ name, description: description || null }),
  });
}
