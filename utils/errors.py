"""Custom exceptions for the attendance bot."""


class AttendanceSessionError(Exception):
    """Base exception for attendance session errors."""
    pass


class SessionAlreadyActiveError(AttendanceSessionError):
    """Raised when trying to start a session while one is already active."""
    pass


class NoActiveSessionError(AttendanceSessionError):
    """Raised when trying to perform an action that requires an active session."""
    pass


class InvalidCodeError(AttendanceSessionError):
    """Raised when a student submits an invalid or expired code."""
    pass


class WrongChannelError(AttendanceSessionError):
    """Raised when a command is used in the wrong channel."""
    pass
