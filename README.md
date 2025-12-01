# Discord Attendance Bot

An automated attendance tracking system for Discord servers using rotating codes. Perfect for classroom environments where you want to take attendance during live sessions.

## Features

- **Rotating Codes**: Attendance codes automatically change every 15 seconds to prevent sharing
- **Slash Commands**: Modern Discord slash commands for easy interaction
- **SQLite Database**: Reliable local storage with automatic concurrent access handling
- **CSV Export**: Export attendance records for analysis or record-keeping
- **Student Registration**: Link Discord accounts to student IDs for gradebook integration
- **Admin Management**: Manually mark students as present, excused, or remove records
- **Last Submission Wins**: Students can correct mistakes by resubmitting
- **Ephemeral Responses**: Student submissions are private (only visible to them)
- **Channel Restrictions**: Admin commands work only in admin channel, attendance only in designated channel

## How It Works

### During Class

1. **Instructor starts attendance** in admin channel:
   ```
   /open_attendance
   ```

2. **Bot posts a message** in the admin channel with a code like "A1B2" (display on projector)

3. **Students submit attendance** in the attendance channel:
   ```
   /here A1B2
   ```

4. **Code rotates automatically** every 15 seconds
   - Old codes become invalid
   - Students using expired codes get an error message

5. **Instructor closes attendance** when done:
   ```
   /close_attendance
   ```

6. All records are automatically saved to the database

## Installation

### Prerequisites

- Python 3.9 or higher
- A Discord bot token
- Admin access to your Discord server

### Step 1: Set Up Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" tab:
   - Click "Add Bot"
   - Enable "Message Content Intent"
   - Copy the bot token (you'll need this later)

4. Go to the "OAuth2" → "URL Generator" tab:
   - Select scopes: `bot` and `applications.commands`
   - Select bot permissions:
     - Send Messages
     - Embed Links
     - Read Messages/View Channels
     - Read Message History
     - Use Slash Commands
   - Copy the generated URL and open it in your browser to invite the bot to your server

5. **Important:** Verify bot permissions in your Discord server:
   - Go to your Discord server settings → Roles
   - Find your bot's role (usually same name as the bot)
   - Ensure it has "View Channels" and "Send Messages" permissions
   - Or, for the attendance and admin channels specifically:
     - Right-click the channel → Edit Channel → Permissions
     - Add your bot's role with "View Channel" and "Send Messages" permissions

### Step 2: Get Channel IDs

1. Enable Developer Mode in Discord (Desktop/Web):
   - Click the User Settings (Gear Icon ⚙️) at the bottom-left near your username
   - In the left sidebar, scroll down past "Billing Settings" until you see "APP SETTINGS"
   - Under "APP SETTINGS", click on "Advanced"
   - Toggle "Developer Mode" to On

2. Right-click on your admin channel → "Copy Channel ID"
3. Right-click on your attendance channel → "Copy Channel ID"

### Step 3: Install the Bot

#### Option A: Using Docker (Recommended)

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd discord-attendance
   ```

2. Create your configuration file:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your Discord credentials:
   ```env
   DISCORD_BOT_TOKEN=your_bot_token_here
   ADMIN_CHANNEL_ID=123456789012345678
   ATTENDANCE_CHANNEL_ID=987654321098765432
   ```

4. Start the bot:
   ```bash
   docker compose up -d
   ```

5. View logs:
   ```bash
   docker compose logs -f
   ```

6. Stop the bot:
   ```bash
   docker compose down
   ```

**Docker Commands Reference:**

| Command | Description |
|---------|-------------|
| `docker compose up -d` | Start the bot in background |
| `docker compose down` | Stop the bot |
| `docker compose logs -f` | View live logs |
| `docker compose restart` | Restart the bot |
| `docker compose build` | Rebuild the image (after code changes) |
| `docker compose pull && docker compose up -d` | Update to latest version |

**Data Persistence:** The database is stored in `data/` which is mounted as a Docker volume. To backup:
```bash
cp data/attendance.db data/attendance.db.backup
```

#### Option B: Using Python Directly

1. Clone or download this repository:
   ```bash
   git clone <repository-url>
   cd discord-attendance
   ```

2. Install dependencies:

   **Using pip (traditional):**
   ```bash
   pip install -r requirements.txt
   ```

   **Using uv (faster, recommended):**
   ```bash
   # Install uv if you haven't already
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install dependencies with uv
   uv pip install -r requirements.txt
   ```

   > **Note:** [uv](https://github.com/astral-sh/uv) is a fast Python package installer that's 10-100x faster than pip.

3. Create your configuration file:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` with your settings:
   ```env
   DISCORD_BOT_TOKEN=your_bot_token_here
   ADMIN_CHANNEL_ID=123456789012345678
   ATTENDANCE_CHANNEL_ID=987654321098765432
   DATABASE_PATH=data/attendance.db
   CODE_ROTATION_INTERVAL=15
   CODE_LENGTH=4
   ```

5. Run the bot:
   ```bash
   python main.py
   ```

You should see:
```
Configuration validated successfully
Starting Discord bot...
Logged in as YourBot (ID: ...)
Bot is ready!
```

## Commands

### Student Commands

#### `/register [student_id] [student_name]` - Register your student information (Any Channel)
- `student_id`: Your student ID number (required)
- `student_name`: Your full name (optional)
- **Examples:**
  - `/register 12345678 John Doe`
  - `/register 12345678`
- Can be updated anytime by running the command again
- Links your Discord account to your student ID for gradebook integration

#### `/here [code]` - Submit attendance (Attendance Channel Only)
- `code`: The current attendance code displayed on screen
- **Example:** `/here A1B2`
- Must match the current code
- Only your last submission counts

### Admin Commands (Admin Channel Only)

#### `/open_attendance` - Start a new attendance session
- Posts code message in admin channel (display on projector)
- Posts notification in attendance channel
- Starts automatic code rotation

#### `/close_attendance` - End the current attendance session
- Saves all records to database
- Shows total submission count
- Updates both channel messages to show session closed

#### `/export_csv [session_id]` - Export attendance records to CSV
- Without `session_id`: exports all records
- With `session_id`: exports only that session's records
- **Examples:**
  - `/export_csv` (all records)
  - `/export_csv 1733068800` (specific session)

#### `/excuse [student] [date]` - Mark a student as excused
- `student`: Student ID, Discord username, or Discord user ID (autocomplete available)
- `date`: Date in YYYY-MM-DD format (defaults to today)
- **Examples:**
  - `/excuse 12345678` (today)
  - `/excuse 12345678 2025-12-15` (specific date)
  - `/excuse @JohnDoe 2025-12-15` (using Discord mention)
- Creates or updates attendance record with "excused" status

#### `/mark_present [student] [date] [session_id]` - Manually mark a student as present
- `student`: Student ID, Discord username, or Discord user ID (autocomplete available)
- `date`: Date in YYYY-MM-DD format (defaults to today)
- `session_id`: Optional specific session ID
- **Examples:**
  - `/mark_present 12345678` (today)
  - `/mark_present 12345678 2025-12-15` (specific date)
  - `/mark_present 12345678 2025-12-15 1733068800` (specific session)
- Creates new attendance record or updates existing record to "present"

#### `/remove_attendance [student] [date] [session_id]` - Remove a student's attendance record
- `student`: Student ID, Discord username, or Discord user ID (autocomplete available)
- `date`: Date in YYYY-MM-DD format (optional if session_id provided)
- `session_id`: Optional specific session ID (optional if date provided)
- **Examples:**
  - `/remove_attendance 12345678 2025-12-15` (all records for that date)
  - `/remove_attendance 12345678 2025-12-15 1733068800` (specific session)
- Must specify at least one of date or session_id
- Removes the attendance record from database

## Configuration Options

Edit `.env` to customize:

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token | (required) |
| `ADMIN_CHANNEL_ID` | Channel ID for admin commands | (required) |
| `ATTENDANCE_CHANNEL_ID` | Channel ID for student submissions | (required) |
| `DATABASE_PATH` | Path to SQLite database file | `data/attendance.db` |
| `CODE_ROTATION_INTERVAL` | Seconds between code changes | `15` |
| `CODE_LENGTH` | Number of characters in codes | `4` |

## Troubleshooting

### Bot doesn't start

- **Check your token**: Make sure `DISCORD_BOT_TOKEN` is correct in `.env`
- **Check .env file**: Ensure all required variables are set
- **Check Python version**: Must be 3.9 or higher (`python --version`)
- **Check Docker**: If using Docker, ensure Docker is running

### Slash commands don't appear

- Wait 1-2 minutes after starting the bot (Discord syncs commands)
- Try leaving and rejoining the server
- Check bot permissions (it needs `applications.commands` scope)
- Restart Discord client

### Commands don't work in channels

- Verify channel IDs are correct (use Developer Mode to copy)
- Check that IDs are just numbers (no `<#...>` formatting)
- Ensure bot has permissions in both channels
- Try `/here test` in attendance channel to see if bot responds

### "403 Forbidden (error code: 50001): Missing Access"

This error means the bot doesn't have permission to send messages in the channel.

**Fix Option 1 (Channel-specific):**
1. Right-click the channel → "Edit Channel"
2. Go to "Permissions" tab
3. Click "+" to add a role/member
4. Select your bot's role
5. Enable these permissions:
   - ✅ View Channel
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Read Message History
6. Click "Save Changes"
7. Repeat for admin channel if needed

**Fix Option 2 (Server-wide):**
1. Server Settings → Roles
2. Find your bot's role
3. Enable "Send Messages" and "View Channels" permissions
4. Save

### "No active attendance session" error

- An admin must run `/open_attendance` first
- If bot restarted during a session, session state is lost - run `/open_attendance` again
- Check that you're using `/here` in the correct attendance channel

### Database errors

- Check that `data/` directory exists and is writable
- Ensure bot has write permissions to the directory
- Check available disk space
- For Docker: ensure volume mount is correct in `docker-compose.yml`

### Code rotation stops

- Check console/logs for error messages
- Verify the admin message wasn't deleted (bot needs it to update)
- Restart the bot if needed
- Check `CODE_ROTATION_INTERVAL` is not set too low (minimum 5 seconds recommended)

### Student autocomplete not working in admin commands

- Make sure students have registered with `/register` first
- Autocomplete searches student IDs, names, and Discord usernames
- Must be in admin channel for autocomplete to work
- Try typing at least 2-3 characters before expecting results

### CSV export is empty or missing students

- Ensure session has been closed with `/close_attendance`
- Check that students registered with `/register` (unregistered students will have empty student_id/student_name columns)
- Verify session_id is correct if exporting specific session
- Try exporting all records without session_id parameter

### Docker container keeps restarting

- Check logs: `docker compose logs -f`
- Verify `.env` file exists and has correct values
- Ensure bot token is valid
- Check that channel IDs are valid integers
- Try running without `-d` flag to see errors: `docker compose up`

## Security Considerations

- **Never commit `.env`**: Contains your bot token (add to `.gitignore`)
- **Restrict admin channel**: Only admins should have access
- **Database backups**: Regularly backup `data/attendance.db`
- **File permissions**: Keep `.env` and database file owner-readable only (chmod 600)

## FAQ

**Q: What happens if a student submits multiple times?**

A: Only their last submission is recorded (allows corrections).

**Q: Can students see who else submitted?**

A: No, all responses are ephemeral (private).

**Q: What if the bot crashes during attendance?**

A: Active session state is lost, but historical data in database remains. Restart and run `/open_attendance` again.

**Q: How long are codes valid?**

A: Each code is valid for exactly 15 seconds (configurable in `.env`).

**Q: Can I run multiple sessions per day?**

A: Yes, each session gets a unique session ID (Unix timestamp).

**Q: How do I backup attendance data?**

A: Copy the `data/attendance.db` file or use `/export_csv` to create CSV backups.

**Q: Can I change the code rotation speed?**

A: Yes, edit `CODE_ROTATION_INTERVAL` in `.env` (minimum 5 seconds recommended).

**Q: Can students who forgot to submit be marked present later?**

A: Yes, admins can use `/mark_present` to manually add attendance records.

**Q: What's the difference between "excused" and removing attendance?**

A: "Excused" marks the student as absent but excused (shows in CSV as "excused" status). Removing attendance completely deletes the record from the database.

**Q: How do I find a session ID?**

A: Session IDs are shown when closing attendance. They're also Unix timestamps (e.g., 1733068800). Use `/export_csv` without parameters to see all sessions in the CSV.

## Technical Documentation

For technical details about the architecture, database schema, and development, see [TECHNICAL.md](TECHNICAL.md).

## License

MIT License - feel free to modify and distribute.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review console output or logs for error messages
3. Verify your configuration in `.env`
4. Check Discord bot permissions
5. Consult [TECHNICAL.md](TECHNICAL.md) for architecture details

## Credits

Built with:
- [discord.py](https://discordpy.readthedocs.io/) - Discord API wrapper
- [aiosqlite](https://aiosqlite.omnilib.dev/) - Async SQLite operations
- [python-dotenv](https://pypi.org/project/python-dotenv/) - Environment variable management
