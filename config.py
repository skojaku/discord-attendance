"""Configuration management for Discord attendance bot."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for bot settings."""

    # Discord Configuration
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    ADMIN_CHANNEL_ID = int(os.getenv('ADMIN_CHANNEL_ID', 0))
    ATTENDANCE_CHANNEL_ID = int(os.getenv('ATTENDANCE_CHANNEL_ID', 0))

    # Database Configuration
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/attendance.db')

    # Bot Settings
    CODE_ROTATION_INTERVAL = int(os.getenv('CODE_ROTATION_INTERVAL', 15))
    CODE_LENGTH = int(os.getenv('CODE_LENGTH', 4))

    @classmethod
    def validate(cls):
        """Validate all required configuration values are present."""
        required_configs = {
            'DISCORD_BOT_TOKEN': cls.DISCORD_BOT_TOKEN,
            'ADMIN_CHANNEL_ID': cls.ADMIN_CHANNEL_ID,
            'ATTENDANCE_CHANNEL_ID': cls.ATTENDANCE_CHANNEL_ID,
        }

        missing = []
        for name, value in required_configs.items():
            if not value:
                missing.append(name)

        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}. "
                f"Please check your .env file."
            )

        # Validate channel IDs are positive integers
        if cls.ADMIN_CHANNEL_ID <= 0:
            raise ValueError("ADMIN_CHANNEL_ID must be a valid positive integer")
        if cls.ATTENDANCE_CHANNEL_ID <= 0:
            raise ValueError("ATTENDANCE_CHANNEL_ID must be a valid positive integer")

        # Validate code settings
        if cls.CODE_ROTATION_INTERVAL < 5:
            raise ValueError("CODE_ROTATION_INTERVAL must be at least 5 seconds")
        if cls.CODE_LENGTH < 3:
            raise ValueError("CODE_LENGTH must be at least 3 characters")

        return True


# Create config instance
config = Config()
