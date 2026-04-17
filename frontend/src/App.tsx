import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { AdminLayersPage } from "./pages/AdminLayersPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { LoginPage } from "./pages/LoginPage";
import { MapPage } from "./pages/MapPage";
import { Media360Page } from "./pages/Media360Page";
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
          // App shell is available only for authenticated users.
          <Protected>
            <AppLayout />
          </Protected>
        }
      >
        <Route index element={<MapPage />} />
        {/* media360 module is integrated into shell as dedicated route */}
        <Route path="media360" element={<Media360Page />} />
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
