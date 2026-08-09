from pydantic import BaseModel
from datetime import datetime

class ImageResponse(BaseModel):
    id: str
    project_id: str
    storage_path: str
    file_url: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
