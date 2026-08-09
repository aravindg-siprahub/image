from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from app.models.base import Base

class ImageAnalysis(Base):
    __tablename__ = "image_analysis"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    image_id = Column(String, ForeignKey("images.id"), nullable=False, unique=True)
    
    # Raw Groq Scores
    sharpness_score = Column(Float, nullable=True)
    blur_score = Column(Float, nullable=True)
    exposure_score = Column(Float, nullable=True)
    lighting_score = Column(Float, nullable=True)
    composition_score = Column(Float, nullable=True)
    subject_clarity_score = Column(Float, nullable=True)
    face_quality_score = Column(Float, nullable=True)
    visual_appeal_score = Column(Float, nullable=True)
    technical_quality_score = Column(Float, nullable=True)
    
    is_usable = Column(Boolean, default=True)
    reason = Column(String, nullable=True)
    
    # Post-processing values
    similarity_group = Column(String, nullable=True)
    recommendation = Column(String, nullable=True)  # e.g., 'keep', 'remove', 'replace'
    final_score = Column(Float, nullable=True)
    
    image = relationship("Image", back_populates="analysis")
