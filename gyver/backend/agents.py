"""Configurable CLI coding agents (Claude Code, OpenCode, Codex, ...).

Agent configs are stored in a JSON file. Launching one starts its CLI in a
pseudo-terminal; the output is buffered and fanned out to any attached
websocket so the frontend can show (and type into) a live terminal. Runs live
only in memory and are killed when the backend shuts down.
"""
import fcntl
import json
import os
import pty
import shlex
import signal
import struct
import subprocess
import termios
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from dotenv import dotenv_values

_DATA_DIR = Path(__file__).parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_FILE = _DATA_DIR / "agents.json"
_LOCK = threading.RLock()

# Command templates per runtime. {model} and {prompt} are substituted as whole
# arguments ({prompt_toml} is the prompt as a quoted TOML string); a flag whose
# value ends up empty is dropped along with the value.
#
# The starting prompt is never sent as an opening message, so the agent stays
# quiet until the user gives it something to do. Claude Code and Codex take it
# as a standing instruction. OpenCode has no flag for that, so ("prefill") it is
# typed into the input box, unsent, ahead of the user's first message.
RUNTIMES: dict[str, dict] = {
    "claude": {"label": "Claude Code", "command": "claude --model {model} --append-system-prompt {prompt}"},
    "opencode": {"label": "OpenCode", "command": "opencode mini --model {model}", "prefill": True},
    "codex": {"label": "Codex", "command": "codex --model {model} -c developer_instructions={prompt_toml}"},
    "custom": {"label": "Custom command", "command": ""},
}

_FIELDS = ("name", "runtime", "model", "prompt", "working_dir", "command")

# Keep roughly the last 512 KB of terminal output per run for replay on attach.
_BUFFER_LIMIT = 512 * 1024
_KILL_GRACE_SECONDS = 3

# Prefill waits for the agent's UI to ask for bracketed paste (i.e. its input
# box exists) and then for the screen to stop changing, before typing.
_PASTE_MODE_ON = b"\x1b[?2004h"
_PREFILL_QUIET_SECONDS = 1.0
_PREFILL_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Agent configs
# ---------------------------------------------------------------------------

def _read() -> list[dict]:
    if not _FILE.exists():
        return []
    return json.loads(_FILE.read_text())


def _write(items: list[dict]) -> None:
    _FILE.write_text(json.dumps(items, indent=2))


def list_agents() -> list[dict]:
    agents = _read()
    # Manually ordered agents first; ones never reordered fall back to creation order
    agents.sort(key=lambda a: (a.get("sort_order", float("inf")), a["created_at"]))
    return agents


def get_agent(agent_id: str) -> Optional[dict]:
    for agent in _read():
        if agent["id"] == agent_id:
            return agent
    return None


def create_agent(name: str, runtime: str = "claude", model: str = "", prompt: str = "",
                 working_dir: str = "", command: str = "") -> dict:
    agent = {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "runtime": runtime,
        "model": model,
        "prompt": prompt,
        "working_dir": working_dir,
        # Empty means "use the runtime's default template"
        "command": command,
        "created_at": datetime.utcnow().isoformat(),
    }
    with _LOCK:
        agents = _read()
        agents.append(agent)
        _write(agents)
    return agent


def update_agent(agent_id: str, updates: dict) -> Optional[dict]:
    with _LOCK:
        agents = _read()
        for agent in agents:
            if agent["id"] == agent_id:
                for k in _FIELDS:
                    if k in updates and updates[k] is not None:
                        agent[k] = updates[k]
                _write(agents)
                return agent
    return None


def reorder_agents(agent_ids: list[str]) -> list[dict]:
    """Bulk reorder: accepts a list of agent IDs in the desired order."""
    id_to_order = {aid: idx for idx, aid in enumerate(agent_ids)}
    with _LOCK:
        agents = _read()
        for agent in agents:
            if agent["id"] in id_to_order:
                agent["sort_order"] = id_to_order[agent["id"]]
            else:
                # Not in the list (e.g. created in another tab): keep it after the ordered ones
                agent.pop("sort_order", None)
        _write(agents)
    return list_agents()


def delete_agent(agent_id: str) -> bool:
    with _LOCK:
        agents = _read()
        new = [a for a in agents if a["id"] != agent_id]
        if len(new) == len(agents):
            return False
        _write(new)
    return True


def build_command(agent: dict) -> list[str]:
    """Expand the agent's command template into an argv list."""
    template = agent.get("command") or RUNTIMES.get(agent.get("runtime", ""), {}).get("command", "")
    prompt = agent.get("prompt", "").strip()
    values = {
        "{model}": agent.get("model", "").strip(),
        "{prompt}": prompt,
        # JSON string escapes are valid in a TOML basic string
        "{prompt_toml}": json.dumps(prompt) if prompt else "",
    }
    argv: list[str] = []
    for token in shlex.split(template):
        used = [ph for ph in values if ph in token]
        if used and not all(values[ph] for ph in used):
            # Nothing to put here: drop it, and the flag that introduced it
            if argv and argv[-1].startswith("-"):
                argv.pop()
            continue
        for ph in used:
            token = token.replace(ph, values[ph])
        argv.append(token)
    return argv


def prefill_text(agent: dict) -> str:
    """The starting prompt, if it should be typed into the agent's input box rather than passed in the command."""
    runtime = RUNTIMES.get(agent.get("runtime", ""), {})
    template = agent.get("command") or runtime.get("command", "")
    # A command override that names {prompt} has already decided where it goes
    if not runtime.get("prefill") or "{prompt" in template:
        return ""
    return agent.get("prompt", "").strip()


# ---------------------------------------------------------------------------
# Models per runtime
# ---------------------------------------------------------------------------

# Claude Code has no command that lists models; these are the aliases and
# full names its --model flag accepts.
_CLAUDE_MODELS = [
    "fable", "opus", "sonnet", "haiku",
    "claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5",
]
_MODELS_TTL_SECONDS = 300
_models_cache: dict[str, tuple[float, list[str]]] = {}


def _parse_opencode_models(output: str) -> list[str]:
    # One provider/model per line
    return [l.strip() for l in output.splitlines() if "/" in l and " " not in l.strip()]


def _parse_codex_models(output: str) -> list[str]:
    # JSON catalog; keep the models Codex itself shows in its picker, in its order
    catalog = json.loads(output).get("models", [])
    listed = [m for m in catalog if m.get("visibility") == "list" and m.get("slug")]
    listed.sort(key=lambda m: m.get("priority", 0))
    return [m["slug"] for m in listed]


# Runtimes whose CLI can report its own models: command to run + output parser
_MODEL_COMMANDS: dict[str, tuple[list[str], Callable[[str], list[str]]]] = {
    "opencode": (["opencode", "models"], _parse_opencode_models),
    "codex": (["codex", "debug", "models"], _parse_codex_models),
}


def list_models(runtime: str) -> list[str]:
    """Models selectable for a runtime; empty when the runtime can't tell us."""
    if runtime == "claude":
        return list(_CLAUDE_MODELS)
    if runtime not in _MODEL_COMMANDS:
        return []
    cached = _models_cache.get(runtime)
    if cached and time.time() - cached[0] < _MODELS_TTL_SECONDS:
        return cached[1]
    command, parse = _MODEL_COMMANDS[runtime]
    try:
        proc = subprocess.run(
            command, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=20, env=_child_env(),
        )
        if proc.returncode != 0:
            return []
        models = parse(proc.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    _models_cache[runtime] = (time.time(), models)
    return models


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

class AgentRun:
    def __init__(self, agent: dict, name: str, argv: list[str], cwd: str, prefill: str = ""):
        self.id = uuid.uuid4().hex[:12]
        self.agent_id = agent["id"]
        self.name = name
        self.runtime = agent.get("runtime", "")
        self.model = agent.get("model", "")
        self.command = shlex.join(argv)
        self.cwd = cwd
        self.started_at = datetime.utcnow().isoformat()
        self.exit_code: Optional[int] = None
        self._buffer = bytearray()
        self._listeners: list[Callable[[Optional[bytes]], None]] = []
        self._lock = threading.Lock()
        self._last_output = time.monotonic()

        self._master, slave = pty.openpty()
        self._set_size(24, 100)
        # Run through the login shell so the agent sees the user's normal PATH.
        shell = os.environ.get("SHELL", "/bin/zsh")
        self._proc = subprocess.Popen(
            [shell, "-l", "-c", 'exec "$@"', "agent", *argv],
            stdin=slave, stdout=slave, stderr=slave,
            cwd=cwd, env=_child_env(), close_fds=True,
            preexec_fn=_become_session_leader,
        )
        os.close(slave)
        threading.Thread(target=self._pump, daemon=True).start()
        if prefill:
            threading.Thread(target=self._prefill, args=(prefill,), daemon=True).start()

    @property
    def running(self) -> bool:
        return self.exit_code is None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "name": self.name,
            "runtime": self.runtime,
            "model": self.model,
            "command": self.command,
            "working_dir": self.cwd,
            "started_at": self.started_at,
            "running": self.running,
            "exit_code": self.exit_code,
        }

    def _pump(self) -> None:
        """Copy terminal output into the buffer and out to listeners until EOF."""
        while True:
            try:
                data = os.read(self._master, 65536)
            except OSError:
                data = b""
            if not data:
                break
            with self._lock:
                self._last_output = time.monotonic()
                self._buffer += data
                if len(self._buffer) > _BUFFER_LIMIT:
                    del self._buffer[: len(self._buffer) - _BUFFER_LIMIT]
                listeners = list(self._listeners)
            for listener in listeners:
                listener(data)
        code = self._proc.wait()
        with self._lock:
            self.exit_code = code
            listeners = list(self._listeners)
        for listener in listeners:
            listener(None)  # None signals exit
        try:
            os.close(self._master)
        except OSError:
            pass

    def _prefill(self, text: str) -> None:
        """Type the starting prompt into the agent's input box without sending it."""
        deadline = time.monotonic() + _PREFILL_TIMEOUT_SECONDS
        while self.running and time.monotonic() < deadline:
            with self._lock:
                ready = _PASTE_MODE_ON in self._buffer
                quiet = time.monotonic() - self._last_output
            if ready and quiet >= _PREFILL_QUIET_SECONDS:
                break
            time.sleep(0.1)
        # As a paste, so line breaks in the prompt stay line breaks instead of
        # submitting; the blank line leaves the cursor where the user's message goes.
        self.write(b"\x1b[200~" + text.encode() + b"\n\n\x1b[201~")

    def attach(self, listener: Callable[[Optional[bytes]], None]) -> bytes:
        """Register a listener and return the output so far (for replay)."""
        with self._lock:
            self._listeners.append(listener)
            return bytes(self._buffer)

    def detach(self, listener: Callable[[Optional[bytes]], None]) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def write(self, data: bytes) -> None:
        if self.running:
            try:
                os.write(self._master, data)
            except OSError:
                pass

    def _set_size(self, rows: int, cols: int) -> None:
        fcntl.ioctl(self._master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def resize(self, rows: int, cols: int, redraw: bool = False) -> None:
        if not self.running or rows < 2 or cols < 2:
            return
        try:
            if redraw:
                # A size change is what makes a full-screen app repaint, so
                # nudge it even when the size is unchanged (e.g. on re-attach).
                self._set_size(rows - 1, cols)
            self._set_size(rows, cols)
        except OSError:
            pass

    def kill(self) -> None:
        if not self.running:
            return
        self._signal(signal.SIGTERM)
        try:
            self._proc.wait(timeout=_KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            self._signal(signal.SIGKILL)

    def _signal(self, sig: int) -> None:
        try:
            os.killpg(self._proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def _become_session_leader() -> None:
    # New session + controlling terminal, so Ctrl-C etc. reach the agent and
    # killing the process group takes its children with it.
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


def _child_env() -> dict:
    env = dict(os.environ)
    # Don't leak this app's own secrets (.env) into agents — e.g. an
    # ANTHROPIC_API_KEY here would switch Claude Code off the user's login.
    for key in dotenv_values(Path(__file__).parent / ".env"):
        env.pop(key, None)
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    return env


_runs: dict[str, AgentRun] = {}
_launch_counts: dict[str, int] = {}


def launch(agent_id: str) -> AgentRun:
    agent = get_agent(agent_id)
    if not agent:
        raise LookupError("Agent not found")
    argv = build_command(agent)
    if not argv:
        raise ValueError("Agent has no command to run")
    cwd = os.path.expanduser(agent.get("working_dir") or "~")
    if not os.path.isdir(cwd):
        raise ValueError(f"Working directory does not exist: {cwd}")
    with _LOCK:
        n = _launch_counts[agent_id] = _launch_counts.get(agent_id, 0) + 1
        run = AgentRun(agent, f"{agent['name']} #{n}", argv, cwd, prefill_text(agent))
        _runs[run.id] = run
    return run


def list_runs() -> list[dict]:
    return [r.to_dict() for r in sorted(_runs.values(), key=lambda r: r.started_at)]


def get_run(run_id: str) -> Optional[AgentRun]:
    return _runs.get(run_id)


def kill_run(run_id: str) -> Optional[dict]:
    run = _runs.get(run_id)
    if not run:
        return None
    run.kill()
    return run.to_dict()


def remove_run(run_id: str) -> bool:
    """Kill the run if needed and drop it from the list."""
    run = _runs.pop(run_id, None)
    if not run:
        return False
    run.kill()
    return True


def kill_all() -> None:
    for run in list(_runs.values()):
        run.kill()
