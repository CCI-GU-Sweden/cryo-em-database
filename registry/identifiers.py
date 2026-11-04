"""Grid suffixes preserve creation order within each sample owner.

0001 ... 9999, a001 ... a999, b001 ... z999. The suffix stays four
characters throughout; exhausting z999 is an explicit error, never a wraparound.
"""

import re
import string

from django.core.exceptions import ValidationError

MAX_GRID_SEQUENCE = 9999 + 26 * 999


def grid_suffix(number: int) -> str:
    if type(number) is not int or not 1 <= number <= MAX_GRID_SEQUENCE:
        raise ValidationError("This owner's grid ID sequence is exhausted (last suffix: z999).")
    if number <= 9999:
        return f"{number:04d}"
    letter_index, remainder = divmod(number - 10000, 999)
    return f"{string.ascii_lowercase[letter_index]}{remainder + 1:03d}"


def suffix_sequence(suffix: str):
    """Read a recognized historical suffix without changing the stored identifier."""
    suffix = suffix.lower()
    if re.fullmatch(r"[0-9]{4}", suffix) and int(suffix) > 0:
        return int(suffix)
    if re.fullmatch(r"[a-z][0-9]{3}", suffix) and int(suffix[1:]) > 0:
        return 9999 + string.ascii_lowercase.index(suffix[0]) * 999 + int(suffix[1:])
    return None
