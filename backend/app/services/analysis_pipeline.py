"""
Analysis Pipeline:
  1. Fetch all uploaded images for the project.
  2. Run Groq visual analysis in parallel (bounded by GROQ_MAX_CONCURRENCY semaphore).
  3. Commit all analysis records.
  4. Group similar images (currently each-image-its-own-group stub).
  5. For each group, mark the best image as 'keep' and others as 'replace'.
  6. Images with is_usable=False get 'remove' regardless.
  7. The image with the highest final_score across ALL groups gets tagged as the top pick.
  8. Commit final recommendations.
"""
import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from app.services.image_analyzer import analyze_single_image
from app.services.similarity_service import similarity_service
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def run_analysis_pipeline(project_id: str):
    async with AsyncSessionLocal() as db:
        try:
            # --- Step 1: Fetch images to analyze ---
            stmt = select(Image).where(
                Image.project_id == project_id,
                Image.status == "uploaded"
            )
            result = await db.execute(stmt)
            images = result.scalars().all()

            if not images:
                logger.info(f"No pending images for project {project_id}")
                return

            logger.info(f"Starting parallel analysis for {len(images)} images in project {project_id}")

            # --- Step 2: Parallel Groq analysis (bounded by semaphore in groq_service) ---
            tasks = [analyze_single_image(db, img) for img in images]
            analyses = await asyncio.gather(*tasks, return_exceptions=False)

            # Collect valid (non-None) analysis results
            valid_analyses = [a for a in analyses if a is not None]
            failed_count = len(analyses) - len(valid_analyses)

            if failed_count > 0:
                logger.warning(f"{failed_count} images failed analysis in project {project_id}")

            # --- Step 3: Commit all analysis records ---
            await db.commit()

            if not valid_analyses:
                logger.warning(f"All images failed analysis for project {project_id}")
                return

            # --- Step 4: Similarity grouping ---
            # Use only successfully analyzed images
            analyzed_images = [img for img in images if img.status == "analyzed"]
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
            # Each similarity group contributes exactly ONE candidate (its best image).
            # Near-duplicates (weaker images in the same group) are always removed.
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
            # No fixed count cap. Each image earns its place independently.
            # QUALITY_THRESHOLD = 65: reflects genuinely usable, well-exposed, reasonably sharp photo.
            QUALITY_THRESHOLD = 65.0
            # Fallback threshold: used only if zero images pass the strict bar, to ensure
            # at least 1 result is shown rather than an empty gallery.
            FALLBACK_THRESHOLD = 50.0

            for winner in group_winners:
                score = winner.final_score or 0.0
                if not winner.is_usable:
                    winner.recommendation = "remove"
                elif score >= QUALITY_THRESHOLD:
                    winner.recommendation = "keep"
                else:
                    winner.recommendation = "remove"

            # Safety fallback: if nothing passed, lower the bar once
            kept = [a for a in group_winners if a.recommendation == "keep"]
            if not kept:
                for winner in group_winners:
                    if winner.is_usable and (winner.final_score or 0.0) >= FALLBACK_THRESHOLD:
                        winner.recommendation = "keep"
                        logger.info(
                            f"Fallback: keeping image {winner.image_id[:8]} "
                            f"with score {winner.final_score:.1f} (below strict threshold)"
                        )

            # Any analysis not assigned a recommendation yet → remove
            for analysis in valid_analyses:
                if analysis.recommendation is None:
                    analysis.recommendation = "remove"



            # --- Step 7: Identify the global top pick ---
            # The top pick is the highest final_score image among all 'keep' recommendations
            keep_analyses = [a for a in valid_analyses if a.recommendation == "keep"]
            if keep_analyses:
                top_pick = max(keep_analyses, key=lambda a: a.final_score or 0.0)
                logger.info(
                    f"Top pick: image_id={top_pick.image_id}, "
                    f"final_score={top_pick.final_score:.1f}, "
                    f"group={top_pick.similarity_group}"
                )
            else:
                # Fallback: if no image is 'keep', top pick = highest scoring overall
                top_pick = max(valid_analyses, key=lambda a: a.final_score or 0.0)
                top_pick.recommendation = "keep"
                logger.warning(f"No 'keep' images found; fallback top pick: {top_pick.image_id}")

            # --- Step 8: Final commit ---
            await db.commit()

            # Log final ranking for debugging
            sorted_all = sorted(valid_analyses, key=lambda a: a.final_score or 0.0, reverse=True)
            logger.info(f"Final ranking for project {project_id}:")
            for rank, a in enumerate(sorted_all, 1):
                logger.info(
                    f"  #{rank} image_id={a.image_id[:8]} "
                    f"score={a.final_score:.1f} "
                    f"rec={a.recommendation} "
                    f"group={a.similarity_group}"
                )

            logger.info(
                f"Pipeline complete for project {project_id}: "
                f"{len(valid_analyses)} analyzed, {failed_count} failed, "
                f"{len(keep_analyses)} recommended to keep"
            )

        except Exception as e:
            logger.error(f"Pipeline error for project {project_id}: {e}", exc_info=True)
            await db.rollback()
