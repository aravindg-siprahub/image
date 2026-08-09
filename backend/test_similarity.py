"""
Similarity Service Test Script.
Tests pHash + color histogram similarity with synthetic image bytes.

Run from backend directory:
  python test_similarity.py

Creates in-memory test images using Pillow (no real files needed).
"""
import io
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PIL import Image as PILImage, ImageFilter, ImageDraw
    import numpy as np
    PIL_OK = True
except ImportError:
    PIL_OK = False
    print("ERROR: Pillow or numpy not installed. Run: pip install pillow numpy")
    sys.exit(1)

from app.services.similarity_service import (
    _compute_phash,
    _compute_color_histogram,
    combined_similarity,
    SimilarityService,
    ImageEmbedding,
)

print("="*70)
print("  SIMILARITY SERVICE TEST")
print("="*70)
print(f"  Method: pHash (DCT-based) + LAB Color Histogram")
print(f"  Threshold: 0.90 (configurable via SIMILARITY_THRESHOLD env var)")
print()


# ── Helper: create test images as bytes ────────────────────────────────────

def make_landscape(color=(100, 150, 200)) -> bytes:
    """A simple gradient landscape."""
    img = PILImage.new("RGB", (400, 300))
    draw = ImageDraw.Draw(img)
    # Sky
    draw.rectangle([0, 0, 400, 150], fill=color)
    # Ground
    draw.rectangle([0, 150, 400, 300], fill=(80, 100, 60))
    # Sun/moon
    draw.ellipse([50, 20, 120, 90], fill=(255, 220, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def make_portrait(skin_tone=(210, 170, 130)) -> bytes:
    """A simple portrait image."""
    img = PILImage.new("RGB", (300, 400), color=(180, 180, 200))
    draw = ImageDraw.Draw(img)
    # Head
    draw.ellipse([80, 60, 220, 200], fill=skin_tone)
    # Eyes
    draw.ellipse([105, 110, 125, 130], fill=(50, 50, 50))
    draw.ellipse([165, 110, 185, 130], fill=(50, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def blur_image(img_bytes: bytes, radius: int = 8) -> bytes:
    """Apply Gaussian blur to simulate motion blur."""
    img = PILImage.open(io.BytesIO(img_bytes))
    img = img.filter(ImageFilter.GaussianBlur(radius=radius))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def darken_image(img_bytes: bytes, factor: float = 0.25) -> bytes:
    """Darken an image to simulate underexposure."""
    img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
    arr = np.array(img, dtype=np.float32)
    arr = (arr * factor).clip(0, 255).astype(np.uint8)
    img2 = PILImage.fromarray(arr)
    buf = io.BytesIO()
    img2.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def jpeg_recompress(img_bytes: bytes, quality: int = 60) -> bytes:
    """Re-compress JPEG to simulate a near-duplicate with compression artifacts."""
    img = PILImage.open(io.BytesIO(img_bytes))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def crop_slightly(img_bytes: bytes, px: int = 15) -> bytes:
    """Crop a few pixels to simulate a slightly different crop of the same photo."""
    img = PILImage.open(io.BytesIO(img_bytes))
    w, h = img.size
    img = img.crop((px, px, w - px, h - px))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ── Create test dataset ────────────────────────────────────────────────────

landscape_bytes   = make_landscape(color=(100, 150, 200))
landscape_dup     = jpeg_recompress(landscape_bytes, quality=70)   # Near-duplicate
landscape_crop    = crop_slightly(landscape_bytes, px=12)           # Near-duplicate (slight crop)
landscape_blur    = blur_image(landscape_bytes, radius=6)           # Blurry version
landscape_dark    = darken_image(landscape_bytes, factor=0.2)       # Underexposed version

portrait_bytes    = make_portrait(skin_tone=(210, 170, 130))
portrait_dup      = jpeg_recompress(portrait_bytes, quality=65)    # Near-duplicate portrait
different_scene   = make_landscape(color=(200, 100, 80))           # Different colors (sunset)

test_images = {
    "landscape_original": landscape_bytes,
    "landscape_neardup":  landscape_dup,
    "landscape_crop":     landscape_crop,
    "landscape_blurry":   landscape_blur,
    "landscape_dark":     landscape_dark,
    "portrait_original":  portrait_bytes,
    "portrait_neardup":   portrait_dup,
    "different_scene":    different_scene,
}


# ── Compute embeddings ─────────────────────────────────────────────────────

svc = SimilarityService(threshold=0.90)

print("Computing embeddings...")
embeddings: dict[str, ImageEmbedding] = {}
for name, img_bytes in test_images.items():
    emb = svc.compute_embedding(img_bytes, image_id=name)
    embeddings[name] = emb
    phash_ok = emb.phash is not None
    color_ok = emb.color_hist is not None
    print(f"  {name:<25} phash={'OK' if phash_ok else 'FAIL'}  color={'OK' if color_ok else 'FAIL'}")

print()
print("-- PAIRWISE SIMILARITY MATRIX ------------------------------------------")
names = list(test_images.keys())

# Print header
header = f"{'':30}"
short = [n.replace('landscape_', 'ls_').replace('portrait_', 'pt_').replace('different_', 'df_') for n in names]
for s in short:
    header += f" {s[:8]:>8}"
print(header)

for i, n1 in enumerate(names):
    row = f"{n1[:30]:<30}"
    e1 = embeddings[n1]
    for j, n2 in enumerate(names):
        e2 = embeddings[n2]
        sim = combined_similarity(e1.phash, e1.color_hist, e2.phash, e2.color_hist)
        if i == j:
            row += f"    1.000"
        elif sim >= 0.90:
            row += f"  * {sim:.3f}"  # Near-duplicate flagged
        else:
            row += f"    {sim:.3f}"
    print(row)

print()
print("  (* = above 0.90 threshold -> grouped as near-duplicate)")
print()


# ── Cluster test ──────────────────────────────────────────────────────────

print("-- CLUSTERING RESULT ---------------------------------------------------")

# Build fake Image objects for cluster_images
class FakeImage:
    def __init__(self, name, img_bytes):
        self.id = name
        self.storage_path = name
        self._bytes = img_bytes

fake_images = [FakeImage(name, b) for name, b in test_images.items()]

# Provide bytes directly without HTTP
def _local_provider(storage_path: str):
    return f"__local__{storage_path}"

# Patch: override cluster_images to use in-memory bytes
emb_list = [embeddings[img.id] for img in fake_images]
id_groups = svc.cluster_by_embeddings(emb_list)

# Reconstruct image groups
img_map = {img.id: img for img in fake_images}
for group_id, id_list in sorted(id_groups.items()):
    imgs_in_group = [img_map[iid] for iid in id_list]
    if len(imgs_in_group) > 1:
        print(f"  Group {group_id} [{len(imgs_in_group)} images - NEAR DUPLICATES]:")
        for img in imgs_in_group:
            print(f"    - {img.id}")
    else:
        print(f"  Group {group_id} [unique]: {imgs_in_group[0].id}")

print()

# ── Sanity checks ─────────────────────────────────────────────────────────

print("-- SANITY CHECKS -------------------------------------------------------")

e = embeddings

checks = [
    ("landscape + neardup similarity >= 0.90",
     combined_similarity(e["landscape_original"].phash, e["landscape_original"].color_hist,
                         e["landscape_neardup"].phash,  e["landscape_neardup"].color_hist) >= 0.90),

    ("landscape + slight crop similarity >= 0.85",
     combined_similarity(e["landscape_original"].phash, e["landscape_original"].color_hist,
                         e["landscape_crop"].phash,     e["landscape_crop"].color_hist) >= 0.85),

    ("portrait + neardup similarity >= 0.90",
     combined_similarity(e["portrait_original"].phash, e["portrait_original"].color_hist,
                         e["portrait_neardup"].phash,  e["portrait_neardup"].color_hist) >= 0.90),

    ("landscape vs portrait similarity < 0.80 (different images)",
     combined_similarity(e["landscape_original"].phash, e["landscape_original"].color_hist,
                         e["portrait_original"].phash,  e["portrait_original"].color_hist) < 0.80),

    ("landscape vs different_scene similarity < 0.90 (different colors, escapes grouping)",
     combined_similarity(e["landscape_original"].phash, e["landscape_original"].color_hist,
                         e["different_scene"].phash,    e["different_scene"].color_hist) < 0.90),

    ("is_real_implementation() returns True",
     svc.is_real_implementation()),

    ("landscape neardup in same group as original",
     any(
        "landscape_original" in ids and "landscape_neardup" in ids
        for ids in id_groups.values()
     )),

    ("portrait neardup in same group as original",
     any(
        "portrait_original" in ids and "portrait_neardup" in ids
        for ids in id_groups.values()
     )),

    ("landscape and portrait in different groups",
     not any(
        "landscape_original" in ids and "portrait_original" in ids
        for ids in id_groups.values()
     )),
]

all_pass = True
for label, passed in checks:
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"  [{status}]  {label}")

print()
if all_pass:
    print("ALL SANITY CHECKS PASSED")
else:
    print("SOME CHECKS FAILED")

print()
print("="*70)
print("  SUMMARY")
print("="*70)
print(f"  Embedding method : pHash (DCT 8x8) + LAB Color Histogram (16-bin)")
print(f"  Default threshold: 0.90 (set SIMILARITY_THRESHOLD env var to change)")
print(f"  New dependencies : Pillow, numpy (already in venv after install)")
print(f"  Files changed    : similarity_service.py, config.py")
print(f"  Interface        : cluster_images(images) unchanged")
print(f"  is_real_impl()   : {svc.is_real_implementation()}")
print()
