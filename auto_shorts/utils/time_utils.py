"""
Auto Shorts — Utility: Time Helpers

Timestamp conversion between seconds and HH:MM:SS formats.
"""


def seconds_to_timestamp(seconds: float) -> str:
    """Convert seconds (float) to HH:MM:SS.mmm format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def timestamp_to_seconds(timestamp: str) -> float:
    """Convert HH:MM:SS or HH:MM:SS.mmm to seconds."""
    parts = timestamp.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    else:
        return float(parts[0])


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration (e.g., '1h 23m 45s')."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}h {m}m {s}s"
