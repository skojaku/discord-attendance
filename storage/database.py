"""SQLite database handler for attendance records."""
import aiosqlite
import csv
import os
from datetime import datetime
from typing import List, Dict, Optional


class AttendanceDatabase:
    """Handles SQLite database operations for attendance records."""

    def __init__(self, db_path: str):
        """
        Initialize the database handler.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_directory()

    def _ensure_directory(self):
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    async def setup_database(self):
        """Create tables and indexes if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for concurrent access
            await db.execute("PRAGMA journal_mode=WAL")

            # Create attendance table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    date_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    status TEXT DEFAULT 'present',
                    UNIQUE(user_id, session_id)
                )
            """)

            # Add status column if it doesn't exist (migration for existing databases)
            try:
                await db.execute("ALTER TABLE attendance ADD COLUMN status TEXT DEFAULT 'present'")
            except Exception:
                pass  # Column already exists

            # Create student registration table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    user_id INTEGER PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    student_name TEXT,
                    registered_at TEXT NOT NULL
                )
            """)

            # Create indexes for faster queries
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_session
                ON attendance(session_id)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_date
                ON attendance(date_id)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_student_id
                ON students(student_id)
            """)

            await db.commit()

    async def save_attendance_records(
        self,
        records: List[Dict],
        session_id: str
    ) -> int:
        """
        Save attendance records to the database using UPSERT.

        Args:
            records: List of dicts with keys: user_id, username, timestamp
            session_id: Unique identifier for this attendance session

        Returns:
            Number of records saved

        Note: Uses INSERT OR REPLACE to handle duplicate submissions
        (only the last submission per student per session is kept).
        """
        if not records:
            return 0

        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            # Prepare data for insertion
            data_to_insert = []
            for record in records:
                timestamp = record['timestamp']
                if isinstance(timestamp, datetime):
                    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    date_id = timestamp.strftime('%Y-%m-%d')
                else:
                    timestamp_str = timestamp
                    date_id = timestamp.split()[0]

                data_to_insert.append((
                    record['user_id'],
                    record['username'],
                    timestamp_str,
                    date_id,
                    session_id
                ))

            # Batch insert with UPSERT logic
            await db.executemany("""
                INSERT OR REPLACE INTO attendance
                (user_id, username, timestamp, date_id, session_id)
                VALUES (?, ?, ?, ?, ?)
            """, data_to_insert)

            await db.commit()
            return len(data_to_insert)

    async def get_session_records(self, session_id: str) -> List[Dict]:
        """
        Retrieve all records for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            List of attendance records as dictionaries
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT user_id, username, timestamp, date_id, session_id
                FROM attendance
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def register_student(
        self,
        user_id: int,
        student_id: str,
        student_name: Optional[str] = None
    ) -> bool:
        """
        Register a student with their student ID and optional name.

        Args:
            user_id: Discord user ID
            student_id: Student ID (from school/university)
            student_name: Optional student real name

        Returns:
            True if registered successfully
        """
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            await db.execute("""
                INSERT OR REPLACE INTO students
                (user_id, student_id, student_name, registered_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, student_id, student_name, timestamp))

            await db.commit()
            return True

    async def get_student_info(self, user_id: int) -> Optional[Dict]:
        """
        Get student registration information.

        Args:
            user_id: Discord user ID

        Returns:
            Dict with student info or None if not registered
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT user_id, student_id, student_name, registered_at
                FROM students
                WHERE user_id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def export_to_csv(
        self,
        output_path: str,
        session_id: Optional[str] = None
    ) -> int:
        """
        Export attendance records to a CSV file with student information.

        Args:
            output_path: Path for the CSV file
            session_id: Optional session ID to filter records (None = all records)

        Returns:
            Number of records exported
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Join attendance with student registration data
            if session_id:
                query = """
                    SELECT
                        a.user_id,
                        a.username as discord_username,
                        s.student_id,
                        s.student_name,
                        a.timestamp,
                        a.date_id,
                        a.session_id,
                        COALESCE(a.status, 'present') as status
                    FROM attendance a
                    LEFT JOIN students s ON a.user_id = s.user_id
                    WHERE a.session_id = ?
                    ORDER BY a.timestamp ASC
                """
                params = (session_id,)
            else:
                query = """
                    SELECT
                        a.user_id,
                        a.username as discord_username,
                        s.student_id,
                        s.student_name,
                        a.timestamp,
                        a.date_id,
                        a.session_id,
                        COALESCE(a.status, 'present') as status
                    FROM attendance a
                    LEFT JOIN students s ON a.user_id = s.user_id
                    ORDER BY a.date_id DESC, a.timestamp DESC
                """
                params = ()

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()

                # Write to CSV
                with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                    if rows:
                        fieldnames = [
                            'student_id',
                            'student_name',
                            'discord_username',
                            'user_id',
                            'timestamp',
                            'date_id',
                            'session_id',
                            'status'
                        ]
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()

                        for row in rows:
                            writer.writerow(dict(row))

                return len(rows)

    async def get_all_sessions(self) -> List[str]:
        """
        Get a list of all session IDs in the database.

        Returns:
            List of session IDs
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT DISTINCT session_id
                FROM attendance
                ORDER BY session_id DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def search_students(self, query: str, limit: int = 25) -> List[Dict]:
        """
        Search for students by partial match on student_id, student_name, or username.

        Args:
            query: Partial search string
            limit: Maximum number of results to return

        Returns:
            List of matching student dicts with user_id, student_id, student_name, username
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query_lower = f"%{query.lower()}%"

            # Search in both students table and attendance records
            async with db.execute("""
                SELECT DISTINCT
                    COALESCE(s.user_id, a.user_id) as user_id,
                    s.student_id,
                    s.student_name,
                    a.username
                FROM attendance a
                LEFT JOIN students s ON a.user_id = s.user_id
                WHERE LOWER(s.student_id) LIKE ?
                   OR LOWER(s.student_name) LIKE ?
                   OR LOWER(a.username) LIKE ?
                ORDER BY
                    CASE WHEN s.student_name IS NOT NULL THEN 0 ELSE 1 END,
                    s.student_name, a.username
                LIMIT ?
            """, (query_lower, query_lower, query_lower, limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def find_student(self, identifier: str) -> Optional[Dict]:
        """
        Find a student by student_id, Discord username, or Discord user_id.

        Args:
            identifier: Student ID, Discord username, or Discord user_id

        Returns:
            Dict with student info including user_id, or None if not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # First try to find by student_id in the students table
            async with db.execute("""
                SELECT user_id, student_id, student_name
                FROM students
                WHERE student_id = ?
            """, (identifier,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)

            # Try to find by Discord user_id (if it's a number)
            try:
                user_id = int(identifier)
                async with db.execute("""
                    SELECT s.user_id, s.student_id, s.student_name
                    FROM students s
                    WHERE s.user_id = ?
                """, (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)

                # Even if not in students table, check if they have attendance records
                async with db.execute("""
                    SELECT DISTINCT user_id, username
                    FROM attendance
                    WHERE user_id = ?
                """, (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {'user_id': row[0], 'student_id': None, 'student_name': None, 'username': row[1]}
            except ValueError:
                pass

            # Try to find by Discord username in attendance records
            async with db.execute("""
                SELECT DISTINCT a.user_id, a.username, s.student_id, s.student_name
                FROM attendance a
                LEFT JOIN students s ON a.user_id = s.user_id
                WHERE LOWER(a.username) = LOWER(?)
            """, (identifier,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'user_id': row[0],
                        'username': row[1],
                        'student_id': row[2],
                        'student_name': row[3]
                    }

            return None

    async def get_sessions_for_date(self, date_id: str) -> List[Dict]:
        """
        Get all sessions for a specific date.

        Args:
            date_id: Date in YYYY-MM-DD format

        Returns:
            List of session info dicts
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT DISTINCT session_id, date_id, COUNT(*) as count
                FROM attendance
                WHERE date_id = ?
                GROUP BY session_id
                ORDER BY session_id DESC
            """, (date_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def add_manual_attendance(
        self,
        user_id: int,
        username: str,
        date_id: str,
        session_id: Optional[str] = None,
        status: str = 'present'
    ) -> Dict:
        """
        Manually add an attendance record.

        Args:
            user_id: Discord user ID
            username: Discord username
            date_id: Date in YYYY-MM-DD format
            session_id: Optional session ID (will create a manual session if not provided)
            status: Status of attendance ('present' or 'excused')

        Returns:
            Dict with the created/updated record info
        """
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # If no session_id provided, find or create one for that date
            if not session_id:
                # Try to find existing session for that date
                async with db.execute("""
                    SELECT session_id FROM attendance
                    WHERE date_id = ?
                    ORDER BY session_id DESC
                    LIMIT 1
                """, (date_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        session_id = row[0]
                    else:
                        # Create a manual session ID
                        session_id = f"manual_{date_id.replace('-', '')}"

            await db.execute("""
                INSERT OR REPLACE INTO attendance
                (user_id, username, timestamp, date_id, session_id, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, timestamp, date_id, session_id, status))

            await db.commit()
            return {
                'user_id': user_id,
                'username': username,
                'date_id': date_id,
                'session_id': session_id,
                'status': status
            }

    async def remove_attendance(
        self,
        user_id: int,
        date_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> int:
        """
        Remove attendance record(s) for a user.

        Args:
            user_id: Discord user ID
            date_id: Optional date filter (YYYY-MM-DD)
            session_id: Optional session ID filter

        Returns:
            Number of records removed
        """
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            if session_id:
                result = await db.execute("""
                    DELETE FROM attendance
                    WHERE user_id = ? AND session_id = ?
                """, (user_id, session_id))
            elif date_id:
                result = await db.execute("""
                    DELETE FROM attendance
                    WHERE user_id = ? AND date_id = ?
                """, (user_id, date_id))
            else:
                # Safety: don't allow deleting all records for a user without a filter
                return 0

            await db.commit()
            return result.rowcount

    async def update_attendance_status(
        self,
        user_id: int,
        status: str,
        date_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> int:
        """
        Update the status of attendance record(s).

        Args:
            user_id: Discord user ID
            status: New status ('present' or 'excused')
            date_id: Optional date filter (YYYY-MM-DD)
            session_id: Optional session ID filter

        Returns:
            Number of records updated
        """
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            if session_id:
                result = await db.execute("""
                    UPDATE attendance
                    SET status = ?
                    WHERE user_id = ? AND session_id = ?
                """, (status, user_id, session_id))
            elif date_id:
                result = await db.execute("""
                    UPDATE attendance
                    SET status = ?
                    WHERE user_id = ? AND date_id = ?
                """, (status, user_id, date_id))
            else:
                return 0

            await db.commit()
            return result.rowcount

    async def get_attendance_record(
        self,
        user_id: int,
        date_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get a specific attendance record.

        Args:
            user_id: Discord user ID
            date_id: Optional date filter
            session_id: Optional session filter

        Returns:
            Attendance record dict or None
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if session_id:
                query = """
                    SELECT a.*, s.student_id, s.student_name
                    FROM attendance a
                    LEFT JOIN students s ON a.user_id = s.user_id
                    WHERE a.user_id = ? AND a.session_id = ?
                """
                params = (user_id, session_id)
            elif date_id:
                query = """
                    SELECT a.*, s.student_id, s.student_name
                    FROM attendance a
                    LEFT JOIN students s ON a.user_id = s.user_id
                    WHERE a.user_id = ? AND a.date_id = ?
                    ORDER BY a.session_id DESC
                    LIMIT 1
                """
                params = (user_id, date_id)
            else:
                return None

            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
