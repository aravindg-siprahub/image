import asyncio
import time
import urllib.request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.project import Project
from app.api.routes.images import upload_image
from app.services.analysis_pipeline import run_analysis_pipeline
from fastapi import UploadFile, BackgroundTasks
import io

class MockFile:
    def __init__(self, filename, content):
        self.filename = filename
        self.content = content
        self.content_type = "image/jpeg"
    async def read(self):
        return self.content

async def run_benchmark(count=2):
    print(f"\n--- BENCHMARK: {count} IMAGES ---")
    print("Downloading valid image...")
    req = urllib.request.Request('https://picsum.photos/400/400.jpg', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        img_bytes = response.read()

    start_total = time.time()
    
    # 1. Project creation
    t0 = time.time()
    async with AsyncSessionLocal() as db:
        project = Project(name=f'Bench_{count}')
        db.add(project)
        await db.commit()
        await db.refresh(project)
    project_id = project.id
    t_proj = time.time() - t0
    print(f"Project creation: {t_proj:.3f}s")
    
    # 2. Upload and background analysis kicks off
    t0 = time.time()
    # To run background tasks, we mock BackgroundTasks
    class MockBackgroundTasks:
        def __init__(self):
            self.tasks = []
        def add_task(self, func, *args, **kwargs):
            self.tasks.append((func, args, kwargs))
            
    # We will upload sequentially in the test script, but in real life it's concurrent
    bg_tasks = MockBackgroundTasks()
    async with AsyncSessionLocal() as db:
        for i in range(count):
            file = MockFile(f"bench_{i}.jpg", img_bytes)
            await upload_image(bg_tasks, project_id, file, db)
    t_up = time.time() - t0
    print(f"Image Upload ({count}): {t_up:.3f}s")
    
    # 3. Simulate FastAPI executing background tasks
    t0 = time.time()
    bg_exec = []
    for func, args, kwargs in bg_tasks.tasks:
        bg_exec.append(func(*args, **kwargs))
    await asyncio.gather(*bg_exec)
    t_bg = time.time() - t0
    print(f"Background ML Analysis ({count}): {t_bg:.3f}s")
    
    # 4. Final Ranking Pipeline
    t0 = time.time()
    await run_analysis_pipeline(project_id)
    t_rank = time.time() - t0
    print(f"Final Ranking Pipeline: {t_rank:.3f}s")
    
    print(f"TOTAL TIME to RESULTS: {time.time() - start_total:.3f}s")

if __name__ == "__main__":
    asyncio.run(run_benchmark(2))
    asyncio.run(run_benchmark(5))
