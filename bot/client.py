"""Discord bot client setup and configuration."""
import discord
from discord.ext import commands


class AttendanceBot(commands.Bot):
    """Custom Discord bot for attendance tracking."""

    def __init__(self):
        """Initialize the bot with required intents and configuration."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",  # Not used since we use slash commands
            intents=intents
        )

    async def setup_hook(self):
        """Setup hook called when bot is starting."""
        # Load cogs
        await self.load_extension('bot.cogs.attendance')

        # Sync slash commands with Discord
        await self.tree.sync()
        print("Slash commands synced")

    async def on_ready(self):
        """Called when the bot is ready and connected to Discord."""
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print(f"Connected to {len(self.guilds)} guild(s)")
        print("Bot is ready!")

    async def on_error(self, event, *args, **kwargs):
        """Global error handler."""
        print(f"Error in event {event}:")
        import traceback
        traceback.print_exc()
