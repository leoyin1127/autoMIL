#!/usr/bin/env python3
"""Experiment graph visualization server.

Watches graph.json for changes via inotify, pushes updates to browser via SSE.
Serves static D3.js dashboard.

Usage:
    uv run python autoMIL/viz/server.py start [--port 8420]
    uv run python autoMIL/viz/server.py status
    uv run python autoMIL/viz/server.py stop
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path

try:
    from aiohttp import web
except ImportError:
    print("aiohttp required: uv add aiohttp")
    sys.exit(1)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("watchdog required: uv add watchdog")
    sys.exit(1)

VIZ_DIR = Path(__file__).parent
STATIC_DIR = VIZ_DIR / "static"

# These are set at runtime by cmd_start() based on project_root
GRAPH_FILE: Path = Path("graph.json")
PID_FILE: Path = Path("viz_server.pid")
LOG_FILE: Path = Path("viz_server.log")

DEFAULT_PORT = 8420


class GraphWatcher(FileSystemEventHandler):
    def __init__(self):
        self.subscribers: list[asyncio.Queue] = []
        self._prev_data: dict | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def _maybe_notify(self, path: str):
        if Path(path).name == GRAPH_FILE.name and self._loop:
            self._loop.call_soon_threadsafe(
                asyncio.ensure_future, self._notify()
            )

    def on_modified(self, event):
        self._maybe_notify(event.src_path)

    def on_moved(self, event):
        self._maybe_notify(event.dest_path)

    def on_created(self, event):
        self._maybe_notify(event.src_path)

    async def _notify(self):
        try:
            data = json.loads(GRAPH_FILE.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return

        changed, added = [], []
        if self._prev_data:
            prev_nodes = set(self._prev_data.get("nodes", {}).keys())
            curr_nodes = set(data.get("nodes", {}).keys())
            added = list(curr_nodes - prev_nodes)
            for nid in curr_nodes & prev_nodes:
                if data["nodes"][nid] != self._prev_data["nodes"].get(nid):
                    changed.append(nid)

        self._prev_data = data
        event = json.dumps({
            "type": "graph_update",
            "changed": changed,
            "added": added,
            "full_graph": data,
        })

        dead = []
        for q in self.subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.subscribers.remove(q)

    async def get_initial(self) -> str:
        try:
            data = json.loads(GRAPH_FILE.read_text())
            self._prev_data = data
        except (json.JSONDecodeError, FileNotFoundError):
            data = {"nodes": {}, "meta": {}, "technique_stats": {}}
        return json.dumps({
            "type": "graph_update",
            "changed": [],
            "added": list(data.get("nodes", {}).keys()),
            "full_graph": data,
        })


watcher = GraphWatcher()


async def sse_handler(request):
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
    await response.prepare(request)

    initial = await watcher.get_initial()
    await response.write(f"data: {initial}\n\n".encode())

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    watcher.subscribers.append(queue)

    try:
        while True:
            event = await queue.get()
            await response.write(f"data: {event}\n\n".encode())
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        if queue in watcher.subscribers:
            watcher.subscribers.remove(queue)

    return response


async def index_handler(request):
    return web.FileResponse(STATIC_DIR / "index.html")


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/events", sse_handler)
    app.router.add_static("/static", STATIC_DIR)
    return app


def cmd_start(port: int = DEFAULT_PORT, project_root: Path | None = None):
    global GRAPH_FILE, PID_FILE, LOG_FILE
    if project_root is None:
        project_root = Path.cwd()
    automil_dir = project_root / "automil"
    GRAPH_FILE = automil_dir / "graph.json"
    PID_FILE = automil_dir / "orchestrator" / "viz_server.pid"
    LOG_FILE = automil_dir / "orchestrator" / "viz_server.log"

    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Viz server already running (PID {pid})")
            return
        except OSError:
            PID_FILE.unlink()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
    )

    PID_FILE.write_text(str(os.getpid()) + "\n")

    observer = Observer()
    observer.schedule(watcher, str(automil_dir), recursive=False)
    observer.start()

    async def run_server():
        app = create_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logging.info(f"Viz server running on http://localhost:{port}")

        # Wait for shutdown signal
        stop_event = asyncio.Event()
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()
        logging.info("Shutting down...")
        await runner.cleanup()

    loop = asyncio.new_event_loop()
    watcher.set_loop(loop)

    try:
        loop.run_until_complete(run_server())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        observer.stop()
        observer.join(timeout=2)
        if PID_FILE.exists():
            PID_FILE.unlink()
        logging.info("Viz server stopped.")


def _resolve_pid_file(project_root: Path | None = None) -> Path:
    """Get the PID file path for the viz server."""
    if project_root is None:
        project_root = Path.cwd()
    return project_root / "automil" / "orchestrator" / "viz_server.pid"


def cmd_status(project_root: Path | None = None):
    pid_file = _resolve_pid_file(project_root)
    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Viz server: RUNNING (PID {pid})")
        except OSError:
            print("Viz server: DEAD (stale PID file)")
    else:
        print("Viz server: NOT RUNNING")


def cmd_stop(project_root: Path | None = None):
    pid_file = _resolve_pid_file(project_root)
    if not pid_file.exists():
        print("Viz server not running")
        return
    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to PID {pid}")
    except OSError as e:
        print(f"Failed to stop: {e}")
        pid_file.unlink()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "start":
        port = DEFAULT_PORT
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            port = int(sys.argv[idx + 1])
        cmd_start(port)
    elif cmd == "status":
        cmd_status()
    elif cmd == "stop":
        cmd_stop()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
