"""
Analysis Pipeline — two-stage smart selection.

SIMILARITY_THRESHOLD (default 0.95):
  Only images that are nearly frame-identical are grouped together.
  - 0.95: Only near-identical crops, same-frame reshots
  - 0.90: Would also group different poses of same people → too aggressive
  At 0.95, three photos of the same family in slightly different poses
  stay as SEPARATE groups and all get a quality decision.

Stage 1: Per-group winner selection
  Within each similarity group, keep the highest-scoring image.
  Mark weaker near-duplicates as removed.

Stage 2: Two-stage quality decision on group winners
  QUALITY_FLOOR (25): below this = clearly unusable (corrupted / completely black / severe blur)
  QUALITY_THRESHOLD (38): above this = always keep
  Between 25-38: keep if it is the relative winner of its group.
  This means any photo that is the best available version of its scene is kept.
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
            # --- Step 1: Wait for background ML processing (max 180 s) ---
            # Each image is analyzed in a background task started at upload time.
            # We just wait for all "uploaded" images to become "analyzed" or "failed".
            waited = 0
            while waited < 180:
                stmt = select(Image).where(
                    Image.project_id == project_id,
                    Image.status == "uploaded"
                )
                result = await db.execute(stmt)
                pending = result.scalars().all()
                if not pending:
                    break
                await asyncio.sleep(1)
                waited += 1

            # Fetch successfully analyzed images
            stmt = select(Image).where(
                Image.project_id == project_id,
                Image.status == "analyzed"
            )
            result = await db.execute(stmt)
            analyzed_images = result.scalars().all()

            logger.info(
                f"Project {project_id}: {len(analyzed_images)} images analyzed, "
                f"waited {waited}s for background tasks"
            )

            if not analyzed_images:
                logger.warning(f"No analyzed images for project {project_id}")
                return

            # Fetch all analysis records in one query (no N+1)
            stmt = select(ImageAnalysis).where(
                ImageAnalysis.image_id.in_([img.id for img in analyzed_images])
            )
            result = await db.execute(stmt)
            valid_analyses = result.scalars().all()

            logger.info(
                f"Loaded {len(valid_analyses)} analysis records for project {project_id}. "
                f"Scores: {sorted([round(a.final_score or 0, 1) for a in valid_analyses], reverse=True)}"
            )

            # --- Step 2: Similarity grouping ---
            # threshold=0.95 means only near-identical frames are grouped.
            # Different poses of the same people → separate groups → all get quality decision.
            groups = similarity_service.cluster_images(analyzed_images)

            logger.info(
                f"Similarity grouping: {len(analyzed_images)} images → {len(groups)} groups "
                f"(threshold={settings.SIMILARITY_THRESHOLD}, "
                f"real_embeddings={similarity_service.is_real_implementation()})"
            )

            analysis_by_image_id: dict[str, ImageAnalysis] = {
                a.image_id: a for a in valid_analyses
            }

            # --- Step 3: Best-of-group selection ---
            # For each similarity group, pick the highest-scoring image.
            # Weaker near-duplicates get marked "remove" immediately.
            group_winners: list[ImageAnalysis] = []

            for group_id, group_imgs in groups.items():
                group_analyses = [
                    analysis_by_image_id[img.id]
                    for img in group_imgs
                    if img.id in analysis_by_image_id
                ]
                if not group_analyses:
                    continue

                # Sort descending by score
                group_analyses.sort(key=lambda a: a.final_score or 0.0, reverse=True)

                best = group_analyses[0]
                best.similarity_group = group_id

                if len(group_analyses) > 1:
                    scores = [f"{a.image_id[:6]}={a.final_score:.1f}" for a in group_analyses]
                    logger.info(
                        f"Group {group_id}: {len(group_analyses)} near-identical photos. "
                        f"Keeping best, removing {len(group_analyses)-1}. Scores: {scores}"
                    )

                # Mark weaker near-duplicates as removed
                for other in group_analyses[1:]:
                    other.similarity_group = group_id
                    other.recommendation = "remove"

                group_winners.append(best)

            # --- Step 4: Two-stage quality decision on group winners ---
            QUALITY_THRESHOLD = settings.QUALITY_THRESHOLD  # always keep above this
            QUALITY_FLOOR = settings.QUALITY_FLOOR          # always reject below this

            for winner in group_winners:
                score = winner.final_score or 0.0
                img_short = winner.image_id[:8]

                # Gate A: corrupted / flagged not usable
                if not winner.is_usable:
                    winner.recommendation = "remove"
                    logger.info(f"[REMOVE] {img_short}: not usable")

                # Gate B: below absolute floor → clearly bad (corrupted/black/extreme blur)
                elif score < QUALITY_FLOOR:
                    winner.recommendation = "remove"
                    logger.info(
                        f"[REMOVE] {img_short}: score={score:.1f} < floor={QUALITY_FLOOR}"
                    )

                # Gate C: above quality threshold → always keep
                elif score >= QUALITY_THRESHOLD:
                    winner.recommendation = "keep"
                    logger.info(
                        f"[KEEP]   {img_short}: score={score:.1f} >= threshold={QUALITY_THRESHOLD}"
                    )

                # Gate D: between floor and threshold → keep as relative winner
                # This image is the best available version of its scene.
                # If it survived grouping, it represents a unique shot worth keeping.
                else:
                    winner.recommendation = "keep"
                    logger.info(
                        f"[KEEP]   {img_short}: score={score:.1f} — best of its scene "
                        f"(floor={QUALITY_FLOOR}, threshold={QUALITY_THRESHOLD})"
                    )

            # Catch any analysis records that were never assigned a recommendation
            for analysis in valid_analyses:
                if analysis.recommendation is None:
                    analysis.recommendation = "remove"
                    logger.warning(
                        f"[REMOVE] {analysis.image_id[:8]}: no recommendation assigned"
                    )

            # --- Step 5: Summary ---
            keep_analyses = [a for a in valid_analyses if a.recommendation == "keep"]
            remove_analyses = [a for a in valid_analyses if a.recommendation == "remove"]

            logger.info(
                f"Pipeline complete [{project_id[:8]}]: "
                f"{len(valid_analyses)} analyzed → "
                f"{len(keep_analyses)} KEPT, {len(remove_analyses)} removed. "
                f"Kept scores: {sorted([round(a.final_score or 0, 1) for a in keep_analyses], reverse=True)}"
            )

            # --- Step 6: Commit ---
            await db.commit()

        except Exception as e:
            logger.error(f"Pipeline error for project {project_id}: {e}", exc_info=True)
            await db.rollback()
