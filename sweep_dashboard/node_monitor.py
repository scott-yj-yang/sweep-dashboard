"""Background node health monitoring."""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from .config import NodeConfigManager
from .ssh_manager import SSHManager
from .models import NodeConfig, NodeStatus, JobInfo

logger = logging.getLogger(__name__)


class NodeMonitor:
    """Polls all configured nodes for health data on a background loop."""

    def __init__(
        self,
        config_manager: NodeConfigManager,
        ssh_manager: SSHManager,
        poll_interval: int = 30,
        max_workers: int = 8,
    ):
        self._config = config_manager
        self._ssh = ssh_manager
        self._poll_interval = poll_interval
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._statuses: dict[str, NodeStatus] = {}
        self._running = False

    @property
    def statuses(self) -> dict[str, NodeStatus]:
        return dict(self._statuses)

    def get_status(self, node_name: str) -> NodeStatus | None:
        return self._statuses.get(node_name)

    async def start(self):
        """Start the background polling loop."""
        self._running = True
        logger.info("Node monitor started (interval=%ds)", self._poll_interval)
        while self._running:
            await self._poll_all()
            await asyncio.sleep(self._poll_interval)

    def stop(self):
        self._running = False

    async def poll_single(self, node_name: str) -> NodeStatus:
        """Force-poll a single node and update cache."""
        nodes = self._config.list_nodes()
        node = next((n for n in nodes if n.name == node_name), None)
        if node is None:
            return NodeStatus(node_name=node_name, online=False, error="Node not found")
        status = await self._poll_node(node)
        self._statuses[node.name] = status
        return status

    async def _poll_all(self):
        """Poll all nodes concurrently."""
        nodes = self._config.list_nodes()
        if not nodes:
            return
        tasks = [self._poll_node(node) for node in nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for node, result in zip(nodes, results):
            if isinstance(result, Exception):
                self._statuses[node.name] = NodeStatus(
                    node_name=node.name, online=False, error=str(result),
                    last_poll_time=datetime.now(timezone.utc).isoformat(),
                )
            else:
                self._statuses[node.name] = result

    async def _poll_node(self, node: NodeConfig) -> NodeStatus:
        """Poll a single node (runs SSH commands in thread pool)."""
        loop = asyncio.get_event_loop()
        try:
            password = self._config.get_password(node.name)
        except Exception as e:
            return NodeStatus(
                node_name=node.name, online=False, error=f"Password error: {e}",
                last_poll_time=datetime.now(timezone.utc).isoformat(),
            )

        try:
            gpu_info = await loop.run_in_executor(
                self._executor, self._ssh.get_gpu_info, node, password
            )
            sys_info = await loop.run_in_executor(
                self._executor, self._ssh.get_system_info, node, password
            )
            jobs_raw = await loop.run_in_executor(
                self._executor, self._ssh.get_running_training_jobs, node, password
            )
            screen_raw = await loop.run_in_executor(
                self._executor, self._ssh.get_screen_sessions, node, password
            )

            running_jobs = self._parse_jobs(jobs_raw, screen_raw)

            return NodeStatus(
                node_name=node.name,
                online=True,
                gpus=gpu_info,
                running_jobs=running_jobs,
                cpu_percent=sys_info.get("cpu_percent"),
                memory_used_mb=sys_info.get("memory_used_mb"),
                memory_total_mb=sys_info.get("memory_total_mb"),
                uptime=sys_info.get("uptime"),
                last_poll_time=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            return NodeStatus(
                node_name=node.name, online=False, error=str(e),
                last_poll_time=datetime.now(timezone.utc).isoformat(),
            )

    @staticmethod
    def _parse_jobs(ps_output: str, screen_output: str) -> list[JobInfo]:
        """Parse ps and screen output into JobInfo list."""
        jobs = []
        screen_sessions = SSHManager.parse_screen_sessions(screen_output)
        for line in ps_output.strip().splitlines():
            parts = line.split()
            if len(parts) < 11:
                continue
            try:
                pid = int(parts[1])
                command = " ".join(parts[10:])
                jobs.append(JobInfo(pid=pid, command=command))
            except (ValueError, IndexError):
                continue
        return jobs
