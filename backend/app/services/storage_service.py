from supabase import create_client, Client
from app.core.config import settings
import uuid

class StorageService:
    def __init__(self):
        self.supabase: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY
        )
        self.bucket_name = settings.SUPABASE_STORAGE_BUCKET

    def upload_image(self, project_id: str, filename: str, file_bytes: bytes, content_type: str) -> str:
        unique_filename = f"{uuid.uuid4()}_{filename}"
        storage_path = f"projects/{project_id}/images/{unique_filename}"
        
        response = self.supabase.storage.from_(self.bucket_name).upload(
            file=file_bytes,
            path=storage_path,
            file_options={"content-type": content_type}
        )
        
        return storage_path

    def get_public_url(self, storage_path: str) -> str:
        return self.supabase.storage.from_(self.bucket_name).get_public_url(storage_path)

    def download_image(self, storage_path: str) -> bytes:
        response = self.supabase.storage.from_(self.bucket_name).download(storage_path)
        return response

storage_service = StorageService()
