import asyncio
import time
import urllib.request
from app.db.session import AsyncSessionLocal
from app.models.project import Project
from app.models.image import Image
from app.services.storage_service import storage_service
from app.services.analysis_pipeline import run_analysis_pipeline
from app.services.image_analyzer import analyze_single_image_background

async def run_benchmark():
    print("Downloading valid image...")
    req = urllib.request.Request('https://picsum.photos/400/400.jpg', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        img_bytes = response.read()

    start_total = time.time()
    
    async with AsyncSessionLocal() as db:
        t0 = time.time()
        project = Project(name='Bench_1')
        db.add(project)
        await db.commit()
        await db.refresh(project)
        t_proj = time.time() - t0
        print(f"Project creation: {t_proj:.3f}s")
        
        t0 = time.time()
        # Mocking the new upload route behavior (1 original)
        storage_path = storage_service.upload_image(project.id, 'bench.jpg', img_bytes, 'image/jpeg')
        img = Image(project_id=project.id, file_url='', storage_path=storage_path, status='uploaded')
        db.add(img)
        await db.commit()
        await db.refresh(img)
        t_up = time.time() - t0
        print(f"Image Upload (Original only): {t_up:.3f}s")

    t0 = time.time()
    # Mocking the background task (running in-memory using bytes)
    await analyze_single_image_background(str(img.id), img_bytes)
    t_bg = time.time() - t0
    print(f"Background ML Analysis (in-memory): {t_bg:.3f}s")

    t0 = time.time()
    # Final Ranking Pipeline
    await run_analysis_pipeline(project.id)
    t_rank = time.time() - t0
    print(f"Final Ranking Pipeline: {t_rank:.3f}s")
    
    print(f"TOTAL TIME to RESULTS: {time.time() - start_total:.3f}s")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
