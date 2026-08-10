"""
Analysis Pipeline — two-stage smart selection.

Stage 1: Absolute floor gate (QUALITY_FLOOR = 35)
  Any image below this is clearly unusable (severe blur / bad exposure / corrupted).
  These are always rejected.

Stage 2: Relative quality threshold (QUALITY_THRESHOLD = 45)
  Images above this absolute threshold are always kept.
  Images between FLOOR and THRESHOLD:
    - If they are the BEST image in their similarity group → keep (relative winner).
    - Otherwise → remove (weaker duplicate/borderline shot).

This means:
  - A burst of 5 nearly-identical shots where all score 40-55:
      → the best one is kept (relative winner), the rest removed.
  - 5 clearly different photos all scoring 48:
      → all 5 are kept (all are relative winners of their own solo groups).
  - A photo scoring 30 (severe blur / black frame):
      → always rejected (below floor).
"""
import asyncio
import logging
from sqlalchemy import select
from app.models.image import Image
from app.models.image_analysis import ImageAnalysis
from app.services.similarity_service import similarity_service
from app.db.session import AsyncSessionLocal
from app.core.config import settings

logger = logging.getLogger(__name__)


async def run_analysis_pipeline(project_id: str):
    async with AsyncSessionLocal() as db:
        try:
            # --- Step 1: Wait for background ML processing (max 30 s) ---
            for _ in range(30):
                stmt = select(Image).where(
                    Image.project_id == project_id,
                    Image.status == "uploaded"
                )
                result = await db.execute(stmt)
                pending = result.scalars().all()
                if not pending:
                    break
                await asyncio.sleep(1)

            # Fetch successfully analyzed images
            stmt = select(Image).where(
                Image.project_id == project_id,
                Image.status == "analyzed"
            )
            result = await db.execute(stmt)
            analyzed_images = result.scalars().all()

            if not analyzed_images:
                logger.info(f"No analyzed images for project {project_id}")
                return

            # Fetch all analysis records in one query (no N+1)
            stmt = select(ImageAnalysis).where(
                ImageAnalysis.image_id.in_([img.id for img in analyzed_images])
            )
            result = await db.execute(stmt)
            valid_analyses = result.scalars().all()

            # --- Step 2: Similarity grouping ---
            groups = similarity_service.cluster_images(analyzed_images)

            logger.info(
                f"Similarity grouping: {len(analyzed_images)} images → {len(groups)} groups "
                f"(real_embeddings={similarity_service.is_real_implementation()})"
            )

            analysis_by_image_id: dict[str, ImageAnalysis] = {
                a.image_id: a for a in valid_analyses
            }

            # --- Step 3: Best-of-group selection ---
            # Pick the best image from each similarity group.
            # Weaker near-duplicates in the same group → removed immediately.
            group_winners: list[ImageAnalysis] = []

            for group_id, group_imgs in groups.items():
                group_analyses = [
                    analysis_by_image_id[img.id]
                    for img in group_imgs
                    if img.id in analysis_by_image_id
                ]
                if not group_analyses:
                    continue

                # Sort by final_score descending
                group_analyses.sort(key=lambda a: a.final_score or 0.0, reverse=True)

                best = group_analyses[0]
                best.similarity_group = group_id

                # Mark weaker near-duplicates as removed
                for other in group_analyses[1:]:
                    other.similarity_group = group_id
                    other.recommendation = "remove"
                    logger.debug(
                        f"Removed near-duplicate image {other.image_id[:8]} "
                        f"(score={other.final_score:.1f}) from group {group_id}"
                    )

                group_winners.append(best)

            # --- Step 4: Two-stage quality decision ---
            QUALITY_THRESHOLD = settings.QUALITY_THRESHOLD  # keep if score >= this
            QUALITY_FLOOR = settings.QUALITY_FLOOR          # reject if score < this

            for winner in group_winners:
                score = winner.final_score or 0.0
                image_id_short = winner.image_id[:8]

                # Gate A: explicitly not usable (corrupted / flagged)
                if not winner.is_usable:
                    winner.recommendation = "remove"
                    logger.info(f"[REMOVE] {image_id_short}: not usable")

                # Gate B: below absolute floor → clearly unusable
                elif score < QUALITY_FLOOR:
                    winner.recommendation = "remove"
                    logger.info(
                        f"[REMOVE] {image_id_short}: score={score:.1f} below floor={QUALITY_FLOOR}"
                    )

                # Gate C: above quality threshold → definitely keep
                elif score >= QUALITY_THRESHOLD:
                    winner.recommendation = "keep"
                    logger.info(
                        f"[KEEP]   {image_id_short}: score={score:.1f} >= threshold={QUALITY_THRESHOLD}"
                    )

                # Gate D: between floor and threshold → relative winner
                # It survived similarity grouping, so it's the best available
                # version of this scene. Keep it.
                else:
                    winner.recommendation = "keep"
                    logger.info(
                        f"[KEEP]   {image_id_short}: score={score:.1f} is relative winner "
                        f"(floor={QUALITY_FLOOR}, threshold={QUALITY_THRESHOLD})"
                    )

            # Catch any analysis records that were never assigned
            for analysis in valid_analyses:
                if analysis.recommendation is None:
                    analysis.recommendation = "remove"

            # --- Step 5: Logging summary ---
            keep_analyses = [a for a in valid_analyses if a.recommendation == "keep"]
            remove_analyses = [a for a in valid_analyses if a.recommendation == "remove"]

            logger.info(
                f"Pipeline complete for project {project_id}: "
                f"{len(valid_analyses)} analyzed → "
                f"{len(keep_analyses)} kept, {len(remove_analyses)} removed"
            )

            if keep_analyses:
                top = max(keep_analyses, key=lambda a: a.final_score or 0.0)
                logger.info(
                    f"Top pick: image_id={top.image_id[:8]}, "
                    f"score={top.final_score:.1f}"
                )
            else:
                logger.info(
                    "No images met the quality floor. "
                    "All photos were too blurry, dark or corrupted."
                )

            # --- Step 6: Commit ---
            await db.commit()

        except Exception as e:
            logger.error(f"Pipeline error for project {project_id}: {e}", exc_info=True)
            await db.rollback()
