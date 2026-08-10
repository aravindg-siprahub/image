import numpy as np
from PIL import Image, ImageStat
import io
import logging

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    def analyze(self, image_bytes: bytes) -> dict:
        """
        Fast technical analysis using PIL and NumPy.
        Returns sharpness, blur, exposure, face_quality signals.

        Sharpness calibration:
          - Uses adaptive log-scale Laplacian variance so real camera photos
            spread across the full 0-100 range instead of saturating at 100.
          - Reference curve (approximate for 800-px downscale):
              lap_var < 30   → sharpness 0-20   (clearly blurry)
              lap_var 30-200 → sharpness 20-60  (soft/acceptable)
              lap_var 200-2000 → sharpness 60-90 (sharp)
              lap_var > 2000 → sharpness 90-100 (very sharp)
        """
        try:
            # verify first (closes the file handle internally)
            with Image.open(io.BytesIO(image_bytes)) as img:
                img.verify()

            # Reopen for real processing
            with Image.open(io.BytesIO(image_bytes)) as img:
                orig_w, orig_h = img.width, img.height
                gray_img = img.convert("L")

                # Resize for consistent processing
                max_dim = 800
                if max(gray_img.width, gray_img.height) > max_dim:
                    gray_img = gray_img.copy()
                    gray_img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)

                gray_array = np.array(gray_img, dtype=np.float32)

                # --- Sharpness via Laplacian variance (log-adaptive) ---
                lap = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
                try:
                    from scipy.ndimage import convolve
                    lap_response = convolve(gray_array, lap)
                except ImportError:
                    # Fallback: manual 2D convolution using stride tricks
                    from numpy.lib.stride_tricks import sliding_window_view
                    padded = np.pad(gray_array, 1, mode='edge')
                    windows = sliding_window_view(padded, (3, 3))
                    lap_response = (windows * lap).sum(axis=(-2, -1))

                lap_var = float(np.var(lap_response))

                # Log-scale mapping: maps [1, 10000] → [0, 100]
                # log(1)=0, log(10000)=4 → scale by 25
                if lap_var > 0:
                    log_var = min(4.0, np.log10(lap_var + 1))
                    sharpness = min(100.0, max(0.0, log_var * 25.0))
                else:
                    sharpness = 0.0

                blur_score = 100.0 - sharpness

                # --- Exposure ---
                stat = ImageStat.Stat(gray_img)
                mean_brightness = stat.mean[0]  # 0-255
                exposure_score = (mean_brightness / 255.0) * 100.0

                # --- Lightweight face detection via haar cascade ---
                face_data = _detect_faces(image_bytes)

                return {
                    "is_corrupted": False,
                    "sharpness": round(sharpness, 2),
                    "blur": round(blur_score, 2),
                    "exposure": round(exposure_score, 2),
                    "resolution": f"{orig_w}x{orig_h}",
                    # Face signals
                    "face_detected": face_data["face_detected"],
                    "face_count": face_data["face_count"],
                    "face_quality": face_data["face_quality"],  # 0-100 or None
                }

        except Exception as e:
            return {
                "is_corrupted": True,
                "error": str(e),
            }


def _detect_faces(image_bytes: bytes) -> dict:
    """
    Lightweight CPU face detection using OpenCV Haar cascades.

    Returns:
        face_detected: bool
        face_count: int
        face_quality: float 0-100 or None (None means no face found — not a penalty)

    Design rules:
    - Face detection failure → face_quality = None (no penalty)
    - Face detected → face_quality reflects face sharpness and relative size
    - Eyes open/closed: we skip unreliable eye detection on CPU; instead we
      rely on face_quality (face sharpness) which is strongly correlated with
      eye clarity and overall portrait sharpness.
    """
    no_face = {"face_detected": False, "face_count": 0, "face_quality": None}

    try:
        import cv2
        import numpy as np
    except ImportError:
        # OpenCV not installed — skip face detection gracefully
        return no_face

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return no_face

        # Resize for faster detection (keep aspect ratio)
        h, w = img_bgr.shape[:2]
        scale = min(1.0, 640.0 / max(h, w))
        if scale < 1.0:
            det_img = cv2.resize(img_bgr, (int(w * scale), int(h * scale)))
        else:
            det_img = img_bgr

        gray = cv2.cvtColor(det_img, cv2.COLOR_BGR2GRAY)

        # Use bundled Haar cascade (no download — ships with opencv-python)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)

        if face_cascade.empty():
            return no_face

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(30, 30),
        )

        if len(faces) == 0:
            return no_face

        # Use the largest face for quality assessment
        areas = [fw * fh for (_, _, fw, fh) in faces]
        idx = int(np.argmax(areas))
        fx, fy, fw, fh = faces[idx]

        # Face sharpness: Laplacian variance of the face crop
        face_crop = gray[fy:fy + fh, fx:fx + fw]
        if face_crop.size > 0:
            face_lap_var = float(np.var(
                cv2.Laplacian(face_crop.astype(np.float32), cv2.CV_32F)
            ))
            # Same log-scale as full-image sharpness
            if face_lap_var > 0:
                log_var = min(4.0, np.log10(face_lap_var + 1))
                face_sharpness = min(100.0, max(0.0, log_var * 25.0))
            else:
                face_sharpness = 0.0
        else:
            face_sharpness = 50.0  # unknown

        # Relative face size (fraction of image area) → 0-100
        det_h, det_w = det_img.shape[:2]
        face_area_frac = (fw * fh) / max(1, det_w * det_h)
        face_size_score = min(100.0, face_area_frac * 500.0)  # 20% of frame → 100

        # face_quality = blend of sharpness and face size
        face_quality = round(face_sharpness * 0.75 + face_size_score * 0.25, 2)

        return {
            "face_detected": True,
            "face_count": len(faces),
            "face_quality": face_quality,
        }

    except Exception as e:
        logger.debug(f"Face detection error (non-fatal): {e}")
        return no_face


technical_analyzer = TechnicalAnalyzer()
