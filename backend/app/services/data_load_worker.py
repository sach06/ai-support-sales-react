"""
Isolated worker process for /api/data/load jobs.
Runs outside the request handler process and writes progress snapshots.
"""
import sys
import time
import re
import subprocess
from typing import List

from app.services.data_service import data_service
from app.services.load_job_service import save_progress


def _cleanup_orphan_spawn_helpers() -> int:
    """Kill orphaned python multiprocessing spawn-helper processes that can hold DB locks."""
    try:
        ps_script = r"""
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
$killed = 0
foreach ($p in $procs) {
    $cmd = [string]$p.CommandLine
    if ($cmd -match 'multiprocessing\.spawn' -and $cmd -match 'spawn_main\(parent_pid=(\d+),') {
        $parentPid = [int]$Matches[1]
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $parentPid" -ErrorAction SilentlyContinue
        if (-not $parent) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            $killed++
        }
    }
}
Write-Output $killed
"""
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_script],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return int(out) if out.isdigit() else 0
    except Exception:
        return 0


def _maybe_cleanup_stale_lock_owner(error_text: str) -> bool:
    """
    Attempt to terminate a stale multiprocessing child that is holding the DB lock.
    Only kills processes that look like orphaned Python spawn-main helpers.
    """
    try:
        m = re.search(r"PID\s+(\d+)", str(error_text))
        if not m:
            return False

        pid = int(m.group(1))
        info_cmd = (
            f"$p = Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\" -ErrorAction SilentlyContinue; "
            "if ($p) { $p.CommandLine }"
        )
        cmdline = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", info_cmd],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()

        if not cmdline:
            return False

        lowered = cmdline.lower()
        if "python" in lowered and "multiprocessing.spawn" in lowered and "spawn_main" in lowered:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True

        return False
    except Exception:
        return False


def _update_progress(job_id: str, step: str, current: int, total: int, logs: List[str] = None):
    percent = int((current / total) * 100) if total > 0 else 0
    payload = {
        "running": True,
        "done": False,
        "step": step,
        "current_step": current,
        "total_steps": total,
        "percent": percent,
    }
    if logs is not None:
        payload["logs"] = logs
    save_progress(job_id, payload)


def run_data_load(job_id: str):
    save_progress(job_id, {
        "running": True,
        "done": False,
        "error": None,
        "step": "Initializing...",
        "current_step": 0,
        "total_steps": 6,
        "percent": 0,
        "logs": [],
    })

    try:
        data_service.clear_logs()
        _cleanup_orphan_spawn_helpers()

        _update_progress(job_id, "Initializing database...", 1, 6)
        init_ok = False
        init_error = None
        for attempt in range(1, 6):
            try:
                data_service.initialize_database()
                init_ok = True
                break
            except Exception as e:
                init_error = e
                err_text = str(e)
                if "being used by another process" in err_text.lower() or "io error" in err_text.lower():
                    cleaned = _maybe_cleanup_stale_lock_owner(err_text)
                    _update_progress(
                        job_id,
                        (
                            f"Database locked (attempt {attempt}/5). Retrying..."
                            + (" Stale lock owner cleaned." if cleaned else "")
                        ),
                        1,
                        6,
                        data_service.get_logs(),
                    )
                    time.sleep(2.0 * attempt)
                    continue
                raise

        if not init_ok:
            raise RuntimeError(f"Failed to initialize database after retries: {init_error}")

        _update_progress(job_id, "Initializing database...", 1, 6, data_service.get_logs())

        _update_progress(job_id, "Discovering data files...", 2, 6, data_service.get_logs())
        available_files = data_service.list_available_files()
        if not available_files:
            save_progress(job_id, {
                "running": False,
                "done": True,
                "error": "No data files found in data/ directory",
                "step": "Error: No data files found",
                "logs": data_service.get_logs(),
            })
            return

        for file in available_files:
            if "bcg" in file.lower():
                _update_progress(job_id, f"Loading BCG installed base ({file})...", 3, 6, data_service.get_logs())
                data_service.load_bcg_installed_base(file)
                _update_progress(job_id, "BCG data loaded", 3, 6, data_service.get_logs())

        for file in available_files:
            if "crm" in file.lower():
                _update_progress(job_id, f"Loading CRM data ({file})...", 4, 6, data_service.get_logs())
                data_service.load_crm_data(file)
                _update_progress(job_id, "CRM data loaded", 4, 6, data_service.get_logs())

        for file in available_files:
            if "crm" not in file.lower() and "bcg" not in file.lower():
                if "install" in file.lower() or "base" in file.lower():
                    _update_progress(job_id, f"Loading {file}...", 5, 6, data_service.get_logs())
                    data_service.load_installed_base(file)

        _update_progress(job_id, "Creating unified company view & matching...", 5, 6, data_service.get_logs())
        data_service.create_unified_view()
        _update_progress(job_id, "Unified view created", 6, 6, data_service.get_logs())

        try:
            from app.services.ml_ranking_service import ml_ranking_service
            ml_ranking_service.clear_cache()
        except Exception:
            pass

        save_progress(job_id, {
            "running": False,
            "done": True,
            "error": None,
            "percent": 100,
            "step": "Complete!",
            "logs": data_service.get_logs(),
        })

    except Exception as e:
        save_progress(job_id, {
            "running": False,
            "done": True,
            "error": str(e),
            "step": f"Error: {e}",
            "logs": data_service.get_logs(),
        })


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m app.services.data_load_worker <job_id>")
    run_data_load(sys.argv[1])


if __name__ == "__main__":
    main()
