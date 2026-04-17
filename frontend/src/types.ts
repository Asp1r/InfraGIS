export type UserRole = "admin" | "viewer";

// Authenticated user profile shared by auth context and protected routes.
export interface User {
  id: number;
  login: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export type LayerSourceType = "uploaded_geojson" | "url_geojson";
export type LayerKind = "road" | "road_axis" | "iri" | "defects";

// Base GIS layer payload used across map/admin screens.
export interface Layer {
  id: number;
  name: string;
  description: string | null;
  source_type: LayerSourceType;
  kind: LayerKind;
  parent_id: number | null;
  axis_layer_id: number | null;
  created_at: string;
}

export interface LayerTreeNode extends Layer {
  // Recursive children for hierarchical road model tree.
  children: LayerTreeNode[];
}

export interface AxisChainagePoint {
  // Chainage calibration point generated from uploaded axis geometry.
  index: number;
  lon: number;
  lat: number;
  km: number;
}

export interface AxisUploadResult extends Layer {
  total_km: number;
  points: AxisChainagePoint[];
}

export interface IriMeasurement {
  id: number;
  layer_id: number;
  axis_layer_id: number;
  direction: string | null;
  lane: string | null;
  km_start: number;
  km_end: number;
  iri_value: number;
  created_at: string;
}

export interface DefectRecord {
  id: number;
  layer_id: number;
  axis_layer_id: number;
  defect_code: string;
  severity: string | null;
  norm_ref: string | null;
  km_start: number;
  km_end: number;
  extent_m: number | null;
  area_m2: number | null;
  created_at: string;
}

export type MediaSourceType = "raw360" | "exported";
export type MediaAssetStatus = "pending" | "ready" | "failed";
export type ProcessingJobStage = "queued" | "processing" | "ready" | "failed";

// Media derivative/source asset descriptor from backend.
export interface MediaAsset {
  id: number;
  kind: "master_equirect" | "hls" | "thumbnail" | "preview";
  storage_key: string;
  codec: string | null;
  bitrate: number | null;
  status: MediaAssetStatus;
  created_at: string;
}

// Background processing status for media conversion jobs.
export interface ProcessingJob {
  id: number;
  media_id: number;
  stage: ProcessingJobStage;
  progress: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

// Geospatial anchor linking media to map coordinates/layer context.
export interface MediaGeoLink {
  id: number;
  media_id: number;
  layer_id: number | null;
  axis_layer_id: number | null;
  feature_id: string | null;
  lon: number;
  lat: number;
  axis_km: number | null;
  heading: number | null;
  pitch: number | null;
  captured_at: string | null;
  created_at: string;
}

// Main media entity including nested assets/jobs/geolinks.
export interface MediaRecord {
  id: number;
  owner_id: number;
  source_type: MediaSourceType;
  original_filename: string;
  storage_key: string;
  duration: number | null;
  resolution: string | null;
  created_at: string;
  assets: MediaAsset[];
  geo_links: MediaGeoLink[];
  jobs: ProcessingJob[];
}

// Playback endpoint response consumed by <video> player.
export interface MediaPlayback {
  media_id: number;
  source_type: MediaSourceType;
  stream_url: string | null;
  download_url: string;
  poster_url: string | null;
  status: MediaAssetStatus;
}

// Compact point response used for map overlay markers.
export interface MediaMapPoint {
  link_id: number;
  media_id: number;
  layer_id: number | null;
  axis_layer_id: number | null;
  feature_id: string | null;
  lon: number;
  lat: number;
  axis_km: number | null;
  heading: number | null;
  pitch: number | null;
  captured_at: string | null;
  source_type: MediaSourceType;
  original_filename: string;
}
