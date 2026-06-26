# Auto Shorts — AI Content Intelligence Engine

> A **CLI-first** Python pipeline that automatically converts long-form YouTube videos into optimized, trend-aware short-form content (YouTube Shorts, TikTok, Reels). Runs locally with a lightweight web UI for status monitoring.

**Status:** Planning / Pre-Development  
**Target Platform:** macOS (MacBook Pro M1 Pro, 16GB)  
**Type:** CLI pipeline + lightweight local web UI (status/progress only)  
**Language:** Python  
**AI Strategy:** Open-source models only (no paid APIs)  
**Created:** 2026-06-26  
**Source Chat:** [ChatGPT – Video Trend Analyzer](./chatgpt-20260626-Video%20Trend%20Analyzer.html)

---

## Vision

Not just a "clip cutter" — this is an **AI Content Intelligence Engine** and a **mini IDE for content creators**. The system goes beyond transcript-only analysis by combining transcript understanding, live internet trend analysis, virality scoring, visual scene detection, and automatic editing to produce much stronger short-form content than existing tools.

> **"Understand why humans watch videos."**  
> The AI becomes an editor, not just a clip cutter.

---

## Complete Pipeline

```
YouTube URL
     │
     ▼
┌────────────────────┐
│ Metadata Extractor │
│ yt-dlp             │
└────────────────────┘
     │
 title, description,
 hashtags, upload date,
 category, channel
     │
     ▼
 Save metadata.json
     │
     ▼
 Download Video (.mp4)
     │
     ▼
 Download Captions
 (or Whisper if missing)
     │
     ▼
 transcript.srt
     │
     ▼
 Internet Trend Agent
     │
 searches web using title,
 keywords, hashtags,
 current trends
     │
     ▼
 trends.json
     │
     ▼
 AI Highlight Analyzer
     │
 Uses:
 • transcript
 • metadata
 • trends
 • emotional moments
 • hook detection
     │
     ▼
 shorts-list.json
     │
     ▼
 Video Cutter (FFmpeg)
     │
     ▼
 Individual clips
     │
     ▼
 Caption Generator
     │
 Word-by-word subtitles
     │
     ▼
 Burn subtitles on video
     │
     ▼
 Add progress bar
 Zoom effects
 Emojis
 B-roll
     │
     ▼
 output/
```

---

## Processing Steps

### Step 1 — Input & Download
- User pastes a YouTube URL
- `yt-dlp` downloads: `video.mp4`, `metadata.json`, `captions.en.vtt`
- If captions unavailable → **Whisper** generates `transcript.srt`

### Step 2 — Metadata Analysis
- Extract keywords from title, description, tags
- Save to `keywords.json`

### Step 3 — Trend Search via Web Crawling (Differentiator)
- **Crawl & scrape** the web using extracted keywords
- Google search for keywords → scrape top-ranked results from:
  - Reddit threads, X.com (Twitter) posts, LinkedIn articles, News sites, YouTube search results, GitHub Trending, Blog posts, Forums
- Use `requests` + `BeautifulSoup` / `playwright` for scraping
- Use `googlesearch-python` or `SerpAPI-free` alternatives for Google search
- Extract trending topics, sentiment, related keywords from scraped content
- LLM summarizes crawled data into structured trends
- Save results to `trends.json`

### Step 4 — Transcript Understanding
- Use an **LLM** (not simple keyword search) to analyze transcript + trends
- Prompt the LLM to find sections with: hooks, surprising facts, emotional statements, controversy, statistics, tips, viral moments
- Return timestamped segments with scores

### Step 5 — Generate Shorts List
- Produce `shorts-list.json` with `{start, end, score}` for each clip candidate

### Step 6 — Cut Video
- **FFmpeg** cuts the source video into individual clips (`clip1.mp4`, `clip2.mp4`, etc.)

### Step 7 — Generate Better Captions
- Instead of original subtitles, generate **word-by-word animated captions** (TikTok-style)
- Example: "This changes EVERYTHING" → animated word-by-word overlay

### Step 8 — Enhance
- ✓ Zoom speaker
- ✓ Highlight words
- ✓ Emoji overlays
- ✓ Progress bar
- ✓ Sound effects
- ✓ Punch-in animation

---

## AI Scoring System

### Multi-Signal Scoring
Each segment is scored using multiple signals:

| Signal                    | Range |
|---------------------------|-------|
| Virality score            | 0-100 |
| Curiosity score           | 0-100 |
| Emotion score             | 0-100 |
| Shock factor              | 0-100 |
| Trend relevance           | 0-100 |
| Question asked            | 0-100 |
| Answer given              | 0-100 |
| Audience retention pred.  | 0-100 |
| Speech speed              | 0-100 |
| Pause detection           | 0-100 |
| Laughter                  | 0-100 |
| Volume spikes             | 0-100 |

### Scoring Formula (per clip)
```
Hook Strength        0-100
Emotion              0-100
Curiosity            0-100
Education            0-100
Entertainment        0-100
Trend Relevance      0-100
Visual Interest      0-100
Story Completeness   0-100
Authority            0-100
Retention Prediction 0-100
─────────────────────────
Overall Viral Score = weighted average (e.g., 91.3)
```

### Clip Card Output
```
🏆 Clip #1
Score: 96.2
Why?
✓ Strong opening hook
✓ Complete story
✓ High emotional payoff
✓ Fast speech pace
✓ Clear visuals
✓ Memorable quote
```

---

## Visual / Video Analysis (Advanced)

Use **computer vision** on video frames to detect:
- Scene changes
- Facial expressions
- Screen changes
- Gestures
- Charts
- Products

These often make excellent clip boundaries that transcript-only analysis misses.

---

## Architecture

### Plug-in Architecture
Each analyzer is independent and follows a standardized interface:

```
Analyzer
│
├── Hook Analyzer
├── Emotion Analyzer
├── Story Analyzer
├── Quote Analyzer
├── Trend Analyzer
├── Visual Analyzer
├── Audio Analyzer
├── Humor Analyzer
├── Education Analyzer
└── Custom Analyzer
```

Each analyzer returns a standardized result:
```json
{
  "analyzer": "hook",
  "score": 92,
  "confidence": 0.94,
  "reason": "Strong curiosity gap in first 4 seconds",
  "timestamps": [
    { "start": 74, "end": 92 }
  ]
}
```

A **Score Fusion Engine** combines all analyzer outputs. Advantages:
- Add new analyzers without touching existing ones
- Disable expensive analyzers when speed matters
- Run analyzers in parallel
- Experiment with different scoring formulas
- Compare different AI models side by side

### Architecture Diagram
```
                    Video
                      │
      ┌───────────────┴───────────────┐
      │                               │
Transcript                    Video Frames
      │                               │
Metadata                     Scene Changes
      │                               │
Audio                        Face Detection
      │                               │
Comments (optional)          Emotion
      │                               │
Internet Trends              OCR (screen text)
      │                               │
      └───────────────┬───────────────┘
                      │
            AI Intelligence Layer
                      │
      ┌───────────────┼───────────────┐
      │               │               │
   Hook AI      Story AI      Education AI
   Emotion AI   Humor AI      Quote AI
   Trend AI     Visual AI     Retention AI
                      │
              Score Fusion Engine
                      │
             Ranked Clip Candidates
                      │
      Auto Editor + Captions + Effects
                      │
                 Final Shorts
```

---

## Project-Based Design

Each YouTube URL is treated as a **Project** (like Premiere Pro, DaVinci Resolve):

### Per-Project Folder Structure
```
project-name/
├── project.json          # Project metadata & status
├── downloads/
│   ├── video.mp4
│   ├── metadata.json
│   ├── captions.srt
│   └── transcript.txt
├── analysis/
│   ├── v1/              # Versioned analysis runs
│   ├── v2/
│   ├── trends.json
│   ├── keywords.json
│   ├── shorts-list.json
│   └── embeddings.db
├── output/
│   ├── short1.mp4
│   ├── short2.mp4
│   └── short3.mp4
├── review/
│   ├── approved/
│   ├── rejected/
│   └── edited/
├── cache/
└── logs/
```

### `project.json` Example
```json
{
  "name": "How AI Will Replace Developers",
  "youtube_url": "...",
  "status": "Completed",
  "created": "2026-06-26",
  "language": "English",
  "duration": "01:34:20",
  "clips": 12,
  "version": "1.0"
}
```

### Key Project Features
- **Resume Processing** — If laptop shuts down, reopen the project and continue from where it stopped (e.g., `✓ Downloaded, ✓ Metadata, ✓ Transcript, ✓ Trends, ✓ Clip Analysis, ⏳ Rendering`)
- **Version History** — Re-run analysis with improved AI → `analysis/v1/`, `analysis/v2/`, `analysis/v3/` — nothing gets overwritten
- **Human Review** — `review/approved/`, `review/rejected/`, `review/edited/` — AI learns user preferences over time
- **Self-contained** — Each project is a folder, portable, easy to back up, doesn't require a server

---

## Workspace Structure

```
Workspace/
├── Projects/
│   ├── AI Agents Podcast/
│   ├── Lex Fridman #482/
│   ├── Joe Rogan Elon Musk/
│   ├── MrBeast New Video/
│   ├── Java Tutorial/
│   └── Startup Podcast/
├── Assets/
├── Models/
├── Templates/
├── Presets/
├── Fonts/
├── Music/
├── Effects/
├── Plugins/
├── Settings/
└── Logs/
```

### Dashboard (on app launch)
```
+---------------------------------------------------------+
          AI Content Studio
-----------------------------------------------------------
📁 AI Agents Podcast     | Status: Completed  | Clips: 18
📁 Lex Fridman #482      | Status: Rendering  | Progress: 72%
📁 Java Spring Boot      | Status: Waiting for Analysis
📁 MrBeast Latest        | Status: Downloading
-----------------------------------------------------------
Total Projects : 248     Generated Shorts : 1893
Videos : 248             Exported : 1702
Pending : 17             Storage : 487 GB
-----------------------------------------------------------
[ New Project ]
```

### Multi-Video / Simultaneous Processing
- Projects run in parallel (one downloading, another analyzing, another rendering)
- Background workers handle long-running tasks

---

## Audience-Aware Clipping

The system can produce different clips from the same video depending on the target audience:
- Software developers
- Business audience
- Finance audience
- Fitness audience
- Students
- Gamers

---

## Future AI Learning

### Personalization
As the user approves/rejects clips across projects, the AI learns preferences:
```
You always approve:
- 20-35 second clips
- Fast speakers
- Educational clips
- Hooks with numbers
- Not motivational content
```

### Custom Model Training
After processing thousands of videos, build a proprietary dataset:
- Topic, Duration, Hook type, Ending type, Emotion, Speaking speed, WPM, Scene changes, View count, Likes, Comments, Shares
- Train a model that predicts: **"This 28-second clip has an 87% chance of outperforming the average clip."**

### Semantic Search Across Projects
```
"Java"       → 27 projects found
"AI Agents"  → 93 projects found
"Best clips above score 90" → filtered results
```

---

## Tech Stack

| Layer     | Technology                                          |
|-----------|-----------------------------------------------------|
| **Core**  | Python CLI pipeline                                 |
| **AI/LLM**| Ollama (`llama3`, `mistral`), MLX models (Apple Silicon optimized) |
| **STT**   | `mlx-whisper` or `faster-whisper` (open-source, local) |
| **NLP**   | Sentence Transformers (local embeddings)             |
| **Video** | FFmpeg, MoviePy (optional), OpenCV                  |
| **Scraping** | `requests` + `BeautifulSoup`, `playwright`, `googlesearch-python` |
| **Storage** | SQLite, JSON (file-based per project)             |
| **Queue** | `asyncio` + `concurrent.futures` (no Redis/Celery needed) |
| **Web UI**| FastAPI + lightweight HTML/JS (status dashboard, file browser, progress) |

---

## Development Phases

| Phase | Description                                              | Priority |
|-------|----------------------------------------------------------|----------|
| v0.1  | CLI: `yt-dlp` download + metadata + captions             | 🔴 High |
| v0.2  | Whisper transcript generation (`mlx-whisper`)             | 🔴 High |
| v0.3  | LLM clip selection via Ollama (local, open-source)        | 🔴 High |
| v0.4  | FFmpeg auto-cut clips                                     | 🔴 High |
| v0.5  | Project folder structure + `project.json` + resume        | 🔴 High |
| v0.6  | Web crawling trend search (Google → Reddit/X scraping)    | 🟡 Med  |
| v0.7  | Basic `.srt` caption burn-in on clips                     | 🟡 Med  |
| v0.8  | Scene detection analyzer (`scenedetect`)                  | 🟡 Med  |
| v1.0  | FastAPI web UI — status dashboard, progress, file browser | 🟡 Med  |
| v2.0  | Animated captions, zoom effects, more analyzers           | 🟢 Later |

---

## Product Potential

- **Local Tool:** Fully offline, open-source, no API costs
- **SaaS (future):** Creators paste a YouTube link → receive 10–30 optimized Shorts
- **Plugin Ecosystem:** Community-built analyzers (Finance Analyzer, Gaming Analyzer, etc.)
- **Name Ideas:** ClipMind, ViralMind, ContentIQ, ShortForge, HookAI, ContentPilot, Viralyze, ClipForge, Creator Intelligence, TrendForge

---

## Key Design Decisions

1. **CLI-first** — pipeline works from terminal before any UI
2. **Open-source only** — no paid APIs, all models run locally (Ollama, MLX-Whisper)
3. **Web crawling for trends** — scrape Google results, Reddit, X, etc. (not official APIs)
4. **Project-based** from day one — not a one-off processing job
5. **Plug-in architecture** for analyzers — most important long-term decision
6. **File-based storage** — each project is a self-contained folder
7. **Versioned analysis** — never overwrite, always append
8. **Human-in-the-loop** — approve/reject clips to train AI preferences
9. **Multi-signal scoring** — not just transcript, but audio, video, trends
10. **Resume support** — crash-safe, can continue from any step
11. **Lightweight web UI** — FastAPI status dashboard only, not a full desktop app

---

## Open-Source AI Models

| Purpose | Model | Runtime |
|---------|-------|---------|
| Speech-to-Text | Whisper (large-v3) | `mlx-whisper` or `faster-whisper` |
| LLM (analysis/scoring) | Llama 3 / Mistral / Qwen 2.5 | `ollama` |
| Embeddings (semantic search) | `all-MiniLM-L6-v2` | `sentence-transformers` |
| Scene detection | — | `scenedetect` (PySceneDetect) |

> All models run **locally** on M1 Pro. No API keys, no cloud costs, no data leaving your machine.

---

## Notes

- MacBook Pro M1 Pro (16GB) is well-suited — CPU + Apple Neural Engine/MLX for AI inference, hardware-accelerated video encoding/decoding
- The real value is the **intelligence layer** that decides *what* to clip and *why*
- Build incrementally — CLI pipeline first, web UI later
- Web scraping for trend analysis keeps the tool free and independent of rate-limited APIs
