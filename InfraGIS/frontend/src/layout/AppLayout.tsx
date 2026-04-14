import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function AppLayout() {
  const { user, logout } = useAuth();
  return (
    <>
      <header className="layout-nav">
        <h1>InfraGIS</h1>
        <nav style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <NavLink to="/">Карта</NavLink>
          {user?.role === "admin" && (
            <>
              <NavLink to="/admin/users">Пользователи</NavLink>
              <NavLink to="/admin/layers">Слои</NavLink>
            </>
          )}
        </nav>
        <div className="spacer" />
        <span style={{ color: "var(--muted)", fontSize: "0.875rem" }}>{user?.login}</span>
        <button type="button" className="btn btn-ghost" onClick={logout}>
          Выйти
        </button>
      </header>
      <Outlet />
    </>
  );
}
