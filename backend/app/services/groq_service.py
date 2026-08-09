import os
import json
import asyncio
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class GroqClientManager:
    def __init__(self):
        self.clients = []
        if settings.GROQ_API_KEY:
            self.clients.append(AsyncGroq(api_key=settings.GROQ_API_KEY))
        if settings.GROQ_API_KEY_2:
            self.clients.append(AsyncGroq(api_key=settings.GROQ_API_KEY_2))
            
        if not self.clients:
            logger.warning("No Groq API keys found. Vision analysis will fail.")
            
        self.current_client_index = 0
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(settings.GROQ_MAX_CONCURRENCY)

    async def get_next_client(self) -> AsyncGroq:
        async with self.lock:
            if not self.clients:
                raise ValueError("No Groq clients available.")
            client = self.clients[self.current_client_index]
            self.current_client_index = (self.current_client_index + 1) % len(self.clients)
            return client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def analyze_image_with_retry(self, image_url: str) -> dict:
        client = await self.get_next_client()
        
        # We pass the proxy URL directly to Groq.
        prompt = """You are a professional photo quality analyst. Analyze this image and score ONLY what you can directly observe.

Return ONLY valid JSON with these exact fields:

{
  "sharpness": <0-100, how sharp/in-focus the main subject is. 100=razor sharp, 0=completely soft>,
  "blur": <0-100, amount of motion blur or defocus blur present. 100=extremely blurry, 0=no blur at all>,
  "exposure": <0-100, where 0=completely black/underexposed, 50-70=well-exposed, 100=completely blown out/overexposed>,
  "lighting": <0-100, quality of light. 100=beautiful directional/golden-hour light, 0=harsh flat or no light>,
  "composition": <0-100, rule of thirds, framing, leading lines, subject placement. 100=professional composition>,
  "subject_clarity": <0-100, how clearly visible and unobstructed the main subject is. 100=perfectly clear>,
  "face_quality": <0-100 IF human faces are present and visible, null if NO faces in image>,
  "visual_appeal": <0-100, overall aesthetic and emotional impact of the image>,
  "technical_quality": <0-100, overall technical execution: focus, noise, chromatic aberration, distortion>,
  "is_usable": <true if image is usable for any purpose, false ONLY if image is corrupted/completely unusable>,
  "reason": "<one concise sentence explaining the most important quality characteristic of this image>"
}

IMPORTANT RULES:
- Score sharpness and blur INDEPENDENTLY (a photo can have low blur but still be soft)
- face_quality MUST be null (not 0) when no faces are present
- is_usable = false ONLY for corrupted files or pitch-black images, NOT for stylistic choices
- Do not invent scores; score only what you can see
- reason should mention the single most impactful positive or negative quality"""

        try:
            response = await client.chat.completions.create(
                model=settings.GROQ_VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1024,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            # Qwen doesn't support json_object mode, so we parse manually
            try:
                # Basic cleanup if model surrounds it with markdown ```json ... ```
                cleaned = content.replace("```json", "").replace("```", "").strip()
                return json.loads(cleaned)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from Qwen: {content}")
                raise ValueError("Invalid JSON from Groq vision model")
        except Exception as e:
            logger.error(f"Groq API error on model {settings.GROQ_VISION_MODEL}: {e}")
            raise e

    async def analyze_image(self, image_url: str) -> dict:
        async with self.semaphore:
            return await self.analyze_image_with_retry(image_url)

groq_manager = GroqClientManager()
