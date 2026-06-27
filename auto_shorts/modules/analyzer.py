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

from auto_shorts.config import MIN_CLIP_DURATION, MAX_CLIP_DURATION, CHUNK_WINDOW_SECONDS, CHUNK_OVERLAP_SECONDS
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

    # 2. Clean transcript and divide into overlapping chunks
    segments = transcript.get("segments", [])
    chunks = _create_chunks(segments)
    logger.info(f"Split {len(segments)} segments into {len(chunks)} overlapping chunks of {CHUNK_WINDOW_SECONDS}s (overlap: {CHUNK_OVERLAP_SECONDS}s)")

    raw_clips = []
    max_global_seg_id = segments[-1].get("id", 0) if segments else 0
    
    # 3. Analyze each chunk
    for chunk_idx, chunk_segs in enumerate(chunks):
        if not chunk_segs:
            continue
        chunk_start_seg = chunk_segs[0].get("id", 0)
        chunk_end_seg = chunk_segs[-1].get("id", 0)
        
        # Format segments for this chunk
        formatted_segments, segment_lookup = _format_segments_for_llm(chunk_segs)
        cleaned_text = _clean_transcript(formatted_segments)
        
        chunk_info = f"This chunk covers segments {chunk_start_seg}-{chunk_end_seg} out of a video with segments 0-{max_global_seg_id} total."
        
        prompt = _build_expert_prompt(video_title, cleaned_text, segment_lookup, chunk_info)
        
        logger.info(f"Sending Chunk {chunk_idx + 1}/{len(chunks)} (seg {chunk_start_seg}-{chunk_end_seg}) to LLM...")
        
        try:
            response_json = ask_json(prompt)
            # Write debug files for trace
            write_json(analysis_dir / f"debug_llm_output_chunk_{chunk_idx + 1}.json", response_json)
            
            chunk_clips = []
            if isinstance(response_json, list):
                chunk_clips = response_json
            elif isinstance(response_json, dict) and "clips" in response_json:
                chunk_clips = response_json["clips"]
                
            for rc in chunk_clips:
                if isinstance(rc, dict):
                    raw_clips.append(rc)
        except Exception as e:
            logger.warning(f"⚠️ Failed to analyze Chunk {chunk_idx + 1}: {e}. Continuing with next chunk.")

    # Write combined raw clips to debug file for user transparency
    write_json(analysis_dir / "debug_llm_output.json", raw_clips)
    logger.info(f"LLM generated {len(raw_clips)} candidate clips across all chunks")

    # 4. Resolve and adjust timestamps for candidates
    candidates = []
    for raw_clip in raw_clips:
        start_seg = raw_clip.get("start_segment_id")
        end_seg = raw_clip.get("end_segment_id")
        
        # Resolve and intelligently adjust timestamps to avoid cutting off context mid-sentence
        if start_seg is not None and end_seg is not None:
            start_ts, end_ts = _adjust_timestamps_to_context_boundaries(start_seg, end_seg, segments)
        else:
            start_ts = None
            end_ts = None
        
        if start_ts is not None and end_ts is not None and end_ts > start_ts:
            duration = end_ts - start_ts
            
            # If clip is short (under MIN_CLIP_DURATION), auto-pad start and end to reach MIN_CLIP_DURATION
            if duration < MIN_CLIP_DURATION and duration > 0.0:
                needed = MIN_CLIP_DURATION - duration
                pad = needed / 2.0
                
                new_start = max(0.0, start_ts - pad)
                actual_start_pad = start_ts - new_start
                remaining_pad = needed - actual_start_pad
                new_end = end_ts + remaining_pad
                
                logger.info(f"Clip (seg {start_seg}-{end_seg}) is {duration:.1f}s — auto-padding to reach {MIN_CLIP_DURATION}s (start_pad={actual_start_pad:.1f}s, end_pad={remaining_pad:.1f}s)")
                
                start_ts = new_start
                end_ts = new_end
                duration = end_ts - start_ts
            
            if duration < MIN_CLIP_DURATION:
                logger.warning(f"Clip too short ({duration:.1f}s < {MIN_CLIP_DURATION}s), skipping: seg {start_seg}-{end_seg}")
                continue
            
            if duration > MAX_CLIP_DURATION + 15:
                logger.warning(f"Clip too long ({duration:.1f}s > {MAX_CLIP_DURATION + 15}s), skipping: seg {start_seg}-{end_seg}")
                continue
                
            candidates.append({
                "start_seconds": round(start_ts, 2),
                "end_seconds": round(end_ts, 2),
                "duration": round(duration, 2),
                "hook": raw_clip.get("hook", ""),
                "reason": raw_clip.get("reason", ""),
                "category": raw_clip.get("category", ""),
                "score": raw_clip.get("score", 0),
                "start_segment_id": start_seg,
                "end_segment_id": end_seg,
            })

    # 5. Deduplicate overlapping candidate clips
    deduped_candidates = _deduplicate_clips(candidates)
    logger.info(f"Deduplicated candidates count: {len(candidates)} -> {len(deduped_candidates)}")

    # 6. Final spacing/diversity pass (Zero-overlap constraint)
    sorted_candidates = sorted(deduped_candidates, key=lambda c: c.get("score", 0), reverse=True)
    final_clips = []
    
    for cand in sorted_candidates:
        c_start = cand["start_seconds"]
        c_end = cand["end_seconds"]
        
        # Check if this candidate overlaps at all with already selected final clips
        has_overlap = False
        for selected in final_clips:
            s_start = selected["start_seconds"]
            s_end = selected["end_seconds"]
            # Intersection duration
            overlap = max(0.0, min(c_end, s_end) - max(c_start, s_start))
            if overlap > 0.0:
                has_overlap = True
                break
                
        if not has_overlap:
            final_clips.append(cand)
            
        if len(final_clips) >= 8:
            break
            
    # Chronologically sort the final clips
    final_clips = sorted(final_clips, key=lambda c: c["start_seconds"])
    
    logger.info(f"Selected final {len(final_clips)} disjoint, high-quality clips")
    write_json(clips_path, final_clips)
    
    return str(clips_path)


def _create_chunks(segments: list) -> list[list]:
    """
    Split flat segments into overlapping list of chunks based on timestamps in config.
    """
    chunks = []
    if not segments:
        return chunks

    start_time = segments[0].get("start", 0.0)
    end_time = segments[-1].get("end", 0.0)
    step = CHUNK_WINDOW_SECONDS - CHUNK_OVERLAP_SECONDS

    current_start = start_time
    while current_start < end_time:
        current_end = current_start + CHUNK_WINDOW_SECONDS
        
        # Gather segments in this window
        chunk_segs = []
        for seg in segments:
            seg_start = seg.get("start", 0.0)
            seg_end = seg.get("end", 0.0)
            if seg_start < current_end and seg_end > current_start:
                chunk_segs.append(seg)
                
        if chunk_segs:
            chunks.append(chunk_segs)
            
        if current_end >= end_time:
            break
        current_start += step

    return chunks


def _deduplicate_clips(candidates: list) -> list:
    """
    Deduplicates clips that overlap significantly (>50% of the duration of either clip).
    Keeps the one with the higher score.
    """
    # Sort candidates by score descending
    sorted_candidates = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)
    deduped = []
    
    for cand in sorted_candidates:
        c_start = cand["start_seconds"]
        c_end = cand["end_seconds"]
        c_dur = c_end - c_start
        
        is_duplicate = False
        for existing in deduped:
            e_start = existing["start_seconds"]
            e_end = existing["end_seconds"]
            e_dur = e_end - e_start
            
            # Calculate overlap duration
            overlap = max(0.0, min(c_end, e_end) - max(c_start, e_start))
            if overlap > 0.0 and c_dur > 0.0 and e_dur > 0.0:
                # If the overlap covers more than 50% of either clip, they are duplicates
                overlap_ratio_cand = overlap / c_dur
                overlap_ratio_exist = overlap / e_dur
                if overlap_ratio_cand > 0.5 or overlap_ratio_exist > 0.5:
                    is_duplicate = True
                    break
                    
        if not is_duplicate:
            deduped.append(cand)
            
    return deduped


def _adjust_timestamps_to_context_boundaries(start_seg: int, end_seg: int, segments: list) -> tuple[float, float]:
    """
    Intelligently adjusts start and end timestamps to avoid cutting off sentences mid-word or mid-thought.
    Uses word-level punctuation and pauses (silent gaps between words) to find natural boundaries.
    """
    # 1. Flatten all words with timestamps
    flat_words = []
    for seg in segments:
        seg_id = seg.get("id")
        for w in seg.get("words", []):
            flat_words.append({
                "word": w.get("word", "").strip(),
                "start": w.get("start", 0.0),
                "end": w.get("end", 0.0),
                "segment_id": seg_id
            })
            
    if not flat_words:
        return 0.0, 0.0
        
    # 2. Find start and end indices matching the segment range
    start_idx = None
    end_idx = None
    
    for idx, w in enumerate(flat_words):
        if w["segment_id"] == start_seg and start_idx is None:
            start_idx = idx
        if w["segment_id"] == end_seg:
            end_idx = idx # Keeps updating to find the last word of the end segment
            
    if start_idx is None:
        start_idx = 0
    if end_idx is None:
        end_idx = len(flat_words) - 1
        
    # Default resolved timestamps from the raw segment IDs
    start_ts = flat_words[start_idx]["start"]
    end_ts = flat_words[end_idx]["end"]
    
    # 3. Look-behind to find clean start boundary (beginning of a sentence or after a pause)
    # Look back up to 10 words
    best_start_idx = start_idx
    for i in range(start_idx, max(-1, start_idx - 10), -1):
        if i == 0:
            best_start_idx = 0
            break
            
        current_word = flat_words[i]
        prev_word = flat_words[i - 1]
        
        # Check if the previous word ends with punctuation (indicating current word starts a sentence)
        has_punctuation = any(prev_word["word"].endswith(p) for p in [".", "?", "!", "।", "|"])
        
        # Check if there was a pause of more than 0.6 seconds before this word
        has_pause = (current_word["start"] - prev_word["end"]) > 0.6
        
        if has_punctuation or has_pause:
            best_start_idx = i
            break
            
    start_ts = flat_words[best_start_idx]["start"]
    
    # 4. Look-ahead to find clean end boundary (end of a sentence or a natural pause)
    # Look forward up to 15 words
    best_end_idx = end_idx
    for i in range(end_idx, min(len(flat_words) - 1, end_idx + 15)):
        current_word = flat_words[i]
        next_word = flat_words[i + 1]
        
        # Check if the current word ends with punctuation
        has_punctuation = any(current_word["word"].endswith(p) for p in [".", "?", "!", "।", "|"])
        
        # Check if there is a pause of more than 0.6 seconds after this word
        has_pause = (next_word["start"] - current_word["end"]) > 0.6
        
        if has_punctuation or has_pause:
            best_end_idx = i
            break
            
    end_ts = flat_words[best_end_idx]["end"]
    
    return start_ts, end_ts


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


def _build_expert_prompt(video_title: str, transcript_text: str, segment_lookup: dict, chunk_info: str = "") -> str:
    """Build a detailed expert prompt for clip extraction."""
    
    max_seg_id = max(segment_lookup.keys()) if segment_lookup else 0
    chunk_header = f"\n## Current Chunk Information\n{chunk_info}\n" if chunk_info else ""
    
    return f"""You are an expert short-form video editor specializing in TikTok, YouTube Shorts, and Instagram Reels.
You are analyzing a transcript from a YouTube video to find the MOST ENGAGING, VIRAL-WORTHY segments.
{chunk_header}
## Video Info
- **Title**: "{video_title}"
- **Total Segments**: {len(segment_lookup)} (IDs from 0 to {max_seg_id})

## Your Task
Find **1 to 3 clips** that would perform best as standalone short-form videos. Each clip MUST be between {MIN_CLIP_DURATION} and {MAX_CLIP_DURATION} seconds long.
Only extract the absolute best highlights. If no high-quality, viral-worthy segment exists in this specific chunk, return an empty array `[]`. Do not force clips that aren't engaging just to hit the number.

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

### 💪 Category 8: MOTIVATIONAL & INSPIRATIONAL
- Deep, inspiring statements about success, mindset, work ethic, or overcoming struggles
- Speeches or advice that make the viewer want to take action immediately
- Core truth bombs that shift the perspective of the listener

## CRITICAL RULES

1. **Use segment IDs**: Each line in the transcript starts with `[SEG <id> | <time>]`. You MUST reference these IDs.
2. **Diversity**: Pick clips from DIFFERENT parts of the video. Don't cluster all clips from the same section.
3. **Strong Hook**: The FIRST 3 seconds (first segment) of each clip MUST immediately grab attention. No slow intros.
4. **Self-Contained**: Each clip must make sense on its own — a viewer who hasn't seen the full video should still find it engaging.
5. **Ignore Noise**: Lines marked `[AUDIENCE NOISE / LAUGHTER]` or `[REPEATED: ...]` are audience reactions, not dialogue. Use them as SIGNALS that something funny happened nearby, but don't include them as the main spoken content of a clip.
6. **Audience Interactions Priority**: Clips that contain or immediately precede major audience reactions (like `[AUDIENCE NOISE / LAUGHTER]` or `[LAUGHTER]`) perform extremely well as shorts because they contain built-in social proof. Favor these segments.
7. **Contextual Conclusion**: The clip MUST end with a satisfying, complete conclusion to the speaker's sentence or thought. **DO NOT cut off a speaker mid-sentence or mid-phrase.** If a sentence continues into the next segments, expand `end_segment_id` to include all segments necessary to complete the thought, joke punchline, or quote. The viewer must hear the final word and conclusion clearly.
8. **Score Honestly**: Don't give every clip 90+. Use the full 0-100 range. Only truly viral-worthy clips should score above 80.

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
- `"category"`: (string) One of: "punchline", "roast", "hot_take", "audience_eruption", "quotable", "absurd", "emotional", "motivational"
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
