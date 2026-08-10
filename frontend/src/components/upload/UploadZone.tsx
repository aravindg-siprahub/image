"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { UploadCloud, Image as ImageIcon, X, AlertCircle, RefreshCw } from "lucide-react";
import { createProject, uploadImage, startAnalysis } from "@/lib/api";

interface UploadZoneProps {
  onUploadsStarted: (projectId: string) => void;
  onUploadsCompleted: () => void;
  projectId: string | null;
  triggerRef?: React.MutableRefObject<(() => void) | undefined>;
}

interface FileWithStatus {
  file: File;
  previewUrl: string;
  status: "pending" | "uploading" | "success" | "error";
  error?: string;
}

const MAX_CONCURRENT_UPLOADS = 3; // Reduced from 5 for safe mobile uploads

export default function UploadZone({ onUploadsStarted, onUploadsCompleted, projectId, triggerRef }: UploadZoneProps) {
  const [files, setFiles] = useState<FileWithStatus[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Expose trigger method to parent
  useEffect(() => {
    if (triggerRef) {
      triggerRef.current = () => {
        if (!isProcessing) fileInputRef.current?.click();
      };
    }
  }, [triggerRef, isProcessing]);

  // Clean up object URLs to prevent memory leaks
  useEffect(() => {
    return () => {
      files.forEach(f => URL.revokeObjectURL(f.previewUrl));
    };
  }, [files]);

  const handleFilesAdded = (newFiles: File[]) => {
    // Remove HEIC from explicit accepted types to trigger iOS/Android auto-transcoding to JPEG
    const validFiles = newFiles.filter(f => 
      f.type.startsWith("image/")
    );
    
    if (validFiles.length === 0) return;

    // Warn about very large files (>50MB each can time out on slow mobile connections)
    const largeFiles = validFiles.filter(f => f.size > 50 * 1024 * 1024);
    if (largeFiles.length > 0) {
      setErrorMsg(
        `${largeFiles.length} photo${largeFiles.length > 1 ? 's are' : ' is'} very large (>50MB). ` +
        "Upload may be slower on mobile."
      );
      setTimeout(() => setErrorMsg(null), 5000);
    }
    
    const newFilesWithStatus: FileWithStatus[] = validFiles.map(f => ({
      file: f,
      previewUrl: URL.createObjectURL(f),
      status: "pending"
    }));
    
    setFiles(prev => [...prev, ...newFilesWithStatus]);
  };

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesAdded(Array.from(e.dataTransfer.files));
    }
  }, []);

  const removeFile = (index: number) => {
    setFiles(prev => {
      const newFiles = [...prev];
      URL.revokeObjectURL(newFiles[index].previewUrl);
      newFiles.splice(index, 1);
      return newFiles;
    });
  };

  const handleStartUpload = async () => {
    if (files.length === 0 || isProcessing) return;
    
    setIsProcessing(true);
    setErrorMsg(null);
    
    let currentProjectId = projectId;
    
    if (!currentProjectId) {
      try {
        const proj = await createProject();
        currentProjectId = proj.id;
        onUploadsStarted(currentProjectId);
      } catch (e: any) {
        const msg = e.message || "";
        if (msg.toLowerCase().includes("fetch") || msg.toLowerCase().includes("network")) {
          setErrorMsg("Cannot reach the server. Check your internet connection and try again.");
        } else {
          setErrorMsg(e.message || "Failed to start. Please try again.");
        }
        setIsProcessing(false);
        return;
      }
    }

    // Process uploads with concurrency limit
    const pendingFiles = files.map((f, i) => ({ ...f, originalIndex: i }))
                              .filter(f => f.status === "pending" || f.status === "error");
    
    if (pendingFiles.length === 0) {
      setIsProcessing(false);
      return;
    }

    let activeUploads = 0;
    let currentIndex = 0;
    
    await new Promise<void>((resolve) => {
      const uploadNext = () => {
        if (currentIndex >= pendingFiles.length && activeUploads === 0) {
          resolve();
          return;
        }
        
        while (activeUploads < MAX_CONCURRENT_UPLOADS && currentIndex < pendingFiles.length) {
          const item = pendingFiles[currentIndex];
          currentIndex++;
          activeUploads++;
          
          // Update status to uploading
          setFiles(prev => {
            const newFiles = [...prev];
            newFiles[item.originalIndex].status = "uploading";
            return newFiles;
          });
          
          uploadImage(currentProjectId as string, item.file)
            .then(() => {
              setFiles(prev => {
                const newFiles = [...prev];
                newFiles[item.originalIndex].status = "success";
                return newFiles;
              });
            })
            .catch((err) => {
              setFiles(prev => {
                const newFiles = [...prev];
                newFiles[item.originalIndex].status = "error";
                newFiles[item.originalIndex].error = err.message;
                return newFiles;
              });
            })
            .finally(() => {
              activeUploads--;
              uploadNext();
            });
        }
      };
      
      uploadNext();
    });
    
    // Check if any errors occurred
    const errorCount = files.filter(f => f.status === "error").length;
    const successCount = files.filter(f => f.status === "success").length;
    
    if (errorCount > 0) {
      if (successCount === 0) {
        setErrorMsg("Upload failed. Check your connection and try again.");
      } else {
        setErrorMsg(`${successCount} photos uploaded. ${errorCount} couldn't be uploaded.`);
        // Start analysis in background for the successful ones so they don't wait
        try { await startAnalysis(currentProjectId as string); } catch (e) {}
      }
      setIsProcessing(false);
      return;
    }
    
    // If we have at least one success, start analysis
    if (successCount > 0) {
      try {
        await startAnalysis(currentProjectId as string);
        onUploadsCompleted();
      } catch (e: any) {
        setErrorMsg(e.message || "Failed to start analysis");
        setIsProcessing(false);
      }
    } else {
      setIsProcessing(false);
    }
  };

  const successfulCount = files.filter(f => f.status === "success").length;
  const pendingCount = files.filter(f => f.status === "pending").length;
  const errorCount = files.filter(f => f.status === "error").length;

  return (
    <div className="w-full relative">
      {errorMsg && (
        <div className="mb-4 p-3 bg-red-50 border border-red-100 rounded-xl flex items-center gap-2 text-red-700 absolute -top-16 left-0 right-0 z-10 shadow-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <p className="text-xs font-medium">{errorMsg}</p>
        </div>
      )}
      
      {/* Drop Zone */}
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`
          relative overflow-hidden rounded-2xl border-2 border-dashed transition-all duration-300
          ${isDragging ? "border-orange-400 bg-orange-50/60 scale-[1.01]" : "border-slate-200 bg-white hover:border-orange-300"}
        `}
      >
        {files.length === 0 ? (
          <div className="px-6 py-12 flex flex-col items-center justify-center text-center">
            {/* Icon */}
            <div className="w-12 h-12 mb-4 rounded-xl bg-orange-50 flex items-center justify-center text-orange-500">
              <UploadCloud className="w-6 h-6" strokeWidth={2} />
            </div>
            <h3 className="text-[17px] font-bold text-slate-900 mb-1">Drop your photos here</h3>
            <p className="text-[13px] text-slate-400 mb-6">or click to browse from your computer</p>

            <button
              onClick={(e) => { e.stopPropagation(); if (!isProcessing) fileInputRef.current?.click(); }}
              className="bg-[#FF6B2C] hover:bg-[#e85f22] active:scale-95 text-white px-7 py-2.5 rounded-full text-sm font-semibold transition-all shadow-[0_2px_12px_rgba(255,107,44,0.35)] hover:shadow-[0_4px_18px_rgba(255,107,44,0.4)] mb-5"
            >
              Choose Photos
            </button>
            
            {/* Format labels */}
            <p className="text-[11px] text-slate-400 font-medium tracking-widest uppercase">
              JPG · PNG · WEBP &nbsp;·&nbsp; Up to 100+ photos
            </p>

            {/* Demo thumbnail strip */}
            <div className="mt-8 flex items-center gap-2">
              {[1, 2, 3, 4, 5].map((num) => (
                <div key={num} className="w-11 h-11 rounded-lg overflow-hidden shadow-sm ring-1 ring-slate-100">
                  <img src={`/demo/demo-${num}.jpg`} alt="demo" className="w-full h-full object-cover" />
                </div>
              ))}
              <div className="w-11 h-11 rounded-lg bg-slate-100 text-slate-500 font-bold flex items-center justify-center text-xs">
                +95
              </div>
            </div>
          </div>
        ) : (
          <div className="p-8 relative z-10 min-h-[400px] flex flex-col">
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
              <h4 className="font-bold text-lg text-slate-900 flex items-center gap-2">
                Selected Photos 
                <span className="bg-slate-100 text-slate-600 text-xs py-1 px-2.5 rounded-full font-bold">{files.length}</span>
              </h4>
              
              {!isProcessing ? (
                <button 
                  onClick={handleStartUpload}
                  className="bg-[#FF6B2C] text-white px-6 py-2.5 rounded-full font-semibold text-sm transition-all shadow-[0_4px_14px_0_rgba(255,107,44,0.39)] hover:shadow-[0_6px_20px_rgba(255,107,44,0.23)] hover:-translate-y-[1px]"
                >
                  Upload & Analyze
                </button>
              ) : (
                <div className="flex items-center gap-2 text-orange-600 font-medium bg-orange-50 px-4 py-2 rounded-full text-sm">
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Photos uploaded — finding your best photos...
                </div>
              )}
            </div>
            
            <div className="grid grid-cols-4 sm:grid-cols-5 gap-3 flex-1 content-start overflow-y-auto max-h-[300px] pr-2 custom-scrollbar">
              {files.map((fileObj, idx) => (
                <div key={idx} className="group relative aspect-square rounded-xl overflow-hidden border border-slate-200 bg-slate-50 shadow-sm">
                  <img 
                    src={fileObj.previewUrl} 
                    alt={fileObj.file.name} 
                    className="w-full h-full object-cover"
                  />
                  
                  {fileObj.status === "uploading" && (
                    <div className="absolute inset-0 bg-white/70 backdrop-blur-sm flex items-center justify-center">
                      <RefreshCw className="w-6 h-6 text-orange-500 animate-spin" />
                    </div>
                  )}
                  
                  {fileObj.status === "success" && (
                    <div className="absolute inset-0 bg-green-500/20 border-2 border-green-500 rounded-xl">
                      <div className="absolute bottom-1 right-1 bg-green-500 text-white rounded-full p-0.5 shadow-sm">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                    </div>
                  )}
                  
                  {fileObj.status === "error" && (
                    <div className="absolute inset-0 bg-red-500/20 border-2 border-red-500 rounded-xl flex items-center justify-center">
                      <AlertCircle className="w-6 h-6 text-red-500 bg-white rounded-full" />
                    </div>
                  )}
                  
                  {fileObj.status !== "uploading" && fileObj.status !== "success" && (
                    <button 
                      onClick={(e) => { e.stopPropagation(); removeFile(idx); }}
                      className="absolute top-1 right-1 p-1 bg-white/90 hover:bg-red-50 text-slate-500 hover:text-red-500 rounded-full opacity-0 group-hover:opacity-100 transition-all shadow-sm"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  )}
                </div>
              ))}
              
              {!isProcessing && (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="aspect-square rounded-xl border-2 border-dashed border-slate-200 hover:border-orange-300 hover:bg-orange-50 flex flex-col items-center justify-center text-slate-400 hover:text-orange-500 transition-colors"
                >
                  <UploadCloud className="w-6 h-6 mb-1" />
                  <span className="text-[10px] font-bold uppercase tracking-wider">Add More</span>
                </button>
              )}
            </div>
            
            {errorCount > 0 && !isProcessing && (
              <div className="mt-4 pt-4 border-t border-slate-100 flex justify-end gap-3">
                <button 
                  onClick={handleStartUpload}
                  className="flex items-center gap-2 text-red-600 hover:text-red-700 font-medium bg-red-50 hover:bg-red-100 px-4 py-2 rounded-full transition-colors text-sm"
                >
                  <RefreshCw className="w-4 h-4" />
                  Retry {errorCount} Failed
                </button>
                {successfulCount > 0 && (
                  <button 
                    onClick={() => onUploadsCompleted()}
                    className="flex items-center gap-2 text-slate-600 hover:text-slate-800 font-medium bg-slate-100 hover:bg-slate-200 px-4 py-2 rounded-full transition-colors text-sm"
                  >
                    Continue to Results
                  </button>
                )}
              </div>
            )}
          </div>
        )}
        
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={(e) => {
            if (e.target.files) handleFilesAdded(Array.from(e.target.files));
            e.target.value = '';
          }}
          className="hidden" 
          multiple 
          accept="image/jpeg,image/png,image/webp" 
        />
      </div>
    </div>
  );
}
