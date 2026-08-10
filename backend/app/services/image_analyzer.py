import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from app.services.image_ranker import ranker
from app.services.technical_analyzer import technical_analyzer
from app.services.nima_service import nima_service
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Bound CPU inference to prevent overloading Railway's 1vCPU limit
from app.core.config import settings
CPU_INFERENCE_SEMAPHORE = asyncio.BoundedSemaphore(settings.MAX_ML_CONCURRENCY)


async def analyze_single_image_background(image_id: str, image_bytes: bytes) -> None:
    async with AsyncSessionLocal() as db:
        try:
            # Fetch the image record
            result = await db.execute(select(Image).where(Image.id == image_id))
            image = result.scalars().first()
            if not image:
                logger.error(f"Image {image_id} not found for background analysis.")
                return

            # Fast technical checks and NIMA (CPU-bounded + Memory-bounded)
            # BYPASS: User requested safe mode without rejection/ML processing
            # We skip the heavy ML processing completely to guarantee stability on mobile
            
            sharpness = 100.0
            exposure = 50.0
            aesthetic_score = 100.0
            composition_proxy = 100.0
            lighting_proxy = 100.0
            face_quality = 100.0
            face_detected = True

            analysis_data = {
                "sharpness":         sharpness,
                "blur":              0.0,
                "exposure":          exposure,
                "visual_appeal":     aesthetic_score,
                "composition":       composition_proxy,
                "lighting":          lighting_proxy,
                "subject_clarity":   sharpness,
                "technical_quality": sharpness,
                "face_quality":      face_quality,
            }

            # Python deterministic scoring (will be 100)
            final_score = 100.0

            # Build ImageAnalysis record
            analysis = ImageAnalysis(
                image_id=image.id,
                sharpness_score=sharpness,
                blur_score=analysis_data["blur"],
                exposure_score=exposure,
                lighting_score=lighting_proxy,
                composition_score=composition_proxy,
                subject_clarity_score=sharpness,
                face_quality_score=face_quality,
                visual_appeal_score=aesthetic_score,
                technical_quality_score=sharpness,
                is_usable=True,
                reason="Auto-kept (Safe mode)",
                final_score=final_score,
            )

            db.add(analysis)
            image.status = "analyzed"
            image.retry_after_s = None
            await db.commit()

            logger.info(
                f"Image {image.id} analyzed (SAFE MODE): final_score={final_score:.1f}"
            )

        except Exception as e:
            logger.error(f"Failed to analyze image {image_id}: {e}")
            try:
                result = await db.execute(select(Image).where(Image.id == image_id))
                err_image = result.scalars().first()
                if err_image:
                    err_image.status = "failed"
                    err_image.retry_after_s = None
                    await db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to mark image {image_id} as failed: {inner_e}")
