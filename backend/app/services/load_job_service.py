"""
Background job tracking utilities for long-running data-load tasks.
Stores progress snapshots as JSON files so API requests stay lightweight.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

from app.core.config import settings

JOBS_DIR = settings.BASE_DIR / "temp" / "load_jobs"
LATEST_JOB_FILE = JOBS_DIR / "latest_job.txt"


def _ensure_jobs_dir() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def _job_file(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _default_progress(job_id: str) -> Dict:
    now = datetime.utcnow().isoformat() + "Z"
    return {
        "job_id": job_id,
        "running": False,
        "step": "",
        "percent": 0,
        "total_steps": 6,
        "current_step": 0,
        "error": None,
        "done": False,
        "logs": [],
        "created_at": now,
        "updated_at": now,
        "pid": None,
    }


def save_progress(job_id: str, payload: Dict) -> Dict:
    """Persist job progress atomically to JSON file."""
    _ensure_jobs_dir()
    path = _job_file(job_id)
    data = load_progress(job_id) or _default_progress(job_id)
    data.update(payload or {})
    data["job_id"] = job_id
    data["updated_at"] = datetime.utcnow().isoformat() + "Z"

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
    
    # Windows-compatible atomic rename with retry
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # Try to remove existing file first (handles file locks better on Windows)
            if path.exists():
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass  # If delete fails, os.replace will overwrite
            os.replace(tmp_path, path)
            break
        except (OSError, PermissionError) as e:
            if attempt < max_retries - 1:
                import time
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff: 0.1s, 0.2s, 0.3s...
            else:
                # Last resort: write directly (sacrifices atomicity but ensures data is saved)
                try:
                    path.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
                    if tmp_path.exists():
                        tmp_path.unlink(missing_ok=True)
                except Exception as final_err:
                    print(f"Failed to save progress for job {job_id}: {final_err}")
                break
    
    return data


def load_progress(job_id: str) -> Optional[Dict]:
    """Read a stored job progress snapshot."""
    if not job_id:
        return None
    path = _job_file(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def set_latest_job_id(job_id: str) -> None:
    _ensure_jobs_dir()
    LATEST_JOB_FILE.write_text(job_id.strip(), encoding="utf-8")


def get_latest_job_id() -> Optional[str]:
    if not LATEST_JOB_FILE.exists():
        return None
    job_id = LATEST_JOB_FILE.read_text(encoding="utf-8").strip()
    return job_id or None


def get_latest_progress() -> Optional[Dict]:
    latest = get_latest_job_id()
    if not latest:
        return None
    return load_progress(latest)


def start_load_job() -> Dict:
    """Spawn an isolated Python process for the data-load worker."""
    _ensure_jobs_dir()
    job_id = uuid4().hex

    # Create initial progress snapshot
    save_progress(
        job_id,
        {
            "running": True,
            "step": "Initializing...",
            "percent": 0,
            "current_step": 0,
            "done": False,
            "error": None,
            "logs": [],
        },
    )

    cmd = [sys.executable, "-m", "app.services.data_load_worker", job_id]
    proc = subprocess.Popen(
        cmd,
        cwd=str(settings.BASE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    save_progress(job_id, {"pid": proc.pid})
    set_latest_job_id(job_id)

    return {
        "job_id": job_id,
        "pid": proc.pid,
    }
