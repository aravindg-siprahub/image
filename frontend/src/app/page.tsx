"use client";

import { useState, useRef } from "react";
import Navbar from "@/components/navbar/Navbar";
import Hero from "@/components/hero/Hero";
import HowItWorks from "@/components/how-it-works/HowItWorks";
import DemoGallery from "@/components/gallery/DemoGallery";
import ProcessingState from "@/components/processing/ProcessingState";
import ResultsGallery from "@/components/gallery/ResultsGallery";

type AppState = "idle" | "uploading" | "processing" | "results";

export default function Home() {
  const [appState, setAppState] = useState<AppState>("idle");
  const [projectId, setProjectId] = useState<string | null>(null);
  const triggerUploadRef = useRef<(() => void) | undefined>(undefined);

  const handleUploadsStarted = (id: string) => {
    setProjectId(id);
    setAppState("uploading");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleUploadsCompleted = () => {
    setAppState("processing");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleAnalysisCompleted = () => {
    setAppState("results");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleGetStarted = () => {
    triggerUploadRef.current?.();
  };

  return (
    <div className="min-h-screen bg-[#F8F7F4] text-slate-900 selection:bg-orange-100">

      {/* Fixed ambient blobs */}
      <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden -z-10">
        <div className="absolute top-0 right-[-10%] w-[45%] h-[55%] rounded-full bg-orange-100/40 blur-3xl" />
        <div className="absolute bottom-0 left-[-15%] w-[55%] h-[50%] rounded-full bg-violet-100/30 blur-3xl" />
      </div>

      <Navbar onGetStarted={handleGetStarted} />

      <main>
        {/* Landing / Upload state */}
        {(appState === "idle" || appState === "uploading") && (
          <div className="animate-fade-in">
            <Hero
              onUploadsStarted={handleUploadsStarted}
              onUploadsCompleted={handleUploadsCompleted}
              projectId={projectId}
              triggerUploadRef={triggerUploadRef}
            />
            <HowItWorks />
            {appState === "idle" && <DemoGallery />}
          </div>
        )}

        {/* AI Processing state */}
        {appState === "processing" && projectId && (
          <div className="animate-fade-in flex items-center justify-center min-h-[70vh] px-6">
            <ProcessingState projectId={projectId} onComplete={handleAnalysisCompleted} />
          </div>
        )}

        {/* Results state */}
        {appState === "results" && projectId && (
          <div className="animate-fade-in w-full max-w-6xl mx-auto px-6 py-14">
            <div className="mb-10">
              <h2 className="text-3xl font-black tracking-tight text-slate-900 mb-2">Your Curated Collection</h2>
              <p className="text-slate-500">AI picked the strongest shots — ranked by visual quality.</p>
            </div>
            <ResultsGallery projectId={projectId} />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-12 py-6 border-t border-slate-200/70 bg-white/60">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400">
          <span>&copy; {new Date().getFullYear()} LensAI — All rights reserved.</span>
          <div className="flex gap-5">
            <a href="#" className="hover:text-slate-700 transition-colors">Privacy</a>
            <a href="#" className="hover:text-slate-700 transition-colors">Terms</a>
          </div>
        </div>
      </footer>

    </div>
  );
}
