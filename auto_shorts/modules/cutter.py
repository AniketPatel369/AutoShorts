"""
Auto Shorts — Module: Cutter

Cuts the source video into individual clips based on the LLM analyzer's timestamps.
Crops the video to a 9:16 vertical format.

Input:  downloads/video.mp4, analysis/clips_raw.json (or clips_scored.json)
Output: output/clip_001.mp4, ...
"""
import logging
from pathlib import Path

import ffmpeg

from auto_shorts.config import CLIP_BUFFER_SECONDS, OUTPUT_WIDTH, OUTPUT_HEIGHT
from auto_shorts.utils.file_utils import read_json
from auto_shorts.models.clip import Clip

logger = logging.getLogger(__name__)


def cut(project_dir: Path) -> str:
    """
    Cut the video into multiple vertical clips based on analyzed timestamps.
    """
    video_path = project_dir / "downloads" / "video.mp4"
    if not video_path.exists():
        raise FileNotFoundError(f"Missing video file: {video_path}")

    # Use scored clips if available, else fallback to raw clips
    analysis_dir = project_dir / "analysis"
    scored_path = analysis_dir / "clips_scored.json"
    raw_path = analysis_dir / "clips_raw.json"
    
    if scored_path.exists():
        clips_data = read_json(scored_path)
    elif raw_path.exists():
        clips_data = read_json(raw_path)
    else:
        raise FileNotFoundError("No clips data found. Run 'analyze' first.")
        
    output_dir = project_dir / "output"
    
    # Process only top 3 clips for now to save time
    clips_data = clips_data[:3]
    
    if not clips_data:
        logger.warning("No clips to cut")
        return str(output_dir)
        
    logger.info(f"Cutting {len(clips_data)} clips...")
    
    for i, clip_dict in enumerate(clips_data, 1):
        # Build Clip object
        clip = Clip(id=i, **{k: v for k, v in clip_dict.items() if k in Clip.__annotations__})
        
        output_path = output_dir / f"clip_{i:03d}.mp4"
        
        if output_path.exists():
            logger.info(f"Clip {i} already exists at {output_path.name}, skipping")
            continue
            
        _cut_single_clip(
            video_path=str(video_path),
            output_path=str(output_path),
            start=clip.start_seconds,
            end=clip.end_seconds,
            buffer=CLIP_BUFFER_SECONDS
        )
        logger.info(f"✓ Cut clip {i}: {output_path.name} ({clip.duration:.1f}s)")
        
    return str(output_dir)


def _cut_single_clip(video_path: str, output_path: str, start: float, end: float, buffer: float):
    """
    Cut a single clip, re-encoding it to crop to a 9:16 vertical center aspect ratio.
    """
    start_buffered = max(0.0, start - buffer)
    duration = (end - start) + (buffer * 2)
    
    try:
        stream = ffmpeg.input(video_path, ss=start_buffered, t=duration)
        
        # Crop center to 9:16 aspect ratio (e.g., 1080x1920)
        # Using ih*9/16 as width to always match the source height in a vertical slice
        video = stream.video.filter('crop', 'ih*9/16', 'ih')
        
        # Scale to standard shorts resolution if needed
        video = video.filter('scale', OUTPUT_WIDTH, OUTPUT_HEIGHT)
        
        audio = stream.audio
        
        # We must re-encode video because of the crop/scale filters
        out = ffmpeg.output(
            video, audio, output_path,
            vcodec='libx264',
            acodec='aac',
            preset='fast',
            crf=23
        )
        
        # Suppress massive ffmpeg logs, run quietly
        out.run(quiet=True, overwrite_output=True)
        
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode('utf-8') if e.stderr else str(e)}")
        raise RuntimeError("Failed to cut clip") from e

# ── Standalone test ──────────────────────────────────────
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m auto_shorts.modules.cutter <project_dir>")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    out_path = cut(project_dir)
    print(f"Done. Output at: {out_path}")
