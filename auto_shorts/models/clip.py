"""
Auto Shorts — Data Models: Clip

Represents a single video clip extracted from the main video.
"""
from dataclasses import dataclass, field

@dataclass
class Clip:
    id: int
    start_seconds: float
    end_seconds: float
    duration: float
    hook: str = ""
    reason: str = ""
    score: int = 0
    start_text: str = ""
    end_text: str = ""
    output_path: str = ""
