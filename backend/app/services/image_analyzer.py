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
            async with CPU_INFERENCE_SEMAPHORE:
                tech_data = await asyncio.to_thread(technical_analyzer.analyze, image_bytes)

                if tech_data.get("is_corrupted"):
                    logger.error(f"Image {image.id} is corrupted or invalid.")
                    image.status = "failed"
                    await db.commit()
                    return

                nima_data = await asyncio.to_thread(nima_service.analyze_image, image_bytes)

            # --- Build analysis_data dict ---
            # NIMA aesthetic score is used ONCE as visual_appeal only.
            # composition and lighting are derived independently from technical signals
            # so the same number does NOT get triple-counted.
            aesthetic_score = nima_data.get("aesthetic_score", 50.0)

            # Composition proxy: balanced blend of sharpness + exposure quality.
            # Higher sharpness + balanced exposure → better composition quality signal.
            sharpness = tech_data.get("sharpness", 50.0)
            exposure = tech_data.get("exposure", 50.0)
            # Exposure quality bell (peaks around 55-65): penalise extremes
            exp_quality = max(0.0, 100.0 - abs(exposure - 60.0) * 1.6)
            composition_proxy = round(sharpness * 0.50 + exp_quality * 0.50, 2)

            # Lighting proxy: directly from exposure quality
            lighting_proxy = round(exp_quality, 2)

            # Face quality from technical analyzer (None if no face detected)
            face_quality = tech_data.get("face_quality")   # float 0-100 or None
            face_detected = tech_data.get("face_detected", False)

            analysis_data = {
                "sharpness":         sharpness,
                "blur":              tech_data.get("blur", 50.0),
                "exposure":          exposure,
                "visual_appeal":     aesthetic_score,      # NIMA used once only
                "composition":       composition_proxy,    # independent proxy
                "lighting":          lighting_proxy,       # independent proxy
                "subject_clarity":   sharpness,            # best proxy without semantic model
                "technical_quality": sharpness,
                "face_quality":      face_quality,         # None or 0-100
            }

            # Python deterministic scoring
            final_score = ranker.calculate_deterministic_score(analysis_data, is_usable=True)

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
                reason="Local ML pipeline analysis",
                final_score=final_score,
            )

            db.add(analysis)
            image.status = "analyzed"
            image.retry_after_s = None
            await db.commit()

            logger.info(
                f"Image {image.id} analyzed: final_score={final_score:.1f}, "
                f"sharpness={sharpness:.1f}, exposure={exposure:.1f}, "
                f"aesthetic={aesthetic_score:.1f}, face_detected={face_detected}, "
                f"face_quality={face_quality}"
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
