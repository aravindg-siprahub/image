from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.storage_service import storage_service
from app.models.image import Image
from app.schemas.image import ImageResponse

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic"
}

@router.post("/upload", response_model=ImageResponse)
async def upload_image(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only JPG, PNG, WEBP, and HEIC are allowed."
        )
        
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file."
        )
        
    try:
        # Upload to Supabase
        storage_path = storage_service.upload_image(
            project_id=project_id,
            filename=file.filename or "unknown",
            file_bytes=file_bytes,
            content_type=file.content_type
        )
        file_url = storage_service.get_public_url(storage_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supabase upload failed: {str(e)}"
        )
        
    # Save to database
    try:
        db_image = Image(
            project_id=project_id,
            file_url=file_url,
            storage_path=storage_path,
            status="uploaded"
        )
        db.add(db_image)
        await db.commit()
        await db.refresh(db_image)
        return db_image
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database failure: {str(e)}"
        )
