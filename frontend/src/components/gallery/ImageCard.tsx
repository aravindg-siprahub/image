"use client";

import { ImageRecord } from "@/types";
import { Maximize2 } from "lucide-react";

interface ImageCardProps {
  image: ImageRecord;
  index: number;
}

export default function ImageCard({ image, index }: ImageCardProps) {
  const scoreColor = (image.final_score || 0) >= 70 ? "text-green-600" : 
                    (image.final_score || 0) >= 50 ? "text-orange-500" : "text-red-500";

  return (
    <div className="group relative rounded-2xl overflow-hidden bg-white shadow-sm hover:shadow-md transition-shadow break-inside-avoid mb-6">
      
      {/* Rank Badge - Top Left */}
      <div className="absolute top-3 left-3 z-10">
        <div className="flex items-center gap-1.5 bg-white/95 backdrop-blur shadow-sm px-3 py-1.5 rounded-lg text-sm font-black uppercase tracking-wider text-slate-700">
          #{index + 1}
        </div>
      </div>
      
      {/* Action buttons - Top Right */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <button className="w-8 h-8 rounded-full bg-white/90 hover:bg-white text-slate-700 flex items-center justify-center shadow-sm backdrop-blur transition-colors">
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      {/* Main Image */}
      <div className="relative w-full overflow-hidden bg-slate-50">
        <img 
          src={image.file_url} 
          alt={`Result ${index + 1}`} 
          className="w-full h-auto object-contain block"
          loading="lazy"
        />
      </div>

      {/* Quality Score Panel */}
      <div className="p-4 flex items-center justify-between bg-white">
        <p className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Quality Score</p>
        <div className="flex items-baseline gap-1">
          <span className={`text-2xl font-black tracking-tight leading-none ${scoreColor}`}>
            {Math.round(image.final_score || 0)}
          </span>
          <span className="text-xs font-bold text-slate-300">/ 100</span>
        </div>
      </div>
    </div>
  );
}
