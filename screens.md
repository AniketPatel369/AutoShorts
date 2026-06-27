# Auto Shorts — GUI Screen Specifications

> **Purpose**: Screen-by-screen spec for Stitch AI to design the web UI.  
> **Tech**: FastAPI backend + HTML/JS frontend (local app, not SaaS).  
> **Theme**: Dark mode, deep navy/charcoal background (#0d0f1a → #141625), purple/blue accents (#7c5cfc, #4f46e5), glowing effects. Inspired by OpenShorts UI.  
> **Font**: Inter or Outfit (Google Fonts)  
> **Layout**: Fixed left sidebar (200px) + scrollable main content area

---

## Global Elements

### Left Sidebar (persistent on all screens)
- **Logo**: "Auto Shorts" with a small lightning bolt or film reel icon, purple gradient
- **Nav Items** (icon + label, vertical stack):
  - 🏠 Dashboard (default active)
  - ➕ New Project
  - 📁 All Projects
  - ⚙️ Settings
- **Bottom of sidebar**: 
  - Storage usage indicator (e.g., "487 GB used")
  - App version ("v0.1.0")
- **Style**: Slightly lighter dark bg than main area (#161830), active item has left purple border + subtle purple bg highlight

### Top Bar (persistent)
- Right side: Nothing for now (local app, no auth needed)
- Can optionally show current project name as breadcrumb when inside a project

---

## Screen 1: Dashboard (Home)

**Route**: `/`  
**Purpose**: Landing screen. Quick way to paste a YouTube URL and start processing, plus see recent projects.

### Layout (top to bottom):

#### Hero Section (centered, upper 40% of viewport)
- **Headline**: "Create Viral Shorts" — large bold white text (36-42px)
- **Subtext**: "Drop your YouTube URL below to automatically find and generate viral short-form clips using AI." — muted gray text (16px)
- **Input Area** (centered card with subtle glass border):
  - YouTube URL input field — dark input with subtle purple border glow on focus
  - Placeholder text: "https://www.youtube.com/watch?v=..."
  - **"Generate Clips" button** — full-width purple gradient button (#7c5cfc → #4f46e5), bold white text
  - Optional: small text below "Supports any YouTube video up to 4 hours"
- **Platform icons row** below button: small YouTube + Instagram + TikTok icons in muted gray (decorative only)

#### Recent Projects Section (below hero, full width)
- **Section header**: "Recent Projects" with a "View All →" link on the right
- **Project cards** in a horizontal scroll row (3-4 visible):
  - Each card: 
    - Video thumbnail (from YouTube metadata) at top
    - Project title (truncated to 2 lines)
    - Status pill badge: 🟢 Completed / 🟡 Processing / 🔴 Failed
    - Stats row: "5 clips · 23m 45s · Score: 91"
    - Created date in muted text
  - Card style: dark card bg (#1a1d2e), rounded 12px, subtle border, hover lifts with purple glow shadow

---

## Screen 2: Processing View (Pipeline Progress)

**Route**: `/project/{project-name}/processing`  
**Purpose**: Shows real-time pipeline progress after user submits a URL. This is the screen users stare at while the AI works.

### Layout:

#### Top Section
- **Project Title**: Large text showing the video title (fetched after download)
- **YouTube URL**: Small muted link below the title
- **Overall Progress Bar**: Full-width thin bar at top, purple gradient fill, shows % complete (e.g., "4/7 steps complete")

#### Pipeline Steps (vertical timeline, centered)
A vertical list of all 7 pipeline steps, displayed as a visual timeline with connecting lines:

Each step is a row:
```
[Status Icon]  Step Name                    [Duration]
               Brief description             
```

Steps in order:
1. **Download** — "Downloading video, metadata, and captions"
2. **Transcribe** — "Generating word-level transcript"
3. **Trend Analysis** — "Extracting keywords and trends from metadata"
4. **AI Analysis** — "Finding the most viral-worthy clip candidates"
5. **Score** — "Scoring and ranking clips"
6. **Cut** — "Cutting video into vertical 9:16 clips"
7. **Caption** — "Burning animated captions onto clips"

Status icons per step:
- ○ Pending (gray circle outline)
- ⏳ Running (animated purple spinner)
- ✓ Completed (green filled circle with checkmark)
- ✗ Failed (red circle with X)

**Currently running step** should be highlighted — expanded card showing:
- Step name in larger text
- Animated progress indicator (pulse or spinner)
- Live log preview: last 3-5 log lines in a small monospace terminal-style box
- Elapsed time counter

#### Bottom Section
- "Cancel" button (muted/outline style)
- If all steps complete: big "View Clips →" button (purple gradient) appears with a confetti/celebration micro-animation

---

## Screen 3: All Projects

**Route**: `/projects`  
**Purpose**: Browse and manage all processed videos. Gallery/list view.

### Layout:

#### Top Bar
- **Page Title**: "All Projects" with total count badge (e.g., "(12)")
- **Search Bar**: Search by project name/title — dark input, right-aligned
- **Filter Chips**: "All" | "Completed" | "Processing" | "Failed" — horizontal toggle pills
- **View Toggle**: Grid view (□□) / List view (≡) icons

#### Grid View (default)
- Cards in a responsive grid (3-4 columns):
  - **Video thumbnail** (16:9 aspect ratio, from YouTube)
  - **Title** (bold, white, 2-line max)
  - **Status badge**: colored pill (green/yellow/red)
  - **Stats line**: "5 clips · 23m · Sep 15"
  - **Action buttons row**: 
    - "▶ Open" (primary, small purple button)
    - "🗑 Delete" (subtle ghost button, appears on hover only)
  - Hover effect: card lifts slightly, purple border glow

#### List View (alternate)
- Table-style rows:
  - Thumbnail (small square) | Title | Status | Clips Count | Duration | Created | Actions

#### Empty State (when no projects)
- Centered illustration or icon (empty folder)
- "No projects yet"
- "Create your first project" → links to Dashboard

---

## Screen 4: Project Detail — Clips Gallery

**Route**: `/project/{project-name}`  
**Purpose**: After processing, show all generated clips for a project. The main "results" screen.

### Layout:

#### Project Header (compact)
- **Video Title** (large bold)
- **Meta row**: Channel name · Duration (1h 23m) · Upload date · Language
- **YouTube URL**: small clickable link
- **Status badge**: 🟢 Completed
- **Pipeline summary**: "7/7 steps · 5 clips generated · Processed on Jun 27, 2026"
- **Action buttons** (right-aligned):
  - "🔄 Re-analyze" (outline button)
  - "📂 Open Folder" (outline button — opens project dir in Finder)
  - "⬇ Download All" (purple button)

#### Clips Grid (main content)
- **Section header**: "Generated Clips (5)" with sort dropdown ("Sort by: Score ↓" / "Duration" / "Timeline Order")
- **Clip cards** in a 2-3 column grid:

Each clip card:
```
┌─────────────────────────────────────┐
│  [9:16 VIDEO THUMBNAIL/PREVIEW]     │
│  ▶ play button overlay in center    │
│                                     │
│  Score Badge (top-right): "92"      │
│  Duration Badge (bottom-left): "32s"│
├─────────────────────────────────────┤
│  Clip #1                            │
│  Category: 🔥 Hot Take              │
│                                     │
│  "Speaker drops a controversial     │
│   opinion about AI replacing..."    │
│                                     │
│  Hook: "What most people don't      │
│  realize about AI is..."            │
│                                     │
│  [▶ Preview]  [⬇ Download]         │
└─────────────────────────────────────┘
```

- **Score badge**: circular badge, color-coded:
  - 90-100: Gold/yellow glow ⭐
  - 70-89: Purple
  - 50-69: Blue
  - Below 50: Gray
- **Category pill**: colored tag matching category (punchline, roast, hot_take, quotable, emotional, motivational, absurd, audience_eruption)
- **Hover**: card border glows, "Preview" button becomes prominent

---

## Screen 5: Clip Detail / Preview

**Route**: `/project/{project-name}/clip/{clip-id}`  
**Purpose**: Full preview of a single clip with all metadata. User can watch, download, and see why the AI chose it.

### Layout (two-column split):

#### Left Column (45% width) — Video Player
- **9:16 vertical video player** (the actual generated clip)
- Standard HTML5 video controls (play/pause, seek, volume, fullscreen)
- **Clip number badge**: "CLIP 3" in top-left corner of player
- Below player:
  - Timeline scrubber showing clip position within the full source video
  - "Original timestamp: 14:32 → 15:04" in muted text

#### Right Column (55% width) — Clip Info

**Score Section**:
- Large circular score display: "92" with animated ring border (color matches score tier)
- Score breakdown (if score fusion is implemented later):
  - Hook Strength: ████████░░ 82
  - Entertainment: █████████░ 95
  - Shareability:  █████████░ 91
  - Clarity:       ████████░░ 88

**Clip Details Card**:
- **Category**: "🔥 Hot Take" (colored pill)
- **Duration**: "32 seconds"
- **Tags**: #shorts #viral (small gray pills)

**AI Analysis Card** (dark card with subtle border):
- **Hook**: "What most people don't realize about AI is..." (quoted text, slightly highlighted)
- **Why it's viral**: "Speaker confidently delivers a controversial opinion about AI replacing developers, followed by immediate audience reaction. Strong curiosity gap in the opening line." (the `reason` field from analyzer)

**Action Buttons** (2x2 grid of large buttons, matching the OpenShorts inspiration):
```
┌──────────────┐  ┌──────────────┐
│  ⬇ Download  │  │  📂 Open in  │
│              │  │   Finder     │
├──────────────┤  ├──────────────┤
│  🔄 Re-cut   │  │  🗑 Delete   │
│              │  │   Clip       │
└──────────────┘  └──────────────┘
```
- Download: Purple gradient (primary)
- Open in Finder: Blue outline
- Re-cut: Teal/cyan outline
- Delete Clip: Red outline (with confirmation modal)

**Navigation**:
- "← Previous Clip" / "Next Clip →" arrows at bottom
- "Back to Clips Gallery" link

---

## Screen 6: Settings

**Route**: `/settings`  
**Purpose**: Configure AI models, paths, video output settings.

### Layout (single column, sectioned cards):

#### Section 1: AI Model
- **LLM Model**: Dropdown or text field showing current model (`mlx-community/Qwen2.5-14B-Instruct-4bit`)
- **Whisper Model**: Dropdown (`large-v3`)
- Model status indicator: "✅ Downloaded" or "⬇ Download needed"
- "Models Directory" path display with "Open" button

#### Section 2: Video Output
- **Output Resolution**: 1080 × 1920 (display only, or dropdown for future presets)
- **Min Clip Duration**: Number input (default 15s)
- **Max Clip Duration**: Number input (default 60s)
- **Clip Buffer**: Number input (default 1.5s)

#### Section 3: Analysis
- **Chunk Window**: Number input (default 180s / 3 minutes)
- **Chunk Overlap**: Number input (default 90s)
- **Max Clips per Video**: Number input (default 8)

#### Section 4: Workspace
- **Workspace Path**: Display with "Open" and "Change" buttons
- **Projects Directory**: path display
- **Storage Used**: progress bar with GB count
- **"Clear Cache" button** (outline red)

#### Section 5: About
- Version: v0.1.0
- GitHub link
- Built with: Python, MLX, FFmpeg, MediaPipe

---

## Screen 7: Empty/Error States

### No Projects Yet (on All Projects page)
- Large muted icon (empty folder or film reel)
- "No projects yet"
- "Create your first project" → links to Dashboard

### Processing Failed
- Red alert banner at top of processing view
- "Step 'analyze' failed: LLM did not return valid JSON"
- "Retry" button (purple) + "View Logs" button (outline)
- Terminal-style log viewer expandable section

### Video Not Found
- "This video is unavailable or restricted"
- Suggestion: "Try a different YouTube URL"

---

## Color Palette Reference

| Token | Hex | Usage |
|-------|-----|-------|
| bg-primary | `#0d0f1a` | Main background |
| bg-secondary | `#141625` | Cards, elevated surfaces |
| bg-sidebar | `#161830` | Sidebar background |
| accent-purple | `#7c5cfc` | Primary buttons, active states, accents |
| accent-blue | `#4f46e5` | Secondary accent, gradients |
| accent-green | `#22c55e` | Success states, completed |
| accent-red | `#ef4444` | Error states, failed, delete |
| accent-yellow | `#eab308` | Warning, high scores |
| accent-teal | `#14b8a6` | Info, re-analyze buttons |
| text-primary | `#f1f5f9` | Headings, primary text |
| text-secondary | `#94a3b8` | Descriptions, muted text |
| text-muted | `#475569` | Timestamps, labels |
| border | `#1e293b` | Card borders, dividers |
| border-glow | `rgba(124, 92, 252, 0.3)` | Hover glow effects |

---

## Typography

| Element | Font | Weight | Size |
|---------|------|--------|------|
| Page Title | Inter/Outfit | 700 (Bold) | 36-42px |
| Section Header | Inter/Outfit | 600 (Semi-Bold) | 24px |
| Card Title | Inter/Outfit | 600 | 18px |
| Body Text | Inter | 400 (Regular) | 15px |
| Muted/Label | Inter | 400 | 13px |
| Button | Inter | 600 | 15px |
| Badge/Pill | Inter | 600 | 12px |
| Monospace (logs) | JetBrains Mono / Fira Code | 400 | 13px |

---

## Interaction Notes

- **All cards**: 4px border-radius rounded corners (12px for larger cards), subtle box-shadow, hover lifts 2px with purple glow
- **Buttons**: Rounded (8px), 150ms ease transition on hover (brighten + slight scale)
- **Page transitions**: Subtle fade-in (200ms)
- **Loading states**: Purple skeleton placeholders (shimmer animation) for cards loading
- **Modals**: Centered overlay with dark backdrop blur, used for delete confirmations
- **Toasts**: Bottom-right corner, auto-dismiss after 4s, used for success/error notifications ("✅ Clip downloaded", "❌ Processing failed")
