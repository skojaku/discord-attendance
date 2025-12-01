"""Session state management for attendance tracking."""
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional
from utils.errors import SessionAlreadyActiveError, NoActiveSessionError, InvalidCodeError


class AttendanceSession:
    """Manages the state of an active attendance session."""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize session manager (only once due to singleton)."""
        if self._initialized:
            return

        self.session_id: Optional[str] = None
        self.current_code: Optional[str] = None
        self.message_id: Optional[int] = None  # Admin channel message (shows code)
        self.channel_id: Optional[int] = None  # Admin channel ID
        self.attendance_message_id: Optional[int] = None  # Attendance channel message
        self.attendance_channel_id: Optional[int] = None  # Attendance channel ID
        self.start_time: Optional[datetime] = None
        self.submissions: Dict[int, Dict] = {}
        self.is_active: bool = False
        self._initialized = True

    def start_session(self, initial_code: str, message_id: int, channel_id: int):
        """
        Initialize a new attendance session.

        Args:
            initial_code: The first attendance code
            message_id: Discord message ID for editing
            channel_id: Channel where attendance message was posted

        Raises:
            SessionAlreadyActiveError: If a session is already active
        """
        if self.is_active:
            raise SessionAlreadyActiveError("An attendance session is already active")

        self.session_id = str(int(time.time()))
        self.current_code = initial_code
        self.message_id = message_id
        self.channel_id = channel_id
        self.start_time = datetime.now()
        self.submissions = {}
        self.is_active = True

    def update_code(self, new_code: str):
        """
        Update the current valid attendance code.

        Args:
            new_code: The new code to set as valid

        Raises:
            NoActiveSessionError: If no session is active
        """
        if not self.is_active:
            raise NoActiveSessionError("No active attendance session")

        self.current_code = new_code

    async def submit_attendance(self, user_id: int, username: str, code: str):
        """
        Record an attendance submission.

        Args:
            user_id: Discord user ID
            username: Discord username
            code: The code submitted by the student

        Raises:
            NoActiveSessionError: If no session is active
            InvalidCodeError: If the submitted code doesn't match the current code

        Note: If a user submits multiple times, only the last submission is kept.
        """
        if not self.is_active:
            raise NoActiveSessionError("No active attendance session")

        async with self._lock:
            if code != self.current_code:
                raise InvalidCodeError(f"Code '{code}' is not valid or has expired")

            # Record submission (overwrites previous submission if exists)
            self.submissions[user_id] = {
                'username': username,
                'timestamp': datetime.now(),
                'code': code
            }

    def validate_code(self, code: str) -> bool:
        """
        Check if a code is currently valid.

        Args:
            code: Code to validate

        Returns:
            True if code matches current code, False otherwise
        """
        if not self.is_active:
            return False
        return code == self.current_code

    def end_session(self) -> List[Dict]:
        """
        End the attendance session and return all submissions.

        Returns:
            List of attendance records ready for database storage

        Raises:
            NoActiveSessionError: If no session is active
        """
        if not self.is_active:
            raise NoActiveSessionError("No active attendance session")

        # Prepare records for database
        records = []
        for user_id, data in self.submissions.items():
            records.append({
                'user_id': user_id,
                'username': data['username'],
                'timestamp': data['timestamp']
            })

        # Store session_id before resetting
        session_id = self.session_id

        # Reset session state
        self.is_active = False
        self.current_code = None
        # Keep message IDs until close_attendance updates both messages
        self.start_time = None
        # Keep submissions until they're saved, then clear

        return records, session_id

    def get_submission_count(self) -> int:
        """
        Get the number of students who have submitted attendance.

        Returns:
            Number of unique students who submitted
        """
        return len(self.submissions)

    def get_session_info(self) -> Dict:
        """
        Get current session information.

        Returns:
            Dictionary with session details
        """
        return {
            'session_id': self.session_id,
            'is_active': self.is_active,
            'current_code': self.current_code,
            'start_time': self.start_time,
            'submission_count': len(self.submissions),
            'message_id': self.message_id,
            'channel_id': self.channel_id
        }

    def reset(self):
        """Reset all session data (for cleanup after saving)."""
        self.session_id = None
        self.current_code = None
        self.message_id = None
        self.channel_id = None
        self.attendance_message_id = None
        self.attendance_channel_id = None
        self.start_time = None
        self.submissions = {}
        self.is_active = False
