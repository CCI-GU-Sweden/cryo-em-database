"""Find tools in the running Python environment, without mixing installations."""

import os
import sys
from pathlib import Path


def find_tool(name: str, *, prefix: Path | None = None, windows: bool | None = None) -> Path:
    """Conda puts Windows tools in Library/bin or Scripts; Unix tools use bin.

    Never fall back to an unrelated system/Cygwin installation on PATH. Optional
    arguments let tests exercise both layouts without needing both operating systems.
    """
    prefix = Path(sys.prefix) if prefix is None else prefix
    windows = os.name == "nt" if windows is None else windows
    filename = f"{name}.exe" if windows else name
    directories = (
        [prefix / "Library" / "bin", prefix / "Scripts", prefix] if windows else [prefix / "bin"]
    )
    for directory in directories:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Cannot find {filename} in the active Python environment ({prefix}). "
        "Activate the project's Conda environment and update it using environment.yml."
    )
