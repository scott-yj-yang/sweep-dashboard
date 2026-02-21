"""Pydantic data models for the sweep dashboard."""

from __future__ import annotations
from pydantic import BaseModel, Field


class NodeConfig(BaseModel):
    """Configuration for a remote compute node."""
    name: str
    hostname: str
    port: int = 22
    user: str
    password_encrypted: str
    work_dir: str
    venv_activate: str | None = None
    gpu_count: int = 1
    network: str = "unknown"
    tags: list[str] = Field(default_factory=list)


class GpuInfo(BaseModel):
    """GPU status from nvidia-smi."""
    index: int
    name: str = "Unknown"
    utilization_pct: float = 0.0
    memory_used_mb: int = 0
    memory_total_mb: int = 0
    temperature_c: int = 0

    @property
    def memory_free_mb(self) -> int:
        return self.memory_total_mb - self.memory_used_mb


class JobInfo(BaseModel):
    """A running training job on a node."""
    pid: int
    command: str
    gpu_index: int | None = None
    screen_name: str | None = None
    runtime_seconds: float | None = None


class NodeStatus(BaseModel):
    """Full status snapshot for a node."""
    node_name: str
    online: bool = False
    error: str | None = None
    gpus: list[GpuInfo] = Field(default_factory=list)
    running_jobs: list[JobInfo] = Field(default_factory=list)
    cpu_percent: float | None = None
    memory_used_mb: int | None = None
    memory_total_mb: int | None = None
    uptime: str | None = None
    last_poll_time: str | None = None


class DispatchRequest(BaseModel):
    """Request to dispatch a job to a node."""
    node_name: str
    script_path: str
    use_screen: bool = True
    screen_name: str | None = None
    gpu_ids: list[int] | None = None
