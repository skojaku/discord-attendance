"""Main entry point for the Discord attendance bot."""
import asyncio
from bot.client import AttendanceBot
from config import config


async def main():
    """Start the attendance bot."""
    # Validate configuration
    try:
        config.validate()
        print("Configuration validated successfully")
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nPlease check your .env file and ensure all required values are set.")
        return

    # Create and start the bot
    bot = AttendanceBot()

    try:
        print("Starting Discord bot...")
        await bot.start(config.DISCORD_BOT_TOKEN)
    except KeyboardInterrupt:
        print("\nShutting down bot...")
        await bot.close()
    except Exception as e:
        print(f"Error running bot: {e}")
        import traceback
        traceback.print_exc()
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped")
