"""
ImageRanker: Deterministic Python scoring engine.

ARCHITECTURE:
  Groq provides raw visual observations (sharpness, blur, exposure, etc.)
  Python calculates ALL derived scores and the final ranking decision.

AUDIT of OLD formula (recorded before change):
  score = sum(val * weight for key in weights) / active_weights
  Weights: sharpness=0.25, technical_quality=0.20, composition=0.15,
           lighting=0.15, subject_clarity=0.10, face_quality=0.10, visual_appeal=0.05
  Weaknesses:
    1. No bad-image penalty gate: blur=95 still ranked highly via sharpness weight
    2. blur_score field from Groq completely ignored
    3. face_quality=None redistributes weight across ALL other fields, distorting landscapes
    4. No normalization: raw Groq 0-100 trusted absolutely
    5. Flat single weighted average: no separation of technical vs aesthetic quality
    6. Single unusable=False multiplied by 0.1 — too coarse, doesn't scale to partial defects

NEW FORMULA:
  technical_score  = f(sharpness, blur, exposure, subject_clarity)  → 0-100
  aesthetic_score  = f(composition, lighting, visual_appeal)         → 0-100
  face_score       = f(face_quality) if faces present, else None     → 0-100
  
  final = technical * 0.55 + aesthetic * 0.30 + face * 0.15  (if faces)
  final = technical * 0.60 + aesthetic * 0.40               (no faces, redistributed)
  
  PENALTY gates applied AFTER base score:
    - severe blur:       if blur >= 70 → multiply by 0.4
    - bad exposure:      if exposure < 20 or > 95 → multiply by 0.55
    - unusable flag:     multiply by 0.3
    - near-zero subject: if subject_clarity < 15 → multiply by 0.6
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Thresholds for hard penalty gates
BLUR_PENALTY_THRESHOLD = 70       # blur_score from Groq (higher = more blurry)
OVEREXPOSURE_THRESHOLD = 95       # exposure > this = blown-out
UNDEREXPOSURE_THRESHOLD = 20      # exposure < this = too dark
SUBJECT_CLARITY_MIN = 15          # below this = subject not visible
SHARPNESS_ACCEPTABLE_MIN = 20     # below this = definitely soft/blurry


class ImageRanker:
    """
    Deterministic scoring engine.
    Inputs: raw Groq analysis dict.
    Output: float final_score in [0, 100].
    
    Design rule: Groq provides observations; Python makes the decision.
    """

    def _safe(self, v, default: float = 50.0) -> float:
        """Safely extract a float from analysis data."""
        if v is None:
            return default
        try:
            return max(0.0, min(100.0, float(v)))
        except (TypeError, ValueError):
            return default

    def calculate_technical_score(self, data: dict) -> float:
        """
        Technical quality: sharpness, blur (inverted), exposure, subject clarity.
        Sharpness and non-blurriness are the two most important technical factors.
        
        blur_score from Groq means: higher = more blur. We invert it.
        sharpness_score means: higher = sharper. Direct.
        """
        sharpness   = self._safe(data.get("sharpness"), 50.0)
        blur        = self._safe(data.get("blur"), 0.0)          # Higher = more blurry
        exposure    = self._safe(data.get("exposure"), 50.0)
        subject     = self._safe(data.get("subject_clarity"), 50.0)
        technical   = self._safe(data.get("technical_quality"), 50.0)

        # blur is inverted: a blur score of 80 → sharpness contribution of 20
        blur_inv = 100.0 - blur

        # Combine sharpness with inverted-blur for a robust focus score
        focus_score = (sharpness * 0.60 + blur_inv * 0.40)

        # Exposure quality: penalize both extremes (dark and blown-out)
        # Model as a bell around 65 (slightly warm exposure preferred)
        exposure_quality = max(0.0, 100.0 - abs(exposure - 65) * 1.8)
        exposure_quality = min(100.0, exposure_quality)

        technical_score = (
            focus_score          * 0.40 +
            exposure_quality     * 0.25 +
            subject              * 0.20 +
            technical            * 0.15
        )
        return round(technical_score, 2)

    def calculate_aesthetic_score(self, data: dict) -> float:
        """
        Aesthetic quality: composition, lighting quality, visual appeal.
        These are subjective but important for the final ranking.
        """
        composition   = self._safe(data.get("composition"), 50.0)
        lighting      = self._safe(data.get("lighting"), 50.0)
        visual_appeal = self._safe(data.get("visual_appeal"), 50.0)

        aesthetic_score = (
            composition   * 0.45 +
            lighting      * 0.35 +
            visual_appeal * 0.20
        )
        return round(aesthetic_score, 2)

    def calculate_face_score(self, data: dict) -> Optional[float]:
        """
        Face quality score — only meaningful if faces are detected.
        Returns None if no face is present (caller redistributes weight safely).
        """
        face_val = data.get("face_quality")
        if face_val is None:
            return None
        return round(self._safe(face_val, 50.0), 2)

    def apply_penalty_gates(self, base_score: float, data: dict, is_usable: bool) -> float:
        """
        Apply hard penalty multipliers for severe technical defects.
        Each gate is independent — penalties stack multiplicatively.
        
        We do NOT reject images outright; we penalize them so they rank lower.
        This allows a very blurry image to still be shown, just ranked near the bottom.
        """
        score = base_score
        penalties_applied = []

        blur = self._safe(data.get("blur"), 0.0)
        exposure = self._safe(data.get("exposure"), 50.0)
        sharpness = self._safe(data.get("sharpness"), 50.0)
        subject = self._safe(data.get("subject_clarity"), 50.0)

        # Gate 1: Severe blur (blur_score >= 70 from Groq)
        if blur >= BLUR_PENALTY_THRESHOLD:
            score *= 0.40
            penalties_applied.append(f"severe_blur({blur:.0f})")

        # Gate 2: Very low sharpness even without high blur score
        elif sharpness < SHARPNESS_ACCEPTABLE_MIN:
            score *= 0.55
            penalties_applied.append(f"low_sharpness({sharpness:.0f})")

        # Gate 3: Overexposure (blown out)
        if exposure > OVEREXPOSURE_THRESHOLD:
            score *= 0.55
            penalties_applied.append(f"overexposed({exposure:.0f})")

        # Gate 4: Severe underexposure (too dark)
        elif exposure < UNDEREXPOSURE_THRESHOLD:
            score *= 0.60
            penalties_applied.append(f"underexposed({exposure:.0f})")

        # Gate 5: Subject not visible
        if subject < SUBJECT_CLARITY_MIN:
            score *= 0.60
            penalties_applied.append(f"no_subject({subject:.0f})")

        # Gate 6: Groq explicitly flagged as unusable
        if not is_usable:
            score *= 0.30
            penalties_applied.append("groq_unusable")

        if penalties_applied:
            logger.debug(f"Penalties applied: {', '.join(penalties_applied)} → {base_score:.1f} → {score:.1f}")

        return round(max(0.0, min(100.0, score)), 2)

    def calculate_deterministic_score(self, analysis_data: dict, is_usable: bool = True) -> float:
        """
        Main entry point: calculate final_score from raw Groq analysis dict.
        
        Returns a float in [0, 100].
        All decisions are deterministic Python — Groq provides inputs, not the verdict.
        """
        technical = self.calculate_technical_score(analysis_data)
        aesthetic = self.calculate_aesthetic_score(analysis_data)
        face      = self.calculate_face_score(analysis_data)

        # Blend technical + aesthetic + face with safe weight redistribution
        if face is not None:
            # Face detected: technical=55%, aesthetic=30%, face=15%
            base_score = technical * 0.55 + aesthetic * 0.30 + face * 0.15
        else:
            # No face: redistribute face weight to technical (60%) and aesthetic (40%)
            base_score = technical * 0.60 + aesthetic * 0.40

        # Apply penalty gates for severe defects
        final_score = self.apply_penalty_gates(base_score, analysis_data, is_usable)

        logger.debug(
            f"Score breakdown — technical={technical:.1f}, aesthetic={aesthetic:.1f}, "
            f"face={face}, base={base_score:.1f}, final={final_score:.1f}, "
            f"is_usable={is_usable}"
        )

        return final_score

    def compare_for_group_best(self, a: dict, b: dict) -> int:
        """
        Compare two analysis dicts to determine which is the better image in a group.
        Returns: 1 if a is better, -1 if b is better, 0 if equal.
        Used for best-of-group selection.
        """
        score_a = a.get("final_score") or 0.0
        score_b = b.get("final_score") or 0.0

        # Use score differential as primary
        if abs(score_a - score_b) > 2.0:
            return 1 if score_a > score_b else -1

        # Tiebreak on sharpness (most impactful for photo quality)
        sharp_a = self._safe(a.get("sharpness_score"), 50.0)
        sharp_b = self._safe(b.get("sharpness_score"), 50.0)
        if abs(sharp_a - sharp_b) > 5.0:
            return 1 if sharp_a > sharp_b else -1

        # Second tiebreak: exposure quality
        exp_a = self._safe(a.get("exposure_score"), 50.0)
        exp_b = self._safe(b.get("exposure_score"), 50.0)
        exp_qual_a = 100.0 - abs(exp_a - 65) * 1.8
        exp_qual_b = 100.0 - abs(exp_b - 65) * 1.8
        return 1 if exp_qual_a >= exp_qual_b else -1

    # Legacy compatibility: old pipeline called this with just analysis_data
    # Keep the same signature, add is_usable default
    def group_similar_images(self, analyses):
        """Delegated to similarity_service in the pipeline."""
        pass


ranker = ImageRanker()
