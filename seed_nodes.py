#!/usr/bin/env python3
"""One-time script to seed initial node configurations.

Usage:
    python seed_nodes.py

You will be prompted for each node's password interactively.
"""
import os
import sys
import getpass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sweep_dashboard.crypto import generate_key
from sweep_dashboard.config import NodeConfigManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(BASE_DIR, "master_key.txt")
CONFIG_PATH = os.path.join(BASE_DIR, "nodes.yaml")

# Generate key if needed
if not os.path.exists(KEY_PATH):
    print(f"Generating new master key: {KEY_PATH}")
    generate_key(KEY_PATH)

mgr = NodeConfigManager(CONFIG_PATH, KEY_PATH)

NODES = [
    {
        "name": "Salk-Scott-Linux",
        "hostname": "100.76.192.27",
        "port": 22,
        "user": "talmolab",
        "work_dir": "/home/talmolab/Desktop/SalkResearch/vnl-playground",
        "venv_activate": "/home/talmolab/Desktop/SalkResearch/mimic-mjx/bin/activate",
        "gpu_count": 2,
        "network": "tailscale",
        "tags": ["local"],
    },
    {
        "name": "Salk-Robot-Linux",
        "hostname": "100.65.172.40",
        "port": 22,
        "user": "talmolab",
        "work_dir": "",
        "venv_activate": "",
        "gpu_count": 1,
        "network": "tailscale",
        "tags": ["salk"],
    },
    {
        "name": "Divya-Salk-Linux",
        "hostname": "100.99.97.102",
        "port": 22,
        "user": "scott",
        "work_dir": "",
        "venv_activate": "",
        "gpu_count": 1,
        "network": "tailscale",
        "tags": ["salk"],
    },
    {
        "name": "runai-1gpu-node1",
        "hostname": "10.7.30.112",
        "port": 30101,
        "user": "root",
        "work_dir": "",
        "venv_activate": "",
        "gpu_count": 1,
        "network": "infranet",
        "tags": ["runai", "1gpu"],
    },
    {
        "name": "runai-2gpus-node1",
        "hostname": "10.7.30.114",
        "port": 30999,
        "user": "root",
        "work_dir": "",
        "venv_activate": "",
        "gpu_count": 2,
        "network": "infranet",
        "tags": ["runai", "2gpu"],
    },
    {
        "name": "runai-2gpus-node2",
        "hostname": "10.7.30.114",
        "port": 31000,
        "user": "root",
        "work_dir": "",
        "venv_activate": "",
        "gpu_count": 2,
        "network": "infranet",
        "tags": ["runai", "2gpu"],
    },
    {
        "name": "runai-2gpus-node3",
        "hostname": "10.7.30.112",
        "port": 31002,
        "user": "root",
        "work_dir": "",
        "venv_activate": "",
        "gpu_count": 2,
        "network": "infranet",
        "tags": ["runai", "2gpu"],
    },
]


def main():
    print("=== Sweep Dashboard: Node Seeding ===\n")

    for node_def in NODES:
        name = node_def["name"]

        # Skip if already exists
        try:
            mgr.get_node(name)
            print(f"  [{name}] Already exists, skipping.")
            continue
        except KeyError:
            pass

        print(f"\n--- {name} ({node_def['hostname']}:{node_def['port']}) ---")

        # Ask for missing fields
        if not node_def["work_dir"]:
            node_def["work_dir"] = input(f"  Work directory for {name}: ").strip()
        if not node_def["venv_activate"]:
            node_def["venv_activate"] = (
                input(f"  Venv activate path for {name} (empty to skip): ").strip()
                or None
            )

        password = getpass.getpass(f"  SSH password for {node_def['user']}@{name}: ")

        mgr.add_node(password=password, **node_def)
        print(f"  Added {name}")

    print(f"\nDone! {len(mgr.list_nodes())} nodes configured.")
    print(f"Config saved to: {CONFIG_PATH}")


if __name__ == "__main__":
    main()
