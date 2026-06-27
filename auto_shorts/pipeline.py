"""
Auto Shorts — Pipeline Orchestrator

Runs processing steps in order, supports resume from any step.
Each step reads/writes from the project folder on disk.
"""
import logging
from pathlib import Path

from auto_shorts.config import (
    PIPELINE_STEPS,
    STATUS_COMPLETED,
    STATUS_RUNNING,
    STATUS_FAILED,
    STATUS_PENDING,
    PROJECTS_DIR,
    ensure_workspace,
)
from auto_shorts.models.project import Project
from auto_shorts.utils.file_utils import sanitize_filename, create_project_dirs
from auto_shorts.modules.downloader import download
from auto_shorts.modules.transcriber import transcribe
from auto_shorts.modules.trend_crawler import crawl_trends
from auto_shorts.modules.analyzer import analyze
from auto_shorts.modules.cutter import cut
from auto_shorts.modules.captioner import caption

logger = logging.getLogger(__name__)


def create_project(youtube_url: str, name: str | None = None) -> tuple[Project, Path]:
    """
    Create a new project from a YouTube URL.

    Args:
        youtube_url: Full YouTube URL
        name: Optional project name (auto-generated from video title if None)

    Returns:
        Tuple of (Project, project_dir_path)
    """
    ensure_workspace()

    # Create project with a temporary name — will rename after metadata is fetched
    temp_name = name or sanitize_filename(youtube_url.split("=")[-1][:20])
    project = Project(name=temp_name, youtube_url=youtube_url)

    # Create project directory
    project_dir = PROJECTS_DIR / sanitize_filename(temp_name)

    # If directory exists, add a numeric suffix
    if project_dir.exists():
        counter = 2
        while (PROJECTS_DIR / f"{sanitize_filename(temp_name)}-{counter}").exists():
            counter += 1
        project_dir = PROJECTS_DIR / f"{sanitize_filename(temp_name)}-{counter}"

    create_project_dirs(project_dir)
    project.save(project_dir)
    project.project_dir = project_dir

    logger.info(f"Created project '{project.name}' at {project_dir}")
    return project, project_dir


def run_pipeline(project: Project, project_dir: Path, stop_after: str | None = None):
    """
    Run the processing pipeline for a project.

    Steps run in order. Completed steps are skipped (resume support).
    If a step fails, it's marked as failed and pipeline stops.

    Args:
        project: Project instance
        project_dir: Path to project folder
        stop_after: Optional step name to stop after (for partial runs)
    """
    logger.info(f"Starting pipeline for '{project.name}'")
    project.status = "in_progress"
    project.save(project_dir)

    for step_name in PIPELINE_STEPS:
        current_status = project.steps.get(step_name, STATUS_PENDING)

        # Skip completed steps
        if current_status == STATUS_COMPLETED:
            logger.info(f"  ✓ {step_name} — already completed, skipping")
            continue

        # Run the step
        logger.info(f"  ⏳ {step_name} — running...")
        project.update_step(step_name, STATUS_RUNNING, project_dir)

        try:
            _run_step(step_name, project, project_dir)
            project.update_step(step_name, STATUS_COMPLETED, project_dir)
            logger.info(f"  ✓ {step_name} — completed")
        except Exception as e:
            project.update_step(step_name, STATUS_FAILED, project_dir)
            logger.error(f"  ✗ {step_name} — failed: {e}")
            project.status = "failed"
            project.save(project_dir)
            raise

        # Stop early if requested
        if stop_after and step_name == stop_after:
            logger.info(f"Stopping after '{stop_after}' as requested")
            break

    # Check if all steps are done
    all_done = all(
        project.steps.get(s) == STATUS_COMPLETED for s in PIPELINE_STEPS
    )
    if all_done:
        project.status = "completed"
    else:
        project.status = "in_progress"
    project.save(project_dir)
    logger.info(f"Pipeline {'completed' if all_done else 'paused'} for '{project.name}'")


def _run_step(step_name: str, project: Project, project_dir: Path):
    """Dispatch to the correct module for each step."""

    if step_name == "download":
        result = download(project_dir, project.youtube_url)

        # Update project name from video title if it was auto-generated
        from auto_shorts.utils.file_utils import read_json
        metadata = read_json(project_dir / "downloads" / "metadata.json")
        if metadata.get("title"):
            project.name = metadata["title"]
        if metadata.get("duration"):
            project.duration_seconds = metadata["duration"]
        if metadata.get("language"):
            project.language = metadata["language"]

    elif step_name == "transcribe":
        video_path = str(project_dir / "downloads" / "video.mp4")
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Missing video file: {video_path}")
        transcribe(project_dir, video_path)

    elif step_name == "crawl_trends":
        crawl_trends(project_dir)

    elif step_name == "analyze":
        analyze(project_dir)

    elif step_name == "score":
        # TODO: v0.5 — Score fusion
        logger.warning(f"Step '{step_name}' not yet implemented — skipping")
        return

    elif step_name == "cut":
        cut(project_dir)

    elif step_name == "caption":
        caption(project_dir)

    else:
        raise ValueError(f"Unknown pipeline step: {step_name}")


def resume_project(project_dir: Path) -> tuple[Project, Path]:
    """Load and resume an existing project."""
    project = Project.load(project_dir)
    project.project_dir = project_dir
    logger.info(f"Resuming project '{project.name}'")
    return project, project_dir


def list_projects() -> list[dict]:
    """List all projects in the workspace."""
    ensure_workspace()
    projects = []
    for path in sorted(PROJECTS_DIR.iterdir()):
        if path.is_dir() and (path / "project.json").exists():
            try:
                project = Project.load(path)
                projects.append({
                    "name": project.name,
                    "status": project.status,
                    "dir": str(path),
                    "url": project.youtube_url,
                    "steps": project.steps,
                })
            except Exception as e:
                logger.warning(f"Could not load project at {path}: {e}")
    return projects
