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

            # Get both channels
            admin_channel = self.bot.get_channel(config.ADMIN_CHANNEL_ID)
            attendance_channel = self.bot.get_channel(config.ATTENDANCE_CHANNEL_ID)

            if not admin_channel:
                await interaction.response.send_message(
                    "❌ Could not find admin channel. Please check configuration.",
                    ephemeral=True
                )
                return

            if not attendance_channel:
                await interaction.response.send_message(
                    "❌ Could not find attendance channel. Please check configuration.",
                    ephemeral=True
                )
                return

            # Post the code message in ADMIN channel (for projector display)
            code_embed = discord.Embed(
                title="📋 Attendance Code (Admin Only)",
                description="Show this code on the projector for students:",
                color=discord.Color.blue()
            )
            code_embed.add_field(
                name="Current Code",
                value=f"# **`{initial_code}`**",
                inline=False
            )
            code_embed.add_field(
                name="Status",
                value="0 student(s) submitted",
                inline=False
            )
            code_embed.set_footer(text="Code changes every 15 seconds • Only the latest submission counts")

            admin_message = await admin_channel.send(embed=code_embed)

            # Post a notification in ATTENDANCE channel (no code shown)
            student_embed = discord.Embed(
                title="📋 Attendance is Now Open!",
                description="Look at the projector for the attendance code.",
                color=discord.Color.green()
            )
            student_embed.add_field(
                name="How to Submit",
                value="Type `/here <code>` in this channel with the code shown on screen",
                inline=False
            )
            student_embed.set_footer(text="Code changes every 15 seconds • Only the latest submission counts")

            attendance_message = await attendance_channel.send(embed=student_embed)

            # Start session (store admin message ID for code updates)
            self.session_manager.start_session(initial_code, admin_message.id, admin_channel.id)
            # Also store attendance message ID for updating when closed
            self.session_manager.attendance_message_id = attendance_message.id
            self.session_manager.attendance_channel_id = attendance_channel.id

            # Start code rotation task
            self.rotation_task = asyncio.create_task(self._rotate_code_loop())

            # Confirm to admin
            await interaction.response.send_message(
                f"✅ Attendance session started!\n"
                f"Current code: `{initial_code}`\n"
                f"Code displayed in this channel (show on projector)\n"
                f"Students notified in <#{config.ATTENDANCE_CHANNEL_ID}>",
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

            # Update the admin channel message to show it's closed
            try:
                admin_channel = self.bot.get_channel(self.session_manager.channel_id or config.ADMIN_CHANNEL_ID)
                if admin_channel and self.session_manager.message_id:
                    admin_message = await admin_channel.fetch_message(self.session_manager.message_id)

                    admin_embed = discord.Embed(
                        title="📋 Attendance Session Closed",
                        description="This attendance session has ended.",
                        color=discord.Color.red()
                    )
                    admin_embed.add_field(
                        name="Total Submissions",
                        value=f"{saved_count} student(s)",
                        inline=False
                    )
                    admin_embed.set_footer(text=f"Session ID: {session_id}")

                    await admin_message.edit(embed=admin_embed)
            except Exception as e:
                print(f"Could not update admin message: {e}")

            # Update the attendance channel message to show it's closed
            try:
                attendance_channel = self.bot.get_channel(
                    getattr(self.session_manager, 'attendance_channel_id', None) or config.ATTENDANCE_CHANNEL_ID
                )
                attendance_msg_id = getattr(self.session_manager, 'attendance_message_id', None)
                if attendance_channel and attendance_msg_id:
                    attendance_message = await attendance_channel.fetch_message(attendance_msg_id)

                    student_embed = discord.Embed(
                        title="📋 Attendance is Now Closed",
                        description="This attendance session has ended.",
                        color=discord.Color.red()
                    )
                    student_embed.add_field(
                        name="Total Submissions",
                        value=f"{saved_count} student(s)",
                        inline=False
                    )
                    student_embed.set_footer(text=f"Session ID: {session_id}")

                    await attendance_message.edit(embed=student_embed)
            except Exception as e:
                print(f"Could not update attendance channel message: {e}")

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

    async def _resolve_student(self, identifier: str) -> tuple:
        """
        Resolve a student identifier to user_id and display name.

        Args:
            identifier: Student ID, Discord username, or Discord user_id

        Returns:
            Tuple of (user_id, display_name, student_info) or (None, None, None) if not found
        """
        student_info = await self.database.find_student(identifier)
        if not student_info:
            return None, None, None

        user_id = student_info['user_id']
        display_name = (
            student_info.get('student_name') or
            student_info.get('username') or
            student_info.get('student_id') or
            str(user_id)
        )
        return user_id, display_name, student_info

    @app_commands.command(name="excuse", description="Mark a student as excused for a date (admin only)")
    @app_commands.describe(
        student="Student ID, Discord username, or Discord user ID",
        date="Date in YYYY-MM-DD format (defaults to today)"
    )
    async def excuse(
        self,
        interaction: discord.Interaction,
        student: str,
        date: str = None
    ):
        """Mark a student as excused for a specific date."""
        # Validate channel
        if not self._is_admin_channel(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the admin channel.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Resolve student
            user_id, display_name, student_info = await self._resolve_student(student)
            if not user_id:
                await interaction.followup.send(
                    f"❌ Student not found: `{student}`\n"
                    f"Try using their student ID, Discord username, or Discord user ID.",
                    ephemeral=True
                )
                return

            # Default to today's date
            if not date:
                date = datetime.now().strftime('%Y-%m-%d')

            # Validate date format
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                await interaction.followup.send(
                    f"❌ Invalid date format: `{date}`\n"
                    f"Please use YYYY-MM-DD format (e.g., 2025-12-01).",
                    ephemeral=True
                )
                return

            # Check if student has an attendance record for this date
            existing = await self.database.get_attendance_record(user_id, date_id=date)

            if existing:
                # Update existing record to excused
                count = await self.database.update_attendance_status(user_id, 'excused', date_id=date)
                if count > 0:
                    await interaction.followup.send(
                        f"✅ Marked **{display_name}** as excused for `{date}`\n"
                        f"(Updated existing attendance record)",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Failed to update attendance record for **{display_name}**.",
                        ephemeral=True
                    )
            else:
                # Create new excused record
                username = student_info.get('username') or student_info.get('student_name') or student
                result = await self.database.add_manual_attendance(
                    user_id=user_id,
                    username=username,
                    date_id=date,
                    status='excused'
                )
                await interaction.followup.send(
                    f"✅ Marked **{display_name}** as excused for `{date}`\n"
                    f"Session ID: `{result['session_id']}`",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error marking student as excused: {str(e)}",
                ephemeral=True
            )
            print(f"Error in excuse command: {e}")
            import traceback
            traceback.print_exc()

    @app_commands.command(name="mark_present", description="Manually mark a student as present (admin only)")
    @app_commands.describe(
        student="Student ID, Discord username, or Discord user ID",
        date="Date in YYYY-MM-DD format (defaults to today)",
        session_id="Optional: specific session ID"
    )
    async def mark_present(
        self,
        interaction: discord.Interaction,
        student: str,
        date: str = None,
        session_id: str = None
    ):
        """Manually mark a student as present for a specific date."""
        # Validate channel
        if not self._is_admin_channel(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the admin channel.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Resolve student
            user_id, display_name, student_info = await self._resolve_student(student)
            if not user_id:
                await interaction.followup.send(
                    f"❌ Student not found: `{student}`\n"
                    f"Try using their student ID, Discord username, or Discord user ID.",
                    ephemeral=True
                )
                return

            # Default to today's date
            if not date:
                date = datetime.now().strftime('%Y-%m-%d')

            # Validate date format
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                await interaction.followup.send(
                    f"❌ Invalid date format: `{date}`\n"
                    f"Please use YYYY-MM-DD format (e.g., 2025-12-01).",
                    ephemeral=True
                )
                return

            # Check if student already has an attendance record
            existing = await self.database.get_attendance_record(
                user_id,
                date_id=date if not session_id else None,
                session_id=session_id
            )

            if existing:
                # Update existing record to present
                count = await self.database.update_attendance_status(
                    user_id, 'present',
                    date_id=date if not session_id else None,
                    session_id=session_id
                )
                if count > 0:
                    await interaction.followup.send(
                        f"✅ Marked **{display_name}** as present for `{date}`\n"
                        f"(Updated existing record - was previously `{existing.get('status', 'unknown')}`)",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Failed to update attendance record for **{display_name}**.",
                        ephemeral=True
                    )
            else:
                # Create new attendance record
                username = student_info.get('username') or student_info.get('student_name') or student
                result = await self.database.add_manual_attendance(
                    user_id=user_id,
                    username=username,
                    date_id=date,
                    session_id=session_id,
                    status='present'
                )
                await interaction.followup.send(
                    f"✅ Marked **{display_name}** as present for `{date}`\n"
                    f"Session ID: `{result['session_id']}`",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error marking student as present: {str(e)}",
                ephemeral=True
            )
            print(f"Error in mark_present command: {e}")
            import traceback
            traceback.print_exc()

    @app_commands.command(name="remove_attendance", description="Remove a student's attendance record (admin only)")
    @app_commands.describe(
        student="Student ID, Discord username, or Discord user ID",
        date="Date in YYYY-MM-DD format",
        session_id="Optional: specific session ID (if not provided, removes all records for the date)"
    )
    async def remove_attendance(
        self,
        interaction: discord.Interaction,
        student: str,
        date: str = None,
        session_id: str = None
    ):
        """Remove a student's attendance record."""
        # Validate channel
        if not self._is_admin_channel(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the admin channel.",
                ephemeral=True
            )
            return

        # Require at least one filter (date or session_id)
        if not date and not session_id:
            await interaction.response.send_message(
                "❌ Please specify either a date or session_id to remove attendance records.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Resolve student
            user_id, display_name, student_info = await self._resolve_student(student)
            if not user_id:
                await interaction.followup.send(
                    f"❌ Student not found: `{student}`\n"
                    f"Try using their student ID, Discord username, or Discord user ID.",
                    ephemeral=True
                )
                return

            # Validate date format if provided
            if date:
                try:
                    datetime.strptime(date, '%Y-%m-%d')
                except ValueError:
                    await interaction.followup.send(
                        f"❌ Invalid date format: `{date}`\n"
                        f"Please use YYYY-MM-DD format (e.g., 2025-12-01).",
                        ephemeral=True
                    )
                    return

            # Check if record exists before removing
            existing = await self.database.get_attendance_record(
                user_id,
                date_id=date if not session_id else None,
                session_id=session_id
            )

            if not existing:
                await interaction.followup.send(
                    f"❌ No attendance record found for **{display_name}**"
                    + (f" on `{date}`" if date else "")
                    + (f" (session: `{session_id}`)" if session_id else ""),
                    ephemeral=True
                )
                return

            # Remove the record
            count = await self.database.remove_attendance(
                user_id,
                date_id=date if not session_id else None,
                session_id=session_id
            )

            if count > 0:
                await interaction.followup.send(
                    f"✅ Removed {count} attendance record(s) for **{display_name}**"
                    + (f" on `{date}`" if date else "")
                    + (f" (session: `{session_id}`)" if session_id else ""),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to remove attendance record for **{display_name}**.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error removing attendance: {str(e)}",
                ephemeral=True
            )
            print(f"Error in remove_attendance command: {e}")
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

                # Update the admin channel message with new code
                try:
                    admin_channel = self.bot.get_channel(self.session_manager.channel_id)
                    if admin_channel and self.session_manager.message_id:
                        message = await admin_channel.fetch_message(self.session_manager.message_id)

                        code_embed = discord.Embed(
                            title="📋 Attendance Code (Admin Only)",
                            description="Show this code on the projector for students:",
                            color=discord.Color.blue()
                        )
                        code_embed.add_field(
                            name="Current Code",
                            value=f"# **`{new_code}`**",
                            inline=False
                        )
                        code_embed.add_field(
                            name="Status",
                            value=f"{self.session_manager.get_submission_count()} student(s) submitted",
                            inline=False
                        )
                        code_embed.set_footer(text="Code changes every 15 seconds • Only the latest submission counts")

                        await message.edit(embed=code_embed)

                except discord.NotFound:
                    print("Admin message not found, stopping rotation")
                    break
                except Exception as e:
                    print(f"Error updating admin message: {e}")
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
