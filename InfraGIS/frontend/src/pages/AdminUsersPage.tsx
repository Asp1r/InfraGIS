import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api";
import type { User, UserRole } from "../types";

export function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    const list = await apiFetch<User[]>("/admin/users");
    setUsers(list);
  }, []);

  useEffect(() => {
    void load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await apiFetch<User>("/admin/users", {
        method: "POST",
        body: JSON.stringify({ login, password, role }),
      });
      setLogin("");
      setPassword("");
      setRole("viewer");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="page">
      <h2 style={{ marginTop: 0 }}>Пользователи</h2>
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Создать пользователя</h3>
        <form onSubmit={onCreate}>
          <div className="field">
            <label htmlFor="nu-login">Логин</label>
            <input id="nu-login" value={login} onChange={(e) => setLogin(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="nu-pass">Пароль (мин. 8 символов)</label>
            <input
              id="nu-pass"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="nu-role">Роль</label>
            <select id="nu-role" value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
              <option value="viewer">Наблюдатель</option>
              <option value="admin">Администратор</option>
            </select>
          </div>
          {error && <p className="error-text">{error}</p>}
          <button type="submit" className="btn btn-primary" disabled={pending}>
            {pending ? "Создание…" : "Создать"}
          </button>
        </form>
      </div>
      <table className="data">
        <thead>
          <tr>
            <th>ID</th>
            <th>Логин</th>
            <th>Роль</th>
            <th>Активен</th>
            <th>Создан</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.id}</td>
              <td>{u.login}</td>
              <td>{u.role}</td>
              <td>{u.is_active ? "да" : "нет"}</td>
              <td>{new Date(u.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
