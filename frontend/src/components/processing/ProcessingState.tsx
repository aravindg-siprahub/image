"use client";

import { useEffect, useState, useRef } from "react";
import { getAnalysisStatus } from "@/lib/api";
import { AnalysisStatus } from "@/types";

interface ProcessingStateProps {
  projectId: string;
  onComplete: () => void;
}

// Checklist steps shown in order
const STEPS = [
  { id: "upload",    label: "Photos uploaded" },
  { id: "quality",   label: "Checking photo quality" },
  { id: "compare",   label: "Comparing similar shots" },
  { id: "select",    label: "Selecting your best photos" },
];

export default function ProcessingState({ projectId, onComplete }: ProcessingStateProps) {
  const [statusData, setStatusData] = useState<AnalysisStatus | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // Smooth animated percent — advances even when real progress is 0
  const [displayPct, setDisplayPct] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const smoothRef = useRef<NodeJS.Timeout | null>(null);

  // Drive a minimum forward animation so the bar is never visually stuck at 0%
  const advanceSmooth = (target: number) => {
    if (smoothRef.current) return; // already running
    smoothRef.current = setInterval(() => {
      setDisplayPct(prev => {
        const next = prev + 1;
        if (next >= target) {
          clearInterval(smoothRef.current!);
          smoothRef.current = null;
          return target;
        }
        return next;
      });
    }, 40); // ~25fps, takes ~1s to move 25 points
  };

  useEffect(() => {
    let mounted = true;

    // Immediately jump to 5% so the bar isn't stuck at 0
    setDisplayPct(5);

    const pollStatus = async () => {
      if (!mounted) return;
      try {
        const data = await getAnalysisStatus(projectId);
        if (!mounted) return;
        setStatusData(data);

        const total = data.total || 1;
        const done = (data.processed || 0) + (data.failed || 0) + (data.quota_exhausted || 0);
        const realPct = Math.min(95, Math.round((done / total) * 90) + 5);

        setDisplayPct(prev => {
          const target = Math.max(prev, realPct);
          if (target > prev) advanceSmooth(target);
          return prev;
        });

        if (data.status === "completed") {
          if (timerRef.current) clearInterval(timerRef.current);
          // Animate to 100% before triggering results
          setDisplayPct(100);
          setTimeout(() => { if (mounted) onComplete(); }, 600);
        } else if (data.status === "failed") {
          if (timerRef.current) clearInterval(timerRef.current);
          setErrorMsg("Analysis failed. Please try again.");
        }
      } catch (err: any) {
        console.error("Polling error:", err);
      }
    };

    // First poll immediately
    pollStatus();
    // Then every 1 second (was 1.5s — 500ms faster results)
    timerRef.current = setInterval(pollStatus, 1000);

    return () => {
      mounted = false;
      if (timerRef.current) clearInterval(timerRef.current);
      if (smoothRef.current) clearInterval(smoothRef.current);
    };
  }, [projectId, onComplete]);

  // Derive which steps are done / active
  const total = statusData?.total || 1;
  const processed = (statusData?.processed || 0) + (statusData?.failed || 0);
  const pct = displayPct;
  const isDone = statusData?.status === "completed";

  const stepDone = {
    upload:  true,                            // always done when this screen shows
    quality: processed > 0 || pct > 30,
    compare: pct >= 85 || isDone,
    select:  isDone,
  };
  const stepActive = {
    upload:  false,
    quality: !stepDone.quality,
    compare: stepDone.quality && !stepDone.compare,
    select:  stepDone.compare && !stepDone.select,
  };

  // Status text
  let stageText = "Reviewing your photos…";
  if (!statusData)                      stageText = "Getting started…";
  else if (isDone)                      stageText = "Done! Preparing your results…";
  else if (pct >= 85)                   stageText = "Almost there…";
  else if (processed > 0)               stageText = `Checked ${processed} of ${total} photos…`;
  else if (pct > 5)                     stageText = "Analyzing photo quality…";

  return (
    <div className="w-full max-w-lg mx-auto bg-white p-8 md:p-10 rounded-3xl border border-slate-100 shadow-sm">
      {/* Icon + title */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-orange-50 rounded-full mb-5 relative">
          <div className="absolute inset-0 rounded-full border-[3px] border-orange-100 border-t-orange-500 animate-spin" />
          <svg className="w-7 h-7 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold tracking-tight text-slate-900">Finding your best photos</h2>
        <p className="text-sm text-slate-500 mt-1">This usually takes a few seconds</p>
      </div>

      {errorMsg ? (
        <div className="bg-red-50 text-red-600 p-4 rounded-xl text-center font-medium text-sm">
          {errorMsg}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Progress bar */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-xs font-medium text-slate-500">
              <span>{stageText}</span>
              <span className="text-orange-500 tabular-nums">{pct}%</span>
            </div>
            <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-orange-400 to-orange-500 rounded-full transition-[width] duration-500 ease-out"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {/* Checklist */}
          <div className="bg-slate-50 rounded-2xl p-5 space-y-3">
            {STEPS.map(step => (
              <ChecklistItem
                key={step.id}
                title={step.label}
                done={stepDone[step.id as keyof typeof stepDone]}
                active={stepActive[step.id as keyof typeof stepActive]}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ChecklistItem({ title, done, active }: { title: string; done: boolean; active: boolean }) {
  return (
    <div className={`flex items-center gap-3 transition-all duration-300 ${
      done || active ? "opacity-100" : "opacity-40"
    }`}>
      <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 transition-colors duration-300 ${
        done   ? "bg-emerald-100 text-emerald-600" :
        active ? "bg-orange-100 text-orange-500" :
                 "bg-slate-200 text-slate-400"
      }`}>
        {done ? (
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        ) : active ? (
          <div className="w-1.5 h-1.5 bg-current rounded-full animate-pulse" />
        ) : (
          <div className="w-1.5 h-1.5 bg-current rounded-full" />
        )}
      </div>
      <span className={`text-sm font-medium ${
        done ? "text-slate-800" : active ? "text-slate-700" : "text-slate-400"
      }`}>
        {title}
      </span>
    </div>
  );
}
