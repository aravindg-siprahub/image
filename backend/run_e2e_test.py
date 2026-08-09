import asyncio
import urllib.request
from app.db.session import AsyncSessionLocal
from app.models.project import Project
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from app.services.storage_service import storage_service
from app.services.analysis_pipeline import run_analysis_pipeline
from sqlalchemy import select

async def run_e2e():
    print("1. Downloading a valid test image...")
    # A small public domain image from Wikimedia
    img_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/React-icon.svg/200px-React-icon.svg.png"
    # Actually SVG/PNG might be weird, let's use a standard JPG photo (e.g. lenna or just a placeholder)
    img_url = "https://picsum.photos/400/400.jpg"
    
    req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        valid_img_bytes = response.read()
        
    invalid_img_bytes = b"This is not a real image, it should fail."
    
    async with AsyncSessionLocal() as db:
        print("2. Creating Project...")
        project = Project(name="E2E Validation")
        db.add(project)
        await db.commit()
        
        print("3. Uploading valid and invalid images to Supabase...")
        valid_storage_path = storage_service.upload_image(project.id, "valid.jpg", valid_img_bytes, "image/jpeg")
        invalid_storage_path = storage_service.upload_image(project.id, "invalid.txt", invalid_img_bytes, "text/plain")
        
        valid_url = storage_service.get_public_url(valid_storage_path)
        invalid_url = storage_service.get_public_url(invalid_storage_path)
        
        valid_img = Image(project_id=project.id, file_url=valid_url, storage_path=valid_storage_path, status="uploaded")
        invalid_img = Image(project_id=project.id, file_url=invalid_url, storage_path=invalid_storage_path, status="uploaded")
        
        db.add(valid_img)
        db.add(invalid_img)
        await db.commit()
        
        print(f"Created images: Valid({valid_img.id}), Invalid({invalid_img.id})")
        
    print("4. Running pipeline...")
    # Normally this is triggered by the API, but we'll run it directly to wait for it.
    await run_analysis_pipeline(project.id)
    
    print("5. Verifying Results...")
    async with AsyncSessionLocal() as db:
        # Check invalid
        stmt = select(Image).where(Image.id == invalid_img.id)
        inv = (await db.execute(stmt)).scalar_one()
        print(f"Invalid image status: {inv.status} (Expected: failed)")
        
        # Check valid
        stmt = select(Image).where(Image.id == valid_img.id)
        val = (await db.execute(stmt)).scalar_one()
        print(f"Valid image status: {val.status} (Expected: analyzed or completed)")
        
        # Check analysis
        stmt = select(ImageAnalysis).where(ImageAnalysis.image_id == valid_img.id)
        analysis = (await db.execute(stmt)).scalar_one_or_none()
        
        if analysis:
            print(f"\n--- SUCCESS: Valid Analysis Data ---")
            print(f"Sharpness: {analysis.sharpness_score}")
            print(f"Exposure: {analysis.exposure_score}")
            print(f"Composition: {analysis.composition_score}")
            print(f"Face Quality: {analysis.face_quality_score}")
            print(f"Python Final Score: {analysis.final_score}")
            print(f"Is Usable: {analysis.is_usable}")
            print(f"Reason: {analysis.reason}")
            print(f"Recommendation: {analysis.recommendation}")
            print(f"------------------------------------")
        else:
            print("ERROR: Valid image analysis record not found.", flush=True)

if __name__ == "__main__":
    asyncio.run(run_e2e())
