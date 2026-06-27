"""
Auto Shorts — Module: Transcriber

Extracts audio from video and generates a word-level transcript.
Supports two modes:
  1. YouTube json3 captions (fast, no local processing)
  2. mlx-whisper local transcription (slow, but always available)

Input:  downloads/video.mp4, downloads/captions*.json3 (optional)
Output: analysis/transcript.json
"""
import json
import logging
import subprocess
from pathlib import Path
from dataclasses import asdict

from auto_shorts.config import WHISPER_MODEL, MODELS_DIR
from auto_shorts.utils.file_utils import write_json
from auto_shorts.models.transcript import Transcript, TranscriptSegment, TranscriptWord

logger = logging.getLogger(__name__)


def transcribe(project_dir: Path, video_path: str) -> str:
    """
    Transcribe video and save to transcript.json.
    
    Tries YouTube captions first (fast), falls back to local Whisper (slow).

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

    # ── Strategy 1: Try YouTube json3 captions (fast) ────
    downloads_dir = project_dir / "downloads"
    json3_files = list(downloads_dir.glob("captions*.json3"))
    
    if json3_files:
        logger.info(f"⚡ Found YouTube captions: {json3_files[0].name} — parsing (fast mode)...")
        try:
            transcript = _parse_youtube_json3(json3_files[0])
            if transcript and len(transcript.segments) > 0:
                write_json(transcript_path, asdict(transcript))
                logger.info(f"✅ Transcript saved from YouTube captions ({len(transcript.segments)} segments)")
                return str(transcript_path)
            else:
                logger.warning("YouTube captions parsed but contained no usable segments, falling back to Whisper")
        except Exception as e:
            logger.warning(f"Failed to parse YouTube json3 captions: {e} — falling back to Whisper")

    # ── Strategy 2: Local Whisper transcription (slow) ───
    logger.info("🧠 No YouTube captions available — using local Whisper transcription...")
    
    audio_path = analysis_dir / "audio.wav"
    
    # Extract audio if not present
    if not audio_path.exists():
        logger.info("Extracting audio from video...")
        _extract_audio(video_path, audio_path)
    else:
        logger.info("Audio file already exists")

    logger.info(f"Starting transcription using {WHISPER_MODEL} (this may take a while)...")
    
    # Transcribe with word-level timestamps
    import mlx_whisper
    from huggingface_hub import snapshot_download
    
    model_name = f"whisper-{WHISPER_MODEL}-mlx"
    repo_id = f"mlx-community/{model_name}"
    local_model_path = MODELS_DIR / model_name
    
    # Download directly to our local models folder if it doesn't exist
    if not local_model_path.exists() or not list(local_model_path.glob("*.npz")):
        logger.info(f"Downloading model {model_name} to local models folder...")
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(local_model_path),
            local_dir_use_symlinks=False
        )

    logger.info("✅ Model ready! Now transcribing audio...")
    logger.info("⏳ (This involves heavy AI processing and will take 5-15 minutes. Please don't close the terminal!)")
    
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=str(local_model_path),
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


def _parse_youtube_json3(json3_path: Path) -> Transcript | None:
    """
    Parse YouTube's json3 caption format into our Transcript model.
    
    json3 structure:
    {
        "events": [
            {
                "tStartMs": 1234,       # Start time in milliseconds
                "dDurationMs": 5678,    # Duration in milliseconds
                "segs": [
                    {"utf8": "word ", "tOffsetMs": 0},
                    {"utf8": "another ", "tOffsetMs": 500},
                    ...
                ]
            },
            ...
        ]
    }
    """
    with open(json3_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    events = data.get("events", [])
    if not events:
        return None
    
    segments = []
    all_text_parts = []
    seg_id = 0
    
    for event in events:
        t_start_ms = event.get("tStartMs", 0)
        d_duration_ms = event.get("dDurationMs", 0)
        segs = event.get("segs", [])
        
        if not segs:
            continue
        
        # Build words from segments
        words = []
        seg_text_parts = []
        
        for seg_data in segs:
            utf8 = seg_data.get("utf8", "").strip()
            if not utf8 or utf8 == "\n":
                continue
                
            t_offset_ms = seg_data.get("tOffsetMs", 0)
            word_start = (t_start_ms + t_offset_ms) / 1000.0
            # Estimate word end: use next offset or segment duration
            word_end = word_start + 0.5  # Default 500ms per word
            
            words.append(TranscriptWord(
                word=f" {utf8}",
                start=round(word_start, 3),
                end=round(word_end, 3)
            ))
            seg_text_parts.append(utf8)
        
        if not words:
            continue
        
        # Fix word end timestamps using next word's start
        for i in range(len(words) - 1):
            words[i] = TranscriptWord(
                word=words[i].word,
                start=words[i].start,
                end=words[i + 1].start
            )
        # Last word ends at segment end
        if words:
            seg_end = (t_start_ms + d_duration_ms) / 1000.0
            words[-1] = TranscriptWord(
                word=words[-1].word,
                start=words[-1].start,
                end=round(seg_end, 3)
            )
        
        seg_text = " ".join(seg_text_parts)
        all_text_parts.append(seg_text)
        
        segments.append(TranscriptSegment(
            id=seg_id,
            start=round(t_start_ms / 1000.0, 3),
            end=round((t_start_ms + d_duration_ms) / 1000.0, 3),
            text=seg_text,
            words=words
        ))
        seg_id += 1
    
    if not segments:
        return None
    
    full_text = " ".join(all_text_parts)
    
    # Detect language from first few segments
    language = "en"
    sample = full_text[:500]
    # Simple Hindi detection: check for Devanagari characters
    if any('\u0900' <= c <= '\u097F' for c in sample):
        language = "hi"
    
    return Transcript(
        text=full_text,
        segments=segments,
        language=language
    )


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
