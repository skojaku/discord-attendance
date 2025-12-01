"""Attendance tracking commands and logic."""
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os

from config import config
from utils.code_generator import generate_code
from utils.errors import (
    SessionAlreadyActiveError,
    NoActiveSessionError,
    InvalidCodeError,
    WrongChannelError
)
from storage.session_manager import AttendanceSession
from storage.database import AttendanceDatabase


class AttendanceCog(commands.Cog):
    """Cog for managing attendance tracking."""

    def __init__(self, bot: commands.Bot):
        """Initialize the attendance cog."""
        self.bot = bot
        self.session_manager = AttendanceSession()
        self.database = AttendanceDatabase(config.DATABASE_PATH)
        self.rotation_task = None

    async def cog_load(self):
        """Called when the cog is loaded."""
        # Setup database tables
        await self.database.setup_database()
        print("Attendance database initialized")

    def _is_admin_channel(self, interaction: discord.Interaction) -> bool:
        """Check if command is used in admin channel."""
        return interaction.channel_id == config.ADMIN_CHANNEL_ID

    def _is_attendance_channel(self, interaction: discord.Interaction) -> bool:
        """Check if command is used in attendance channel."""
        return interaction.channel_id == config.ATTENDANCE_CHANNEL_ID

    @app_commands.command(name="open_attendance", description="Start attendance session (admin only)")
    async def open_attendance(self, interaction: discord.Interaction):
        """Start a new attendance session."""
        # Validate channel
        if not self._is_admin_channel(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the admin channel.",
                ephemeral=True
            )
            return

        # Check if session already active
        try:
            # Generate initial code
            initial_code = generate_code(config.CODE_LENGTH)

            # Send initial message in attendance channel
            attendance_channel = self.bot.get_channel(config.ATTENDANCE_CHANNEL_ID)
            if not attendance_channel:
                await interaction.response.send_message(
                    "❌ Could not find attendance channel. Please check configuration.",
                    ephemeral=True
                )
                return

            # Post the attendance message
            embed = discord.Embed(
                title="📋 Attendance is Now Open!",
                description=f"Use the code below to mark your attendance:",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Current Code",
                value=f"**`{initial_code}`**",
                inline=False
            )
            embed.add_field(
                name="How to Submit",
                value=f"Type `/here {initial_code}` in this channel",
                inline=False
            )
            embed.set_footer(text="Code changes every 15 seconds • Only the latest submission counts")

            message = await attendance_channel.send(embed=embed)

            # Start session
            self.session_manager.start_session(initial_code, message.id, attendance_channel.id)

            # Start code rotation task
            self.rotation_task = asyncio.create_task(self._rotate_code_loop())

            # Confirm to admin
            await interaction.response.send_message(
                f"✅ Attendance session started!\n"
                f"Initial code: `{initial_code}`\n"
                f"Message posted in <#{config.ATTENDANCE_CHANNEL_ID}>",
                ephemeral=True
            )

        except SessionAlreadyActiveError:
            await interaction.response.send_message(
                "❌ An attendance session is already active. Please close it first.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error starting attendance: {str(e)}",
                ephemeral=True
            )
            print(f"Error in open_attendance: {e}")
            import traceback
            traceback.print_exc()

    @app_commands.command(name="close_attendance", description="Stop attendance session (admin only)")
    async def close_attendance(self, interaction: discord.Interaction):
        """Close the active attendance session and save records."""
        # Validate channel
        if not self._is_admin_channel(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the admin channel.",
                ephemeral=True
            )
            return

        try:
            # Cancel rotation task
            if self.rotation_task:
                self.rotation_task.cancel()
                try:
                    await self.rotation_task
                except asyncio.CancelledError:
                    pass

            # Get session data
            records, session_id = self.session_manager.end_session()

            # Save to database
            saved_count = await self.database.save_attendance_records(records, session_id)

            # Update the attendance message to show it's closed
            try:
                channel = self.bot.get_channel(self.session_manager.channel_id or config.ATTENDANCE_CHANNEL_ID)
                if channel and self.session_manager.message_id:
                    message = await channel.fetch_message(self.session_manager.message_id)

                    embed = discord.Embed(
                        title="📋 Attendance is Now Closed",
                        description="This attendance session has ended.",
                        color=discord.Color.red()
                    )
                    embed.add_field(
                        name="Total Submissions",
                        value=f"{saved_count} student(s)",
                        inline=False
                    )
                    embed.set_footer(text=f"Session ID: {session_id}")

                    await message.edit(embed=embed)
            except Exception as e:
                print(f"Could not update attendance message: {e}")

            # Reset session manager
            self.session_manager.reset()

            # Confirm to admin
            await interaction.response.send_message(
                f"✅ Attendance session closed!\n"
                f"Total submissions saved: {saved_count}\n"
                f"Session ID: `{session_id}`",
                ephemeral=True
            )

        except NoActiveSessionError:
            await interaction.response.send_message(
                "❌ No active attendance session to close.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error closing attendance: {str(e)}",
                ephemeral=True
            )
            print(f"Error in close_attendance: {e}")
            import traceback
            traceback.print_exc()

    @app_commands.command(name="here", description="Submit your attendance with the current code")
    @app_commands.describe(code="The current attendance code")
    async def here(self, interaction: discord.Interaction, code: str):
        """Submit attendance with the current code."""
        # Validate channel
        if not self._is_attendance_channel(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the attendance channel.",
                ephemeral=True
            )
            return

        try:
            # Submit attendance
            code_upper = code.upper().strip()
            await self.session_manager.submit_attendance(
                interaction.user.id,
                interaction.user.name,
                code_upper
            )

            # Confirm to student (ephemeral)
            await interaction.response.send_message(
                f"✅ Attendance recorded for {interaction.user.mention}!\n"
                f"Code: `{code_upper}`\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}",
                ephemeral=True
            )

        except NoActiveSessionError:
            await interaction.response.send_message(
                "❌ No active attendance session. Please wait for the instructor to start attendance.",
                ephemeral=True
            )
        except InvalidCodeError:
            await interaction.response.send_message(
                f"❌ Code `{code.upper()}` is invalid or has expired.\n"
                f"Please use the current code shown in the attendance message.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error submitting attendance: {str(e)}",
                ephemeral=True
            )
            print(f"Error in here command: {e}")

    @app_commands.command(name="register", description="Register your student ID and name")
    @app_commands.describe(
        student_id="Your student ID",
        student_name="Your full name (optional)"
    )
    async def register(
        self,
        interaction: discord.Interaction,
        student_id: str,
        student_name: str = None
    ):
        """Register student ID and name for gradebook integration."""
        try:
            # Check if already registered
            existing = await self.database.get_student_info(interaction.user.id)

            # Register the student
            await self.database.register_student(
                interaction.user.id,
                student_id,
                student_name
            )

            if existing:
                # Update message
                await interaction.response.send_message(
                    f"✅ Registration updated!\n"
                    f"Student ID: `{student_id}`\n"
                    f"Name: {student_name if student_name else '(not provided)'}\n"
                    f"Discord: {interaction.user.mention}",
                    ephemeral=True
                )
            else:
                # New registration message
                await interaction.response.send_message(
                    f"✅ Registration successful!\n"
                    f"Student ID: `{student_id}`\n"
                    f"Name: {student_name if student_name else '(not provided)'}\n"
                    f"Discord: {interaction.user.mention}\n\n"
                    f"Your attendance records will now include your student information.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error registering: {str(e)}",
                ephemeral=True
            )
            print(f"Error in register command: {e}")
            import traceback
            traceback.print_exc()

    @app_commands.command(name="export_csv", description="Export attendance records to CSV (admin only)")
    @app_commands.describe(session_id="Optional: Session ID to export (leave empty for all records)")
    async def export_csv(self, interaction: discord.Interaction, session_id: str = None):
        """Export attendance records to CSV file."""
        # Validate channel
        if not self._is_admin_channel(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the admin channel.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if session_id:
                filename = f"attendance_{session_id}.csv"
            else:
                filename = f"attendance_all_{timestamp}.csv"

            output_path = os.path.join("data", filename)

            # Export to CSV
            record_count = await self.database.export_to_csv(output_path, session_id)

            if record_count == 0:
                await interaction.followup.send(
                    "❌ No records found to export.",
                    ephemeral=True
                )
                return

            # Send the file
            file = discord.File(output_path, filename=filename)
            await interaction.followup.send(
                f"✅ Exported {record_count} record(s) to CSV:",
                file=file,
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error exporting CSV: {str(e)}",
                ephemeral=True
            )
            print(f"Error in export_csv: {e}")
            import traceback
            traceback.print_exc()

    async def _rotate_code_loop(self):
        """Background task to rotate attendance codes every N seconds."""
        try:
            while self.session_manager.is_active:
                # Wait for the configured interval
                await asyncio.sleep(config.CODE_ROTATION_INTERVAL)

                if not self.session_manager.is_active:
                    break

                # Generate new code
                old_code = self.session_manager.current_code
                new_code = generate_code(config.CODE_LENGTH, previous_code=old_code)

                # Update session manager
                self.session_manager.update_code(new_code)

                # Update Discord message
                try:
                    channel = self.bot.get_channel(self.session_manager.channel_id)
                    if channel and self.session_manager.message_id:
                        message = await channel.fetch_message(self.session_manager.message_id)

                        embed = discord.Embed(
                            title="📋 Attendance is Now Open!",
                            description=f"Use the code below to mark your attendance:",
                            color=discord.Color.green()
                        )
                        embed.add_field(
                            name="Current Code",
                            value=f"**`{new_code}`**",
                            inline=False
                        )
                        embed.add_field(
                            name="How to Submit",
                            value=f"Type `/here {new_code}` in this channel",
                            inline=False
                        )
                        embed.add_field(
                            name="Status",
                            value=f"{self.session_manager.get_submission_count()} student(s) submitted",
                            inline=False
                        )
                        embed.set_footer(text="Code changes every 15 seconds • Only the latest submission counts")

                        await message.edit(embed=embed)

                except discord.NotFound:
                    print("Attendance message not found, stopping rotation")
                    break
                except Exception as e:
                    print(f"Error updating attendance message: {e}")
                    # Continue rotation even if message update fails

        except asyncio.CancelledError:
            print("Code rotation task cancelled")
        except Exception as e:
            print(f"Error in code rotation loop: {e}")
            import traceback
            traceback.print_exc()


async def setup(bot: commands.Bot):
    """Setup function to load the cog."""
    await bot.add_cog(AttendanceCog(bot))
