"use client";

import { Shield } from "lucide-react";
import UploadZone from "../upload/UploadZone";

interface HeroProps {
  onUploadsStarted: (projectId: string) => void;
  onUploadsCompleted: () => void;
  projectId: string | null;
  triggerUploadRef?: React.MutableRefObject<(() => void) | undefined>;
}

export default function Hero({ onUploadsStarted, onUploadsCompleted, projectId, triggerUploadRef }: HeroProps) {
  return (
    <section className="w-full max-w-6xl mx-auto px-6 pt-14 pb-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-14 items-start">

        {/* Left – Headline + trust */}
        <div className="flex flex-col gap-6 pt-3">

          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-orange-50 border border-orange-100 text-orange-600 px-3.5 py-1.5 rounded-full text-xs font-semibold uppercase tracking-widest w-fit">
            <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" />
            AI Photo Selection
          </div>

          {/* Headline */}
          <div>
            <h1 className="text-[2.25rem] md:text-[3.5rem] font-black leading-[1.08] tracking-tight text-slate-900">
              Find your{" "}
              <span className="text-[#FF6B2C]">best photos.</span>
            </h1>
            <h1 className="text-[2.25rem] md:text-[3.5rem] font-black leading-[1.08] tracking-tight text-slate-900 mt-1">
              Let AI choose.
            </h1>
          </div>

          {/* Subtext */}
          <p className="text-base text-slate-500 leading-relaxed max-w-[420px]">
            Upload your photos. AI analyzes quality, clarity, composition and similarity to find the images worth keeping.
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-2 mt-1">
            {[
              { label: "Upload many photos", color: "bg-orange-50 text-orange-600 border-orange-100" },
              { label: "AI analyzes every detail", color: "bg-violet-50 text-violet-600 border-violet-100" },
              { label: "Get the best instantly", color: "bg-emerald-50 text-emerald-600 border-emerald-100" },
            ].map(({ label, color }) => (
              <span key={label} className={`inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-[10px] sm:text-xs font-semibold border ${color}`}>
                <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />
                {label}
              </span>
            ))}
          </div>

          {/* Trust line */}
          <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-1">
            <Shield className="w-3.5 h-3.5" />
            <span>100% private &amp; secure — your photos are never shared</span>
          </div>
        </div>

        {/* Right – Upload Panel */}
        <div className="relative">
          {/* Soft ambient glow behind the card */}
          <div className="absolute -inset-4 bg-gradient-to-br from-orange-100/50 via-transparent to-purple-100/30 rounded-[3rem] blur-2xl -z-10" />

          <div className="bg-white rounded-3xl shadow-[0_8px_40px_rgba(0,0,0,0.07)] border border-slate-100 p-4">
            <UploadZone
              onUploadsStarted={onUploadsStarted}
              onUploadsCompleted={onUploadsCompleted}
              projectId={projectId}
              triggerRef={triggerUploadRef}
            />
          </div>
        </div>

      </div>
    </section>
  );
}
