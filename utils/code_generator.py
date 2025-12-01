"""Generate random attendance codes."""
import secrets


# Character set excludes ambiguous characters (I, O, 1, 0)
CHAR_SET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_code(length: int = 4, previous_code: str = None) -> str:
    """
    Generate a random alphanumeric code for attendance.

    Args:
        length: Length of the code (default: 4)
        previous_code: Previous code to avoid duplicates (optional)

    Returns:
        A random code string (e.g., "A1B2")

    The character set excludes ambiguous characters:
    - No 'I' or 'O' (confused with 1 and 0)
    - No '1' or '0' (confused with I and O)

    With 4 characters, this provides 1,336,336 unique combinations.
    """
    while True:
        code = ''.join(secrets.choice(CHAR_SET) for _ in range(length))

        # Ensure we don't generate the same code twice in a row
        if code != previous_code:
            return code
