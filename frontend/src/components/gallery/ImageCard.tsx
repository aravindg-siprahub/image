"use client";

import { ImageRecord } from "@/types";
import { Download, Share2 } from "lucide-react";

interface ImageCardProps {
  image: ImageRecord;
  index: number;
  projectId: string;
}

async function shareImage(image: ImageRecord, projectId: string) {
  const title = `Photo #${image.image_id?.slice(0, 6)} — LensAI`;
  const text = `Check out this AI-selected photo from my LensAI collection!`;
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
    alert("Link copied to clipboard!");
  } catch {
    prompt("Copy this link:", url);
  }
}

function downloadSingleImage(image: ImageRecord) {
  if (!image.file_url) return;
  const a = document.createElement("a");
  a.href = image.file_url;
  a.download = `lensai_photo_${image.image_id?.slice(0, 8) ?? "image"}.jpg`;
  a.target = "_blank"; // signed URL must open in same origin
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export default function ImageCard({ image, index, projectId }: ImageCardProps) {
  const score = Math.round(image.final_score || 0);
  const scoreColor =
    score >= 80 ? "text-emerald-600" :
    score >= 65 ? "text-green-600" :
    score >= 50 ? "text-orange-500" : "text-red-500";

  const scoreBg =
    score >= 80 ? "bg-emerald-50 border-emerald-200" :
    score >= 65 ? "bg-green-50 border-green-200" :
    "bg-orange-50 border-orange-200";

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

      {/* Action row */}
      <div className="flex items-center gap-2 p-3 border-t border-slate-100">
        <button
          onClick={() => downloadSingleImage(image)}
          className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold py-2 rounded-lg bg-slate-900 text-white hover:bg-slate-700 active:scale-95 transition-all"
          title="Download this photo"
        >
          <Download className="w-3.5 h-3.5" />
          Download
        </button>
        <button
          onClick={() => shareImage(image, projectId)}
          className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold py-2 rounded-lg bg-white text-slate-700 border border-slate-200 hover:border-slate-300 active:scale-95 transition-all"
          title="Share this photo"
        >
          <Share2 className="w-3.5 h-3.5" />
          Share
        </button>
      </div>
    </div>
  );
}
