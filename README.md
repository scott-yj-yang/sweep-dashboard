# Sweep Dashboard

Web-based dashboard to monitor, manage, and dispatch RL training sweep jobs across a heterogeneous GPU cluster.

## Features

- Real-time cluster overview with node health, GPU utilization, and running jobs
- Per-node GPU monitoring (utilization, VRAM, temperature) via `nvidia-smi`
- Remote log viewer with auto-refresh
- Job dispatch -- upload and launch sweep scripts to any node via `screen`/`nohup`
- Browser-based SSH terminal (xterm.js) for quick node access
- Node management -- add, remove, and configure nodes via the web UI
- Encrypted password storage (Fernet symmetric encryption)
- Configurable per-node working directories and virtual environments

## Architecture

The dashboard is a single-server application built on **FastAPI + Jinja2 + vanilla JS**.
It connects to remote nodes over SSH using **paramiko** -- no agents, daemons, or
additional software is required on the compute nodes. A background polling loop
queries each node for GPU stats, running processes, and system health every 30 seconds.

## Quick Start

```bash
# Clone the repository
git clone <repo-url> && cd sweep-dashboard

# Install dependencies
source /path/to/your/venv/bin/activate
uv pip install -r requirements.txt

# Seed initial node configurations (interactive -- prompts for passwords)
python seed_nodes.py

# Launch the dashboard
./run_dashboard.sh
# Open http://localhost:8050
```

## Node Setup

Each node requires:

- **SSH access** with password authentication (key-based auth is not yet supported)
- A **working directory** (`work_dir`) where scripts are copied and executed
- Optionally, a **virtualenv activate path** (`venv_activate`) to source before running jobs

Nodes can be added interactively via `seed_nodes.py` or through the Settings page
in the web UI. Passwords are encrypted at rest with a Fernet key stored in
`master_key.txt` (auto-generated on first run).

## Writing Sweep Scripts

Sweep scripts are self-contained bash files that run one or more training experiments.
The dashboard copies each script to the target node and launches it inside a `screen`
session.

See [SWEEP_SCRIPT_PROTOCOL.md](SWEEP_SCRIPT_PROTOCOL.md) for the full specification,
including required structure, environment variables, GPU scheduling patterns, and
naming conventions.

## Project Structure

```
sweep-dashboard/
├── run_dashboard.sh                # Launch script
├── seed_nodes.py                   # Interactive node seeding
├── requirements.txt                # Python dependencies
├── SWEEP_SCRIPT_PROTOCOL.md        # Sweep script authoring guide
├── scripts/                        # Uploaded sweep scripts (gitkeep)
├── sweep_dashboard/
│   ├── __init__.py
│   ├── app.py                      # FastAPI routes and lifespan
│   ├── config.py                   # Node config manager (YAML + Fernet)
│   ├── crypto.py                   # Key generation and encryption helpers
│   ├── job_dispatcher.py           # Script upload and remote execution
│   ├── models.py                   # Pydantic models (NodeConfig, GpuInfo, etc.)
│   ├── node_monitor.py             # Background SSH polling loop
│   ├── ssh_manager.py              # Paramiko SSH wrapper
│   ├── terminal.py                 # WebSocket-to-SSH bridge (xterm.js)
│   ├── static/
│   │   ├── dashboard.js            # Client-side polling and UI updates
│   │   └── style.css
│   └── templates/
│       ├── base.html
│       ├── dashboard.html           # Cluster overview
│       ├── dispatch.html            # Job dispatch form
│       ├── logs.html                # Remote log viewer
│       ├── node_detail.html         # Single-node detail view
│       ├── settings.html            # Node management
│       └── terminal.html            # In-browser SSH terminal
└── tests/
    ├── test_app.py
    ├── test_config.py
    ├── test_crypto.py
    ├── test_models.py
    └── test_ssh_manager.py
```

## Tech Stack

| Component       | Library / Tool                       |
|-----------------|--------------------------------------|
| Web framework   | FastAPI + Uvicorn                    |
| Templating      | Jinja2                               |
| SSH             | paramiko                             |
| Encryption      | cryptography (Fernet)                |
| Data models     | Pydantic v2                          |
| Terminal        | xterm.js (via WebSocket)             |
| Frontend        | Vanilla JS + CSS                     |
| File uploads    | python-multipart + aiofiles          |

## License

Internal project -- not currently published under an open-source license.
