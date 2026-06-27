---
name: Synthetic Motion
colors:
  surface: '#11131e'
  surface-dim: '#11131e'
  surface-bright: '#373845'
  surface-container-lowest: '#0c0e18'
  surface-container-low: '#191b26'
  surface-container: '#1d1f2b'
  surface-container-high: '#272935'
  surface-container-highest: '#323440'
  on-surface: '#e1e1f2'
  on-surface-variant: '#c9c4d8'
  inverse-surface: '#e1e1f2'
  inverse-on-surface: '#2e303c'
  outline: '#938ea1'
  outline-variant: '#484555'
  surface-tint: '#cabeff'
  primary: '#cabeff'
  on-primary: '#32009a'
  primary-container: '#947dff'
  on-primary-container: '#2b0088'
  inverse-primary: '#613de0'
  secondary: '#c3c0ff'
  on-secondary: '#1d00a5'
  secondary-container: '#3626ce'
  on-secondary-container: '#b3b1ff'
  tertiary: '#4fdbc8'
  on-tertiary: '#003731'
  tertiary-container: '#00a392'
  on-tertiary-container: '#00302a'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e6deff'
  primary-fixed-dim: '#cabeff'
  on-primary-fixed: '#1c0062'
  on-primary-fixed-variant: '#4918c8'
  secondary-fixed: '#e2dfff'
  secondary-fixed-dim: '#c3c0ff'
  on-secondary-fixed: '#0f0069'
  on-secondary-fixed-variant: '#3323cc'
  tertiary-fixed: '#71f8e4'
  tertiary-fixed-dim: '#4fdbc8'
  on-tertiary-fixed: '#00201c'
  on-tertiary-fixed-variant: '#005048'
  background: '#11131e'
  on-background: '#e1e1f2'
  surface-variant: '#323440'
typography:
  display:
    fontFamily: Outfit
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Outfit
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Outfit
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Outfit
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  code:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar_width: 200px
  topbar_height: 64px
  container_max_width: 1440px
  gutter: 24px
  margin_page: 32px
  stack_xs: 4px
  stack_sm: 8px
  stack_md: 16px
  stack_lg: 24px
---

## Brand & Style

This design system is built for a high-performance AI video processing environment. The brand personality is technical, futuristic, and immersive, utilizing a **Glassmorphic** approach layered over a deep **Minimalist** foundation. 

The UI should evoke a sense of "computational power" through the use of dark, expansive surfaces and precise, glowing accents. The target audience consists of content creators and developers who value speed and modern aesthetics. Visual interest is generated through depth—using semi-transparent layers, backdrop blurs, and subtle neon gradients to differentiate active processing states from static interface elements.

## Colors

The palette is anchored in deep cosmic tones. The primary background (#0d0f1a) provides a void-like canvas that allows the vibrant accent colors to "pop" with high perceived luminosity. 

- **Primary & Secondary:** A duo of Purple and Indigo used for primary actions, progress indicators, and AI-driven features.
- **Surface Logic:** Use `bg_sidebar` for the persistent navigation and `bg_secondary` for elevated cards and containers.
- **Accents:** Green, Red, and Yellow are reserved strictly for functional feedback (success, error, warning). Teal is used for secondary data visualizations or "Optimization" status.
- **Borders:** Standard borders use a muted slate, while "Active" or "Processing" states should utilize the `border_glow` to simulate a light-emitting edge.

## Typography

This system employs a dual-font strategy. **Outfit** is used for headings and display text to provide a modern, geometric character that feels premium. **Inter** is used for all functional body text, inputs, and UI labels to ensure maximum legibility at small sizes.

- Use **Display** styles for large hero stats or "Video Export Complete" screens.
- **Label-md** should be used for metadata and sidebar category headers, always in uppercase with slight tracking to enhance the technical feel.
- A monospaced font is introduced for file paths, timestamps, and AI logs.

## Layout & Spacing

The layout follows a strict **Fixed-Fluid** hybrid model. 
- **Sidebar:** A fixed 200px vertical navigation bar on the left. It remains persistent to allow quick switching between processing queues.
- **Topbar:** A fixed 64px horizontal bar for global search, user profile, and system-wide status (e.g., CPU/GPU usage).
- **Main Content:** Content exists within a fluid area that maintains a maximum width of 1440px for readability. 
- **Grid:** Use a 12-column grid for the main canvas. Cards typically span 3 columns (4 per row) for video previews, or 12 columns for the primary timeline editor.
- **Mobile:** On mobile devices, the sidebar collapses into a bottom navigation bar or a hamburger menu, and page margins reduce to 16px.

## Elevation & Depth

Hierarchy is established through **Backdrop Saturation** and **Tonal Layering**.
- **Level 0 (Base):** `#0d0f1a` (Background).
- **Level 1 (Panels):** `#141625` with a subtle 1px border of `#1e293b`.
- **Level 2 (Cards/Modals):** Glassmorphism effect. Use a background of `rgba(30, 41, 59, 0.5)` with a `backdrop-filter: blur(12px)`.
- **Glow Effects:** Interactive elements in an "Active" or "Hover" state should trigger a box-shadow using the primary purple: `0 0 20px rgba(124, 92, 252, 0.15)`.
- **Shadows:** Avoid heavy black shadows. Instead, use soft, colored shadows that match the background's hue to maintain the dark, luminous aesthetic.

## Shapes

The shape language is **Rounded**, striking a balance between approachable software and professional tooling. 
- **Standard Radius:** 0.5rem (8px) for cards, buttons, and input fields.
- **Large Radius:** 1rem (16px) for main content containers and modals.
- **Interactive Elements:** Buttons should use a standard 8px radius. Avoid pill shapes for primary buttons to maintain the structured, technical grid feel; reserve pill shapes only for status "Chips" or "Badges."

## Components

- **Buttons:** 
  - *Primary:* Linear gradient from `#7c5cfc` to `#4f46e5`. On hover, increase the brightness and add a 10px outer purple glow.
  - *Secondary:* Ghost style with a `#1e293b` border. On hover, the border changes to the primary purple.
- **Cards:** 
  - Use `bg_secondary` with a 1px border. 
  - For video thumbnails, apply a slight inner-shadow overlay so text labels remain legible over bright frames.
- **Input Fields:** 
  - Dark fill (`#0d0f1a`) with a 1px border. 
  - On focus, the border transitions to `#7c5cfc` with a soft outer glow.
- **Chips/Badges:** 
  - Small, high-contrast indicators for "AI Rendering," "Uploaded," or "Queued."
  - Use the tertiary teal for "Optimized" status badges.
- **Timeline / Progress Bars:** 
  - The track should be `#1e293b`. 
  - The fill should be a purple-to-blue gradient. For active rendering, add an animated "shimmer" effect to the fill.
- **Sidebar Links:** 
  - Default state: `text_secondary`. 
  - Active state: `text_primary` with a vertical 2px purple line on the far left edge of the sidebar.