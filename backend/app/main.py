import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.routes import images, projects

app = FastAPI(title="AI Image Curation API")

# CORS: allow localhost for dev + any Railway frontend URL set via ALLOWED_ORIGINS env var
# Example Railway env var: ALLOWED_ORIGINS=https://my-frontend.up.railway.app
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(images.router, prefix="/api/v1/images", tags=["images"])

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "ok",
        "database": db_status
    }
