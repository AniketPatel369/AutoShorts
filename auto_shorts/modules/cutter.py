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
    
    if not clips_data:
        logger.warning("No clips to cut")
        return str(output_dir)
        
    logger.info(f"Cutting {len(clips_data)} clips...")
    
    for i, clip_dict in enumerate(clips_data, 1):
        # Build Clip object
        clip = Clip(id=i, **{k: v for k, v in clip_dict.items() if k in Clip.__annotations__})
        
        score = clip_dict.get("score", 0)
        output_path = output_dir / f"clip_{i:02d}_score_{score}.mp4"
        
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
    Cut a single clip, then apply active-speaker-aware vertical reframing.
    """
    import tempfile
    import os
    from auto_shorts.modules.reframer import reframe_active_speaker
    
    start_buffered = max(0.0, start - buffer)
    duration = (end - start) + (buffer * 2)
    
    # 1. Cut the segment from source video without cropping (keep landscape)
    temp_fd, temp_landscape_path = tempfile.mkstemp(suffix=".mp4")
    os.close(temp_fd)
    
    try:
        logger.info(f"Cutting temporary landscape segment for active speaker detection...")
        stream = ffmpeg.input(video_path, ss=start_buffered, t=duration)
        video = stream.video
        audio = stream.audio
        
        # Output uncropped landscape video segment
        out = ffmpeg.output(
            video, audio, temp_landscape_path,
            vcodec='libx264',
            acodec='aac',
            preset='fast',
            crf=23
        )
        out.run(quiet=True, overwrite_output=True)
        
        # 2. Run active-speaker-aware reframing on the cut segment
        # Pass empty audio_path to let reframer extract audio from the cut segment
        reframe_active_speaker(
            video_path=temp_landscape_path,
            audio_path="",
            aspect_ratio="9:16",
            out_path=output_path,
            debug=False # Disable debug overlay for clean final render
        )
        
    except Exception as e:
        logger.error(f"Error during active speaker reframing: {e}")
        raise RuntimeError("Failed to reframe clip") from e
    finally:
        # Clean up temp landscape clip
        if os.path.exists(temp_landscape_path):
            try:
                os.remove(temp_landscape_path)
            except OSError:
                pass

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
