"""
Auto Shorts — Module: Analyzer

Passes transcript to LLM to find the most engaging short-form clip candidates.

Input:  analysis/transcript.json, downloads/metadata.json
Output: analysis/clips_raw.json
"""
import json
import logging
from pathlib import Path
from dataclasses import asdict

from auto_shorts.config import MIN_CLIP_DURATION, MAX_CLIP_DURATION
from auto_shorts.utils.file_utils import read_json, write_json
from auto_shorts.utils.llm import ask_json

logger = logging.getLogger(__name__)


def analyze(project_dir: Path) -> str:
    """
    Read transcript, ask LLM for clip candidates, save to clips_raw.json.
    """
    analysis_dir = project_dir / "analysis"
    clips_path = analysis_dir / "clips_raw.json"
    
    if clips_path.exists():
        logger.info("Clips already analyzed, skipping")
        return str(clips_path)

    # 1. Load Data
    transcript_path = analysis_dir / "transcript.json"
    metadata_path = project_dir / "downloads" / "metadata.json"
    
    if not transcript_path.exists():
        raise FileNotFoundError("Transcript not found")
        
    transcript = read_json(transcript_path)
    metadata = read_json(metadata_path) if metadata_path.exists() else {}
    
    video_title = metadata.get("title", "Unknown Video")
    full_text = transcript.get("text", "")
    
    # Fast paths for short videos
    if len(full_text.split()) < 50:
        logger.warning("Transcript is too short for meaningful analysis")
        write_json(clips_path, [])
        return str(clips_path)
        
    # TODO: Chunking for very long transcripts
    # For v0.3, we assume the transcript fits in the context window (8k tokens for llama3.1)
    
    # 2. Build Prompt
    prompt = f"""
You are an expert short-form video editor (TikTok, YouTube Shorts, Reels).
Your job is to read the transcript of a YouTube video and find the most engaging, viral segments.

Video Title: "{video_title}"

Constraints for each clip:
1. Duration: Must be between {MIN_CLIP_DURATION} and {MAX_CLIP_DURATION} seconds.
2. Must have a strong hook (first 3 seconds).
3. Must be a complete, self-contained thought.
4. Extract the exact text for the start and end of the clip so we can find the timestamps.

Transcript:
{full_text}

Output format requirements:
Provide the output as a JSON array of objects. Each object must have:
- "hook": A short description of why the first 3 seconds grab attention.
- "reason": Why this clip will go viral.
- "score": A score from 0-100 estimating virality.
- "start_text": The exact first 5-10 words of the clip (copy-pasted from the transcript).
- "end_text": The exact last 5-10 words of the clip (copy-pasted from the transcript).

Output ONLY JSON. No explanation.
"""

    logger.info("Sending transcript to LLM for clip extraction...")
    
    try:
        response_json = ask_json(prompt)
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        raise
        
    # 3. Process LLM output and match timestamps
    if not isinstance(response_json, list):
        if isinstance(response_json, dict) and "clips" in response_json:
            response_json = response_json["clips"]
        else:
            logger.error(f"Unexpected LLM output format: {response_json}")
            response_json = []

    clips = []
    for raw_clip in response_json:
        start_text = raw_clip.get("start_text", "")
        end_text = raw_clip.get("end_text", "")
        
        # Simple fuzzy matching (future: use sentence-transformers or fuzzywuzzy)
        start_ts = _find_timestamp(transcript, start_text, from_end=False)
        end_ts = _find_timestamp(transcript, end_text, from_end=True)
        
        if start_ts is not None and end_ts is not None and end_ts > start_ts:
            duration = end_ts - start_ts
            if MIN_CLIP_DURATION <= duration <= MAX_CLIP_DURATION + 10:  # Allow some leniency
                clips.append({
                    "start_seconds": start_ts,
                    "end_seconds": end_ts,
                    "duration": duration,
                    "hook": raw_clip.get("hook", ""),
                    "reason": raw_clip.get("reason", ""),
                    "score": raw_clip.get("score", 0),
                    "start_text": start_text,
                    "end_text": end_text
                })
            else:
                logger.debug(f"Discarding clip: duration {duration}s out of bounds")
        else:
            logger.debug(f"Could not reliably match timestamps for clip: '{start_text}'")

    # Sort by score descending
    clips = sorted(clips, key=lambda c: c.get("score", 0), reverse=True)
    
    logger.info(f"Found {len(clips)} valid clips from LLM analysis")
    write_json(clips_path, clips)
    
    return str(clips_path)


def _find_timestamp(transcript: dict, text_snippet: str, from_end: bool = False) -> float | None:
    """
    Very naive string search to find the timestamp of a text snippet.
    Iterates through word-level timestamps in the transcript.
    """
    if not text_snippet:
        return None
        
    # Clean the search text
    search_words = [w.lower().strip(".,!?'\"") for w in text_snippet.split() if w.strip()]
    if not search_words:
        return None
        
    # Flatten all words from all segments
    all_words = []
    for seg in transcript.get("segments", []):
        for w in seg.get("words", []):
            clean_word = w.get("word", "").lower().strip(".,!?'\"")
            if clean_word:
                all_words.append({
                    "word": clean_word,
                    "start": w.get("start", 0),
                    "end": w.get("end", 0)
                })

    if not all_words:
        return None

    # Search for a match of the first few words
    search_len = min(len(search_words), 5)  # Match up to 5 words
    best_match_idx = -1
    
    # Iterate to find the sequence
    for i in range(len(all_words) - search_len + 1):
        match_count = 0
        for j in range(search_len):
            if all_words[i+j]["word"] == search_words[j]:
                match_count += 1
                
        if match_count >= max(1, search_len - 1):  # Allow 1 word mismatch
            best_match_idx = i
            if not from_end:
                break  # If looking for start, take first match
            # If looking for end, keep going to find the last match
            
    if best_match_idx != -1:
        if from_end:
            # Return the end timestamp of the last word in the matched sequence
            return all_words[best_match_idx + search_len - 1]["end"]
        else:
            # Return the start timestamp of the first word
            return all_words[best_match_idx]["start"]
            
    return None

# ── Standalone test ──────────────────────────────────────
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m auto_shorts.modules.analyzer <project_dir>")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    out_path = analyze(project_dir)
    print(f"Done. Output at: {out_path}")
