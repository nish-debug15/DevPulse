import asyncio
from main import scheduled_github_sync

if __name__ == "__main__":
    asyncio.run(scheduled_github_sync())
