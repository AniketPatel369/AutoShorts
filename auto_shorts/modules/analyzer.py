"""
Auto Shorts — Module: Analyzer

Passes transcript to LLM to find the most engaging short-form clip candidates.
Uses segment-based timestamps and detailed expert prompting for high-quality clips.

Input:  analysis/transcript.json, downloads/metadata.json
Output: analysis/clips_raw.json
"""
import json
import logging
import re
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
    
    # Fast paths for short videos
    full_text = transcript.get("text", "")
    if len(full_text.split()) < 50:
        logger.warning("Transcript is too short for meaningful analysis")
        write_json(clips_path, [])
        return str(clips_path)

    # 2. Clean transcript and format as numbered segments
    segments = transcript.get("segments", [])
    formatted_segments, segment_lookup = _format_segments_for_llm(segments)
    
    cleaned_text = _clean_transcript(formatted_segments)
    
    logger.info(f"Formatted {len(segment_lookup)} segments for LLM (cleaned transcript: {len(cleaned_text)} chars)")
    
    # 3. Build Expert Prompt
    prompt = _build_expert_prompt(video_title, cleaned_text, segment_lookup)

    logger.info("Sending transcript to LLM for clip extraction...")
    
    try:
        response_json = ask_json(prompt)
        write_json(analysis_dir / "debug_llm_output.json", response_json)
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        raise
        
    # 4. Process LLM output and resolve segment timestamps
    if not isinstance(response_json, list):
        if isinstance(response_json, dict) and "clips" in response_json:
            response_json = response_json["clips"]
        else:
            logger.error(f"Unexpected LLM output format: {type(response_json)}")
            response_json = []

    clips = []
    for raw_clip in response_json:
        start_seg = raw_clip.get("start_segment_id")
        end_seg = raw_clip.get("end_segment_id")
        
        # Resolve timestamps from segment IDs
        start_ts = segment_lookup.get(start_seg, {}).get("start") if start_seg is not None else None
        end_ts = segment_lookup.get(end_seg, {}).get("end") if end_seg is not None else None
        
        if start_ts is not None and end_ts is not None and end_ts > start_ts:
            duration = end_ts - start_ts
            
            # If clip is short (between 10s and MIN_CLIP_DURATION), auto-pad start and end equally to reach MIN_CLIP_DURATION
            if duration < MIN_CLIP_DURATION and duration >= 10.0:
                needed = MIN_CLIP_DURATION - duration
                pad = needed / 2.0
                logger.info(f"Clip (seg {start_seg}-{end_seg}) is {duration:.1f}s — auto-padding by {pad:.1f}s on both ends to reach {MIN_CLIP_DURATION}s")
                start_ts = max(0.0, start_ts - pad)
                end_ts = end_ts + pad
                duration = end_ts - start_ts
            
            if duration < MIN_CLIP_DURATION:
                logger.warning(f"Clip too short ({duration:.1f}s < {MIN_CLIP_DURATION}s), skipping: seg {start_seg}-{end_seg}")
                continue
            
            if duration > MAX_CLIP_DURATION + 15:
                logger.warning(f"Clip too long ({duration:.1f}s > {MAX_CLIP_DURATION + 15}s), skipping: seg {start_seg}-{end_seg}")
                continue
                
            clips.append({
                "start_seconds": start_ts,
                "end_seconds": end_ts,
                "duration": round(duration, 2),
                "hook": raw_clip.get("hook", ""),
                "reason": raw_clip.get("reason", ""),
                "category": raw_clip.get("category", ""),
                "score": raw_clip.get("score", 0),
                "start_segment_id": start_seg,
                "end_segment_id": end_seg,
            })
        else:
            logger.warning(
                f"Could not resolve segment timestamps: "
                f"start_seg={start_seg} (found={start_ts}), end_seg={end_seg} (found={end_ts})"
            )

    # Sort by score descending
    clips = sorted(clips, key=lambda c: c.get("score", 0), reverse=True)
    
    logger.info(f"Found {len(clips)} valid clips from LLM analysis")
    write_json(clips_path, clips)
    
    return str(clips_path)


def _clean_transcript(formatted_text: str) -> str:
    """
    Clean transcript noise before sending to LLM.
    Collapses repeated words (audience cheering/laughter misidentified by Whisper).
    """
    # Collapse repeated Hindi filler words (हेलो, हो, etc.)
    # Pattern: same word repeated 4+ times in a row
    def collapse_repeats(text: str) -> str:
        # Match any word repeated 4+ times (works for Hindi and English)
        pattern = r'\b(\S+?)(?:\s+\1){3,}\b'
        result = re.sub(pattern, r'[REPEATED: \1]', text, flags=re.UNICODE)
        return result
    
    cleaned = collapse_repeats(formatted_text)
    
    # Also collapse lines that are purely noise markers
    lines = cleaned.split('\n')
    cleaned_lines = []
    for line in lines:
        # Skip lines that are entirely repeated noise
        stripped = line.strip()
        if stripped and not re.match(r'^\[SEG \d+.*?\]\s*(\[REPEATED:.*?\]\s*)+$', stripped):
            cleaned_lines.append(line)
        elif stripped:
            # Keep the segment marker but note it's noise
            seg_match = re.match(r'(\[SEG \d+ \| [\d:.]+\s*-\s*[\d:.]+\])', stripped)
            if seg_match:
                cleaned_lines.append(f"{seg_match.group(1)} [AUDIENCE NOISE / LAUGHTER]")
            else:
                cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def _format_segments_for_llm(segments: list) -> tuple[str, dict]:
    """
    Format transcript segments as numbered lines with timestamps.
    Returns (formatted_text, segment_lookup_dict).
    
    Example output:
        [SEG 0 | 0:02 - 0:04] हेलो हेलो
        [SEG 1 | 0:04 - 0:08] यह वला भाई करो करो करो
    """
    lines = []
    lookup = {}
    
    for seg in segments:
        seg_id = seg.get("id", 0)
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        text = seg.get("text", "").strip()
        
        if not text:
            continue
            
        start_fmt = _format_time(start)
        end_fmt = _format_time(end)
        
        lines.append(f"[SEG {seg_id} | {start_fmt} - {end_fmt}] {text}")
        lookup[seg_id] = {"start": start, "end": end, "text": text}
    
    return '\n'.join(lines), lookup


def _format_time(seconds: float) -> str:
    """Format seconds as M:SS or H:MM:SS."""
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _build_expert_prompt(video_title: str, transcript_text: str, segment_lookup: dict) -> str:
    """Build a detailed expert prompt for clip extraction."""
    
    max_seg_id = max(segment_lookup.keys()) if segment_lookup else 0
    
    return f"""You are an expert short-form video editor specializing in TikTok, YouTube Shorts, and Instagram Reels.
You are analyzing a transcript from a YouTube video to find the MOST ENGAGING, VIRAL-WORTHY segments.

## Video Info
- **Title**: "{video_title}"
- **Total Segments**: {len(segment_lookup)} (IDs from 0 to {max_seg_id})

## Your Task
Find **5 to 8 clips** that would perform best as standalone short-form videos. Each clip MUST be between {MIN_CLIP_DURATION} and {MAX_CLIP_DURATION} seconds long.

## What Makes a Clip Go Viral — Look For These Signals

### 🎯 Category 1: PUNCHLINES & JOKES
- A joke with a clear setup and punchline
- Dark humor, wordplay, or unexpected twists
- Double entendres or clever callbacks

### 🔥 Category 2: ROASTS & BURNS  
- One person roasting another with a savage comeback
- Playful insults that make the audience lose it
- Self-deprecating humor that hits hard

### 💣 Category 3: HOT TAKES & CONTROVERSY
- Bold, controversial, or unpopular opinions stated confidently
- Moments where someone says something shocking or taboo
- Debates or arguments that escalate quickly

### 😂 Category 4: AUDIENCE ERUPTION
- Moments right before or during massive audience laughter
- When a joke lands SO hard the speaker can't even continue
- Standing ovation or collective gasp moments

### 💬 Category 5: QUOTABLE ONE-LINERS
- Short, punchy statements people would share or screenshot
- Motivational or philosophical bombs dropped casually
- Memorable catchphrases or iconic moments

### 🤯 Category 6: ABSURD / UNEXPECTED MOMENTS
- Something completely random or unexpected happening
- When the conversation takes a wild, unplanned turn
- Breaking character or fourth-wall moments

### ❤️ Category 7: EMOTIONAL / REAL MOMENTS
- Genuine vulnerability or heartfelt confession
- A real, raw moment that breaks through the comedy
- Touching stories or personal revelations

## CRITICAL RULES

1. **Use segment IDs**: Each line in the transcript starts with `[SEG <id> | <time>]`. You MUST reference these IDs.
2. **Diversity**: Pick clips from DIFFERENT parts of the video. Don't cluster all clips from the same section.
3. **Strong Hook**: The FIRST 3 seconds (first segment) of each clip MUST immediately grab attention. No slow intros.
4. **Self-Contained**: Each clip must make sense on its own — a viewer who hasn't seen the full video should still find it engaging.
5. **Ignore Noise**: Lines marked `[AUDIENCE NOISE / LAUGHTER]` or `[REPEATED: ...]` are audience reactions, not dialogue. Use them as SIGNALS that something funny happened nearby, but don't include them as the main spoken content of a clip.
6. **Audience Interactions Priority**: Clips that contain or immediately precede major audience reactions (like `[AUDIENCE NOISE / LAUGHTER]` or `[LAUGHTER]`) perform extremely well as shorts because they contain built-in social proof. Favor these segments.
7. **Score Honestly**: Don't give every clip 90+. Use the full 0-100 range. Only truly viral-worthy clips should score above 80.

## Scoring Rubric (use this to calculate the score)
- **Hook Strength** (0-25): How immediately attention-grabbing are the first 3 seconds?
- **Entertainment Value** (0-25): How funny, shocking, or emotionally impactful is it?
- **Shareability** (0-25): Would someone send this to a friend or repost it?
- **Self-Contained Clarity** (0-25): Does it make sense without context?
- **Audience Laughter/Reaction Bonus** (Add up to +10 points): If the clip contains, is directly preceded by, or immediately followed by audience laughter (`[AUDIENCE NOISE / LAUGHTER]` or similar reactions), add up to 10 points to the final score (capping the final score at 100). Explicitly state this bonus in the "reason" field.

## Transcript
{transcript_text}

## Output Format
Return a JSON array. Each object MUST have these fields:
- `"start_segment_id"`: (integer) The segment ID where the clip starts
- `"end_segment_id"`: (integer) The segment ID where the clip ends
- `"hook"`: (string) What makes the first 3 seconds grab attention
- `"reason"`: (string) Why this specific clip will go viral (be specific, not generic)
- `"category"`: (string) One of: "punchline", "roast", "hot_take", "audience_eruption", "quotable", "absurd", "emotional"
- `"score"`: (integer 0-100) Virality score using the rubric above

Output ONLY the JSON array. No explanation before or after.
"""


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
