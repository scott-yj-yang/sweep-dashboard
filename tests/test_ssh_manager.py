import pytest
from unittest.mock import patch, MagicMock
from sweep_dashboard.ssh_manager import SSHManager
from sweep_dashboard.models import NodeConfig


@pytest.fixture
def node():
    return NodeConfig(
        name="test",
        hostname="10.0.0.1",
        port=22,
        user="root",
        password_encrypted="irrelevant",
        work_dir="/root/project",
    )


@patch("sweep_dashboard.ssh_manager.paramiko.SSHClient")
def test_execute_command(mock_ssh_cls, node):
    mock_client = MagicMock()
    mock_ssh_cls.return_value = mock_client
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = b"hello world\n"
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = b""
    mock_client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

    mgr = SSHManager()
    exit_code, stdout, stderr = mgr.execute(node, "echo hello", password="secret")
    assert exit_code == 0
    assert stdout == "hello world\n"
    mock_client.connect.assert_called_once_with(
        "10.0.0.1", port=22, username="root", password="secret", timeout=10,
    )


@patch("sweep_dashboard.ssh_manager.paramiko.SSHClient")
def test_execute_command_failure(mock_ssh_cls, node):
    mock_client = MagicMock()
    mock_ssh_cls.return_value = mock_client
    mock_client.connect.side_effect = Exception("Connection refused")

    mgr = SSHManager()
    exit_code, stdout, stderr = mgr.execute(node, "echo hello", password="secret")
    assert exit_code == -1
    assert "Connection refused" in stderr


def test_parse_nvidia_smi():
    raw = (
        "0, NVIDIA GeForce RTX 4090, 85, 20000, 24576, 72\n"
        "1, NVIDIA GeForce RTX 4090, 30, 5000, 24576, 55\n"
    )
    mgr = SSHManager()
    gpus = mgr.parse_nvidia_smi(raw)
    assert len(gpus) == 2
    assert gpus[0].index == 0
    assert gpus[0].utilization_pct == 85.0
    assert gpus[0].memory_used_mb == 20000
    assert gpus[1].temperature_c == 55


def test_parse_nvidia_smi_empty():
    mgr = SSHManager()
    gpus = mgr.parse_nvidia_smi("")
    assert gpus == []


def test_parse_screen_sessions():
    raw = (
        "There are screens on:\n"
        "\t12345.sweep_p1a\t(02/21/2026 10:00:00 AM)\t(Detached)\n"
        "\t67890.sweep_p2b\t(02/21/2026 11:00:00 AM)\t(Detached)\n"
        "2 Sockets in /run/screen/S-root.\n"
    )
    mgr = SSHManager()
    sessions = mgr.parse_screen_sessions(raw)
    assert len(sessions) == 2
    assert sessions[0] == ("12345", "sweep_p1a")
    assert sessions[1] == ("67890", "sweep_p2b")
