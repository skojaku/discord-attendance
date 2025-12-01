# Technical Documentation

This document provides technical details about the Discord Attendance Bot's architecture, database schema, and implementation details.

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
├── Dockerfile              # Docker container definition
├── docker-compose.yml      # Docker Compose configuration
├── .dockerignore           # Files excluded from Docker build
└── README.md              # User documentation
```

## Database Schema

The SQLite database uses two main tables with relationships for tracking attendance and student information.

### Attendance Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incrementing primary key |
| `user_id` | INTEGER | Discord user ID |
| `username` | TEXT | Discord username |
| `timestamp` | TEXT | Submission timestamp |
| `date_id` | TEXT | Date of submission (YYYY-MM-DD) |
| `session_id` | TEXT | Unique session identifier |
| `status` | TEXT | Attendance status: 'present', 'excused', or NULL (default present) |

**Unique constraint**: `(user_id, session_id)` ensures one record per student per session.

### Students Table (Registration)

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | INTEGER | Discord user ID (primary key) |
| `student_id` | TEXT | Student ID number |
| `student_name` | TEXT | Student's real name (optional) |
| `registered_at` | TEXT | Registration timestamp |

### CSV Export Format

Exported CSV files join data from both tables to provide complete student information:

```csv
student_id,student_name,discord_username,user_id,timestamp,date_id,session_id,status
12345678,John Doe,john_doe,123456789,2025-12-01 14:35:22,2025-12-01,1733068800,present
87654321,Jane Smith,jane_s,987654321,2025-12-01 14:36:10,2025-12-01,1733068800,excused
```

**Note**: If a student hasn't registered with `/register`, their `student_id` and `student_name` columns will be empty in the CSV export.

## Concurrent Access Architecture

The bot safely handles multiple students submitting simultaneously using several techniques:

### 1. SQLite Write-Ahead Logging (WAL) Mode
- Allows concurrent reads during writes
- Improves performance under high load
- Reduces lock contention

### 2. asyncio.Lock()
- Prevents race conditions in the session manager
- Ensures thread-safe access to shared state
- Guards critical sections of code

### 3. UNIQUE Constraint
- Database enforces one record per student per session
- Prevents duplicate entries at the database level
- Automatic conflict resolution

### 4. INSERT OR REPLACE
- Atomic upsert operations for duplicate submissions
- Implements "last submission wins" behavior
- No need for separate UPDATE logic

### 5. aiosqlite
- Async-compatible database operations
- Non-blocking I/O for better concurrency
- Integrates seamlessly with discord.py's async architecture

This architecture safely handles 50-200 concurrent students without data loss or corruption.

## Code Generation

### Algorithm

The bot generates attendance codes using cryptographically secure random generation:

```python
import secrets
import string

def generate_code(length: int, previous_code: str = None) -> str:
    """Generate a random alphanumeric code."""
    characters = string.ascii_uppercase + string.digits

    # Generate new code, avoiding collision with previous
    while True:
        code = ''.join(secrets.choice(characters) for _ in range(length))
        if code != previous_code:
            return code
```

### Security Features

- **Cryptographically secure**: Uses `secrets` module, not `random`
- **Collision avoidance**: Never repeats the immediately previous code
- **Character set**: Uppercase letters (A-Z) + digits (0-9) = 36 possibilities
- **Default length**: 4 characters = 36^4 = 1,679,616 possible codes

### Code Rotation

Codes rotate automatically every 15 seconds (configurable):

1. Background asyncio task runs continuously during active session
2. Generates new code different from previous
3. Updates in-memory session state
4. Updates Discord message embed with new code
5. Old code immediately becomes invalid

## Session Management

### In-Memory State

The `AttendanceSession` class maintains active session state:

```python
class AttendanceSession:
    def __init__(self):
        self.is_active: bool = False
        self.current_code: str = None
        self.session_id: str = None
        self.submissions: dict = {}  # {user_id: submission_data}
        self.message_id: int = None
        self.channel_id: int = None
        self._lock = asyncio.Lock()
```

### Lifecycle

1. **Start**: `/open_attendance` creates new session with unique ID (Unix timestamp)
2. **Active**: Students submit, codes rotate, submissions tracked in memory
3. **End**: `/close_attendance` saves all submissions to database
4. **Reset**: Session state cleared, ready for next session

### Why In-Memory?

- **Performance**: No database writes during active session (fast submissions)
- **Atomic saves**: All records saved together when session ends
- **Simplicity**: Clear lifecycle, easier to reason about
- **Tradeoff**: Active session lost if bot crashes (historical data preserved)

## Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DISCORD_BOT_TOKEN` | string | (required) | Discord bot authentication token |
| `ADMIN_CHANNEL_ID` | integer | (required) | Channel ID for admin commands |
| `ATTENDANCE_CHANNEL_ID` | integer | (required) | Channel ID for student submissions |
| `DATABASE_PATH` | string | `data/attendance.db` | Path to SQLite database file |
| `CODE_ROTATION_INTERVAL` | integer | `15` | Seconds between code changes |
| `CODE_LENGTH` | integer | `4` | Number of characters in codes |

### Validation

Configuration is validated on startup:

```python
def validate_config():
    """Validate required configuration."""
    required = ['DISCORD_BOT_TOKEN', 'ADMIN_CHANNEL_ID', 'ATTENDANCE_CHANNEL_ID']
    for key in required:
        if not getattr(config, key):
            raise ValueError(f"Missing required configuration: {key}")
```

## Error Handling

### Custom Exceptions

```python
class SessionAlreadyActiveError(Exception):
    """Raised when trying to start a session while one is active."""

class NoActiveSessionError(Exception):
    """Raised when trying to use session features with no active session."""

class InvalidCodeError(Exception):
    """Raised when student submits wrong or expired code."""

class WrongChannelError(Exception):
    """Raised when command used in wrong channel."""
```

### User-Facing Error Messages

All errors result in ephemeral Discord messages (only visible to the user):

- Clear explanation of what went wrong
- Actionable guidance on how to fix it
- No technical jargon or stack traces

## Docker Deployment

### Multi-Stage Build

The Dockerfile uses a multi-stage build for smaller images:

```dockerfile
# Build stage: Install dependencies
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage: Copy only necessary files
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
CMD ["python", "main.py"]
```

### Data Persistence

Docker Compose mounts a volume for the database:

```yaml
volumes:
  - ./data:/app/data
```

This ensures attendance records persist even when containers are stopped or rebuilt.

## Development

### Code Structure

- **config.py**: Configuration validation and environment variable loading
- **utils/code_generator.py**: Code generation with collision avoidance
- **utils/errors.py**: Custom exception classes
- **storage/session_manager.py**: In-memory session state (singleton pattern)
- **storage/database.py**: SQLite operations with concurrent access handling
- **bot/client.py**: Bot initialization and event handlers
- **bot/cogs/attendance.py**: Slash command implementations

### Testing

Run the test suite:

```bash
pytest
```

### Adding New Commands

1. Add command method in `bot/cogs/attendance.py`
2. Use `@app_commands.command` decorator
3. Add channel validation if needed
4. Handle errors with try/except
5. Send ephemeral responses
6. Update documentation

## Security Considerations

### Bot Token Security

- **Never commit `.env`**: Contains sensitive authentication credentials
- **Environment variables**: Token loaded at runtime, not hardcoded
- **File permissions**: Keep `.env` readable only by owner (chmod 600)

### Database Security

- **File permissions**: Keep database file owner-readable only (chmod 600)
- **Regular backups**: Prevent data loss from corruption or accidents
- **No sensitive data**: Only Discord IDs, usernames, and student IDs stored
- **SQL injection**: Parameterized queries prevent injection attacks

### Channel Restrictions

- **Admin channel**: Only admins should have access
- **Attendance channel**: Students need read/write access
- **Command validation**: Each command checks channel before executing

### Code Security

- **Cryptographically secure random**: Uses `secrets` module
- **No pattern predictability**: Each code is truly random
- **Time-limited validity**: Codes expire after 15 seconds
- **No reuse**: Collision avoidance prevents immediate reuse

## Performance Characteristics

### Scalability

- **Concurrent submissions**: Handles 50-200 students simultaneously
- **Database performance**: WAL mode allows concurrent reads during writes
- **Memory usage**: In-memory session state is minimal (< 1 MB for typical class)
- **Network**: Ephemeral responses reduce Discord API calls

### Bottlenecks

- **Discord rate limits**: Bot is limited by Discord API rate limits
- **Message edits**: Code rotation requires editing message embed
- **Database writes**: Batch save at session end can take a few seconds for large classes

### Optimization Opportunities

- **Connection pooling**: Could use connection pool for database (currently single connection)
- **Batch message updates**: Could update less frequently for very large classes
- **Caching**: Could cache student lookups for admin commands

## FAQ for Developers

**Q: Why use in-memory session state instead of database?**

A: Performance and simplicity. Writing to database on every submission would be slower and more complex. Batch saving at the end is faster and atomic.

**Q: What happens to active session if bot crashes?**

A: Active session data is lost (students must resubmit after restart), but historical data in database is preserved.

**Q: Why SQLite instead of PostgreSQL/MySQL?**

A: Simplicity and portability. No separate database server required. Perfect for small-to-medium deployments. Easy to backup (single file).

**Q: Can I run multiple bot instances?**

A: Not recommended. Session state is in-memory and not shared between instances. Multiple instances would conflict.

**Q: How do I migrate to a different database?**

A: Implement a new database adapter following the same interface as `storage/database.py`. Swap the implementation in the cog.

**Q: Can I add webhooks or external integrations?**

A: Yes! Add webhook calls in the appropriate command handlers or create new commands. Consider async HTTP clients like `aiohttp`.
