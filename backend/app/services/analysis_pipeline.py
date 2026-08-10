"""
Analysis Pipeline:
  1. Wait for all images to finish background ML processing.
  2. Group similar images (currently each-image-its-own-group stub).
  3. For each group, mark the best image as 'keep' and others as 'replace'.
  4. Images with is_usable=False get 'remove' regardless.
  5. The image with the highest final_score across ALL groups gets tagged as the top pick.
  6. Commit final recommendations.
"""
import asyncio
import logging
from sqlalchemy import select
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from app.services.similarity_service import similarity_service
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def run_analysis_pipeline(project_id: str):
    async with AsyncSessionLocal() as db:
        try:
            # --- Step 1: Wait for background processing to finish ---
            # Max wait time 30 seconds
            for _ in range(30):
                stmt = select(Image).where(
                    Image.project_id == project_id,
                    Image.status == "uploaded"
                )
                result = await db.execute(stmt)
                pending_images = result.scalars().all()
                if not pending_images:
                    break
                await asyncio.sleep(1)

            # Fetch all successfully analyzed images
            stmt = select(Image).where(
                Image.project_id == project_id,
                Image.status == "analyzed"
            )
            result = await db.execute(stmt)
            analyzed_images = result.scalars().all()

            if not analyzed_images:
                logger.info(f"No analyzed images for project {project_id}")
                return

            # Fetch all analysis records
            stmt = select(ImageAnalysis).where(
                ImageAnalysis.image_id.in_([img.id for img in analyzed_images])
            )
            result = await db.execute(stmt)
            valid_analyses = result.scalars().all()

            # --- Step 4: Similarity grouping ---
            groups = similarity_service.cluster_images(analyzed_images)

            logger.info(
                f"Similarity grouping: {len(analyzed_images)} images → {len(groups)} groups "
                f"(real_embeddings={similarity_service.is_real_implementation()})"
            )

            # Build a lookup from image_id → analysis for efficient access
            analysis_by_image_id: dict[str, ImageAnalysis] = {
                a.image_id: a for a in valid_analyses
            }

            # --- Step 5: Best-of-group selection ---
            group_winners: list[ImageAnalysis] = []

            for group_id, group_imgs in groups.items():
                group_analyses = [
                    analysis_by_image_id[img.id]
                    for img in group_imgs
                    if img.id in analysis_by_image_id
                ]
                if not group_analyses:
                    continue

                # Sort group by final_score descending — best first
                group_analyses.sort(key=lambda a: a.final_score or 0.0, reverse=True)

                best = group_analyses[0]
                best.similarity_group = group_id

                # Mark all weaker near-duplicates as removed immediately
                for other in group_analyses[1:]:
                    other.similarity_group = group_id
                    other.recommendation = "remove"

                # Best candidate moves on to quality threshold check
                group_winners.append(best)

            # --- Step 5b: Quality threshold — keep EVERY winner that is good enough ---
            QUALITY_THRESHOLD = 60.0

            for winner in group_winners:
                score = winner.final_score or 0.0
                if not winner.is_usable:
                    winner.recommendation = "remove"
                elif score >= QUALITY_THRESHOLD:
                    winner.recommendation = "keep"
                else:
                    winner.recommendation = "remove"

            # Any analysis not assigned a recommendation yet → remove
            for analysis in valid_analyses:
                if analysis.recommendation is None:
                    analysis.recommendation = "remove"

            # --- Step 7: Identify the global top pick ---
            keep_analyses = [a for a in valid_analyses if a.recommendation == "keep"]
            if keep_analyses:
                top_pick = max(keep_analyses, key=lambda a: a.final_score or 0.0)
                logger.info(
                    f"Top pick: image_id={top_pick.image_id}, "
                    f"final_score={top_pick.final_score:.1f}, "
                    f"group={top_pick.similarity_group}"
                )
            else:
                logger.info("No images met the quality threshold. Returning empty selection.")

            # --- Step 8: Final commit ---
            await db.commit()

            logger.info(
                f"Pipeline complete for project {project_id}: "
                f"{len(valid_analyses)} analyzed, "
                f"{len(keep_analyses)} recommended to keep"
            )

        except Exception as e:
            logger.error(f"Pipeline error for project {project_id}: {e}", exc_info=True)
            await db.rollback()
