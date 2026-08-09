import asyncio
import httpx

async def test_groq():
    async with httpx.AsyncClient() as http:
        resp = await http.get("https://console.groq.com/docs/models")
        # Just grab the HTML and find any mention of "vision"
        html = resp.text
        lines = html.splitlines()
        for line in lines:
            if "vision" in line.lower() or "llama-3.2" in line.lower():
                print(line.strip())

if __name__ == "__main__":
    asyncio.run(test_groq())
