"""
DSS script validation.

Security checks to prevent file I/O and other dangerous operations.
"""

import re
from typing import Optional

from py_dss_service.common.errors import ScriptValidationError

# Forbidden commands that could access the filesystem or external resources
# These are checked case-insensitively
FORBIDDEN_COMMANDS = [
    "compile",
    "redirect",
    "buscoords",
    "export",
    "save",
    "open",
]

# Build regex pattern to match forbidden commands at the start of a line
# Matches: compile, compile(, compile , etc.
FORBIDDEN_PATTERN = re.compile(
    r"^\s*(" + "|".join(FORBIDDEN_COMMANDS) + r")\b",
    re.IGNORECASE | re.MULTILINE,
)


def validate_dss_script(
    script: str,
    max_length: int = 200 * 1024,
) -> Optional[str]:
    """
    Validate a DSS script for security and size constraints.

    Args:
        script: The DSS script to validate
        max_length: Maximum allowed script length in bytes (default 200KB)

    Returns:
        None if valid

    Raises:
        ScriptValidationError: If validation fails, with a descriptive message
    """
    # Check script length
    script_bytes = len(script.encode("utf-8"))
    if script_bytes > max_length:
        raise ScriptValidationError(
            "Script exceeds maximum length: "
            "{script_bytes} bytes > {max_length} bytes ({max_length // 1024} KB)"
        )

    # Check for empty script
    if not script.strip():
        raise ScriptValidationError("Script cannot be empty")

    # Check for forbidden commands
    match = FORBIDDEN_PATTERN.search(script)
    if match:
        forbidden_cmd = match.group(1).lower()
        raise ScriptValidationError(
            f"Script contains forbidden command: '{forbidden_cmd}'. "
            f"File I/O commands are not allowed for security reasons. "
            f"Forbidden commands: {', '.join(FORBIDDEN_COMMANDS)}"
        )

    return None


def get_script_lines(script: str) -> list[str]:
    """
    Parse a DSS script into executable lines.

    - Splits by newlines
    - Strips whitespace
    - Filters out empty lines and comment-only lines

    Args:
        script: The DSS script to parse

    Returns:
        List of non-empty, non-comment lines
    """
    lines = []
    for line in script.split("\n"):
        stripped = line.strip()
        # Skip empty lines
        if not stripped:
            continue
        # Skip comment-only lines (DSS uses ! or // for comments)
        if stripped.startswith("!") or stripped.startswith("//"):
            continue
        lines.append(stripped)
    return lines
