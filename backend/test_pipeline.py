import asyncio
import time
import os
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.project import Project
from app.models.image import Image
from app.services.storage_service import storage_service
from app.services.analysis_pipeline import run_analysis_pipeline

async def upload_dummy_images(db: AsyncSession, project_id: str, count: int):
    # Just upload dummy records for the pipeline to fetch
    # We need valid storage paths so the signed URL generation actually works, but for testing we can just use 1 real image path
    # Actually, we need to upload a tiny dummy image to supabase so Groq doesn't crash on invalid image!
    dummy_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    
    images = []
    t0 = time.time()
    for i in range(count):
        storage_path = storage_service.upload_image(project_id, f"test_{i}.png", dummy_bytes, "image/png")
        img = Image(project_id=project_id, filename=f"test_{i}.png", storage_path=storage_path)
        db.add(img)
        images.append(img)
    
    await db.commit()
    t1 = time.time()
    print(f"Uploaded {count} images in {t1 - t0:.2f}s")
    return images

async def test_pipeline_with_count(count: int):
    print(f"\n--- Testing Pipeline with {count} images ---")
    async with AsyncSessionLocal() as db:
        project = Project(name=f"Test {count}")
        db.add(project)
        await db.commit()
        await db.refresh(project)
        
        await upload_dummy_images(db, project.id, count)
        
        t0 = time.time()
        await run_analysis_pipeline(project.id)
        t1 = time.time()
        print(f"Pipeline complete in {t1 - t0:.2f}s")
        
        # Check results
        from sqlalchemy import select
        from app.models.image_analysis import ImageAnalysis
        result = await db.execute(select(ImageAnalysis).where(ImageAnalysis.image_id.in_(
            select(Image.id).where(Image.project_id == project.id)
        )))
        analyses = result.scalars().all()
        print(f"Generated {len(analyses)} analysis records")

async def main():
    await test_pipeline_with_count(2)
    await test_pipeline_with_count(5)
    # await test_pipeline_with_count(10) # Takes a bit too long for quick test

if __name__ == "__main__":
    asyncio.run(main())
