"""
SimilarityService: Real perceptual image similarity using pHash + color histograms.

EMBEDDING APPROACH:
  Perceptual Hash (pHash) + LAB Color Histogram — no external ML model required.

  Why pHash?
  - Standard algorithm for near-duplicate image detection (used in production by
    YouTube, Google Images, etc.)
  - Same image → identical 64-bit hash
  - Near-duplicate image → hash distance 0-6 bits (Hamming distance)
  - Completely different image → hash distance typically 20+ bits
  - Runs on CPU with only Pillow + numpy; zero model download/loading overhead
  - Threshold can be set by environment variable SIMILARITY_THRESHOLD

  Why LAB Color Histogram?
  - Supplements pHash to distinguish images that look similar in structure but
    differ in color/exposure (e.g., same scene shot day vs. night)
  - 16-bin histogram per channel in CIE-LAB space (perceptually uniform colorspace)

  Combined similarity (pHash=0.7, color=0.3):
  - 1.0 = identical image
  - 0.92+ = near-duplicate / same shot
  - 0.75-0.91 = similar composition
  - <0.75 = different images

ALGORITHM:
  For each pair of images:
    1. Compute pHash similarity: 1 - (hamming_bits / 64)
    2. Compute color histogram cosine similarity
    3. combined = 0.7 * phash_sim + 0.3 * color_sim

  Greedy clustering:
    - Start with first unassigned image as group seed
    - Any image with combined_similarity >= threshold → same group
    - Each image belongs to at most one group (greedy first-fit)

CONFIGURATION:
  SIMILARITY_THRESHOLD (env var, default 0.90):
    - 0.95: only near-identical crops/rotations
    - 0.90: safe near-duplicate detection (recommended)
    - 0.80: groups similar compositions

FILES CHANGED: similarity_service.py only
"""

import io
import logging
import asyncio
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Lazy imports — only loaded if Pillow/numpy are available
_PIL_AVAILABLE = False
try:
    from PIL import Image as PILImage
    _PIL_AVAILABLE = True
except ImportError:
    logger.warning("Pillow not installed — similarity will fall back to solo groups")


# --------------------------------------------------------------------------- #
#  Low-level embedding functions                                               #
# --------------------------------------------------------------------------- #

def _compute_phash(img_bytes: bytes, hash_size: int = 8) -> Optional[np.ndarray]:
    """
    Compute a Discrete Cosine Transform perceptual hash (pHash).
    
    Returns a 64-bit binary array (hash_size^2 bits).
    Returns None on failure.
    
    Algorithm:
      1. Resize to (hash_size*4, hash_size*4) grayscale
      2. Apply 2D DCT
      3. Take top-left hash_size x hash_size (low-frequency) coefficients
      4. Threshold at median → 64-bit binary fingerprint
    """
    if not _PIL_AVAILABLE:
        return None
    try:
        img = PILImage.open(io.BytesIO(img_bytes)).convert("L")  # grayscale
        # Resize to hash_size * 4 for DCT quality
        size = hash_size * 4
        img = img.resize((size, size), PILImage.LANCZOS)
        pixels = np.array(img, dtype=np.float64)

        # 2D DCT via separable 1D DCT
        dct = _dct2(pixels)

        # Take low-frequency block
        dct_low = dct[:hash_size, :hash_size]

        # Hash = pixels above median
        median = np.median(dct_low)
        phash = (dct_low > median).flatten().astype(np.uint8)
        return phash  # shape (64,)

    except Exception as e:
        logger.debug(f"pHash computation failed: {e}")
        return None


def _dct2(block: np.ndarray) -> np.ndarray:
    """Fast 2D DCT using scipy if available, otherwise naive row/col DCT."""
    try:
        from scipy.fft import dct
        return dct(dct(block, axis=0, norm="ortho"), axis=1, norm="ortho")
    except ImportError:
        # Pure numpy fallback: type-II DCT via FFT
        n = block.shape[0]
        result = np.zeros_like(block)
        for i in range(n):
            result[i] = _dct1d(block[i])
        for j in range(n):
            result[:, j] = _dct1d(result[:, j])
        return result


def _dct1d(x: np.ndarray) -> np.ndarray:
    """Type-II DCT via FFT (numpy only)."""
    n = len(x)
    # Extend and FFT
    v = np.zeros(4 * n)
    v[:n] = x
    v[n:2*n] = x[::-1]
    V = np.real(np.fft.fft(v))[:2*n]
    # Weight
    k = np.arange(n)
    W = 2 * np.exp(-1j * np.pi * k / (2 * n))
    return np.real(V[:n] * W)


def _compute_color_histogram(img_bytes: bytes, bins: int = 16) -> Optional[np.ndarray]:
    """
    Compute a normalized LAB color histogram.
    
    Returns a flat float32 array of shape (bins*3,), normalized to sum=1.
    Returns None on failure.
    
    Uses CIE-LAB (perceptually uniform) instead of RGB to avoid brightness
    sensitivity that would make underexposed/overexposed copies look different.
    """
    if not _PIL_AVAILABLE:
        return None
    try:
        img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
        # Resize small for speed — only need color distribution
        img = img.resize((64, 64), PILImage.LANCZOS)

        # Convert to LAB via numpy (no scipy needed)
        rgb = np.array(img, dtype=np.float32) / 255.0

        # sRGB → linear RGB
        mask = rgb > 0.04045
        rgb[mask] = ((rgb[mask] + 0.055) / 1.055) ** 2.4
        rgb[~mask] = rgb[~mask] / 12.92

        # Linear RGB → XYZ (D65)
        M = np.array([
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041]
        ])
        xyz = rgb.reshape(-1, 3) @ M.T

        # XYZ → LAB
        xyz /= np.array([0.95047, 1.00000, 1.08883])
        mask2 = xyz > 0.008856
        xyz[mask2] = xyz[mask2] ** (1.0 / 3.0)
        xyz[~mask2] = 7.787 * xyz[~mask2] + 16.0 / 116.0

        L = (116.0 * xyz[:, 1] - 16.0).clip(0, 100)
        a = (500.0 * (xyz[:, 0] - xyz[:, 1])).clip(-128, 127)
        b = (200.0 * (xyz[:, 1] - xyz[:, 2])).clip(-128, 127)

        # Histogram per channel
        hist_L, _ = np.histogram(L, bins=bins, range=(0, 100))
        hist_a, _ = np.histogram(a, bins=bins, range=(-128, 127))
        hist_b, _ = np.histogram(b, bins=bins, range=(-128, 127))

        hist = np.concatenate([hist_L, hist_a, hist_b]).astype(np.float32)
        total = hist.sum()
        if total > 0:
            hist /= total
        return hist  # shape (bins*3,)

    except Exception as e:
        logger.debug(f"Color histogram failed: {e}")
        return None


def _phash_similarity(h1: np.ndarray, h2: np.ndarray) -> float:
    """Hamming similarity: 1.0 = identical, 0.0 = completely different."""
    hamming_bits = int(np.sum(h1 != h2))
    return 1.0 - hamming_bits / len(h1)


def _cosine_similarity(h1: np.ndarray, h2: np.ndarray) -> float:
    """Cosine similarity between two histograms."""
    denom = np.linalg.norm(h1) * np.linalg.norm(h2)
    if denom < 1e-9:
        return 0.0
    return float(np.dot(h1, h2) / denom)


def combined_similarity(
    phash1: Optional[np.ndarray],
    color1: Optional[np.ndarray],
    phash2: Optional[np.ndarray],
    color2: Optional[np.ndarray],
    phash_weight: float = 0.70,
    color_weight: float = 0.30,
) -> float:
    """
    Combined similarity score: pHash (70%) + color histogram (30%).
    
    Falls back gracefully if either embedding is unavailable:
    - Both available: weighted combination
    - Only pHash: use pHash only
    - Only color: use color only
    - Neither: return 0.0 (treat as different)
    """
    sims = []
    weights = []

    if phash1 is not None and phash2 is not None:
        sims.append(_phash_similarity(phash1, phash2))
        weights.append(phash_weight)

    if color1 is not None and color2 is not None:
        sims.append(_cosine_similarity(color1, color2))
        weights.append(color_weight)

    if not sims:
        return 0.0

    total_w = sum(weights)
    return sum(s * w for s, w in zip(sims, weights)) / total_w


# --------------------------------------------------------------------------- #
#  Embedding dataclass                                                         #
# --------------------------------------------------------------------------- #

class ImageEmbedding:
    """Holds computed embeddings for a single image."""
    __slots__ = ("image_id", "phash", "color_hist", "ok")

    def __init__(self, image_id: str):
        self.image_id = image_id
        self.phash: Optional[np.ndarray] = None
        self.color_hist: Optional[np.ndarray] = None
        self.ok: bool = False  # True if at least one embedding succeeded


# --------------------------------------------------------------------------- #
#  SimilarityService                                                           #
# --------------------------------------------------------------------------- #

class SimilarityService:
    """
    Real perceptual image similarity using pHash + LAB color histograms.
    
    Interface contract (unchanged from stub):
      cluster_images(images) -> dict[group_id: str, images: list]
    
    The images list items must have .id and .storage_path attributes.
    Image bytes are fetched via the signed_url_provider callable.
    """

    def __init__(self, threshold: float = 0.90):
        """
        threshold: minimum combined_similarity to consider two images duplicates.
          0.95 = near-identical only
          0.90 = near-duplicates (recommended)
          0.80 = similar compositions
        """
        self.threshold = threshold
        logger.info(
            f"SimilarityService initialized: method=pHash+ColorHistogram, "
            f"threshold={threshold}, pillow_available={_PIL_AVAILABLE}"
        )

    def is_real_implementation(self) -> bool:
        return _PIL_AVAILABLE

    def compute_embedding(self, img_bytes: bytes, image_id: str) -> ImageEmbedding:
        """Compute both embeddings for a single image from raw bytes."""
        emb = ImageEmbedding(image_id)
        emb.phash = _compute_phash(img_bytes)
        emb.color_hist = _compute_color_histogram(img_bytes)
        emb.ok = (emb.phash is not None) or (emb.color_hist is not None)
        return emb

    def cluster_by_embeddings(
        self, embeddings: list[ImageEmbedding]
    ) -> dict[str, list[str]]:
        """
        Greedy single-pass clustering.
        
        Returns: dict[group_id → list[image_id]]
        
        Algorithm:
          - Each unassigned image becomes a potential seed.
          - Any subsequent unassigned image with combined_similarity >= threshold
            joins the seed's group.
          - O(n²) — acceptable for up to ~200 images (typical photo session).
        """
        n = len(embeddings)
        assigned = [False] * n
        groups: dict[str, list[str]] = {}
        group_idx = 0

        for i in range(n):
            if assigned[i]:
                continue

            group_id = f"g{group_idx:04d}"
            group_idx += 1
            groups[group_id] = [embeddings[i].image_id]
            assigned[i] = True

            for j in range(i + 1, n):
                if assigned[j]:
                    continue

                sim = combined_similarity(
                    embeddings[i].phash, embeddings[i].color_hist,
                    embeddings[j].phash, embeddings[j].color_hist,
                )

                if sim >= self.threshold:
                    groups[group_id].append(embeddings[j].image_id)
                    assigned[j] = True
                    logger.debug(
                        f"Grouped {embeddings[i].image_id[:8]} + "
                        f"{embeddings[j].image_id[:8]}: sim={sim:.3f}"
                    )

        return groups

    def cluster_images(
        self,
        images: list,
        signed_url_provider=None,
    ) -> dict[str, list]:
        """
        Main entry point — matches the original stub interface.
        
        Args:
            images: list of Image model objects (with .id, .storage_path)
            signed_url_provider: optional callable(storage_path) -> url string
                                 If None, falls back to storage_service.
        
        Returns: dict[group_id → list[Image]]
        
        On any per-image failure: that image gets its own solo group (safe fallback).
        """
        if not images:
            return {}

        if not _PIL_AVAILABLE:
            logger.warning(
                "Pillow not available — falling back to solo groups (no similarity)"
            )
            return {f"solo_{img.id}": [img] for img in images}

        # Resolve URL provider (kept for callers that pass a custom provider; default unused
        # now that embeddings load via storage_service.download_analysis_or_original).
        if signed_url_provider is None:
            from app.services.storage_service import storage_service
            def signed_url_provider(storage_path: str) -> Optional[str]:
                try:
                    resp = storage_service.supabase.storage.from_(
                        storage_service.bucket_name
                    ).create_signed_url(storage_path, 120)  # 2 min — only for embedding
                    if isinstance(resp, dict):
                        return resp.get("signedURL") or resp.get("signed_url")
                    return resp
                except Exception:
                    return None

        # Download images and compute embeddings
        embeddings: list[ImageEmbedding] = []
        # Map image_id → Image model for output reconstruction
        img_map: dict[str, object] = {img.id: img for img in images}

        for img in images:
            emb = ImageEmbedding(img.id)
            try:
                # Prefer resized analysis derivative (same asset Groq proxy serves).
                from app.services.storage_service import storage_service as _storage
                img_bytes = _storage.download_analysis_or_original(img.storage_path)

                emb = self.compute_embedding(img_bytes, img.id)
                if emb.ok:
                    logger.debug(f"Embedding OK for image {img.id[:8]}")
                else:
                    logger.warning(f"Embedding failed for image {img.id[:8]}")

            except Exception as e:
                logger.warning(f"Could not embed image {img.id[:8]}: {e}")
                emb.ok = False

            embeddings.append(emb)

        # Cluster by embeddings
        id_groups = self.cluster_by_embeddings(embeddings)

        # Convert image_id groups → Image model groups
        result: dict[str, list] = {}
        for group_id, id_list in id_groups.items():
            group_images = [img_map[iid] for iid in id_list if iid in img_map]
            if group_images:
                result[group_id] = group_images

        # Log grouping summary
        multi_groups = {k: v for k, v in result.items() if len(v) > 1}
        logger.info(
            f"Similarity clustering complete: {len(images)} images → "
            f"{len(result)} groups ({len(multi_groups)} with duplicates), "
            f"threshold={self.threshold:.2f}, "
            f"real_embeddings={self.is_real_implementation()}"
        )
        for gid, imgs in multi_groups.items():
            logger.info(
                f"  Group {gid}: {len(imgs)} similar images — "
                f"{[i.id[:8] for i in imgs]}"
            )

        return result


# --------------------------------------------------------------------------- #
#  Module-level singleton (reads threshold from settings if available)         #
# --------------------------------------------------------------------------- #

def _get_threshold() -> float:
    try:
        from app.core.config import settings
        return getattr(settings, "SIMILARITY_THRESHOLD", 0.90)
    except Exception:
        return 0.90


similarity_service = SimilarityService(threshold=_get_threshold())
