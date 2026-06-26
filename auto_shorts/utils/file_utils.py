"""
Auto Shorts — Utility: File Helpers

JSON read/write, path sanitization, project directory creation.
"""
import json
import re
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """
    Convert a string into a safe directory/file name.
    - Lowercase
    - Replace spaces and special chars with hyphens
    - Remove consecutive hyphens
    - Trim to 80 chars
    """
    # Remove or replace problematic characters
    name = name.lower().strip()
    name = re.sub(r'[<>:"/\\|?*\'\[\](){}!@#$%^&+=,;`~]', '', name)
    name = re.sub(r'[\s_]+', '-', name)      # spaces/underscores → hyphens
    name = re.sub(r'-+', '-', name)           # collapse multiple hyphens
    name = name.strip('-')                    # trim leading/trailing hyphens
    return name[:80] if name else "untitled"


def create_project_dirs(project_dir: Path):
    """Create the standard project subdirectory structure."""
    subdirs = ["downloads", "analysis", "output", "output/final", "logs"]
    for subdir in subdirs:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)
    logger.info(f"Created project directory structure at {project_dir}")


def read_json(path: Path) -> Any:
    """Read and parse a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any, indent: int = 2):
    """Write data to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=indent, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.debug(f"Wrote JSON to {path}")
