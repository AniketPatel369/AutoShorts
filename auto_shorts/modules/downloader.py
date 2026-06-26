"""
Auto Shorts — Module: Downloader

Downloads YouTube video, metadata, and captions using yt-dlp.

Input:  YouTube URL
Output: downloads/video.mp4, downloads/metadata.json, downloads/captions.*.vtt (if available)
"""
import json
import logging
import subprocess
from pathlib import Path

from auto_shorts.utils.file_utils import write_json

logger = logging.getLogger(__name__)


def download(project_dir: Path, youtube_url: str) -> dict:
    """
    Download video + metadata + captions for a YouTube URL.

    Args:
        project_dir: Path to the project folder
        youtube_url: Full YouTube URL

    Returns:
        dict with keys: video_path, metadata, has_captions
    """
    downloads_dir = project_dir / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Extract metadata (no download) ──────────
    logger.info("Extracting metadata...")
    metadata = _extract_metadata(youtube_url)
    metadata_path = downloads_dir / "metadata.json"
    write_json(metadata_path, metadata)
    logger.info(f"Metadata saved: {metadata.get('title', 'Unknown')}")

    # ── Step 2: Download video ──────────────────────────
    video_path = downloads_dir / "video.mp4"
    if video_path.exists():
        logger.info("Video already downloaded, skipping")
    else:
        logger.info("Downloading video...")
        _download_video(youtube_url, video_path)
        logger.info(f"Video downloaded: {video_path} ({video_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # ── Step 3: Download captions if available ──────────
    has_captions = False
    logger.info("Checking for captions...")
    captions_path = _download_captions(youtube_url, downloads_dir)
    if captions_path:
        has_captions = True
        logger.info(f"Captions downloaded: {captions_path.name}")
    else:
        logger.info("No captions available — will use Whisper in next step")

    return {
        "video_path": str(video_path),
        "metadata_path": str(metadata_path),
        "has_captions": has_captions,
    }


def _extract_metadata(youtube_url: str) -> dict:
    """Extract video metadata using yt-dlp --dump-json."""
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        "--no-warnings",
        youtube_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata extraction failed: {result.stderr.strip()}")

    raw = json.loads(result.stdout)

    # Extract only the fields we need
    metadata = {
        "title": raw.get("title", ""),
        "description": raw.get("description", ""),
        "uploader": raw.get("uploader", ""),
        "channel": raw.get("channel", ""),
        "upload_date": raw.get("upload_date", ""),
        "duration": raw.get("duration", 0),
        "view_count": raw.get("view_count", 0),
        "like_count": raw.get("like_count", 0),
        "categories": raw.get("categories", []),
        "tags": raw.get("tags", []),
        "thumbnail": raw.get("thumbnail", ""),
        "webpage_url": raw.get("webpage_url", youtube_url),
        "language": raw.get("language", None),
        "subtitles_available": list(raw.get("subtitles", {}).keys()),
        "automatic_captions_available": list(raw.get("automatic_captions", {}).keys()),
    }
    return metadata


def _download_video(youtube_url: str, output_path: Path):
    """Download video using yt-dlp."""
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "-o", str(output_path),
        "--merge-output-format", "mp4",
        "--no-warnings",
        "--no-playlist",
        youtube_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp download failed: {result.stderr.strip()}")

    if not output_path.exists():
        raise FileNotFoundError(f"Video file not created at {output_path}")


def _download_captions(youtube_url: str, downloads_dir: Path) -> Path | None:
    """
    Try to download English captions/subtitles.
    Returns path to the caption file, or None if unavailable.
    """
    # Try manual (human-written) subtitles first, then auto-generated
    for sub_flag in ["--write-subs", "--write-auto-subs"]:
        cmd = [
            "yt-dlp",
            sub_flag,
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--skip-download",
            "--no-warnings",
            "--no-playlist",
            "-o", str(downloads_dir / "captions"),
            youtube_url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        # Check if any .vtt file was created
        vtt_files = list(downloads_dir.glob("captions*.vtt"))
        if vtt_files:
            return vtt_files[0]

    return None


# ── Standalone test ──────────────────────────────────────
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m auto_shorts.modules.downloader <youtube_url> [output_dir]")
        sys.exit(1)

    url = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("./test_download")

    result = download(out, url)
    print(json.dumps(result, indent=2))
