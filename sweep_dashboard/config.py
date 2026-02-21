"""Node configuration manager with encrypted password storage."""

from __future__ import annotations
import os
import yaml
from .crypto import load_key, encrypt_password, decrypt_password
from .models import NodeConfig


class NodeConfigManager:
    """Manages node configurations persisted to an encrypted YAML file."""

    def __init__(self, config_path: str, key_path: str):
        self._config_path = config_path
        self._key = load_key(key_path)
        self._nodes: dict[str, NodeConfig] = {}
        self._load()

    def _load(self):
        if not os.path.exists(self._config_path):
            self._nodes = {}
            return
        with open(self._config_path) as f:
            data = yaml.safe_load(f) or {}
        self._nodes = {}
        for entry in data.get("nodes", []):
            node = NodeConfig(**entry)
            self._nodes[node.name] = node

    def _save(self):
        data = {"nodes": [n.model_dump() for n in self._nodes.values()]}
        with open(self._config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def list_nodes(self) -> list[NodeConfig]:
        return list(self._nodes.values())

    def get_node(self, name: str) -> NodeConfig:
        if name not in self._nodes:
            raise KeyError(f"Node '{name}' not found")
        return self._nodes[name]

    def get_password(self, name: str) -> str:
        node = self.get_node(name)
        return decrypt_password(node.password_encrypted, self._key)

    def add_node(
        self,
        name: str,
        hostname: str,
        user: str,
        password: str,
        work_dir: str,
        port: int = 22,
        venv_activate: str | None = None,
        gpu_count: int = 1,
        network: str = "unknown",
        tags: list[str] | None = None,
    ):
        if name in self._nodes:
            raise ValueError(f"Node '{name}' already exists")
        enc_password = encrypt_password(password, self._key)
        node = NodeConfig(
            name=name, hostname=hostname, port=port, user=user,
            password_encrypted=enc_password, work_dir=work_dir,
            venv_activate=venv_activate, gpu_count=gpu_count,
            network=network, tags=tags or [],
        )
        self._nodes[name] = node
        self._save()

    def update_node(self, name: str, **kwargs):
        node = self.get_node(name)
        data = node.model_dump()
        if "password" in kwargs:
            kwargs["password_encrypted"] = encrypt_password(kwargs.pop("password"), self._key)
        data.update(kwargs)
        self._nodes[name] = NodeConfig(**data)
        self._save()

    def remove_node(self, name: str):
        if name not in self._nodes:
            raise KeyError(f"Node '{name}' not found")
        del self._nodes[name]
        self._save()
