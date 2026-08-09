import asyncio
from groq import AsyncGroq
from app.core.config import settings

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

async def test_groq():
    models = await client.models.list()
    for m in models.data:
        print(m.id)

if __name__ == "__main__":
    asyncio.run(test_groq())
