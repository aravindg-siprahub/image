import asyncio
import time
import base64
import httpx
from supabase import create_client
from app.core.config import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

async def measure_bottlenecks():
    print("--- Measuring Bottlenecks ---")
    
    # 1. Sync Supabase Signed URL
    t0 = time.time()
    try:
        url = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).create_signed_url("dummy.jpg", 300)
    except Exception as e:
        pass
    t1 = time.time()
    print(f"Sync create_signed_url: {(t1 - t0) * 1000:.1f} ms")

    # 2. Async httpx client creation + fetch vs reused client
    # Let's fetch a public small image
    test_img_url = "https://picsum.photos/200"
    
    t0 = time.time()
    async with httpx.AsyncClient() as client:
        resp = await client.get(test_img_url)
    t1 = time.time()
    print(f"Fetch with NEW httpx.AsyncClient: {(t1 - t0) * 1000:.1f} ms")
    
    client = httpx.AsyncClient()
    t0 = time.time()
    resp = await client.get(test_img_url)
    t1 = time.time()
    print(f"Fetch with REUSED httpx.AsyncClient: {(t1 - t0) * 1000:.1f} ms")
    await client.aclose()
    
    # 3. Simulate sequential blocking
    t0 = time.time()
    for _ in range(5):
        try:
            supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).create_signed_url("dummy.jpg", 300)
        except:
            pass
    t1 = time.time()
    print(f"5 sequential sync signed_url calls: {(t1 - t0) * 1000:.1f} ms")

if __name__ == "__main__":
    asyncio.run(measure_bottlenecks())
