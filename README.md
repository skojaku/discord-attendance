# Discord Attendance Bot

An automated attendance tracking system for Discord servers using rotating codes. Perfect for classroom environments where you want to take attendance during live sessions.

## Features

- **Rotating Codes**: Attendance codes automatically change every 15 seconds to prevent sharing
- **Slash Commands**: Modern Discord slash commands for easy interaction
- **SQLite Database**: Reliable local storage with automatic concurrent access handling
- **CSV Export**: Export attendance records for analysis or record-keeping
- **Last Submission Wins**: Students can correct mistakes by resubmitting
- **Ephemeral Responses**: Student submissions are private (only visible to them)
- **Channel Restrictions**: Admin commands work only in admin channel, attendance only in designated channel

## How It Works

### During Class

1. **Instructor starts attendance** in admin channel:
   ```
   /open_attendance
   ```

2. **Bot posts a message** in the attendance channel with a code like "A1B2"

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
   - Click the User Settings (Gear Icon ⚙️) at the bottom-left near your username.
   - In the left sidebar, scroll down past "Billing Settings" until you see the section header "APP SETTINGS".
   - Under "APP SETTINGS", click on "Advanced".
   - Toggle "Developer Mode" to On.

2. Right-click on your admin channel → "Copy Channel ID"
3. Right-click on your attendance channel → "Copy Channel ID"

### Step 3: Install the Bot

1. Clone or download this repository:
   ```bash
   git clone <repository-url>
   cd discord-attendance
   ```

2. Install dependencies:

   **Option A: Using pip (traditional)**
   ```bash
   pip install -r requirements.txt
   ```

   **Option B: Using uv (faster, recommended)**
   ```bash
   # Install uv if you haven't already
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install dependencies with uv
   uv pip install -r requirements.txt
   ```

   > **Note:** [uv](https://github.com/astral-sh/uv) is a fast Python package installer that's 10-100x faster than pip. It's fully compatible with pip and can be used as a drop-in replacement.

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

### Admin Commands (Admin Channel Only)

- `/open_attendance` - Start a new attendance session
  - Posts attendance message in attendance channel
  - Starts code rotation

- `/close_attendance` - End the current attendance session
  - Saves all records to database
  - Shows total submission count

- `/export_csv [session_id]` - Export attendance records to CSV
  - Without `session_id`: exports all records
  - With `session_id`: exports only that session's records

### Student Commands (Attendance Channel Only)

- `/here [code]` - Submit attendance with the current code
  - Example: `/here A1B2`
  - Must match the current code displayed
  - Only your last submission counts

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

## Database Schema

The SQLite database stores records in the `attendance` table:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incrementing primary key |
| `user_id` | INTEGER | Discord user ID |
| `username` | TEXT | Discord username |
| `timestamp` | TEXT | Submission timestamp |
| `date_id` | TEXT | Date of submission (YYYY-MM-DD) |
| `session_id` | TEXT | Unique session identifier |

**Unique constraint**: `(user_id, session_id)` ensures one record per student per session.

## CSV Export Format

Exported CSV files contain the following columns:

```csv
user_id,username,timestamp,date_id,session_id
123456789,john_doe,2025-12-01 14:35:22,2025-12-01,1733068800
```

## Project Structure

```
discord-attendance/
├── bot/
│   ├── client.py           # Bot initialization
│   └── cogs/
│       └── attendance.py   # Attendance commands
├── storage/
│   ├── database.py         # SQLite database handler
│   └── session_manager.py  # Session state management
├── utils/
│   ├── code_generator.py   # Random code generation
│   └── errors.py           # Custom exceptions
├── data/
│   └── attendance.db       # SQLite database (created automatically)
├── config.py               # Configuration management
├── main.py                 # Entry point
├── requirements.txt        # Python dependencies
├── .env.example            # Configuration template
└── README.md              # This file
```

## How Concurrent Access Works

The bot handles multiple students submitting at the same time using:

1. **SQLite Write-Ahead Logging (WAL) mode**: Allows concurrent reads during writes
2. **asyncio.Lock()**: Prevents race conditions in the session manager
3. **UNIQUE constraint**: Database ensures one record per student per session
4. **INSERT OR REPLACE**: Atomic upsert operations for duplicate submissions
5. **aiosqlite**: Async-compatible database operations

This architecture safely handles 50-200 concurrent students without data loss or corruption.

## Troubleshooting

### Bot doesn't start

- **Check your token**: Make sure `DISCORD_BOT_TOKEN` is correct
- **Check .env file**: Ensure all required variables are set
- **Check Python version**: Must be 3.9 or higher

### Slash commands don't appear

- Wait 1-2 minutes after starting the bot (Discord syncs commands)
- Try leaving and rejoining the server
- Check bot permissions (it needs `applications.commands` scope)

### Commands don't work in channels

- Verify channel IDs are correct (use Developer Mode to copy)
- Check that IDs are just numbers (no `<#...>` formatting)
- Ensure bot has permissions in both channels

### "403 Forbidden (error code: 50001): Missing Access"

This error means the bot doesn't have permission to send messages in the channel.

**Fix:**
1. Right-click the attendance channel → "Edit Channel"
2. Go to "Permissions" tab
3. Click "+" to add a role/member
4. Select your bot's role
5. Enable these permissions:
   - ✅ View Channel
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Read Message History
6. Click "Save Changes"
7. Repeat for the admin channel if needed

**Alternative fix (server-wide):**
1. Server Settings → Roles
2. Find your bot's role
3. Enable "Send Messages" and "View Channels" permissions
4. Save

### "No active attendance session" error

- An admin must run `/open_attendance` first
- If bot restarted during a session, run `/open_attendance` again

### Database errors

- Check that `data/` directory exists
- Ensure bot has write permissions
- Check disk space

### Code rotation stops

- Check console for error messages
- Verify the attendance message wasn't deleted
- Restart the bot if needed

## Security Considerations

- **Never commit `.env`**: Contains your bot token
- **Restrict admin channel**: Only admins should access it
- **Database backups**: Regularly backup `data/attendance.db`
- **Code security**: Uses cryptographically secure random generation
- **File permissions**: Keep database file owner-readable only (chmod 600)

## Development

### Running tests

```bash
pytest
```

### Code structure

- `config.py`: Configuration validation
- `utils/code_generator.py`: Code generation with collision avoidance
- `utils/errors.py`: Custom exception classes
- `storage/session_manager.py`: In-memory session state (singleton pattern)
- `storage/database.py`: SQLite operations with concurrent access
- `bot/client.py`: Bot initialization and event handlers
- `bot/cogs/attendance.py`: Slash command implementations

## FAQ

**Q: What happens if a student submits multiple times?**
A: Only their last submission is recorded (allows corrections).

**Q: Can students see who else submitted?**
A: No, all responses are ephemeral (private).

**Q: What if the bot crashes during attendance?**
A: Active session state is lost, but historical data remains. Restart and run `/open_attendance` again.

**Q: How long are codes valid?**
A: Each code is valid for exactly 15 seconds (configurable).

**Q: Can I run multiple sessions per day?**
A: Yes, each session gets a unique session ID (Unix timestamp).

**Q: How do I backup attendance data?**
A: Copy the `data/attendance.db` file or use `/export_csv` to create backups.

**Q: Can I change the code rotation speed?**
A: Yes, edit `CODE_ROTATION_INTERVAL` in `.env` (minimum 5 seconds recommended).

## License

MIT License - feel free to modify and distribute.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review console output for error messages
3. Verify your configuration in `.env`
4. Check Discord bot permissions

## Credits

Built with:
- [discord.py](https://discordpy.readthedocs.io/) - Discord API wrapper
- [aiosqlite](https://aiosqlite.omnilib.dev/) - Async SQLite operations
- [python-dotenv](https://pypi.org/project/python-dotenv/) - Environment variable management
