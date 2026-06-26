"""
Auto Shorts — Data Models: Project

Represents a single video processing project.
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from auto_shorts.config import PIPELINE_STEPS, STATUS_PENDING


@dataclass
class Project:
    """A single video processing project."""

    name: str
    youtube_url: str
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "created"
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
    clips_found: int = 0
    version: str = "1.0"
    steps: dict = field(default_factory=dict)

    def __post_init__(self):
        # Initialize all steps as pending if not already set
        if not self.steps:
            self.steps = {step: STATUS_PENDING for step in PIPELINE_STEPS}

    @property
    def project_dir(self) -> Optional[Path]:
        """Set externally after creation."""
        return self._project_dir if hasattr(self, "_project_dir") else None

    @project_dir.setter
    def project_dir(self, path: Path):
        self._project_dir = path

    def save(self, project_dir: Path):
        """Save project.json to disk."""
        data = asdict(self)
        path = project_dir / "project.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, project_dir: Path) -> "Project":
        """Load project from project.json."""
        path = project_dir / "project.json"
        if not path.exists():
            raise FileNotFoundError(f"No project.json found in {project_dir}")
        data = json.loads(path.read_text())
        project = cls(**data)
        project.project_dir = project_dir
        return project

    def update_step(self, step_name: str, status: str, project_dir: Path):
        """Update a step's status and save immediately."""
        self.steps[step_name] = status
        self.save(project_dir)
