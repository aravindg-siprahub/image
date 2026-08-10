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
        console.error("Polling error:", err);
      }
    };
    
    // Initial fetch
    pollStatus();
    
    // Start polling every 1 second (faster polling for near-instant results)
    timerRef.current = setInterval(pollStatus, 1000);
    
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
  let stageText = "Finding your best photos...";
  if (!statusData) stageText = "Connecting...";
  else if (statusData.status === "completed") stageText = "Preparing results...";
  else if (percent === 100) stageText = "Ranking best photos...";
  else if (percent > 0) stageText = "Analyzing visual quality...";
  
  return (
    <div className="w-full max-w-2xl mx-auto bg-white p-8 md:p-12 rounded-3xl border border-slate-100 shadow-sm">
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-20 h-20 bg-orange-50 text-orange-500 rounded-full mb-6 relative">
          <div className="absolute inset-0 rounded-full border-4 border-orange-100 border-t-orange-500 animate-spin" />
          <svg className="w-8 h-8 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold tracking-tight mb-2">Finding your best photos</h2>
        <p className="text-slate-500">Please wait while we curate your images.</p>
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
                className="h-full bg-gradient-to-r from-orange-400 to-orange-500 transition-all duration-300 ease-out rounded-full"
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>
          
          {/* Status checklist */}
          <div className="bg-slate-50 rounded-xl p-6 space-y-4">
            <ChecklistItem title="Photos uploaded" done={true} active={false} />
            <ChecklistItem title="Quality checked" done={percent === 100} active={percent > 0 && percent < 100} />
            <ChecklistItem title="Finding strongest photos" done={statusData?.status === "completed"} active={percent === 100 && statusData?.status !== "completed"} />
            <ChecklistItem title="Removing duplicates" done={statusData?.status === "completed"} active={percent === 100 && statusData?.status !== "completed"} />
          </div>
        </div>
      )}
    </div>
  );
}

function ChecklistItem({ title, done, active }: { title: string; done: boolean; active: boolean }) {
  return (
    <div className={`flex items-center gap-3 transition-colors duration-300 ${done || active ? "text-slate-900" : "text-slate-400"}`}>
      <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 transition-colors duration-300 ${
        done ? "bg-green-100 text-green-600" : active ? "bg-orange-100 text-orange-600" : "bg-slate-200 text-slate-400"
      }`}>
        {done ? (
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        ) : active ? (
          <div className="w-2 h-2 bg-current rounded-full animate-pulse" />
        ) : (
          <span className="w-1.5 h-1.5 bg-current rounded-full" />
        )}
      </div>
      <span className="text-sm font-medium">{title}</span>
    </div>
  );
}
