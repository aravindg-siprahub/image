import asyncio
import io
import uuid
from app.db.session import AsyncSessionLocal
from app.models.project import Project
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from app.services.storage_service import storage_service

async def test_integration():
    print("Testing DB and Storage integration...")
    
    # 1. Create a Project
    async with AsyncSessionLocal() as db:
        new_project = Project(name="Test Project")
        db.add(new_project)
        await db.commit()
        await db.refresh(new_project)
        print(f"Created project: {new_project.id}")
        
    # 2. Test Supabase Storage Upload
    try:
        dummy_file_bytes = b"Hello world this is a test image."
        storage_path = storage_service.upload_image(
            project_id=new_project.id,
            filename="test.png",
            file_bytes=dummy_file_bytes,
            content_type="image/png"
        )
        file_url = storage_service.get_public_url(storage_path)
        print(f"Uploaded successfully to: {storage_path}")
        print(f"Public URL: {file_url}")
        # 3. Create Image Record
        async with AsyncSessionLocal() as db2:
            new_img = Image(
                project_id=new_project.id,
                file_url=file_url,
                storage_path=storage_path,
                status="uploaded"
            )
            db2.add(new_img)
            await db2.commit()
            print(f"Image record inserted: {new_img.id}")
            
    except Exception as e:
        print(f"Upload failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_integration())
