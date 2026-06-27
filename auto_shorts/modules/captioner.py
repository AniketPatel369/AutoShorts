"""
Auto Shorts — Module: Captioner

Burns word-level synced captions onto vertical clips.
Supports custom fonts, colors, layouts, and animations (e.g. CapCut-style active word scale pop-in).
"""
import os
import logging
import subprocess
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from auto_shorts.config import PROJECT_ROOT, CLIP_BUFFER_SECONDS
from auto_shorts.utils.file_utils import read_json

logger = logging.getLogger(__name__)

# Default search paths for standard bold TrueType fonts across platforms
DEFAULT_FONTS = [
    # macOS Supplemental
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
    "/System/Library/Fonts/Supplemental/Trebuchet MS Bold.ttf",
    # macOS core
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/HelveticaNeue.dfont",
    # Windows
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\verdanab.ttf",
    "C:\\Windows\\Fonts\\tahomabd.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def add_animated_captions(
    video_path: str,
    words: list[dict],
    out_path: str,
    style: dict | None = None,
) -> str:
    """
    Returns path to vertical video with burned-in animated word-synced captions.
    
    Args:
        video_path: Path to the vertical (already cropped 9:16) video clip.
        words: List of words, e.g. [{"word": "hello", "start": 0.12, "end": 0.45}, ...]
               Timestamps must be relative to the start of this clip.
        out_path: Output video file path.
        style: Optional dictionary containing font, color, positioning, and animation overrides.
    """
    logger.info(f"Adding animated captions to video: {video_path}")
    
    # 1. Resolve Style Configuration
    if style is None:
        style = {}
        
    font_path = style.get("font_path", "")
    if not font_path or not os.path.exists(font_path):
        # Check local Poppins Bold (which supports Devanagari/Hindi perfectly)
        local_poppins = str(PROJECT_ROOT / "models" / "Poppins-Bold.ttf")
        if os.path.exists(local_poppins):
            font_path = local_poppins
        else:
            # Automatically find a bold TrueType font on the host system
            for fp in DEFAULT_FONTS:
                if os.path.exists(fp):
                    font_path = fp
                    break
            else:
                font_path = "" # Pillow will fallback to default font
            
    font_size = style.get("font_size", 60) # Increased size for better readability
    base_color = style.get("base_color", (255, 255, 255))      # White
    active_color_rgb = style.get("active_color", (255, 255, 0)) # Neon Yellow in RGB
    
    stroke_color = style.get("stroke_color", (0, 0, 0))        # Black
    stroke_width = style.get("stroke_width", 6)                # Thicker border/stroke
    
    y_position_percent = style.get("y_position_percent", 0.72)  # Place in lower third (72% height)
    animation_type = style.get("animation_type", "pop")         # Options: "pop" (active scales up), "karaoke" (active color only)
    
    max_words_per_chunk = style.get("max_words_per_chunk", 4)
    max_chunk_duration = style.get("max_chunk_duration_seconds", 1.8)
    
    # 2. Group words into display chunks
    chunks = _group_words_into_chunks(words, max_words_per_chunk, max_chunk_duration)
    logger.info(f"Grouped {len(words)} words into {len(chunks)} caption display chunks")
    
    # 3. Open Video Reader
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open clip: {video_path}")
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Target height coordinate for text center
    y_pos = int(height * y_position_percent)
    
    # Load Font
    try:
        if font_path:
            font = ImageFont.truetype(font_path, font_size)
            logger.info(f"Loaded font: {font_path} at size {font_size}")
        else:
            font = ImageFont.load_default()
            logger.warning("No TTF font found on system, using Pillow default font (styling disabled)")
    except Exception as e:
        logger.error(f"Failed to load font {font_path}, fallback to default: {e}")
        font = ImageFont.load_default()
        font_path = ""
        
    # 4. Render captioned frames
    temp_output_path = out_path + ".tmp.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_output_path, fourcc, fps, (width, height))
    
    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        current_time = frame_idx / fps
        
        # Find if there is an active word chunk for this timestamp
        active_chunk = None
        for chunk in chunks:
            if chunk["start"] <= current_time <= chunk["end"]:
                active_chunk = chunk
                break
                
        if active_chunk:
            # Render captions overlay on this frame
            frame = _render_caption_frame(
                frame=frame,
                chunk=active_chunk,
                current_time=current_time,
                font=font,
                font_path=font_path,
                font_size=font_size,
                base_color=base_color,
                active_color=active_color_rgb,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
                y_pos=y_pos,
                animation=animation_type
            )
            
        out.write(frame)
        frame_idx += 1
        
    cap.release()
    out.release()
    
    # 5. Mux original audio into captioned video using FFmpeg
    logger.info("Muxing audio track back into captioned clip...")
    try:
        if os.path.exists(out_path):
            os.remove(out_path)
            
        cmd = [
            "ffmpeg", "-y",
            "-i", temp_output_path,
            "-i", video_path, # pull audio from uncaptioned clip
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            out_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        # Clean up temp file
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
            
        logger.info(f"✅ Captioning complete: {out_path}")
        return out_path
    except Exception as e:
        logger.error(f"Failed to mux audio using ffmpeg: {e}")
        if os.path.exists(temp_output_path):
            if os.path.exists(out_path):
                os.remove(out_path)
            os.rename(temp_output_path, out_path)
        return out_path


def _group_words_into_chunks(words: list[dict], max_words: int, max_duration: float) -> list[dict]:
    """
    Groups individual words into cohesive multi-word caption chunks for display.
    """
    chunks = []
    if not words:
        return chunks
        
    current_chunk = []
    chunk_start_time = None
    
    for w in words:
        word_text = w.get("word", "").strip()
        if not word_text:
            continue
            
        w_start = w.get("start", 0.0)
        w_end = w.get("end", 0.0)
        
        if chunk_start_time is None:
            chunk_start_time = w_start
            
        # Check constraints: word limit or duration limit reached, or a long pause (>0.7s)
        duration_exceeded = (w_end - chunk_start_time) > max_duration
        word_limit_reached = len(current_chunk) >= max_words
        pause_detected = len(current_chunk) > 0 and (w_start - current_chunk[-1]["end"]) > 0.7
        
        if (duration_exceeded or word_limit_reached or pause_detected) and current_chunk:
            # Save completed chunk
            chunks.append({
                "words": current_chunk,
                "start": chunk_start_time,
                "end": current_chunk[-1]["end"]
            })
            # Start new chunk
            current_chunk = []
            chunk_start_time = w_start
            
        current_chunk.append({
            "word": word_text,
            "start": w_start,
            "end": w_end
        })
        
    if current_chunk:
        chunks.append({
            "words": current_chunk,
            "start": chunk_start_time,
            "end": current_chunk[-1]["end"]
        })
        
    return chunks


def _render_caption_frame(
    frame: np.ndarray,
    chunk: dict,
    current_time: float,
    font: ImageFont.ImageFont,
    font_path: str,
    font_size: int,
    base_color: tuple[int, int, int],
    active_color: tuple[int, int, int],
    stroke_color: tuple[int, int, int],
    stroke_width: int,
    y_pos: int,
    animation: str
) -> np.ndarray:
    """
    Composite word-highlighted text onto OpenCV frame using Pillow.
    """
    # 1. Convert BGR frame to PIL RGB Image
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    width, height = pil_img.size
    
    # 2. Pre-calculate spacing and text layout coordinates based on original (unscaled) sizes
    # This prevents the surrounding words from jumping/shaking when active words are scaled.
    word_elements = []
    total_text_width = 0
    space_width = 0
    
    # Get space width
    if font_path:
        space_bbox = font.getbbox(" ")
        space_width = space_bbox[2] - space_bbox[0]
    else:
        # Default fallback space
        space_width = 6
        
    for w in chunk["words"]:
        w_text = w["word"]
        
        # Find if this word is the active highlighted word at current timestamp
        # Floor display duration to at least 150ms visually so highlights are readable
        is_active = (w["start"] <= current_time <= max(w["end"], w["start"] + 0.15))
        
        if font_path:
            bbox = font.getbbox(w_text)
            w_w = bbox[2] - bbox[0]
            w_h = bbox[3] - bbox[1]
        else:
            # Fallback metrics
            w_w = len(w_text) * 10
            w_h = 15
            
        word_elements.append({
            "word": w_text,
            "width": w_w,
            "height": w_h,
            "is_active": is_active,
            "start": w["start"],
            "end": w["end"]
        })
        
    # Calculate total line width including spaces
    total_text_width = sum(el["width"] for el in word_elements) + (space_width * (len(word_elements) - 1))
    
    # Apply safety margins and dynamic downscaling to prevent text overflow at edges
    horizontal_padding = 45
    max_text_width = width - (horizontal_padding * 2)
    active_font = font
    active_font_size = font_size
    
    if total_text_width > max_text_width and font_path:
        scale_factor = max_text_width / total_text_width
        active_font_size = int(font_size * scale_factor)
        active_font_size = max(28, active_font_size) # Floor minimum readability size
        active_font = ImageFont.truetype(font_path, active_font_size)
        
        # Re-layout elements with adjusted font size
        word_elements = []
        space_bbox = active_font.getbbox(" ")
        space_width = space_bbox[2] - space_bbox[0]
        for w in chunk["words"]:
            w_text = w["word"]
            is_active = (w["start"] <= current_time <= max(w["end"], w["start"] + 0.15))
            bbox = active_font.getbbox(w_text)
            w_w = bbox[2] - bbox[0]
            w_h = bbox[3] - bbox[1]
            word_elements.append({
                "word": w_text,
                "width": w_w,
                "height": w_h,
                "is_active": is_active,
                "start": w["start"],
                "end": w["end"]
            })
        total_text_width = sum(el["width"] for el in word_elements) + (space_width * (len(word_elements) - 1))
        
    # Starting X coordinate to center-align the whole chunk line
    start_x = (width - total_text_width) / 2
    
    # 3. Draw each word
    current_x = start_x
    for el in word_elements:
        w_text = el["word"]
        w_w = el["width"]
        w_h = el["height"]
        
        if el["is_active"]:
            if animation == "pop" and font_path:
                # Active word scale pop-in (draw it 18% larger, centered over its original box)
                pop_size = int(active_font_size * 1.18)
                pop_font = ImageFont.truetype(font_path, pop_size)
                pop_bbox = pop_font.getbbox(w_text)
                pop_w = pop_bbox[2] - pop_bbox[0]
                pop_h = pop_bbox[3] - pop_bbox[1]
                
                # Offset coordinate centering
                dx = (w_w - pop_w) / 2
                dy = (w_h - pop_h) / 2
                
                draw.text(
                    xy=(current_x + dx, y_pos + dy),
                    text=w_text,
                    font=pop_font,
                    fill=active_color,
                    stroke_fill=stroke_color,
                    stroke_width=stroke_width
                )
            else:
                # Simple karaoke highlight
                draw.text(
                    xy=(current_x, y_pos),
                    text=w_text,
                    font=active_font,
                    fill=active_color,
                    stroke_fill=stroke_color,
                    stroke_width=stroke_width
                )
        else:
            # Inactive base word
            draw.text(
                xy=(current_x, y_pos),
                text=w_text,
                font=active_font,
                fill=base_color,
                stroke_fill=stroke_color,
                stroke_width=stroke_width
            )
            
        current_x += w_w + space_width
        
    # 4. Convert back to OpenCV BGR frame
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def caption(project_dir: Path) -> str:
    """
    Load project clips, align transcript words, burn captions, and replace clips.
    """
    analysis_dir = project_dir / "analysis"
    output_dir = project_dir / "output"
    
    # Load scored clips if available, else raw clips
    scored_path = analysis_dir / "clips_scored.json"
    raw_path = analysis_dir / "clips_raw.json"
    
    if scored_path.exists():
        clips_data = read_json(scored_path)
    elif raw_path.exists():
        clips_data = read_json(raw_path)
    else:
        raise FileNotFoundError("No clips data found. Run 'analyze' first.")
        
    transcript_path = analysis_dir / "transcript.json"
    if not transcript_path.exists():
        raise FileNotFoundError("Transcript not found")
    transcript = read_json(transcript_path)
    
    # Flatten all words from segments
    all_words = []
    for seg in transcript.get("segments", []):
        for w in seg.get("words", []):
            all_words.append(w)
            
    if not clips_data:
        logger.warning("No clips to caption")
        return str(output_dir)
        
    logger.info(f"Captioning {len(clips_data)} clips...")
    
    for i, clip_dict in enumerate(clips_data, 1):
        score = clip_dict.get("score", 0)
        # Search for the cut clip file matching index
        matches = list(output_dir.glob(f"clip_{i:02d}_score_*.mp4"))
        if not matches:
            logger.warning(f"Could not find cut clip for index {i}, skipping")
            continue
            
        clip_file = matches[0]
        temp_out = clip_file.parent / f"captioned_temp_{clip_file.name}"
        
        # Calculate clip start and end timestamps (offset by the 5.0 seconds buffer we added to the end)
        # When cut, start was: max(0.0, start_seconds - buffer)
        # When cut, end was: end_seconds + 5.0 + buffer
        clip_start_abs = max(0.0, clip_dict.get("start_seconds", 0.0) - CLIP_BUFFER_SECONDS)
        clip_end_abs = clip_dict.get("end_seconds", 0.0) + 5.0 + CLIP_BUFFER_SECONDS
        
        # Filter words matching this absolute timestamp range
        clip_words = []
        for w in all_words:
            w_start = w.get("start", 0.0)
            w_end = w.get("end", 0.0)
            if w_start >= clip_start_abs and w_end <= clip_end_abs:
                # Shift relative to the clip start
                clip_words.append({
                    "word": w.get("word", ""),
                    "start": w_start - clip_start_abs,
                    "end": w_end - clip_start_abs
                })
                
        # Burn animated captions
        add_animated_captions(
            video_path=str(clip_file),
            words=clip_words,
            out_path=str(temp_out)
        )
        
        # Overwrite the original clip
        if temp_out.exists():
            if clip_file.exists():
                os.remove(clip_file)
            os.rename(temp_out, clip_file)
            logger.info(f"✓ Captioned clip {i}: {clip_file.name}")
            
    return str(output_dir)


# ── Standalone test ──────────────────────────────────────
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    if len(sys.argv) < 2:
        print("Usage: python -m auto_shorts.modules.captioner <project_dir>")
        sys.exit(1)
        
    project_dir = Path(sys.argv[1])
    logger.info(f"Running standalone caption test for: {project_dir}")
    
    # Load first cut clip and test captioning it
    output_dir = project_dir / "output"
    clips = list(output_dir.glob("clip_*.mp4"))
    
    if not clips:
        print("No cut clips found. Run 'cut' stage first.")
        sys.exit(1)
        
    test_clip = clips[0]
    out_clip = test_clip.parent / f"captioned_{test_clip.name}"
    
    # Load transcript word-level timestamps to test
    transcript_path = project_dir / "analysis" / "transcript.json"
    if not transcript_path.exists():
        print("No transcript.json found. Run 'transcribe' first.")
        sys.exit(1)
        
    from auto_shorts.config import PROJECT_ROOT, CLIP_BUFFER_SECONDS
    from auto_shorts.utils.file_utils import read_json
    transcript = read_json(transcript_path)
    
    # Gather dummy words for first 15 seconds
    words = []
    for seg in transcript.get("segments", []):
        for w in seg.get("words", []):
            if w.get("start", 0.0) <= 15.0:
                words.append(w)
                
    add_animated_captions(str(test_clip), words, str(out_clip))
    print(f"Test clip captioned at: {out_clip}")
