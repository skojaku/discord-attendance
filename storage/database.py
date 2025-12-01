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
                    UNIQUE(user_id, session_id)
                )
            """)

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
                        a.session_id
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
                        a.session_id
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
                            'session_id'
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
