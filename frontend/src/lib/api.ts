// NEXT_PUBLIC_API_BASE_URL must be set in Railway to the deployed backend URL.
// e.g. https://lensai-backend.up.railway.app/api/v1
// Falls back to localhost for local development.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export async function createProject(): Promise<{ id: string }> {
  try {
    const res = await fetch(`${API_BASE}/projects/`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to create project");
    return res.json();
  } catch (error: any) {
    if (error.name === "TypeError" && error.message === "Failed to fetch") {
      throw new Error("Unable to connect to the server. Please try again.");
    }
    throw error;
  }
}

export async function uploadImage(projectId: string, file: File): Promise<any> {
  const formData = new FormData();
  formData.append("project_id", projectId);
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/images/upload`, { method: "POST", body: formData });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Upload failed: ${errorText}`);
  }
  return res.json();
}

export async function startAnalysis(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/analyze`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to start analysis");
  return res.json();
}

export async function getAnalysisStatus(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/analysis-status`);
  if (!res.ok) throw new Error("Failed to get analysis status");
  return res.json();
}

export async function getProjectImages(projectId: string): Promise<any[]> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/images`);
  if (!res.ok) throw new Error("Failed to fetch project images");
  return res.json();
}

/**
 * Triggers a browser download of a ZIP file from the backend.
 * filter: "all" | "keep"
 */
export function downloadImages(projectId: string, filter: "all" | "keep" = "all") {
  const url = `${API_BASE}/projects/${projectId}/download?filter=${filter}`;
  const a = document.createElement("a");
  a.href = url;
  a.download = `lensai_${filter}.zip`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/**
 * Generates a shareable URL for the gallery.
 * Uses a simple hash-based URL with the project ID.
 */
export function getShareUrl(projectId: string): string {
  if (typeof window === "undefined") return "";
  return `${window.location.origin}/gallery/${projectId}`;
}
