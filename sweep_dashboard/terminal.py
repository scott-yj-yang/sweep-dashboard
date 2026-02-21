"""WebSocket-to-SSH bridge for browser-based terminal access."""

from __future__ import annotations
import asyncio
import logging
import paramiko
from fastapi import WebSocket, WebSocketDisconnect
from .config import NodeConfigManager

logger = logging.getLogger(__name__)


async def websocket_ssh_bridge(
    ws: WebSocket,
    node_name: str,
    config_mgr: NodeConfigManager,
):
    """
    Bridge a WebSocket connection to an SSH shell on the target node.

    Protocol:
      - Client sends text (keystrokes) via WebSocket
      - Server forwards to SSH channel
      - Server reads SSH channel output and sends back via WebSocket
    """
    await ws.accept()

    try:
        node = config_mgr.get_node(node_name)
        password = config_mgr.get_password(node_name)
    except KeyError:
        await ws.send_text(f"\r\nError: Node '{node_name}' not found.\r\n")
        await ws.close()
        return

    # Connect SSH
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            node.hostname, port=node.port, username=node.user,
            password=password, timeout=10,
        )
    except Exception as e:
        await ws.send_text(f"\r\nSSH connection failed: {e}\r\n")
        await ws.close()
        return

    # Open interactive shell
    channel = client.invoke_shell(term="xterm-256color", width=120, height=40)
    channel.settimeout(0.1)

    await ws.send_text(f"\r\nConnected to {node.name} ({node.user}@{node.hostname})\r\n")

    async def read_ssh():
        """Read from SSH channel and send to WebSocket."""
        loop = asyncio.get_event_loop()
        while True:
            try:
                data = await loop.run_in_executor(None, _read_channel, channel)
                if data:
                    await ws.send_text(data)
                else:
                    await asyncio.sleep(0.05)
            except Exception:
                break

    async def write_ssh():
        """Read from WebSocket and send to SSH channel."""
        try:
            while True:
                data = await ws.receive_text()
                if data:
                    channel.send(data)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    read_task = asyncio.create_task(read_ssh())
    write_task = asyncio.create_task(write_ssh())

    try:
        await asyncio.gather(read_task, write_task, return_exceptions=True)
    finally:
        channel.close()
        client.close()
        try:
            await ws.close()
        except Exception:
            pass


def _read_channel(channel) -> str | None:
    """Blocking read from paramiko channel (run in executor)."""
    try:
        if channel.recv_ready():
            return channel.recv(4096).decode(errors="replace")
        return None
    except Exception:
        return None
