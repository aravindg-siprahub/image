import asyncio
import logging
from app.db.session import AsyncSessionLocal
from app.models.project import Project
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from sqlalchemy import select
from app.services.analysis_pipeline import run_analysis_pipeline

logging.basicConfig(level=logging.INFO)

async def test_run():
    async with AsyncSessionLocal() as db:
        # 1. Check if we have an image in the DB, or create a mock one.
        stmt = select(Image).limit(1)
        res = await db.execute(stmt)
        img = res.scalar_one_or_none()
        
        if not img:
            print("No image found to test. Please upload an image first through the frontend.")
            return

        project_id = img.project_id
        
        # Reset its status so we can analyze it
        img.status = "uploaded"
        await db.commit()
        
        print(f"Testing analysis pipeline for project {project_id} with image {img.id} (url: {img.file_url})")

    # 2. Run the pipeline
    await run_analysis_pipeline(project_id)
    
    # 3. Check results
    async with AsyncSessionLocal() as db:
        stmt = select(ImageAnalysis).where(ImageAnalysis.image_id == img.id)
        res = await db.execute(stmt)
        analysis = res.scalar_one_or_none()
        
        if analysis:
            print(f"Success! Analysis created: {analysis.id}")
            print(f"Final Score: {analysis.final_score}")
            print(f"Reason: {analysis.reason}")
            print(f"Recommendation: {analysis.recommendation}")
            print(f"Sharpness: {analysis.sharpness_score}, Lighting: {analysis.lighting_score}")
        else:
            print("Analysis failed or no record created.")

if __name__ == "__main__":
    asyncio.run(test_run())
