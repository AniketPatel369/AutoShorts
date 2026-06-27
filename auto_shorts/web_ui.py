import logging
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from auto_shorts.config import PROJECT_ROOT, PROJECTS_DIR, PIPELINE_STEPS, STATUS_COMPLETED, STATUS_PENDING
from auto_shorts.models.project import Project
from auto_shorts.pipeline import create_project, run_pipeline, resume_project, list_projects
from auto_shorts.utils.file_utils import read_json, sanitize_filename
from auto_shorts.utils.time_utils import format_duration

logger = logging.getLogger("auto_shorts.web_ui")

app = FastAPI(title="Auto Shorts Studio")

# Set up templates
templates_dir = PROJECT_ROOT / "auto_shorts" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Global dictionary to track active pipeline threads
active_threads = {}


def _get_project_dir_by_name(name: str) -> Optional[Path]:
    """Find the project directory matching a sanitized name."""
    # Try direct match
    dir_path = PROJECTS_DIR / name
    if dir_path.is_dir() and (dir_path / "project.json").exists():
        return dir_path
    
    # Try matching directory by sanitizing the name
    sanitized = sanitize_filename(name)
    dir_path_san = PROJECTS_DIR / sanitized
    if dir_path_san.is_dir() and (dir_path_san / "project.json").exists():
        return dir_path_san
        
    # Search all project folders for a name match
    for path in PROJECTS_DIR.iterdir():
        if path.is_dir() and (path / "project.json").exists():
            if path.name.lower() == name.lower() or path.name.lower() == sanitized.lower():
                return path
            try:
                p = Project.load(path)
                if sanitize_filename(p.name) == sanitized:
                    return path
            except Exception:
                pass
    return None


def _background_pipeline_runner(project: Project, project_dir: Path):
    """Run the pipeline in a background thread."""
    project_name = project_dir.name
    try:
        logger.info(f"Background pipeline thread started for project: {project.name}")
        run_pipeline(project, project_dir)
        logger.info(f"Background pipeline thread finished successfully for: {project.name}")
    except Exception as e:
        logger.error(f"Background pipeline thread failed for {project.name}: {e}", exc_info=True)
    finally:
        active_threads.pop(project_name, None)


@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    """Render the dashboard home page."""
    projects = list_projects()
    # Sort projects by creation time (descending)
    projects_sorted = sorted(projects, key=lambda x: x.get("created", ""), reverse=True)
    recent_projects = projects_sorted[:4]
    
    # Format duration for template
    for p in recent_projects:
        # Load full project details if possible
        p_dir = Path(p["dir"])
        try:
            full_p = Project.load(p_dir)
            p["duration_str"] = format_duration(full_p.duration_seconds) if full_p.duration_seconds else "Unknown"
        except Exception:
            p["duration_str"] = "Unknown"
            
    return templates.TemplateResponse(
        request=request,
        name="dashbaord.html", 
        context={"recent_projects": recent_projects}
    )



@app.post("/project")
async def create_new_project(request: Request, url: str = Form(...), name: Optional[str] = Form(None)):
    """Create a new project and start pipeline in background."""
    if not url.strip():
        raise HTTPException(status_code=400, detail="YouTube URL is required")
        
    project, project_dir = create_project(url, name=name)
    project_name = project_dir.name
    
    # Start the pipeline execution in a background thread
    t = threading.Thread(
        target=_background_pipeline_runner,
        args=(project, project_dir),
        daemon=True
    )
    active_threads[project_name] = t
    t.start()
    
    return RedirectResponse(url=f"/project/{project_name}/processing", status_code=303)


@app.get("/project/{name}/processing", response_class=HTMLResponse)
async def view_processing(request: Request, name: str):
    """Render the processing/progress view for a project."""
    project_dir = _get_project_dir_by_name(name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")
        
    project = Project.load(project_dir)
    return templates.TemplateResponse(
        request=request,
        name="processing.html",
        context={"project": project, "project_name": project_dir.name}
    )



@app.get("/project/{name}", response_class=HTMLResponse)
async def view_project_detail(request: Request, name: str):
    """Render project detail / clips gallery page."""
    project_dir = _get_project_dir_by_name(name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")
        
    project = Project.load(project_dir)
    
    # Load clips data
    clips = []
    analysis_dir = project_dir / "analysis"
    scored_path = analysis_dir / "clips_scored.json"
    raw_path = analysis_dir / "clips_raw.json"
    
    if scored_path.exists():
        clips = read_json(scored_path)
    elif raw_path.exists():
        clips = read_json(raw_path)
        
    # Check if there are cut clips files on disk
    output_dir = project_dir / "output"
    for idx, clip in enumerate(clips, 1):
        clip["id"] = idx
        clip["duration_str"] = f"{int(clip.get('duration', 0))}s"
        # Find if clip file exists
        matches = list(output_dir.glob(f"clip_{idx:02d}_score_*.mp4"))
        clip["has_file"] = len(matches) > 0
        clip["category_icon"] = {
            "punchline": "mood",
            "roast": "local_fire_department",
            "hot_take": "campaign",
            "audience_eruption": "group",
            "quotable": "format_quote",
            "absurd": "question_mark",
            "emotional": "favorite",
            "motivational": "fitness_center"
        }.get(clip.get("category", ""), "movie")
        
    project_duration = format_duration(project.duration_seconds) if project.duration_seconds else "Unknown"
    
    return templates.TemplateResponse(
        request=request,
        name="project_detail.html",
        context={
            "project": project, 
            "project_name": project_dir.name, 
            "clips": clips,
            "project_duration": project_duration
        }
    )



@app.get("/project/{name}/clip/{clip_id}", response_class=HTMLResponse)
async def view_clip_detail(request: Request, name: str, clip_id: int):
    """Render detailed preview page for a single clip."""
    project_dir = _get_project_dir_by_name(name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")
        
    project = Project.load(project_dir)
    
    # Load clips
    clips = []
    analysis_dir = project_dir / "analysis"
    scored_path = analysis_dir / "clips_scored.json"
    raw_path = analysis_dir / "clips_raw.json"
    
    if scored_path.exists():
        clips = read_json(scored_path)
    elif raw_path.exists():
        clips = read_json(raw_path)
        
    if clip_id < 1 or clip_id > len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")
        
    clip = clips[clip_id - 1]
    clip["id"] = clip_id
    clip["duration_str"] = f"{int(clip.get('duration', 0))}s"
    
    # Check if clip file exists
    output_dir = project_dir / "output"
    matches = list(output_dir.glob(f"clip_{clip_id:02d}_score_*.mp4"))
    clip["has_file"] = len(matches) > 0
    
    return templates.TemplateResponse(
        request=request,
        name="clip_detail.html",
        context={
            "project": project,
            "project_name": project_dir.name,
            "clip": clip,
            "total_clips": len(clips)
        }
    )



@app.get("/projects", response_class=HTMLResponse)
async def view_all_projects(request: Request):
    """Render gallery page of all projects."""
    projects = list_projects()
    
    # Format and enrich project data
    for p in projects:
        p_dir = Path(p["dir"])
        try:
            full_p = Project.load(p_dir)
            p["duration_str"] = format_duration(full_p.duration_seconds) if full_p.duration_seconds else "Unknown"
        except Exception:
            p["duration_str"] = "Unknown"
            
        # Try count clips
        analysis_dir = p_dir / "analysis"
        clips_count = 0
        for f in ["clips_scored.json", "clips_raw.json"]:
            path = analysis_dir / f
            if path.exists():
                try:
                    clips_count = len(read_json(path))
                    break
                except Exception:
                    pass
        p["clips_count"] = clips_count
        p["folder_name"] = p_dir.name
        
    return templates.TemplateResponse(
        request=request,
        name="all_projects.html",
        context={"projects": projects}
    )



@app.get("/settings", response_class=HTMLResponse)
async def view_settings(request: Request):
    """Render configuration settings page."""
    import auto_shorts.config as cfg
    
    # Simple settings dict
    settings_data = {
        "llm_model": cfg.LLM_MODEL,
        "whisper_model": cfg.WHISPER_MODEL,
        "output_width": cfg.OUTPUT_WIDTH,
        "output_height": cfg.OUTPUT_HEIGHT,
        "min_clip_duration": cfg.MIN_CLIP_DURATION,
        "max_clip_duration": cfg.MAX_CLIP_DURATION,
        "chunk_window_seconds": cfg.CHUNK_WINDOW_SECONDS,
        "chunk_overlap_seconds": cfg.CHUNK_OVERLAP_SECONDS,
        "projects_dir": str(cfg.PROJECTS_DIR),
        "models_dir": str(cfg.MODELS_DIR)
    }
    
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"settings": settings_data}
    )



@app.get("/api/project/{name}/status")
async def api_project_status(name: str):
    """Return JSON status of project pipeline steps."""
    project_dir = _get_project_dir_by_name(name)
    if not project_dir:
        return {"status": "not_found", "steps": {}}
        
    project = Project.load(project_dir)
    return {
        "status": project.status,
        "steps": project.steps,
        "name": project.name,
        "duration_seconds": project.duration_seconds
    }


@app.get("/api/project/{name}/clip/{clip_id}/video")
async def api_project_clip_video(name: str, clip_id: int):
    """Stream clip MP4 file."""
    project_dir = _get_project_dir_by_name(name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")
        
    output_dir = project_dir / "output"
    matches = list(output_dir.glob(f"clip_{clip_id:02d}_score_*.mp4"))
    if not matches:
        raise HTTPException(status_code=404, detail="Clip video file not found")
        
    return FileResponse(str(matches[0]), media_type="video/mp4")


@app.post("/project/{name}/reanalyze")
async def reanalyze_project(name: str):
    """Reset project steps and re-run pipeline in background."""
    project_dir = _get_project_dir_by_name(name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")
        
    project = Project.load(project_dir)
    project_name = project_dir.name
    
    # Reset steps in project metadata
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
    for step in ["analyze", "score", "cut", "caption"]:
        project.steps[step] = STATUS_PENDING
    project.status = "created"
    project.save(project_dir)
    
    # Start thread
    t = threading.Thread(
        target=_background_pipeline_runner,
        args=(project, project_dir),
        daemon=True
    )
    active_threads[project_name] = t
    t.start()
    
    return RedirectResponse(url=f"/project/{project_name}/processing", status_code=303)


@app.post("/project/{name}/delete")
async def delete_project(name: str):
    """Delete a project and its folder."""
    project_dir = _get_project_dir_by_name(name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Delete directory and all its files recursively
    import shutil
    try:
        shutil.rmtree(project_dir)
        logger.info(f"Deleted project folder: {project_dir}")
    except Exception as e:
        logger.error(f"Failed to delete project folder {project_dir}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete project folder")
        
    return RedirectResponse(url="/projects", status_code=303)


@app.post("/project/{name}/open")
async def open_project_folder(name: str):
    """Open project folder in Finder (macOS/OSX support)."""
    project_dir = _get_project_dir_by_name(name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")
        
    import subprocess
    try:
        subprocess.run(["open", str(project_dir)])
        logger.info(f"Opened project directory in Finder: {project_dir}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to open directory {project_dir}: {e}")
        raise HTTPException(status_code=500, detail="Failed to open directory")

