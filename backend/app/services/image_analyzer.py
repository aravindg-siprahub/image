"""
analyze_single_image:
  - Generates a temporary signed URL for the image from Supabase Storage.
  - Sends the image to Groq for visual analysis.
  - Calls the deterministic Python ranker to calculate the final score.
  - Stores the ImageAnalysis record (no commit here — done in pipeline for batch).
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from app.services.groq_service import groq_manager, QuotaExhaustedError
from app.services.image_ranker import ranker
from app.services.storage_service import storage_service
import os

logger = logging.getLogger(__name__)

import asyncio

async def analyze_single_image(db: AsyncSession, image: Image) -> ImageAnalysis | None:
    try:
        # Construct proxy URL for Groq to fetch the image from our backend
        base_api_url = os.environ.get("NEXT_PUBLIC_API_URL", "http://localhost:8080/api/v1").rstrip("/")
        proxy_url = f"{base_api_url}/images/proxy/{image.id}.jpg"

        # Step 2: Pass the proxy URL to Groq
        analysis_data = await groq_manager.analyze_image(proxy_url)

        # Step 3: Extract is_usable from Groq observation
        is_usable = bool(analysis_data.get("is_usable", True))

        # Step 4: Calculate final score deterministically in Python
        # Groq provides raw visual observations; ranker makes the scoring decision.
        final_score = ranker.calculate_deterministic_score(analysis_data, is_usable=is_usable)

        # Step 5: Build the ImageAnalysis record
        analysis = ImageAnalysis(
            image_id=image.id,
            sharpness_score=analysis_data.get("sharpness"),
            blur_score=analysis_data.get("blur"),
            exposure_score=analysis_data.get("exposure"),
            lighting_score=analysis_data.get("lighting"),
            composition_score=analysis_data.get("composition"),
            subject_clarity_score=analysis_data.get("subject_clarity"),
            face_quality_score=analysis_data.get("face_quality"),   # None if no face
            visual_appeal_score=analysis_data.get("visual_appeal"),
            technical_quality_score=analysis_data.get("technical_quality"),
            is_usable=is_usable,
            reason=analysis_data.get("reason"),
            final_score=final_score,
        )

        db.add(analysis)
        image.status = "analyzed"
        image.retry_after_s = None

        logger.info(
            f"Image {image.id} analyzed: final_score={final_score:.1f}, "
            f"sharpness={analysis_data.get('sharpness')}, blur={analysis_data.get('blur')}, "
            f"is_usable={is_usable}"
        )

        # Do NOT commit here — pipeline does a batch commit
        return analysis

    except QuotaExhaustedError as e:
        # Distinct from generic failure so the Results UI can show quota messaging.
        image.status = "quota_exhausted"
        image.retry_after_s = e.retry_after_s
        logger.error(
            f"Quota exhausted for image {image.id}: retry_after_s={e.retry_after_s}"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to analyze image {image.id}: {e}")
        image.status = "failed"
        image.retry_after_s = None
        return None
