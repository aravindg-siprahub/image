"""
Accuracy Audit Test Script for image_ranker.py

Tests the new scoring formula with simulated Groq analysis data
representing the test dataset described in the accuracy improvement task.

Run from backend directory:
  python test_ranker_accuracy.py

No real images or API calls needed — uses synthetic Groq-like analysis data.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.image_ranker import ranker

# ── Synthetic test dataset ──────────────────────────────────────────────────
TEST_CASES = [
    {
        "name": "Excellent landscape (golden hour, sharp)",
        "data": {
            "sharpness": 92, "blur": 5, "exposure": 62, "lighting": 90,
            "composition": 88, "subject_clarity": 90, "face_quality": None,
            "visual_appeal": 90, "technical_quality": 91,
            "is_usable": True, "reason": "Beautiful golden hour, sharp mountains"
        },
        "expected_rank": 1,  # Should be top pick
    },
    {
        "name": "Portrait, sharp, well lit, expressive",
        "data": {
            "sharpness": 88, "blur": 8, "exposure": 60, "lighting": 82,
            "composition": 80, "subject_clarity": 92, "face_quality": 87,
            "visual_appeal": 85, "technical_quality": 87,
            "is_usable": True, "reason": "Sharp portrait with excellent facial clarity"
        },
        "expected_rank": 2,
    },
    {
        "name": "Average quality photo",
        "data": {
            "sharpness": 60, "blur": 30, "exposure": 58, "lighting": 58,
            "composition": 55, "subject_clarity": 62, "face_quality": None,
            "visual_appeal": 55, "technical_quality": 58,
            "is_usable": True, "reason": "Acceptable but unremarkable quality"
        },
        "expected_rank": 3,  # Middle of pack
    },
    {
        "name": "Group photo, slightly soft",
        "data": {
            "sharpness": 62, "blur": 28, "exposure": 60, "lighting": 65,
            "composition": 70, "subject_clarity": 72, "face_quality": 68,
            "visual_appeal": 65, "technical_quality": 60,
            "is_usable": True, "reason": "Good group framing but slightly soft focus"
        },
        "expected_rank": 4,
    },
    {
        "name": "Blurry photo (motion blur)",
        "data": {
            "sharpness": 20, "blur": 80, "exposure": 55, "lighting": 60,
            "composition": 58, "subject_clarity": 30, "face_quality": None,
            "visual_appeal": 35, "technical_quality": 25,
            "is_usable": True, "reason": "Heavy motion blur ruins the shot"
        },
        "expected_rank": 7,  # Should be near bottom
        "expected_penalty": "severe_blur",
    },
    {
        "name": "Severely underexposed (dark) photo",
        "data": {
            "sharpness": 70, "blur": 10, "exposure": 12, "lighting": 20,
            "composition": 60, "subject_clarity": 25, "face_quality": None,
            "visual_appeal": 20, "technical_quality": 40,
            "is_usable": True, "reason": "Image too dark, underexposed"
        },
        "expected_rank": 8,
        "expected_penalty": "underexposed",
    },
    {
        "name": "Overexposed (blown-out highlights) photo",
        "data": {
            "sharpness": 65, "blur": 15, "exposure": 97, "lighting": 30,
            "composition": 58, "subject_clarity": 40, "face_quality": None,
            "visual_appeal": 25, "technical_quality": 35,
            "is_usable": True, "reason": "Highlights blown out, overexposed"
        },
        "expected_rank": 7,
        "expected_penalty": "overexposed",
    },
    {
        "name": "Duplicate of excellent landscape (nearly identical, slightly worse)",
        "data": {
            "sharpness": 89, "blur": 8, "exposure": 63, "lighting": 88,
            "composition": 85, "subject_clarity": 87, "face_quality": None,
            "visual_appeal": 87, "technical_quality": 88,
            "is_usable": True, "reason": "Similar to best landscape, fractionally less sharp"
        },
        "expected_rank": 2,  # Without similarity grouping, should rank #2 by score
        "note": "Similarity grouping would demote this if embeddings were active"
    },
    {
        "name": "Portrait with closed eyes / poor face quality",
        "data": {
            "sharpness": 82, "blur": 10, "exposure": 62, "lighting": 78,
            "composition": 75, "subject_clarity": 80, "face_quality": 25,
            "visual_appeal": 50, "technical_quality": 80,
            "is_usable": True, "reason": "Sharp portrait but subject has eyes closed"
        },
        "expected_rank": 5,  # Technically good but face score drags it down
    },
    {
        "name": "Corrupted / unusable image",
        "data": {
            "sharpness": 10, "blur": 90, "exposure": 5, "lighting": 5,
            "composition": 10, "subject_clarity": 5, "face_quality": None,
            "visual_appeal": 2, "technical_quality": 5,
            "is_usable": False, "reason": "Image appears corrupted or completely black"
        },
        "expected_rank": 9,  # Dead last
        "expected_penalty": "groq_unusable",
    },
]

# ── Run scoring ──────────────────────────────────────────────────────────────

print("\n" + "="*80)
print("  LENSAI RANKER ACCURACY AUDIT")
print("="*80)
print("\nBEFORE formula (old):")
print("  score = sum(val * weight) / active_weights")
print("  weights: sharpness=0.25, tech=0.20, comp=0.15, lighting=0.15,")
print("           subject=0.10, face=0.10 (skipped if null), appeal=0.05")
print("  Issues: no blur penalty, no exposure gate, face weight redistributed wrongly")
print()
print("AFTER formula (new):")
print("  technical = 0.40*focus_score + 0.25*exposure_quality + 0.20*subject + 0.15*tech")
print("    focus_score = 0.60*sharpness + 0.40*(100-blur)")
print("    exposure_quality = bell curve centered at 65")
print("  aesthetic = 0.45*composition + 0.35*lighting + 0.20*visual_appeal")
print("  face (if present)")
print("  base = tech*0.55 + aesthetic*0.30 + face*0.15  (if face)")
print("       = tech*0.60 + aesthetic*0.40              (no face)")
print("  Penalty gates: severe_blur×0.40, low_sharpness×0.55,")
print("                 overexposed×0.55, underexposed×0.60,")
print("                 no_subject×0.60, groq_unusable×0.30")
print()

results = []
for tc in TEST_CASES:
    data = tc["data"]
    is_usable = data.get("is_usable", True)

    technical  = ranker.calculate_technical_score(data)
    aesthetic  = ranker.calculate_aesthetic_score(data)
    face       = ranker.calculate_face_score(data)
    final      = ranker.calculate_deterministic_score(data, is_usable=is_usable)

    results.append({
        "name": tc["name"],
        "technical": technical,
        "aesthetic": aesthetic,
        "face": face,
        "final_score": final,
        "expected_rank": tc.get("expected_rank"),
        "note": tc.get("note", ""),
        "expected_penalty": tc.get("expected_penalty"),
    })

# Sort by final_score to get actual ranking
results.sort(key=lambda r: r["final_score"], reverse=True)

print(f"{'RANK':<5} {'FINAL':>6} {'TECH':>6} {'AESTH':>6} {'FACE':>6}  {'IMAGE NAME'}")
print("-"*80)
for rank, r in enumerate(results, 1):
    face_str = f"{r['face']:.0f}" if r['face'] is not None else " n/a"
    print(
        f"  #{rank:<3} {r['final_score']:>6.1f} {r['technical']:>6.1f} "
        f"{r['aesthetic']:>6.1f} {face_str:>6}  {r['name']}"
    )

print()
print("-- SANITY CHECKS " + "-"*63)
checks = [
    ("Excellent landscape is #1",
     results[0]["name"].startswith("Excellent landscape")),

    ("Blurry photo is in bottom 3",
     any(r["name"].startswith("Blurry") and i >= len(results) - 3
         for i, r in enumerate(results))),

    ("Underexposed photo is in bottom 3",
     any("underexposed" in r["name"].lower() and i >= len(results) - 3
         for i, r in enumerate(results))),

    ("Overexposed photo is in bottom 4",
     any("overexposed" in r["name"].lower() and i >= len(results) - 4
         for i, r in enumerate(results))),

    ("Corrupted photo is LAST",
     results[-1]["name"].startswith("Corrupted")),

    ("Portrait with bad face ranks lower than sharp portrait",
     next((i for i, r in enumerate(results) if "closed eyes" in r["name"]), 99) >
     next((i for i, r in enumerate(results) if "sharp, well lit" in r["name"].lower()), 0)),

    ("Blurry final score < 40",
     next((r["final_score"] for r in results if r["name"].startswith("Blurry")), 999) < 40),

    ("Unusable image final score < 15",
     next((r["final_score"] for r in results if "Corrupted" in r["name"]), 999) < 15),
]

all_pass = True
for label, passed in checks:
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"  [{status}]  {label}")

print()
if all_pass:
    print("ALL SANITY CHECKS PASSED -- ranking behaves correctly")
else:
    print("SOME CHECKS FAILED -- review formula weights")

print()
print("-- SIMILARITY STATUS " + "-"*59)
print("  Status: STUB (honest — each image is its own group)")
print("  Old bug: idx % 3 grouping forcefully overwrote recommendations with 'replace'")
print("           on arbitrary images — NOT content-based similarity")
print("  Fix: removed fake grouping. Each image treated as unique until real")
print("       embeddings (CLIP/ViT) are implemented.")
print("  Interface: cluster_images(images) -> dict[group_id, list[Image]]")
print("  is_real_implementation() -> False (caller can check before trusting groups)")
print()
print("="*80)
