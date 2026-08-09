from supabase import create_client, Client
from app.core.config import settings
import uuid
import io
import logging

logger = logging.getLogger(__name__)

# Analysis derivative: max longest edge / JPEG quality for Groq + similarity.
ANALYSIS_MAX_EDGE = 1024
ANALYSIS_JPEG_QUALITY = 80


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

    @staticmethod
    def analysis_path_for(storage_path: str) -> str:
        """Predictable sibling path for the resized analysis JPEG (no DB column)."""
        return f"{storage_path}.analysis.jpg"

    def upload_bytes(self, storage_path: str, file_bytes: bytes, content_type: str) -> str:
        self.supabase.storage.from_(self.bucket_name).upload(
            file=file_bytes,
            path=storage_path,
            file_options={"content-type": content_type},
        )
        return storage_path

    @staticmethod
    def make_analysis_jpeg(
        file_bytes: bytes,
        max_edge: int = ANALYSIS_MAX_EDGE,
        quality: int = ANALYSIS_JPEG_QUALITY,
    ) -> bytes:
        """Resize to max longest edge and JPEG-compress for analysis hot path."""
        from PIL import Image as PILImage

        img = PILImage.open(io.BytesIO(file_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        longest = max(w, h)
        if longest > max_edge:
            scale = max_edge / float(longest)
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), PILImage.LANCZOS)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue()

    def upload_analysis_derivative(self, storage_path: str, original_bytes: bytes) -> str | None:
        """
        Create and store resized analysis JPEG alongside the original.
        Returns analysis path on success, None on failure (caller keeps original usable).
        """
        try:
            analysis_bytes = self.make_analysis_jpeg(original_bytes)
            analysis_path = self.analysis_path_for(storage_path)
            self.upload_bytes(analysis_path, analysis_bytes, "image/jpeg")
            logger.info(
                f"Stored analysis derivative path={analysis_path} "
                f"bytes={len(analysis_bytes)} (original={len(original_bytes)})"
            )
            return analysis_path
        except Exception as e:
            logger.warning(f"Failed to create analysis derivative for {storage_path}: {e}")
            return None

    def download_analysis_or_original(self, storage_path: str) -> bytes:
        """Prefer resized analysis copy; fall back to original for legacy uploads."""
        analysis_path = self.analysis_path_for(storage_path)
        try:
            return self.download_image(analysis_path)
        except Exception:
            return self.download_image(storage_path)

storage_service = StorageService()
