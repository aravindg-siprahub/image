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
CPU_INFERENCE_SEMAPHORE = asyncio.BoundedSemaphore(4)

async def analyze_single_image_background(image_id: str, image_bytes: bytes) -> None:
    async with AsyncSessionLocal() as db:
        try:
            # Fetch the image record
            result = await db.execute(select(Image).where(Image.id == image_id))
            image = result.scalars().first()
            if not image:
                logger.error(f"Image {image_id} not found for background analysis.")
                return

            # Fast technical checks
            tech_data = await asyncio.to_thread(technical_analyzer.analyze, image_bytes)
            
            if tech_data.get("is_corrupted"):
                logger.error(f"Image {image.id} is corrupted or invalid.")
                image.status = "failed"
                await db.commit()
                return

            # NIMA MobileNet aesthetic check
            async with CPU_INFERENCE_SEMAPHORE:
                nima_data = await asyncio.to_thread(nima_service.analyze_image, image_bytes)
            
            # Merge data for the ranker
            analysis_data = {
                "sharpness": tech_data.get("sharpness", 50.0),
                "blur": tech_data.get("blur", 50.0),
                "exposure": tech_data.get("exposure", 50.0),
                "visual_appeal": nima_data.get("aesthetic_score", 50.0),
                # Composition/lighting mapped to aesthetic score for ranker compatibility
                "composition": nima_data.get("aesthetic_score", 50.0), 
                "lighting": nima_data.get("aesthetic_score", 50.0),
                # Subject clarity mapped to sharpness for now since we lack semantic models
                "subject_clarity": tech_data.get("sharpness", 50.0),
                "technical_quality": tech_data.get("sharpness", 50.0),
            }

            # Python deterministic scoring
            final_score = ranker.calculate_deterministic_score(analysis_data, is_usable=True)

            # Build ImageAnalysis record
            analysis = ImageAnalysis(
                image_id=image.id,
                sharpness_score=analysis_data.get("sharpness"),
                blur_score=analysis_data.get("blur"),
                exposure_score=analysis_data.get("exposure"),
                lighting_score=analysis_data.get("lighting"),
                composition_score=analysis_data.get("composition"),
                subject_clarity_score=analysis_data.get("subject_clarity"),
                face_quality_score=None,
                visual_appeal_score=analysis_data.get("visual_appeal"),
                technical_quality_score=analysis_data.get("technical_quality"),
                is_usable=True,
                reason="Local ML pipeline analysis",
                final_score=final_score,
            )

            db.add(analysis)
            image.status = "analyzed"
            image.retry_after_s = None
            await db.commit()

            logger.info(
                f"Image {image.id} analyzed locally: final_score={final_score:.1f}, "
                f"blur={analysis_data['blur']}, aesthetic={analysis_data['visual_appeal']}"
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
