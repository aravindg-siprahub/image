import numpy as np
from PIL import Image, ImageStat
import io

class TechnicalAnalyzer:
    def analyze(self, image_bytes: bytes) -> dict:
        """
        Fast technical analysis using PIL and NumPy.
        Returns metrics for blur and exposure.
        """
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Basic checks
                img.verify()
                
            # Reopen for processing after verify
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Convert to RGB if needed, though grayscale is better for Laplacian
                gray_img = img.convert("L")
                
                # Resize for faster processing if it's very large
                max_dim = 800
                if max(gray_img.width, gray_img.height) > max_dim:
                    gray_img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)

                gray_array = np.array(gray_img, dtype=np.float32)

                # 1. Blur (Variance of Laplacian)
                # Simple laplacian kernel
                lap = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
                # Use scipy.ndimage for fast convolution if available, otherwise manual or correlate
                from scipy.ndimage import convolve
                lap_var = np.var(convolve(gray_array, lap))
                
                # Normalize lap_var heuristically:
                # High lap_var (> 1000) is sharp, low (< 100) is blurry.
                # We map this to a sharpness score 0-100 where higher is sharper.
                sharpness = min(100.0, max(0.0, (lap_var / 1500.0) * 100))
                # For compatibility with older logic, blur_score was higher=more blurry.
                blur_score = 100.0 - sharpness

                # 2. Exposure (Mean Brightness)
                stat = ImageStat.Stat(gray_img)
                mean_brightness = stat.mean[0] # 0-255
                
                # Map 0-255 to 0-100 exposure score
                exposure_score = (mean_brightness / 255.0) * 100.0

                return {
                    "is_corrupted": False,
                    "sharpness": round(sharpness, 2),
                    "blur": round(blur_score, 2),
                    "exposure": round(exposure_score, 2),
                    "resolution": f"{img.width}x{img.height}"
                }
                
        except Exception as e:
            return {
                "is_corrupted": True,
                "error": str(e)
            }

technical_analyzer = TechnicalAnalyzer()
