import asyncio
import sys

import config
from bot import CommitBot


async def main():
    missing = []
    if not config.DISCORD_TOKEN:
        missing.append("DISCORD_TOKEN")
    if not config.DISCORD_CHANNEL_ID:
        missing.append("DISCORD_CHANNEL_ID")
    if not config.GIT_REPO_URL:
        missing.append("GIT_REPO_URL")

    if missing:
        print(f"Missing required env vars: {', '.join(missing)}")
        sys.exit(1)

    bot = CommitBot()
    try:
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
