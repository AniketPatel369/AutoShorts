# Auto Shorts — Development Guide

> This file is the **single source of truth** for building this project.
> If we stop today and resume tomorrow, read this file first.

**Full vision & features →** [project.md](./project.md)  
**This file →** How to build it, step by step, with exact modules, dependencies, and commands.

---

## Quick Context

**What:** CLI pipeline that takes a YouTube URL → downloads → transcribes → analyzes with LLM → cuts short clips → outputs ready-to-upload Shorts.

**How it runs:**
```
python main.py --url "https://youtube.com/watch?v=xxx"
```
Later: lightweight FastAPI web UI for status/progress monitoring.

**Key constraints:**
- All AI models run **locally** (no paid APIs)
- Open-source only (Ollama, MLX-Whisper)
- Trend data comes from **web crawling** (scrape Google → Reddit, X, etc.)
- Each video = a self-contained "project" folder
- Must support **resume** (crash-safe, pick up from last completed step)

---

## Tech Stack (Exact)

| Component | Package | Why |
|-----------|---------|-----|
| Python | 3.11+ | MLX/async support |
| Video Download | `yt-dlp` | Best YouTube downloader |
| Speech-to-Text | `mlx-whisper` (primary) or `faster-whisper` (fallback) | Local, fast on M1 |
| LLM | `ollama` + `llama3.1:8b` or `mistral:7b` | Local, free, good quality |
| LLM Python Client | `ollama` (pip package) | Simple API |
| Video Processing | `ffmpeg-python` + system `ffmpeg` | Industry standard |
| Web Scraping | `requests` + `beautifulsoup4` | Simple, reliable |
| Google Search | `googlesearch-python` | No API key needed |
| Scene Detection | `scenedetect[opencv]` | PySceneDetect |
| Embeddings | `sentence-transformers` | Semantic search (later) |
| Web UI (later) | `fastapi` + `uvicorn` + `jinja2` | Lightweight |
| Task Queue | `asyncio` + `concurrent.futures` | No Redis needed |
| Storage | JSON files + SQLite | File-based, portable |

### System Dependencies (must be installed)
```bash
brew install ffmpeg
brew install ollama
# then: ollama pull llama3.1:8b
```

### Python Dependencies
```bash
pip install yt-dlp mlx-whisper ollama ffmpeg-python
pip install requests beautifulsoup4 googlesearch-python
pip install scenedetect[opencv]
# Later phases:
# pip install fastapi uvicorn jinja2 sentence-transformers
```

---

## Project Source Structure

```
auto_shorts/
├── main.py                     # CLI entry point
├── config.py                   # Global config, paths, model names
├── pipeline.py                 # Orchestrator — runs steps in order, handles resume
│
├── modules/
│   ├── __init__.py
│   ├── downloader.py           # Step 1: yt-dlp download + metadata
│   ├── transcriber.py          # Step 2: Whisper speech-to-text
│   ├── analyzer.py             # Step 3: LLM transcript analysis → clip candidates
│   ├── trend_crawler.py        # Step 4: Web crawling for trends
│   ├── scorer.py               # Step 5: Score fusion — combine all signals
│   ├── cutter.py               # Step 6: FFmpeg clip cutting
│   ├── captioner.py            # Step 7: Generate & burn SRT captions
│   └── enhancer.py             # Step 8: Zoom, effects, progress bar (later)
│
├── analyzers/                  # Plug-in analyzers (each independent)
│   ├── __init__.py
│   ├── base.py                 # Abstract base class for all analyzers
│   ├── hook_analyzer.py        # Detects hooks, curiosity gaps
│   ├── trend_analyzer.py       # Scores trend relevance
│   └── scene_analyzer.py       # Scene change detection
│
├── models/                     # Data models / schemas
│   ├── __init__.py
│   ├── project.py              # Project dataclass (project.json schema)
│   ├── clip.py                 # Clip candidate dataclass
│   └── transcript.py           # Transcript segment dataclass
│
├── utils/
│   ├── __init__.py
│   ├── file_utils.py           # Path helpers, JSON read/write
│   ├── time_utils.py           # Timestamp conversion (seconds ↔ HH:MM:SS)
│   └── llm.py                  # Ollama wrapper — single place to change LLM
│
├── workspace/                  # Created at runtime — all project data lives here
│   └── projects/
│       └── <project-name>/
│           ├── project.json
│           ├── downloads/
│           ├── analysis/
│           ├── output/
│           └── logs/
│
├── requirements.txt
└── README.md
```

---

## Module Dependency Graph

```
main.py
  │
  └──▶ pipeline.py (orchestrator)
         │
         ├──▶ modules/downloader.py     [Step 1]  ── depends on: yt-dlp
         │         └── outputs: video.mp4, metadata.json, captions.vtt
         │
         ├──▶ modules/transcriber.py    [Step 2]  ── depends on: mlx-whisper
         │         └── needs: video.mp4 (or audio extracted from it)
         │         └── outputs: transcript.json (word-level timestamps)
         │
         ├──▶ modules/trend_crawler.py  [Step 3]  ── depends on: requests, bs4
         │         └── needs: metadata.json (keywords)
         │         └── outputs: trends.json
         │
         ├──▶ modules/analyzer.py       [Step 4]  ── depends on: ollama
         │         └── needs: transcript.json + trends.json + metadata.json
         │         └── outputs: clips_raw.json (candidate clips with timestamps)
         │
         ├──▶ modules/scorer.py         [Step 5]  ── depends on: analyzers/*
         │         └── needs: clips_raw.json
         │         └── runs each analyzer plugin
         │         └── outputs: clips_scored.json (ranked, with scores)
         │
         ├──▶ modules/cutter.py         [Step 6]  ── depends on: ffmpeg
         │         └── needs: video.mp4 + clips_scored.json
         │         └── outputs: output/clip_001.mp4, clip_002.mp4, ...
         │
         ├──▶ modules/captioner.py      [Step 7]  ── depends on: ffmpeg
         │         └── needs: output/clip_*.mp4 + transcript.json
         │         └── outputs: output/clip_*_captioned.mp4
         │
         └──▶ modules/enhancer.py       [Step 8]  ── depends on: ffmpeg, opencv
                   └── needs: output/clip_*_captioned.mp4
                   └── outputs: output/final/short_001.mp4, ...
```

### Key Rule: Each step reads from disk, writes to disk
- No step passes data in-memory to the next step
- Everything goes through the project folder
- This is what makes **resume** possible

---

## Data Flow (Files)

Each project folder accumulates files as steps complete:

```
project-name/
├── project.json                    ← Created by pipeline (Step 0)
│
├── downloads/
│   ├── video.mp4                   ← Step 1 (downloader)
│   ├── metadata.json               ← Step 1 (downloader)
│   └── captions.en.vtt             ← Step 1 (downloader, if available)
│
├── analysis/
│   ├── transcript.json             ← Step 2 (transcriber)
│   ├── keywords.json               ← Step 2 (extracted from metadata)
│   ├── trends.json                 ← Step 3 (trend_crawler)
│   ├── clips_raw.json              ← Step 4 (analyzer — LLM output)
│   └── clips_scored.json           ← Step 5 (scorer — ranked clips)
│
├── output/
│   ├── clip_001.mp4                ← Step 6 (cutter)
│   ├── clip_002.mp4                ← Step 6
│   ├── clip_001_captioned.mp4      ← Step 7 (captioner)
│   └── final/
│       ├── short_001.mp4           ← Step 8 (enhancer)
│       └── short_002.mp4           ← Step 8
│
└── logs/
    └── pipeline.log                ← All steps log here
```

---

## Resume Mechanism

`project.json` tracks which steps are done:

```json
{
  "name": "How AI Will Replace Developers",
  "youtube_url": "https://...",
  "created": "2026-06-26T17:00:00",
  "status": "in_progress",
  "steps": {
    "download":    "completed",
    "transcribe":  "completed",
    "crawl_trends": "completed",
    "analyze":     "completed",
    "score":       "running",
    "cut":         "pending",
    "caption":     "pending",
    "enhance":     "pending"
  },
  "language": "English",
  "duration_seconds": 5660,
  "clips_found": 12,
  "version": "1.0"
}
```

**Pipeline logic:**
```python
for step in STEPS:
    if project.steps[step.name] == "completed":
        log(f"Skipping {step.name} — already done")
        continue
    project.steps[step.name] = "running"
    save_project(project)
    step.run(project_dir)
    project.steps[step.name] = "completed"
    save_project(project)
```

---

## Analyzer Plugin Interface

Every analyzer must implement this interface:

```python
# analyzers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class AnalyzerResult:
    analyzer: str           # e.g. "hook"
    score: float            # 0-100
    confidence: float       # 0.0-1.0
    reason: str             # why this score
    timestamps: list        # [{"start": 74, "end": 92}]

class BaseAnalyzer(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def analyze(self, project_dir: str) -> list[AnalyzerResult]:
        """Read whatever files you need from project_dir, return results."""
        pass
```

**To add a new analyzer:** Create a file in `analyzers/`, implement `BaseAnalyzer`, register it in `analyzers/__init__.py`.

---

## LLM Interface (Ollama)

Single wrapper so we can swap models easily:

```python
# utils/llm.py

import ollama

DEFAULT_MODEL = "llama3.1:8b"

def ask(prompt: str, model: str = DEFAULT_MODEL) -> str:
    response = ollama.chat(model=model, messages=[
        {"role": "user", "content": prompt}
    ])
    return response["message"]["content"]

def ask_json(prompt: str, model: str = DEFAULT_MODEL) -> dict:
    """Ask LLM and parse JSON response."""
    raw = ask(prompt + "\n\nRespond ONLY with valid JSON.", model)
    # strip markdown code fences if present
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    return json.loads(raw)
```

---

## Development Order (Step by Step)

### Phase 1: v0.1 — Download Pipeline
**Goal:** `python main.py --url <URL>` → creates project folder with video + metadata

**Files to create:**
1. `config.py` — workspace path, model names
2. `models/project.py` — Project dataclass
3. `utils/file_utils.py` — JSON helpers
4. `modules/downloader.py` — yt-dlp wrapper
5. `pipeline.py` — orchestrator (just step 1 for now)
6. `main.py` — argparse CLI

**Test:** Run with any YouTube URL, check that `workspace/projects/<name>/downloads/` has video.mp4 + metadata.json

---

### Phase 2: v0.2 — Transcription
**Goal:** Automatically transcribe downloaded video

**Files to create:**
1. `modules/transcriber.py` — mlx-whisper wrapper
2. `models/transcript.py` — Segment dataclass

**Depends on:** v0.1 (needs video.mp4)

**Test:** Check `analysis/transcript.json` has word-level timestamps

**⚠️ Keep in mind:**
- `mlx-whisper` needs audio, not video — extract audio first with ffmpeg
- Use `whisper.large-v3` model for best accuracy
- Output format must include word-level timestamps (needed for captions later)

---

### Phase 3: v0.3 — LLM Clip Analysis
**Goal:** LLM reads transcript + metadata → suggests clip timestamps

**Files to create:**
1. `utils/llm.py` — Ollama wrapper
2. `modules/analyzer.py` — Prompt engineering + clip extraction

**Depends on:** v0.2 (needs transcript.json) + v0.1 (needs metadata.json)

**⚠️ Keep in mind:**
- Transcripts can be VERY long — chunk them if > model context window
- Prompt must ask for JSON output with `start_seconds`, `end_seconds`, `reason`, `score`
- Validate LLM output — it may hallucinate timestamps outside video duration
- Clips should be 15-60 seconds for Shorts format

---

### Phase 4: v0.4 — FFmpeg Clip Cutting
**Goal:** Cut source video into individual clips

**Files to create:**
1. `modules/cutter.py` — ffmpeg-python wrapper
2. `models/clip.py` — Clip dataclass

**Depends on:** v0.3 (needs clips_raw.json) + v0.1 (needs video.mp4)

**⚠️ Keep in mind:**
- Use `-c copy` for fast cutting (no re-encoding) when possible
- If exact frame accuracy needed, use `-c:v libx264` (slower but precise)
- Re-encode to 9:16 vertical format for Shorts (crop or pad with blur)
- Add 1-2 second buffer before/after timestamps for natural cuts

---

### Phase 5: v0.5 — Project Structure + Resume
**Goal:** Full project.json lifecycle, resume from any step

**Files to modify:**
1. `pipeline.py` — add resume logic
2. `models/project.py` — add steps tracking
3. `main.py` — add `--resume` flag, `--list-projects` command

**Depends on:** v0.1-v0.4 (all steps must support skip-if-done)

---

### Phase 6: v0.6 — Web Crawling for Trends
**Goal:** Crawl Google → scrape Reddit/X/news for trending topics related to video

**Files to create:**
1. `modules/trend_crawler.py` — Google search + scrape + LLM summarize

**Depends on:** v0.1 (needs metadata.json keywords)

**⚠️ Keep in mind:**
- `googlesearch-python` can get rate-limited — add delays between requests
- Scrape with `requests` + `BeautifulSoup` — don't need Playwright unless JS-rendered
- Reddit: scrape `old.reddit.com` (no JS needed)
- X.com: may need `nitter` instances or Playwright
- LLM summarizes scraped content into structured `trends.json`
- This step is **independent** of steps 2-5 — can run in parallel with transcription

---

### Phase 7: v0.7 — Caption Burn-in
**Goal:** Burn SRT subtitles onto clip videos

**Files to create:**
1. `modules/captioner.py` — extract relevant transcript segment, generate SRT, burn with ffmpeg

**Depends on:** v0.4 (needs cut clips) + v0.2 (needs transcript)

**⚠️ Keep in mind:**
- Extract only the transcript segment matching each clip's timestamps
- Use ffmpeg `subtitles` filter for SRT burn-in
- Style: white text, black outline, bottom-center, large font

---

### Phase 8: v0.8 — Scene Detection Analyzer
**Goal:** First plug-in analyzer — detect scene changes

**Files to create:**
1. `analyzers/base.py` — abstract base class
2. `analyzers/scene_analyzer.py` — PySceneDetect wrapper
3. `modules/scorer.py` — score fusion engine

**Depends on:** v0.1 (needs video.mp4)

---

### Phase 9: v1.0 — Web UI
**Goal:** FastAPI dashboard showing project status, progress, file browser

**Files to create:**
1. `web/app.py` — FastAPI app
2. `web/templates/` — Jinja2 HTML templates
3. `web/static/` — minimal CSS/JS

**Depends on:** v0.5 (needs project.json structure)

---

## Important Rules for All Development

1. **Every module must be independently testable**
   ```bash
   python -m modules.downloader --url "https://..." --output ./test_project/
   ```

2. **Never hardcode paths** — always derive from `project_dir`

3. **Log everything** — use Python `logging` module, write to `logs/pipeline.log`

4. **Fail gracefully** — if a step fails, mark it as `"failed"` in project.json, don't corrupt other steps

5. **LLM outputs are unreliable** — always validate JSON, clamp timestamps to video duration, handle parse errors

6. **Keep the analyzer interface stable** — `BaseAnalyzer.analyze(project_dir) → list[AnalyzerResult]` should not change

7. **9:16 vertical format** — all output clips must be vertical (1080x1920) for Shorts/TikTok/Reels

---

## How to Resume Work

1. Read this file (`DEVELOPMENT.md`)
2. Check `project.md` for full vision context
3. Look at which phases are built (check if files exist in `auto_shorts/`)
4. Pick up the next phase
5. Follow the "Files to create" list for that phase
6. Run tests with a real YouTube URL

---

## Quick Commands Reference

```bash
# Run pipeline
python main.py --url "https://youtube.com/watch?v=xxx"

# Resume a project
python main.py --resume "project-name"

# List all projects
python main.py --list

# Run a single module for testing
python -m modules.downloader --url "https://..." --output ./test/

# Start web UI (v1.0+)
python -m web.app

# Check Ollama is running
ollama list
ollama run llama3.1:8b "Hello"
```
