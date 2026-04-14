import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { AdminLayersPage } from "./pages/AdminLayersPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { LoginPage } from "./pages/LoginPage";
import { MapPage } from "./pages/MapPage";
import { AppLayout } from "./layout/AppLayout";

function Protected({ children }: { children: ReactNode }) {
  const { user, loading, token } = useAuth();
  if (loading && token) return <div className="page">Загрузка…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AdminOnly({ children }: { children: ReactNode }) {
  const { user, loading, token } = useAuth();
  if (loading && token) return <div className="page">Загрузка…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <Protected>
            <AppLayout />
          </Protected>
        }
      >
        <Route index element={<MapPage />} />
        <Route
          path="admin/users"
          element={
            <AdminOnly>
              <AdminUsersPage />
            </AdminOnly>
          }
        />
        <Route
          path="admin/layers"
          element={
            <AdminOnly>
              <AdminLayersPage />
            </AdminOnly>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
