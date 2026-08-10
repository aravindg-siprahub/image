import os
import io
import logging
import numpy as np
from PIL import Image
import onnxruntime as ort

logger = logging.getLogger(__name__)

class NimaService:
    def __init__(self):
        self.session = None
        self.model_path = os.path.join(os.path.dirname(__file__), "..", "..", "nima_mobilenet_aesthetic.onnx")

    def load_model(self):
        if self.session is None:
            if not os.path.exists(self.model_path):
                logger.warning(f"NIMA model not found at {self.model_path}")
                return False
            try:
                # Use CPUExecutionProvider for maximum compatibility on Railway
                self.session = ort.InferenceSession(self.model_path, providers=['CPUExecutionProvider'])
                logger.info("NIMA ONNX model loaded successfully.")
                return True
            except Exception as e:
                logger.error(f"Failed to load NIMA model: {e}")
                return False
        return True

    def preprocess_image(self, image_bytes: bytes) -> np.ndarray:
        """
        Preprocesses image bytes into the format expected by the NIMA MobileNet ONNX model.
        Input shape: (1, 224, 224, 3) NHWC
        Value range: [-1, 1] (standard MobileNet preprocessing)

        Performance: pre-downscales to max 448px before center-crop so PIL never
        holds a full 108MP image in memory during NIMA preprocessing.
        """
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGB")

            # Fast pre-downscale: shrink to max 448px (2× the 224 NIMA input)
            # before doing any crop math — avoids holding 108MP in memory
            if img.width > 448 or img.height > 448:
                img.thumbnail((448, 448), Image.Resampling.BILINEAR)

            # Resize so shortest edge is 224
            aspect = img.width / img.height
            if img.width < img.height:
                new_w = 224
                new_h = int(new_w / aspect)
            else:
                new_h = 224
                new_w = int(new_h * aspect)

            img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

            # Center crop to 224×224
            left = (img.width - 224) / 2
            top = (img.height - 224) / 2
            right = (img.width + 224) / 2
            bottom = (img.height + 224) / 2
            img = img.crop((left, top, right, bottom))

            img_array = np.array(img, dtype=np.float32)

            # MobileNet preprocessing (scale to [-1, 1])
            img_array = (img_array / 127.5) - 1.0

            # Add batch dimension
            img_array = np.expand_dims(img_array, axis=0)
            return img_array

    def analyze_image(self, image_bytes: bytes) -> dict:
        """
        Analyzes the aesthetic quality of an image using NIMA.
        Returns the aesthetic score (0-100).
        """
        if not self.load_model():
            return {"aesthetic_score": 50.0}

        try:
            input_array = self.preprocess_image(image_bytes)
            
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: input_array})
            
            # Outputs shape is (1, 10), representing probabilities for scores 1-10
            preds = outputs[0][0]
            
            # Calculate the expected value (mean score)
            scores = np.arange(1, 11)
            mean_score = np.sum(preds * scores) # Value between 1 and 10
            
            # Scale to 0-100 for consistency with our ranking system
            scaled_score = (mean_score / 10.0) * 100.0
            
            return {
                "aesthetic_score": round(float(scaled_score), 2)
            }
        except Exception as e:
            logger.error(f"Error during NIMA inference: {e}")
            return {"aesthetic_score": 50.0}

nima_service = NimaService()
