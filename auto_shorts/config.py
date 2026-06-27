"""
Auto Shorts — Global Configuration

All paths, model names, and defaults in one place.
"""
import os
from pathlib import Path

# ─── Workspace ───────────────────────────────────────────
# Root directory where all projects live
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
WORKSPACE_DIR = PROJECT_ROOT / "auto_shorts" / "workspace"
PROJECTS_DIR = WORKSPACE_DIR / "projects"
LOGS_DIR = WORKSPACE_DIR / "logs"
MODELS_DIR = PROJECT_ROOT / "models"

# ─── AI Models ───────────────────────────────────────────
# MLX-LM (runs locally via Apple MLX, no server needed)
LLM_MODEL = "mlx-community/Qwen2.5-14B-Instruct-4bit"

# Whisper STT
WHISPER_MODEL = "large-v3"

# ─── Video Settings ──────────────────────────────────────
# Shorts format: 9:16 vertical
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

# Clip duration limits (seconds)
MIN_CLIP_DURATION = 15
MAX_CLIP_DURATION = 60

# Buffer added before/after clip timestamps (seconds)
CLIP_BUFFER_SECONDS = 1.5

# ─── Download Settings ───────────────────────────────────
# yt-dlp format: best mp4 up to 1080p
YTDLP_FORMAT = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best"

# ─── Pipeline Steps ──────────────────────────────────────
# Ordered list of pipeline step names (must match project.json keys)
PIPELINE_STEPS = [
    "download",
    "transcribe",
    "crawl_trends",
    "analyze",
    "score",
    "cut",
    "caption",
    "enhance",
]

# Step statuses
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

# ─── Logging ─────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def ensure_workspace():
    """Create workspace directories if they don't exist."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
