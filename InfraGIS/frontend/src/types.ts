export type UserRole = "admin" | "viewer";

export interface User {
  id: number;
  login: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export type LayerSourceType = "uploaded_geojson" | "url_geojson";

export interface Layer {
  id: number;
  name: string;
  description: string | null;
  source_type: LayerSourceType;
  created_at: string;
}
