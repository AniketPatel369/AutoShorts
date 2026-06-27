#!/usr/bin/env python3
"""
Auto Shorts — CLI Entry Point

Usage:
    python main.py --url <youtube_url>           # Process a new video
    python main.py --resume <project_name>       # Resume a project
    python main.py --list                        # List all projects
"""
import argparse
import logging
import sys
from pathlib import Path

from auto_shorts.config import LOG_FORMAT, LOG_DATE_FORMAT, PROJECTS_DIR, ensure_workspace
from auto_shorts.pipeline import create_project, run_pipeline, resume_project, list_projects
from auto_shorts.utils.file_utils import sanitize_filename
from auto_shorts.utils.time_utils import format_duration


def setup_logging(verbose: bool = False):
    """Configure logging for CLI output."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
    # Quiet noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def cmd_process(args):
    """Process a new YouTube video."""
    project, project_dir = create_project(args.url, name=args.name)
    print(f"\n📁 Project created: {project_dir.name}")
    print(f"🔗 URL: {args.url}\n")

    stop_after = args.stop_after if hasattr(args, "stop_after") else None
    run_pipeline(project, project_dir, stop_after=stop_after)

    print(f"\n✅ Done! Project: {project_dir}")
    _print_project_status(project)


def cmd_resume(args):
    """Resume an existing project."""
    # Find the project directory
    project_dir = _find_project(args.project)
    if not project_dir:
        print(f"❌ Project not found: '{args.project}'")
        print("   Use --list to see available projects")
        sys.exit(1)

    project, project_dir = resume_project(project_dir)
    
    # Handle --reanalyze flag
    if hasattr(args, 'reanalyze') and args.reanalyze:
        print("🔄 Re-analyzing: resetting analyze/score/cut steps...")
        # Delete old clips files
        analysis_dir = project_dir / "analysis"
        for f in ["clips_raw.json", "clips_scored.json", "debug_llm_output.json"]:
            path = analysis_dir / f
            if path.exists():
                path.unlink()
        # Delete old output clips
        output_dir = project_dir / "output"
        if output_dir.exists():
            for clip_file in output_dir.glob("clip_*.mp4"):
                clip_file.unlink()
        # Reset step statuses
        for step in ["analyze", "score", "cut"]:
            project.steps[step] = "pending"
        project.save(project_dir)
    
    print(f"\n📁 Resuming: {project.name}")

    stop_after = args.stop_after if hasattr(args, "stop_after") else None
    run_pipeline(project, project_dir, stop_after=stop_after)

    print(f"\n✅ Done! Project: {project_dir}")
    _print_project_status(project)


def cmd_list(args):
    """List all projects."""
    projects = list_projects()
    if not projects:
        print("\n📭 No projects found. Use --url to create one.")
        return

    print(f"\n📋 Projects ({len(projects)}):\n")
    for p in projects:
        status_icon = {
            "completed": "🟢",
            "in_progress": "🟡",
            "failed": "🔴",
            "created": "⚪",
        }.get(p["status"], "⚫")

        completed_steps = sum(1 for s in p["steps"].values() if s == "completed")
        total_steps = len(p["steps"])

        print(f"  {status_icon} {p['name']}")
        print(f"     Status: {p['status']}  |  Steps: {completed_steps}/{total_steps}")
        print(f"     Dir: {Path(p['dir']).name}")
        print()


def cmd_status(args):
    """Show detailed status of a project."""
    project_dir = _find_project(args.project)
    if not project_dir:
        print(f"❌ Project not found: '{args.project}'")
        sys.exit(1)

    from auto_shorts.models.project import Project
    project = Project.load(project_dir)
    _print_project_status(project)


def cmd_ui(args):
    """Start the FastAPI Web UI."""
    import uvicorn
    print(f"\n🚀 Starting Auto Shorts Web UI at http://{args.host}:{args.port}")
    uvicorn.run("auto_shorts.web_ui:app", host=args.host, port=args.port, reload=True)


def _find_project(name: str) -> Path | None:
    """Find a project directory by name or partial match."""
    ensure_workspace()
    
    # Try exact directory match first
    exact = PROJECTS_DIR / name
    if exact.is_dir() and (exact / "project.json").exists():
        return exact
        
    sanitized = sanitize_filename(name)
    exact_sanitized = PROJECTS_DIR / sanitized
    if exact_sanitized.is_dir() and (exact_sanitized / "project.json").exists():
        return exact_sanitized

    # Try partial match on directory name or project title
    name_lower = name.lower()
    for path in PROJECTS_DIR.iterdir():
        if path.is_dir() and (path / "project.json").exists():
            if sanitized in path.name:
                return path
            
            # Check title inside project.json
            try:
                from auto_shorts.models.project import Project
                project = Project.load(path)
                if name_lower in project.name.lower():
                    return path
            except Exception:
                pass

    return None


def _print_project_status(project):
    """Print a formatted project status."""
    print(f"\n{'─' * 50}")
    print(f"  📁 {project.name}")
    print(f"  Status: {project.status}")
    if project.duration_seconds:
        print(f"  Duration: {format_duration(project.duration_seconds)}")
    print(f"{'─' * 50}")
    for step, status in project.steps.items():
        icon = {"completed": "✓", "running": "⏳", "failed": "✗", "pending": "○"}.get(status, "?")
        print(f"  {icon} {step}: {status}")
    print(f"{'─' * 50}\n")


def main():
    parser = argparse.ArgumentParser(
        prog="auto-shorts",
        description="Auto Shorts — AI Content Intelligence Engine",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── process ──────────────────────────────────────────
    p_process = subparsers.add_parser("process", help="Process a new YouTube video")
    p_process.add_argument("--url", required=True, help="YouTube video URL")
    p_process.add_argument("--name", default=None, help="Custom project name")
    p_process.add_argument("--stop-after", default=None, help="Stop after this step (e.g., 'download')")
    p_process.set_defaults(func=cmd_process)

    # ── resume ───────────────────────────────────────────
    p_resume = subparsers.add_parser("resume", help="Resume an existing project")
    p_resume.add_argument("project", help="Project name or directory name")
    p_resume.add_argument("--stop-after", default=None, help="Stop after this step")
    p_resume.add_argument("--reanalyze", action="store_true", help="Re-run analyze/score/cut steps (deletes old clips)")
    p_resume.set_defaults(func=cmd_resume)

    # ── list ─────────────────────────────────────────────
    p_list = subparsers.add_parser("list", help="List all projects")
    p_list.set_defaults(func=cmd_list)

    # ── status ───────────────────────────────────────────
    p_status = subparsers.add_parser("status", help="Show project status")
    p_status.add_argument("project", help="Project name or directory name")
    p_status.set_defaults(func=cmd_status)

    # ── ui ───────────────────────────────────────────────
    p_ui = subparsers.add_parser("ui", help="Start the local Web UI dashboard")
    p_ui.add_argument("--host", default="127.0.0.1", help="Bind host")
    p_ui.add_argument("--port", type=int, default=8000, help="Bind port")
    p_ui.set_defaults(func=cmd_ui)


    # Parse and dispatch
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
