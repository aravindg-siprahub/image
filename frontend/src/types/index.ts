export interface Project {
  id: string;
  name: string | null;
  status: string;
  created_at: string;
}

export interface ImageRecord {
  image_id: string;
  project_id: string;
  file_url: string;
  status: 'uploaded' | 'analyzing' | 'analyzed' | 'selected' | 'failed';
  final_score: number | null;
  recommendation: 'keep' | 'remove' | 'replace' | null;
  reason: string | null;
  sharpness_score: number | null;
  lighting_score: number | null;
  composition_score: number | null;
  face_score: number | null;
}

export interface AnalysisStatus {
  status: 'processing' | 'completed' | 'failed' | string;
  total: number;
  processed: number;
  failed: number;
  selected: number;
}


