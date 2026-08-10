"use client";

import { ImageRecord } from "@/types";
import { Download, Share2, Loader2 } from "lucide-react";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

interface ImageCardProps {
  image: ImageRecord;
  index: number;
  projectId: string;
}

async function shareImage(image: ImageRecord, projectId: string) {
  const title = `Photo from my LensAI collection`;
  const text = `Check out this photo selected by LensAI!`;
  const url = `${window.location.origin}/gallery/${projectId}`;

  if (navigator.share) {
    try {
      await navigator.share({ title, text, url });
      return;
    } catch {
      // User cancelled or share failed → fall through to copy
    }
  }

  // Fallback: copy link to clipboard
  try {
    await navigator.clipboard.writeText(url);
    alert("Gallery link copied to clipboard!");
  } catch {
    prompt("Copy this link:", url);
  }
}

/**
 * Downloads a single image via the backend proxy endpoint.
 * 
 * Why proxy instead of direct Supabase URL?
 * - Supabase signed URLs are cross-origin → browser blocks the `download` attribute.
 * - The backend /proxy endpoint streams the image bytes from the same origin as the API,
 *   so the browser respects the Content-Disposition: attachment header and saves the file.
 */
async function downloadSingleImage(
  image: ImageRecord,
  setDownloading: (v: boolean) => void,
  setError: (v: string | null) => void,
) {
  setDownloading(true);
  setError(null);
  try {
    const url = `${API_BASE}/images/proxy/${image.image_id}.jpg`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Download failed: ${res.statusText}`);
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = `lensai_photo_${image.image_id?.slice(0, 8) ?? "image"}.jpg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(objectUrl), 5000);
  } catch (err: any) {
    setError("Download failed. Please try again.");
    setTimeout(() => setError(null), 4000);
  } finally {
    setDownloading(false);
  }
}

export default function ImageCard({ image, index, projectId }: ImageCardProps) {
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);

  return (
    <div className="group relative rounded-2xl overflow-hidden bg-white shadow-sm hover:shadow-md transition-shadow">

      {/* Image */}
      <div className="relative w-full overflow-hidden bg-slate-100">
        <img
          src={image.file_url!}
          alt={`Photo ${index + 1}`}
          className="w-full h-auto object-contain block"
          loading="lazy"
          decoding="async"
        />

        {/* Rank badge — top-left */}
        <div className="absolute top-2.5 left-2.5 bg-white/95 backdrop-blur-sm text-slate-800 text-xs font-black px-2.5 py-1 rounded-lg shadow-sm">
          #{index + 1}
        </div>
      </div>

      {/* Error banner */}
      {downloadError && (
        <div className="px-3 py-1.5 bg-red-50 border-t border-red-100">
          <p className="text-xs text-red-600 text-center font-medium">{downloadError}</p>
        </div>
      )}

      {/* Action row */}
      <div className="flex items-center gap-2 p-3 border-t border-slate-100">
        <button
          onClick={() => downloadSingleImage(image, setDownloading, setDownloadError)}
          disabled={downloading}
          className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold py-2 rounded-lg bg-slate-900 text-white hover:bg-slate-700 active:scale-95 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          title="Download this photo"
        >
          {downloading
            ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Downloading…</>
            : <><Download className="w-3.5 h-3.5" /> Download</>
          }
        </button>
        <button
          onClick={async () => {
            setSharing(true);
            await shareImage(image, projectId);
            setSharing(false);
          }}
          disabled={sharing}
          className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold py-2 rounded-lg bg-white text-slate-700 border border-slate-200 hover:border-slate-300 active:scale-95 transition-all disabled:opacity-60"
          title="Share this photo"
        >
          <Share2 className="w-3.5 h-3.5" />
          Share
        </button>
      </div>
    </div>
  );
}
