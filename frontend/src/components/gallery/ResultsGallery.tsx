"use client";

import { useEffect, useState, useCallback } from "react";
import { getProjectImages, downloadImages } from "@/lib/api";
import { ImageRecord } from "@/types";
import { AlertCircle, Loader2, Download, CheckCircle } from "lucide-react";
import ImageCard from "./ImageCard";

interface ResultsGalleryProps {
  projectId: string;
}

export default function ResultsGallery({ projectId }: ResultsGalleryProps) {
  const [images, setImages] = useState<ImageRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadDone, setDownloadDone] = useState(false);

  useEffect(() => {
    let mounted = true;
    setIsLoading(true);
    getProjectImages(projectId)
      .then((data) => {
        if (mounted) { setImages(data); setIsLoading(false); }
      })
      .catch((err) => {
        if (mounted) { setError(err.message); setIsLoading(false); }
      });
    return () => { mounted = false; };
  }, [projectId]);

  const handleDownloadAll = useCallback(() => {
    downloadImages(projectId, "keep");
    setDownloadDone(true);
    setTimeout(() => setDownloadDone(false), 2500);
  }, [projectId]);

  /* ── Loading ── */
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-400 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
        <p className="text-sm font-medium">Curating your best photos…</p>
      </div>
    );
  }

  /* ── Error ── */
  if (error) {
    return (
      <div className="max-w-lg mx-auto bg-red-50 p-6 rounded-2xl flex flex-col items-center text-center gap-3">
        <AlertCircle className="w-8 h-8 text-red-500" />
        <p className="font-semibold text-red-900">Could not load results</p>
        <p className="text-red-600 text-sm">{error}</p>
      </div>
    );
  }

  /* ── Compute sets ── */
  const totalAnalyzed = images.filter(i => i.status === "analyzed" || i.recommendation).length;
  const bestPhotos = images.filter(i => i.recommendation === "keep");
  const quotaImages = images.filter(i => i.status === "quota_exhausted");
  const failedImages = images.filter(i => i.status === "failed");
  const maxRetryAfter = quotaImages.reduce<number | null>((max, img) => {
    const v = img.retry_after_s;
    if (v == null) return max;
    if (max == null) return v;
    return Math.max(max, v);
  }, null);
  const retryMinutes = maxRetryAfter != null ? Math.max(1, Math.ceil(maxRetryAfter / 60)) : null;

  /* ── Empty (nothing kept) ── */
  if (bestPhotos.length === 0) {
    // Distinct quota UX — do not collapse into "nothing was analyzed"
    if (quotaImages.length > 0) {
      return (
        <div className="text-center py-24 bg-white rounded-2xl border border-slate-100 shadow-sm px-6">
          <p className="text-2xl font-black text-slate-800 mb-2">Analysis paused</p>
          <p className="text-slate-500">
            Daily AI quota reached.
            {retryMinutes != null
              ? ` Try again in ~${retryMinutes} minute${retryMinutes === 1 ? "" : "s"}.`
              : " Try again later."}
          </p>
        </div>
      );
    }

    if (failedImages.length > 0 && totalAnalyzed === 0) {
      return (
        <div className="text-center py-24 bg-white rounded-2xl border border-slate-100 shadow-sm px-6">
          <p className="text-2xl font-black text-slate-800 mb-2">Analysis failed</p>
          <p className="text-slate-500">
            We couldn&apos;t analyze your photos. Please try again.
          </p>
        </div>
      );
    }

    return (
      <div className="text-center py-24 bg-white rounded-2xl border border-slate-100 shadow-sm px-6">
        <p className="text-2xl font-black text-slate-800 mb-2">No photos met the quality bar</p>
        <p className="text-slate-500">
          {totalAnalyzed > 0
            ? `The AI analyzed ${totalAnalyzed} photo${totalAnalyzed !== 1 ? "s" : ""} but none were sharp / well-exposed enough to recommend.`
            : "No images were analyzed for this project."}
        </p>
      </div>
    );
  }

  /* ── Gallery ── */
  return (
    <div className="w-full space-y-6 sm:space-y-8">

      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Your Best Photos
          </h2>
          <p className="text-slate-500 font-medium mt-1 text-sm sm:text-base">
            {bestPhotos.length} great {bestPhotos.length === 1 ? "photo" : "photos"} selected from {totalAnalyzed} analyzed
          </p>
        </div>

        {/* Download all button */}
        <button
          onClick={handleDownloadAll}
          className="flex items-center gap-2 text-sm font-bold px-5 py-2.5 rounded-full bg-[#FF6B2C] text-white hover:bg-[#e85f22] active:scale-95 transition-all shadow-sm shrink-0 self-start sm:self-auto"
        >
          {downloadDone
            ? <><CheckCircle className="w-4 h-4" /> Downloaded!</>
            : <><Download className="w-4 h-4" /> Download Best Photos</>
          }
        </button>
      </div>

      {/* ── Responsive grid ──
          Mobile:  2 columns (side-by-side, full width)
          Tablet:  3 columns
          Desktop: 4 columns
          No horizontal scroll. Images preserve aspect ratio. */}
      <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4 md:gap-5">
        {bestPhotos.map((img, idx) => (
          <ImageCard
            key={img.image_id ?? idx}
            image={img}
            index={idx}
            projectId={projectId}
          />
        ))}
      </div>

    </div>
  );
}
