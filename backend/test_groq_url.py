import asyncio
import os
import time
import json
from groq import AsyncGroq
from app.core.config import settings
import httpx
import base64

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

async def test_groq():
    url = "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png"
    
    print("\nTesting Base64 method with Qwen (RAW BASE64)...")
    t0 = time.time()
    try:
        async with httpx.AsyncClient() as http:
            img_resp = await http.get(url)
            b64 = base64.b64encode(img_resp.content).decode("utf-8")
            
        resp = await client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this image? Return JSON ONLY: {\"description\": \"...\"}"},
                        {"type": "image_url", "image_url": {"url": b64}} # RAW Base64
                    ]
                }
            ],
            max_tokens=1024
        )
        print(f"Base64 Method Success! Time: {time.time() - t0:.2f}s")
        print(resp.choices[0].message.content)
    except Exception as e:
        print(f"Base64 Method FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_groq())
