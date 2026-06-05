"""
scripts/gen_session.py
======================
Run this ONCE to generate a Pyrogram session string for the userbot.
Then store the output as the USERBOT_SESSION secret in Replit.

Usage:
  cd SeekHub
  python scripts/gen_session.py

You will need:
  - API_ID and API_HASH from https://my.telegram.org/apps
  - The phone number of the Telegram account to use as userbot
"""
import asyncio
from pyrogram import Client


async def main():
    print("SeekHub Userbot Session Generator")
    print("=" * 40)
    print("Get API_ID and API_HASH from: https://my.telegram.org/apps\n")

    api_id   = int(input("Enter API_ID:   ").strip())
    api_hash = input("Enter API_HASH: ").strip()

    async with Client(
        name="session_gen",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
    ) as client:
        session_string = await client.export_session_string()

    print("\n" + "=" * 40)
    print("✅ Session generated successfully!")
    print("\nCopy the string below and save it as USERBOT_SESSION in Replit Secrets:\n")
    print(session_string)
    print("\nAlso save these as secrets:")
    print(f"  USERBOT_API_ID   = {api_id}")
    print(f"  USERBOT_API_HASH = {api_hash}")


if __name__ == "__main__":
    asyncio.run(main())
