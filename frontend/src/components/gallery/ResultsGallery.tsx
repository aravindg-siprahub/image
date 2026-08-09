"use client";

import { useEffect, useState, useCallback } from "react";
import { getProjectImages, downloadImages, getShareUrl } from "@/lib/api";
import { ImageRecord } from "@/types";
import { AlertCircle, Loader2, Download, Share2, Copy, CheckCircle } from "lucide-react";
import ImageCard from "./ImageCard";

interface ResultsGalleryProps {
  projectId: string;
}

export default function ResultsGallery({ projectId }: ResultsGalleryProps) {
  const [images, setImages] = useState<ImageRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    let mounted = true;
    setIsLoading(true);
    getProjectImages(projectId)
      .then((data) => { if (mounted) { setImages(data); setIsLoading(false); } })
      .catch((err) => { if (mounted) { setError(err.message); setIsLoading(false); } });
    return () => { mounted = false; };
  }, [projectId]);

  const handleDownload = useCallback(() => {
    setIsDownloading(true);
    try {
      downloadImages(projectId, "keep");
    } finally {
      setTimeout(() => setIsDownloading(false), 2000);
    }
  }, [projectId]);

  const handleCopyLink = useCallback(async () => {
    const url = getShareUrl(projectId);
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const ta = document.createElement("textarea");
      ta.value = url;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [projectId]);

  const handleWhatsApp = useCallback(() => {
    const url = getShareUrl(projectId);
    const text = encodeURIComponent(`Check out my AI-curated photo selection: ${url}`);
    window.open(`https://wa.me/?text=${text}`, "_blank");
  }, [projectId]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-400 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
        <p className="text-sm font-medium">Curating your best photos...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-lg mx-auto bg-red-50 p-6 rounded-2xl flex flex-col items-center text-center gap-3">
        <AlertCircle className="w-8 h-8 text-red-500" />
        <p className="font-semibold text-red-900">Could not load results</p>
        <p className="text-red-600 text-sm">{error}</p>
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="text-center py-20 text-slate-500 bg-white rounded-2xl border border-slate-100">
        No images found for this project.
      </div>
    );
  }

  // Only show the photos the AI selected as "keep"
  const bestPhotos = images.filter(i => i.recommendation === "keep");
  const totalAnalyzed = images.filter(i => i.status !== "failed").length;

  if (bestPhotos.length === 0) {
    return (
      <div className="text-center py-20 text-slate-500 bg-white rounded-2xl border border-slate-100 shadow-sm">
        <h3 className="text-lg font-bold text-slate-800 mb-2">No photos met the quality threshold</h3>
        <p>The AI analyzed {totalAnalyzed} photos but none were selected as strong keepers.</p>
      </div>
    );
  }

  return (
    <div className="w-full space-y-8">
      
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-slate-200 pb-6">
        <div>
          <h2 className="text-3xl font-black text-slate-900 tracking-tight">Your Best Photos</h2>
          <p className="text-slate-500 font-medium mt-1">
            {bestPhotos.length} best {bestPhotos.length === 1 ? 'photo' : 'photos'} from {totalAnalyzed} analyzed
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className="flex items-center gap-2 text-sm font-bold px-5 py-2.5 rounded-full bg-[#FF6B2C] text-white hover:bg-[#e85f22] disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            <Download className="w-4 h-4" />
            {isDownloading ? "Preparing..." : "Download Best Photos"}
          </button>

          <button
            onClick={handleCopyLink}
            className="flex items-center gap-2 text-sm font-bold px-5 py-2.5 rounded-full bg-white text-slate-700 border border-slate-200 hover:border-slate-300 transition-all shadow-sm"
          >
            {copied ? <CheckCircle className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
            {copied ? "Copied!" : "Copy Link"}
          </button>

          <button
            onClick={handleWhatsApp}
            className="flex items-center gap-2 text-sm font-bold px-5 py-2.5 rounded-full bg-[#25D366] text-white hover:bg-[#1ebe5c] transition-all shadow-sm"
          >
            <Share2 className="w-4 h-4" />
            Share Best Photos
          </button>
        </div>
      </div>

      {/* Image Grid */}
      <div className="columns-1 sm:columns-2 lg:columns-3 xl:columns-4 gap-6 space-y-6">
        {bestPhotos.map((img, idx) => (
          <ImageCard
            key={img.image_id || idx}
            image={img}
            index={idx}
          />
        ))}
      </div>
      
    </div>
  );
}
