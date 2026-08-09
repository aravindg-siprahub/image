from sqlalchemy import Column, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone
from app.models.base import Base

class Image(Base):
    __tablename__ = "images"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    file_url = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    status = Column(String, default="uploaded")
    # Set when status == "quota_exhausted" (Groq TPD / long Retry-After).
    retry_after_s = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    project = relationship("Project", back_populates="images")
    analysis = relationship("ImageAnalysis", back_populates="image", uselist=False)
