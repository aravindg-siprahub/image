"use client";

import { useEffect, useState, useRef } from "react";
import { getAnalysisStatus } from "@/lib/api";
import { AnalysisStatus } from "@/types";

interface ProcessingStateProps {
  projectId: string;
  onComplete: () => void;
}

export default function ProcessingState({ projectId, onComplete }: ProcessingStateProps) {
  const [statusData, setStatusData] = useState<AnalysisStatus | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    let mounted = true;
    
    const pollStatus = async () => {
      if (!mounted) return;
      
      try {
        const data = await getAnalysisStatus(projectId);
        setStatusData(data);
        
        if (data.status === "completed") {
          if (timerRef.current) clearInterval(timerRef.current);
          if (mounted) onComplete();
        } else if (data.status === "failed") {
          if (timerRef.current) clearInterval(timerRef.current);
          setErrorMsg("Analysis failed. Please try again.");
        }
      } catch (err: any) {
        // Just log the error, don't stop polling unless it fails multiple times in a real app.
        // For MVP, we will keep polling.
        console.error("Polling error:", err);
      }
    };
    
    // Initial fetch
    pollStatus();
    
    // Start polling every 1.5 seconds
    timerRef.current = setInterval(pollStatus, 1500);
    
    return () => {
      mounted = false;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [projectId, onComplete]);

  // Calculate progress
  const total = statusData?.total || 1;
  const processed = (statusData?.processed || 0) + (statusData?.failed || 0);
  const percent = Math.min(Math.round((processed / total) * 100), 100);
  
  // Determine text stage
  let stageText = "Analyzing images...";
  if (!statusData) stageText = "Connecting to pipeline...";
  else if (statusData.status === "completed") stageText = "Preparing results...";
  else if (percent > 90) stageText = "Ranking best photos...";
  
  return (
    <div className="w-full max-w-2xl mx-auto bg-white p-8 md:p-12 rounded-3xl border border-slate-100 shadow-sm">
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-20 h-20 bg-orange-50 text-orange-500 rounded-full mb-6">
          <svg className="w-10 h-10 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </div>
        <h2 className="text-2xl font-bold tracking-tight mb-2">Analyzing your photos</h2>
        <p className="text-slate-500">Our AI vision models are reviewing {statusData?.total || "your"} images.</p>
      </div>

      {errorMsg ? (
        <div className="bg-red-50 text-red-600 p-4 rounded-xl text-center font-medium">
          {errorMsg}
        </div>
      ) : (
        <div className="space-y-8">
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-sm font-medium">
              <span className="text-slate-700">{stageText}</span>
              <span className="text-orange-600">{percent}%</span>
            </div>
            <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-orange-400 to-orange-500 transition-all duration-500 ease-out rounded-full"
                style={{ width: `${percent}%` }}
              />
            </div>
            
            {statusData && statusData.total > 0 && (
              <p className="text-xs text-slate-400 mt-2 text-right">
                Analyzed {processed} / {statusData.total}
              </p>
            )}
          </div>
          
          {/* Status checklist */}
          <div className="bg-slate-50 rounded-xl p-6 space-y-4">
            <div className="flex items-center gap-3 text-slate-900">
              <div className="w-6 h-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center shrink-0">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
              </div>
              <span className="text-sm font-medium">Uploading & stored</span>
            </div>
            
            <div className={`flex items-center gap-3 ${percent > 0 ? "text-slate-900" : "text-slate-400"}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${percent > 0 && percent < 100 ? "bg-orange-100 text-orange-600" : percent === 100 ? "bg-green-100 text-green-600" : "bg-slate-200 text-slate-400"}`}>
                {percent === 100 ? (
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                ) : (
                  <div className="w-2 h-2 bg-current rounded-full animate-pulse" />
                )}
              </div>
              <span className="text-sm font-medium">Visual quality analysis</span>
            </div>
            
            <div className={`flex items-center gap-3 ${percent === 100 ? "text-slate-900" : "text-slate-400"}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${percent === 100 ? "bg-green-100 text-green-600" : "bg-slate-200 text-slate-400"}`}>
                {percent === 100 ? (
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                ) : (
                   <span className="w-1.5 h-1.5 bg-current rounded-full" />
                )}
              </div>
              <span className="text-sm font-medium">Ranking & selection</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
