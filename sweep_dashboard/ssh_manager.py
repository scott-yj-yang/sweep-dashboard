"""SSH connection management for remote node operations."""

from __future__ import annotations
import re
import paramiko
from .models import NodeConfig, GpuInfo


class SSHManager:
    """Execute commands on remote nodes via SSH."""

    def __init__(self, timeout: int = 10):
        self._timeout = timeout

    def execute(
        self, node: NodeConfig, command: str, password: str,
        timeout: int | None = None,
    ) -> tuple[int, str, str]:
        """Execute a command on a remote node. Returns (exit_code, stdout, stderr)."""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                node.hostname, port=node.port, username=node.user,
                password=password, timeout=timeout or self._timeout,
            )
            _, stdout_ch, stderr_ch = client.exec_command(command, timeout=timeout or 30)
            exit_code = stdout_ch.channel.recv_exit_status()
            stdout = stdout_ch.read().decode(errors="replace")
            stderr = stderr_ch.read().decode(errors="replace")
            client.close()
            return exit_code, stdout, stderr
        except Exception as e:
            return -1, "", str(e)

    def check_online(self, node: NodeConfig, password: str) -> bool:
        code, _, _ = self.execute(node, "echo ok", password, timeout=5)
        return code == 0

    def get_gpu_info(self, node: NodeConfig, password: str) -> list[GpuInfo]:
        cmd = (
            "nvidia-smi --query-gpu=index,name,utilization.gpu,"
            "memory.used,memory.total,temperature.gpu "
            "--format=csv,noheader,nounits"
        )
        code, stdout, _ = self.execute(node, cmd, password)
        if code != 0:
            return []
        return self.parse_nvidia_smi(stdout)

    def get_system_info(self, node: NodeConfig, password: str) -> dict:
        cmd = (
            "echo '---CPU---' && "
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' && "
            "echo '---MEM---' && "
            "free -m | awk '/Mem:/{print $3,$2}' && "
            "echo '---UPTIME---' && "
            "uptime -p"
        )
        code, stdout, _ = self.execute(node, cmd, password)
        if code != 0:
            return {}
        result = {}
        sections = stdout.split("---")
        for i, section in enumerate(sections):
            section = section.strip()
            if section == "CPU" and i + 1 < len(sections):
                try:
                    result["cpu_percent"] = float(sections[i + 1].strip())
                except (ValueError, IndexError):
                    pass
            elif section == "MEM" and i + 1 < len(sections):
                try:
                    parts = sections[i + 1].strip().split()
                    result["memory_used_mb"] = int(parts[0])
                    result["memory_total_mb"] = int(parts[1])
                except (ValueError, IndexError):
                    pass
            elif section == "UPTIME" and i + 1 < len(sections):
                result["uptime"] = sections[i + 1].strip()
        return result

    def get_running_training_jobs(self, node: NodeConfig, password: str) -> str:
        cmd = "ps aux | grep '[p]ython.*train_highlvl\\|[r]un_with_autoresume' || true"
        code, stdout, _ = self.execute(node, cmd, password)
        return stdout if code == 0 else ""

    def get_screen_sessions(self, node: NodeConfig, password: str) -> str:
        code, stdout, _ = self.execute(node, "screen -ls 2>&1 || true", password)
        return stdout if code == 0 else ""

    def tail_log(self, node: NodeConfig, password: str, log_path: str, lines: int = 100) -> str:
        cmd = f"tail -n {lines} {log_path} 2>&1"
        code, stdout, _ = self.execute(node, cmd, password, timeout=15)
        return stdout

    def list_log_files(self, node: NodeConfig, password: str) -> str:
        cmd = (
            f"find {node.work_dir} -maxdepth 1 -name 'training_attempt_*.log' "
            f"-printf '%T@ %p\\n' 2>/dev/null | sort -rn | head -20 | "
            f"awk '{{print $2}}'"
        )
        code, stdout, _ = self.execute(node, cmd, password, timeout=10)
        return stdout if code == 0 else ""

    def scp_file(self, node: NodeConfig, password: str, local_path: str, remote_path: str):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            node.hostname, port=node.port, username=node.user,
            password=password, timeout=self._timeout,
        )
        sftp = client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()
        client.close()

    @staticmethod
    def parse_nvidia_smi(raw: str) -> list[GpuInfo]:
        gpus = []
        for line in raw.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 6:
                continue
            try:
                gpus.append(GpuInfo(
                    index=int(parts[0]), name=parts[1],
                    utilization_pct=float(parts[2]),
                    memory_used_mb=int(parts[3]),
                    memory_total_mb=int(parts[4]),
                    temperature_c=int(parts[5]),
                ))
            except (ValueError, IndexError):
                continue
        return gpus

    @staticmethod
    def parse_screen_sessions(raw: str) -> list[tuple[str, str]]:
        sessions = []
        for match in re.finditer(r"\t(\d+)\.(\S+)\t", raw):
            sessions.append((match.group(1), match.group(2)))
        return sessions
