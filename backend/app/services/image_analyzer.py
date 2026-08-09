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
from app.services.groq_service import groq_manager
from app.services.image_ranker import ranker
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)


async def analyze_single_image(db: AsyncSession, image: Image) -> ImageAnalysis | None:
    try:
        # Step 1: Generate a short-lived signed URL (5 minutes is enough for Groq fetch)
        signed_url = storage_service.supabase.storage.from_(
            storage_service.bucket_name
        ).create_signed_url(image.storage_path, 300)

        if isinstance(signed_url, dict):
            url_to_use = signed_url.get("signedURL") or signed_url.get("signed_url")
        else:
            url_to_use = signed_url

        if not url_to_use:
            logger.error(f"Failed to create signed URL for image {image.id}")
            image.status = "failed"
            return None

        # Step 2: Send to Groq for visual analysis
        logger.info(f"Analyzing image {image.id} with Groq...")
        analysis_data = await groq_manager.analyze_image(url_to_use)

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

        logger.info(
            f"Image {image.id} analyzed: final_score={final_score:.1f}, "
            f"sharpness={analysis_data.get('sharpness')}, blur={analysis_data.get('blur')}, "
            f"is_usable={is_usable}"
        )

        # Do NOT commit here — pipeline does a batch commit
        return analysis

    except Exception as e:
        logger.error(f"Failed to analyze image {image.id}: {e}")
        image.status = "failed"
        return None
