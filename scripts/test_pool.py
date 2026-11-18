import asyncio

import httpx


async def main():
    url = "http://127.0.0.1:8000/health"

    async with httpx.AsyncClient(timeout=15.0) as client:
        for number in range(1, 51):
            response = await client.get(url)
            print(f"Request {number}: HTTP {response.status_code}")
            response.raise_for_status()

    print("\nCompleted 50 successful HTTP requests.")


if __name__ == "__main__":
    asyncio.run(main())
