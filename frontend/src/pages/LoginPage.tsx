import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const base = import.meta.env.VITE_API_URL ?? "";

export function LoginPage() {
  const { user, setToken } = useAuth();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const res = await fetch(`${base}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        setError(typeof j.detail === "string" ? j.detail : "Ошибка входа");
        return;
      }
      const data = (await res.json()) as { access_token: string };
      setToken(data.access_token);
    } catch {
      setError("Сеть недоступна");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 400, marginTop: "4rem" }}>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Вход</h2>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="login">Логин</label>
            <input
              id="login"
              autoComplete="username"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Пароль</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="error-text">{error}</p>}
          <button type="submit" className="btn btn-primary" disabled={pending}>
            {pending ? "Вход…" : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}
