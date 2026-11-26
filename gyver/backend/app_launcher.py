"""Local app/script launcher backed by a JSON file."""
import json
import os
import signal
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_FILE = _DATA_DIR / "apps.json"

# Track running processes: app_id -> Popen
_processes: dict[str, subprocess.Popen] = {}


def _read() -> list[dict]:
    if not _FILE.exists():
        return []
    return json.loads(_FILE.read_text())


def _write(items: list[dict]) -> None:
    _FILE.write_text(json.dumps(items, indent=2))


def list_apps() -> list[dict]:
    apps = _read()
    # Attach live running status
    for app in apps:
        app["running"] = _is_running(app["id"])
    apps.sort(key=lambda a: a["created_at"])
    return apps


def get_app(app_id: str) -> Optional[dict]:
    for app in _read():
        if app["id"] == app_id:
            app["running"] = _is_running(app_id)
            return app
    return None


def create_app(name: str, start_script: str, url: str = "",
               stop_script: str = "", working_dir: str = "") -> dict:
    apps = _read()
    app = {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "start_script": start_script,
        "stop_script": stop_script,
        "url": url,
        "working_dir": working_dir,
        "created_at": datetime.utcnow().isoformat(),
    }
    apps.append(app)
    _write(apps)
    app["running"] = False
    return app


def update_app(app_id: str, updates: dict) -> Optional[dict]:
    apps = _read()
    for app in apps:
        if app["id"] == app_id:
            for k in ("name", "start_script", "stop_script", "url", "working_dir"):
                if k in updates and updates[k] is not None:
                    app[k] = updates[k]
            _write(apps)
            app["running"] = _is_running(app_id)
            return app
    return None


def delete_app(app_id: str) -> bool:
    # Stop if running
    stop_app(app_id)
    apps = _read()
    new = [a for a in apps if a["id"] != app_id]
    if len(new) == len(apps):
        return False
    _write(new)
    return True


def start_app(app_id: str) -> Optional[dict]:
    """Start an app by running its start_script."""
    app = get_app(app_id)
    if not app:
        return None

    if _is_running(app_id):
        return app

    script = app["start_script"]
    if not script:
        return None

    cwd = app.get("working_dir") or None
    if cwd:
        cwd = os.path.expanduser(cwd)

    proc = subprocess.Popen(
        script,
        shell=True,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # detach from parent
    )
    _processes[app_id] = proc
    app["running"] = True
    return app


def stop_app(app_id: str) -> Optional[dict]:
    """Stop an app using its stop_script or by killing the process."""
    app_data = get_app(app_id)

    # Try custom stop script first
    if app_data and app_data.get("stop_script"):
        cwd = app_data.get("working_dir") or None
        if cwd:
            cwd = os.path.expanduser(cwd)
        try:
            subprocess.run(
                app_data["stop_script"],
                shell=True,
                cwd=cwd,
                timeout=10,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (subprocess.TimeoutExpired, Exception):
            pass

    # Kill tracked process and its process group
    proc = _processes.pop(app_id, None)
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    if app_data:
        app_data["running"] = False
    return app_data


def _is_running(app_id: str) -> bool:
    proc = _processes.get(app_id)
    if proc is None:
        return False
    return proc.poll() is None
