"""
Auto Shorts — Module: Transcriber

Extracts audio from video and generates a word-level transcript using mlx-whisper.

Input:  downloads/video.mp4
Output: analysis/transcript.json, analysis/audio.wav (temporary)
"""
import json
import logging
import subprocess
from pathlib import Path
from dataclasses import asdict

import mlx_whisper

from auto_shorts.config import WHISPER_MODEL
from auto_shorts.utils.file_utils import write_json
from auto_shorts.models.transcript import Transcript, TranscriptSegment, TranscriptWord

logger = logging.getLogger(__name__)


def transcribe(project_dir: Path, video_path: str) -> str:
    """
    Transcribe video using mlx-whisper and save to transcript.json.

    Args:
        project_dir: Path to the project folder
        video_path: Full path to the video.mp4

    Returns:
        transcript_path
    """
    analysis_dir = project_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    
    transcript_path = analysis_dir / "transcript.json"
    
    if transcript_path.exists():
        logger.info("Transcript already exists, skipping transcription")
        return str(transcript_path)

    audio_path = analysis_dir / "audio.wav"
    
    # Extract audio if not present
    if not audio_path.exists():
        logger.info("Extracting audio from video...")
        _extract_audio(video_path, audio_path)
    else:
        logger.info("Audio file already exists")

    logger.info(f"Starting transcription using {WHISPER_MODEL} (this may take a while)...")
    
    # Transcribe with word-level timestamps
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=f"mlx-community/whisper-{WHISPER_MODEL}-mlx",
        word_timestamps=True
    )
    
    # Convert mlx-whisper dict output to our data classes
    logger.info("Transcription complete. Parsing results...")
    
    segments = []
    for seg in result.get("segments", []):
        words = []
        for w in seg.get("words", []):
            words.append(TranscriptWord(
                word=w.get("word", ""),
                start=w.get("start", 0.0),
                end=w.get("end", 0.0)
            ))
            
        segments.append(TranscriptSegment(
            id=seg.get("id", 0),
            start=seg.get("start", 0.0),
            end=seg.get("end", 0.0),
            text=seg.get("text", ""),
            words=words
        ))
        
    transcript = Transcript(
        text=result.get("text", ""),
        segments=segments,
        language=result.get("language", "en")
    )
    
    write_json(transcript_path, asdict(transcript))
    logger.info(f"Transcript saved to {transcript_path}")
    
    # Clean up audio file to save space
    if audio_path.exists():
        audio_path.unlink()
        logger.info("Cleaned up temporary audio.wav")
        
    return str(transcript_path)


def _extract_audio(video_path: str, output_path: Path):
    """Extract audio from video using FFmpeg as a 16kHz WAV file (required by Whisper)."""
    import sys
    cmd = [
        "ffmpeg",
        "-y",               # Overwrite
        "-i", video_path,   # Input video
        "-vn",              # Disable video
        "-acodec", "pcm_s16le", # 16-bit PCM
        "-ar", "16000",     # 16kHz sample rate
        "-ac", "1",         # Mono audio
        str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr.strip()}")

# ── Standalone test ──────────────────────────────────────
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 3:
        print("Usage: python -m auto_shorts.modules.transcriber <project_dir> <video_path>")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    video_path = sys.argv[2]

    out_path = transcribe(project_dir, video_path)
    print(f"Done. Output at: {out_path}")
