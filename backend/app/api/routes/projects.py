from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.models.project import Project
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from app.services.analysis_pipeline import run_analysis_pipeline
from app.services.storage_service import storage_service
from pydantic import BaseModel
from datetime import datetime
from fastapi.responses import StreamingResponse
import asyncio
import httpx
import zipfile
import io

router = APIRouter()

class ProjectResponse(BaseModel):
    id: str
    name: str | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/", response_model=ProjectResponse)
async def create_project(db: AsyncSession = Depends(get_db)):
    try:
        new_project = Project(name="New Upload Session")
        db.add(new_project)
        await db.commit()
        await db.refresh(new_project)
        return new_project
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )

@router.post("/{project_id}/analyze")
async def start_analysis(project_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    project.status = "processing"
    await db.commit()
    
    background_tasks.add_task(run_analysis_pipeline, project_id)
    return {"project_id": project_id, "status": "processing"}

@router.get("/{project_id}/analysis-status")
async def get_analysis_status(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    total_stmt = select(func.count(Image.id)).where(Image.project_id == project_id)
    total = (await db.execute(total_stmt)).scalar() or 0
    
    processed_stmt = select(func.count(Image.id)).where(Image.project_id == project_id, Image.status == "analyzed")
    processed = (await db.execute(processed_stmt)).scalar() or 0
    
    failed_stmt = select(func.count(Image.id)).where(Image.project_id == project_id, Image.status == "failed")
    failed = (await db.execute(failed_stmt)).scalar() or 0

    quota_stmt = select(func.count(Image.id)).where(
        Image.project_id == project_id, Image.status == "quota_exhausted"
    )
    quota_exhausted = (await db.execute(quota_stmt)).scalar() or 0

    retry_stmt = select(func.max(Image.retry_after_s)).where(
        Image.project_id == project_id, Image.status == "quota_exhausted"
    )
    retry_after_s = (await db.execute(retry_stmt)).scalar()
    
    selected_stmt = select(func.count(ImageAnalysis.id)).join(Image).where(
        Image.project_id == project_id, ImageAnalysis.recommendation == "keep"
    )
    selected = (await db.execute(selected_stmt)).scalar() or 0
    
    # quota_exhausted counts as a terminal outcome (like failed) for completion.
    done = processed + failed + quota_exhausted
    pipeline_status = "completed" if (done == total and total > 0) else project.status
    
    return {
        "status": pipeline_status,
        "total": total,
        "processed": processed,
        "failed": failed,
        "quota_exhausted": quota_exhausted,
        "retry_after_s": retry_after_s,
        "selected": selected
    }

def _create_signed_url_sync(storage_path: str, expires_in: int) -> str | None:
    """Synchronous signed URL creation (runs in thread pool via run_in_executor)."""
    try:
        resp = storage_service.supabase.storage.from_(storage_service.bucket_name).create_signed_url(storage_path, expires_in)
        if isinstance(resp, dict):
            return resp.get("signedURL") or resp.get("signed_url")
        return resp
    except Exception:
        return None

@router.get("/{project_id}/images")
async def get_project_images(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    stmt = (
        select(Image, ImageAnalysis)
        .outerjoin(ImageAnalysis, Image.id == ImageAnalysis.image_id)
        .where(Image.project_id == project_id)
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    # Sort in memory by final_score descending
    def get_score(row):
        img, analysis = row
        if analysis and analysis.final_score is not None:
            return analysis.final_score
        if img.status in ("failed", "quota_exhausted"):
            return -2.0
        return -1.0
        
    rows.sort(key=get_score, reverse=True)
    
    # --- PERF FIX: Generate all signed URLs in parallel (was sequential) ---
    loop = asyncio.get_event_loop()
    
    async def make_signed_url(storage_path: str) -> str | None:
        return await loop.run_in_executor(None, _create_signed_url_sync, storage_path, 3600)
    
    urls = await asyncio.gather(*[make_signed_url(img.storage_path) for img, _ in rows])
    
    output = []
    for (img, analysis), url in zip(rows, urls):
        output.append({
            "image_id": img.id,
            "project_id": img.project_id,
            "file_url": url,
            "storage_path": img.storage_path,   # needed for download
            "status": img.status,
            "retry_after_s": img.retry_after_s,
            "final_score": analysis.final_score if analysis else None,
            "recommendation": analysis.recommendation if analysis else None,
            "reason": analysis.reason if analysis else None,
            "sharpness_score": analysis.sharpness_score if analysis else None,
            "lighting_score": analysis.lighting_score if analysis else None,
            "composition_score": analysis.composition_score if analysis else None,
            "face_score": analysis.face_quality_score if analysis else None,
        })
        
    return output

@router.get("/{project_id}/download")
async def download_project_images(
    project_id: str,
    filter: str = "all",  # "all" | "keep"
    db: AsyncSession = Depends(get_db)
):
    """Stream a ZIP of project images. filter=keep for recommended only."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get images with their analysis
    stmt = (
        select(Image, ImageAnalysis)
        .outerjoin(ImageAnalysis, Image.id == ImageAnalysis.image_id)
        .where(Image.project_id == project_id, Image.status == "analyzed")
    )
    result = await db.execute(stmt)
    rows = result.all()

    if filter == "keep":
        rows = [(img, analysis) for img, analysis in rows if analysis and analysis.recommendation == "keep"]

    if not rows:
        raise HTTPException(status_code=404, detail="No images found to download")

    # Generate short-lived signed URLs for all images in parallel
    loop = asyncio.get_event_loop()

    async def make_url(storage_path: str) -> str | None:
        return await loop.run_in_executor(None, _create_signed_url_sync, storage_path, 300)

    urls = await asyncio.gather(*[make_url(img.storage_path) for img, _ in rows])

    from fastapi.responses import FileResponse
    from starlette.background import BackgroundTask
    import tempfile
    import os

    # Build ZIP on disk to prevent OOM
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_zip_path = temp_zip.name
    temp_zip.close() # Close so we can write to it via zipfile

    async def build_zip_on_disk():
        async with httpx.AsyncClient(timeout=60) as client:
            with zipfile.ZipFile(temp_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for i, ((img, _), url) in enumerate(zip(rows, urls)):
                    if not url:
                        continue
                    try:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        ext = img.storage_path.rsplit(".", 1)[-1] if "." in img.storage_path else "jpg"
                        filename = f"image_{i+1:03d}.{ext}"
                        zf.writestr(filename, resp.content)
                    except Exception as e:
                        print(f"Failed to zip {img.id}: {e}")

    await build_zip_on_disk()

    filename = f"lensai_{project_id[:8]}_{filter}.zip"
    
    def cleanup_temp_file():
        try:
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)
        except Exception:
            pass

    return FileResponse(
        path=temp_zip_path,
        filename=filename,
        media_type="application/zip",
        background=BackgroundTask(cleanup_temp_file)
    )
