"""FastAPI application — routes for the sweep dashboard."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import NodeConfigManager
from .job_dispatcher import JobDispatcher
from .node_monitor import NodeMonitor
from .ssh_manager import SSHManager

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent  # sweep-dashboard/
KEY_PATH = str(BASE_DIR / "master_key.txt")
CONFIG_PATH = str(BASE_DIR / "nodes.yaml")
SCRIPTS_DIR = str(BASE_DIR / "scripts")

# Shared instances (initialized in lifespan)
config_mgr: NodeConfigManager | None = None
ssh_mgr: SSHManager | None = None
monitor: NodeMonitor | None = None
dispatcher: JobDispatcher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared resources on startup and clean up on shutdown."""
    global config_mgr, ssh_mgr, monitor, dispatcher

    from .crypto import generate_key

    if not os.path.exists(KEY_PATH):
        logger.info("Generating new master key at %s", KEY_PATH)
        generate_key(KEY_PATH)

    config_mgr = NodeConfigManager(CONFIG_PATH, KEY_PATH)
    ssh_mgr = SSHManager(timeout=10)
    monitor = NodeMonitor(config_mgr, ssh_mgr, poll_interval=30)
    dispatcher = JobDispatcher(config_mgr, ssh_mgr)

    monitor_task = asyncio.create_task(monitor.start())

    yield

    monitor.stop()
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Sweep Dashboard", lifespan=lifespan)

# Static files & templates
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# HTML Pages
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Main dashboard showing all nodes and their statuses."""
    nodes = config_mgr.list_nodes()
    statuses = monitor.statuses
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "nodes": nodes, "statuses": statuses},
    )


@app.get("/node/{node_name}", response_class=HTMLResponse)
async def node_detail_page(request: Request, node_name: str):
    """Detail view for a single node."""
    try:
        node = config_mgr.get_node(node_name)
    except KeyError:
        raise HTTPException(404, f"Node '{node_name}' not found")
    status = monitor.get_status(node_name)
    return templates.TemplateResponse(
        "node_detail.html",
        {"request": request, "node": node, "status": status},
    )


@app.get("/logs/{node_name}", response_class=HTMLResponse)
async def logs_page(request: Request, node_name: str, path: str = ""):
    """Log viewer for a node's training logs."""
    try:
        node = config_mgr.get_node(node_name)
    except KeyError:
        raise HTTPException(404, f"Node '{node_name}' not found")
    return templates.TemplateResponse(
        "logs.html",
        {"request": request, "node": node, "log_path": path},
    )


@app.get("/dispatch", response_class=HTMLResponse)
async def dispatch_page(request: Request):
    """Page for dispatching jobs to nodes."""
    nodes = config_mgr.list_nodes()
    scripts: list[str] = []
    if os.path.isdir(SCRIPTS_DIR):
        scripts = sorted(f for f in os.listdir(SCRIPTS_DIR) if f.endswith(".sh"))
    return templates.TemplateResponse(
        "dispatch.html",
        {"request": request, "nodes": nodes, "scripts": scripts},
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page for managing node configurations."""
    nodes = config_mgr.list_nodes()
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "nodes": nodes},
    )


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


def _status_to_dict(status) -> dict:
    """Convert a NodeStatus to a dict, including computed memory_free_mb."""
    data = status.model_dump()
    for i, gpu in enumerate(data["gpus"]):
        gpu["memory_free_mb"] = status.gpus[i].memory_free_mb
    return data


@app.get("/api/statuses")
async def api_statuses():
    """Return current status for all nodes."""
    statuses = monitor.statuses
    return {name: _status_to_dict(status) for name, status in statuses.items()}


@app.get("/api/status/{node_name}")
async def api_node_status(node_name: str):
    """Return current status for a specific node."""
    status = monitor.get_status(node_name)
    if status is None:
        raise HTTPException(404, "Node not found or never polled")
    return _status_to_dict(status)


@app.post("/api/poll/{node_name}")
async def api_force_poll(node_name: str):
    """Force an immediate poll of a specific node."""
    status = await monitor.poll_single(node_name)
    return _status_to_dict(status)


@app.get("/api/logs/{node_name}")
async def api_get_logs(node_name: str, path: str = "", lines: int = 200):
    """Retrieve log content or list of log files for a node."""
    try:
        node = config_mgr.get_node(node_name)
        password = config_mgr.get_password(node_name)
    except KeyError:
        raise HTTPException(404, "Node not found")
    if path:
        content = ssh_mgr.tail_log(node, password, path, lines)
    else:
        content = ssh_mgr.list_log_files(node, password)
    return {"content": content, "path": path}


@app.post("/api/dispatch")
async def api_dispatch_job(
    node_name: str = Form(...),
    script_name: str = Form(""),
    use_screen: bool = Form(True),
    screen_name: str = Form(""),
    env_vars: str = Form(""),
):
    """Dispatch a script to a remote node."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.isfile(script_path):
        raise HTTPException(400, f"Script not found: {script_name}")

    parsed_env: dict[str, str] = {}
    if env_vars.strip():
        for line in env_vars.strip().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                parsed_env[k.strip()] = v.strip()

    result = dispatcher.dispatch(
        node_name=node_name,
        local_script_path=script_path,
        use_screen=use_screen,
        screen_name=screen_name or None,
        env_vars=parsed_env or None,
    )
    return result


@app.post("/api/upload-script")
async def api_upload_script(file: UploadFile = File(...)):
    """Upload a bash script to the local scripts directory."""
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    dest = os.path.join(SCRIPTS_DIR, file.filename)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    os.chmod(dest, 0o755)
    return {"success": True, "filename": file.filename}


@app.post("/api/kill-screen/{node_name}/{screen_name}")
async def api_kill_screen(node_name: str, screen_name: str):
    """Kill a screen session on a remote node."""
    result = dispatcher.kill_screen_session(node_name, screen_name)
    return result


# ---------------------------------------------------------------------------
# Node Management
# ---------------------------------------------------------------------------


@app.post("/api/nodes")
async def api_add_node(
    name: str = Form(...),
    hostname: str = Form(...),
    port: int = Form(22),
    user: str = Form(...),
    password: str = Form(...),
    work_dir: str = Form(...),
    venv_activate: str = Form(""),
    gpu_count: int = Form(1),
    network: str = Form("unknown"),
    tags: str = Form(""),
):
    """Add a new node configuration."""
    try:
        config_mgr.add_node(
            name=name,
            hostname=hostname,
            port=port,
            user=user,
            password=password,
            work_dir=work_dir,
            venv_activate=venv_activate or None,
            gpu_count=gpu_count,
            network=network,
            tags=[t.strip() for t in tags.split(",") if t.strip()],
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "message": f"Node '{name}' added"}


@app.delete("/api/nodes/{node_name}")
async def api_remove_node(node_name: str):
    """Remove a node configuration."""
    try:
        config_mgr.remove_node(node_name)
    except KeyError:
        raise HTTPException(404, f"Node '{node_name}' not found")
    return {"success": True, "message": f"Node '{node_name}' removed"}


@app.put("/api/nodes/{node_name}")
async def api_update_node(node_name: str, request: Request):
    """Update an existing node configuration."""
    body = await request.json()
    try:
        config_mgr.update_node(node_name, **body)
    except KeyError:
        raise HTTPException(404, f"Node '{node_name}' not found")
    return {"success": True}
