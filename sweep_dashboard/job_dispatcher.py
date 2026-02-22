"""Remote job dispatch — copy scripts and launch via screen or nohup."""

from __future__ import annotations
import os
import logging
from datetime import datetime
from .config import NodeConfigManager
from .ssh_manager import SSHManager

logger = logging.getLogger(__name__)


class JobDispatcher:
    """Dispatches sweep scripts to remote nodes."""

    def __init__(self, config_manager: NodeConfigManager, ssh_manager: SSHManager):
        self._config = config_manager
        self._ssh = ssh_manager

    def dispatch(
        self,
        node_name: str,
        local_script_path: str,
        use_screen: bool = True,
        screen_name: str | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> dict:
        """
        Dispatch a bash script to a remote node.

        1. Copies the script to the node's work_dir/dispatched_scripts/
        2. Launches it via screen (detached) or nohup

        Returns dict with status, remote_path, and any output.
        """
        node = self._config.get_node(node_name)
        password = self._config.get_password(node_name)

        if not os.path.isfile(local_script_path):
            return {"success": False, "error": f"Script not found: {local_script_path}"}

        script_basename = os.path.basename(local_script_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote_dir = f"{node.work_dir}/dispatched_scripts"
        remote_path = f"{remote_dir}/{timestamp}_{script_basename}"

        self._ssh.execute(node, f"mkdir -p {remote_dir}", password)

        try:
            self._ssh.scp_file(node, password, local_script_path, remote_path)
        except Exception as e:
            return {"success": False, "error": f"SCP failed: {e}"}

        self._ssh.execute(node, f"chmod +x {remote_path}", password)

        activate = ""
        if node.venv_activate:
            activate = f"source {node.venv_activate} && "

        cd_cmd = f"cd {node.work_dir} && "

        env_prefix = ""
        if env_vars:
            env_prefix = " ".join(f"{k}={v}" for k, v in env_vars.items()) + " "

        if use_screen:
            sname = screen_name or f"sweep_{timestamp}"
            log_file = f"{node.work_dir}/dispatched_scripts/{sname}.log"
            launch_cmd = (
                f"screen -dmS {sname} bash -c '"
                f"{activate}{cd_cmd}{env_prefix}bash {remote_path} "
                f"> {log_file} 2>&1'"
            )
        else:
            log_file = f"{node.work_dir}/dispatched_scripts/{timestamp}_{script_basename}.log"
            launch_cmd = (
                f"nohup bash -c '{activate}{cd_cmd}{env_prefix}bash {remote_path}' "
                f"> {log_file} 2>&1 &"
            )

        code, stdout, stderr = self._ssh.execute(node, launch_cmd, password, timeout=15)

        if code == 0 or (code == -1 and not stderr):
            return {
                "success": True,
                "node": node_name,
                "remote_script": remote_path,
                "log_file": log_file,
                "screen_name": sname if use_screen else None,
                "message": f"Job dispatched to {node_name}",
            }
        else:
            return {"success": False, "error": f"Launch failed (exit={code}): {stderr}"}

    def kill_screen_session(self, node_name: str, screen_name: str) -> dict:
        node = self._config.get_node(node_name)
        password = self._config.get_password(node_name)
        code, stdout, stderr = self._ssh.execute(
            node, f"screen -S {screen_name} -X quit", password
        )
        return {"success": code == 0, "message": f"Killed {screen_name}" if code == 0 else stderr}

    def list_dispatched_scripts(self, node_name: str) -> list[str]:
        node = self._config.get_node(node_name)
        password = self._config.get_password(node_name)
        cmd = f"ls -t {node.work_dir}/dispatched_scripts/*.sh 2>/dev/null | head -20"
        code, stdout, _ = self._ssh.execute(node, cmd, password)
        if code != 0:
            return []
        return [l.strip() for l in stdout.strip().splitlines() if l.strip()]
