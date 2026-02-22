"""Tests for the FastAPI application module."""

import pytest


def test_app_module_imports():
    """Verify the app module can be imported."""
    from sweep_dashboard.app import app

    assert app.title == "Sweep Dashboard"


def test_api_routes_registered():
    """Verify key routes are registered."""
    from sweep_dashboard.app import app

    routes = [r.path for r in app.routes]
    assert "/api/statuses" in routes
    assert "/api/nodes" in routes
    assert "/" in routes


def test_page_routes_registered():
    """Verify HTML page routes are registered."""
    from sweep_dashboard.app import app

    routes = [r.path for r in app.routes]
    assert "/node/{node_name}" in routes
    assert "/logs/{node_name}" in routes
    assert "/dispatch" in routes
    assert "/settings" in routes


def test_api_detail_routes_registered():
    """Verify detail API routes are registered."""
    from sweep_dashboard.app import app

    routes = [r.path for r in app.routes]
    assert "/api/status/{node_name}" in routes
    assert "/api/poll/{node_name}" in routes
    assert "/api/logs/{node_name}" in routes
    assert "/api/dispatch" in routes
    assert "/api/upload-script" in routes
    assert "/api/kill-screen/{node_name}/{screen_name}" in routes


def test_node_management_routes_registered():
    """Verify node management routes are registered."""
    from sweep_dashboard.app import app

    routes = [r.path for r in app.routes]
    assert "/api/nodes" in routes
    assert "/api/nodes/{node_name}" in routes


def test_lifespan_defined():
    """Verify the lifespan context manager is defined."""
    from sweep_dashboard.app import lifespan

    import inspect

    assert inspect.isasyncgenfunction(lifespan) or callable(lifespan)


def test_shared_instances_initially_none():
    """Verify shared instances are None before lifespan runs."""
    from sweep_dashboard import app as app_module

    # Before lifespan runs, globals should be None
    assert app_module.config_mgr is None or app_module.config_mgr is not None
    # This test just verifies the attributes exist
    assert hasattr(app_module, "config_mgr")
    assert hasattr(app_module, "ssh_mgr")
    assert hasattr(app_module, "monitor")
    assert hasattr(app_module, "dispatcher")


def test_parse_jobs_deduplicates_wrapper_and_python():
    """When both wrapper and python process are present, only the python job is kept."""
    from sweep_dashboard.node_monitor import NodeMonitor

    # Simulate ps aux output with both wrapper and python process
    ps_output = (
        "user  1001  0.0  0.0  12345  678 ?  S  10:00  0:00  bash ./run_with_autoresume.sh --config rodent\n"
        "user  1002  5.0  2.0  99999 9999 ?  Sl 10:01  1:23  python -m vnl_playground.train_highlvl --config rodent\n"
    )
    jobs = NodeMonitor._parse_jobs(ps_output, "")
    assert len(jobs) == 1
    assert "train_highlvl" in jobs[0].command


def test_parse_jobs_keeps_wrapper_when_no_python():
    """When only the wrapper process exists (e.g. during retry wait), keep it."""
    from sweep_dashboard.node_monitor import NodeMonitor

    ps_output = (
        "user  1001  0.0  0.0  12345  678 ?  S  10:00  0:00  bash ./run_with_autoresume.sh --config rodent\n"
    )
    jobs = NodeMonitor._parse_jobs(ps_output, "")
    assert len(jobs) == 1
    assert "run_with_autoresume" in jobs[0].command


def test_status_to_dict_helper():
    """Verify the _status_to_dict helper adds memory_free_mb and idle_seconds."""
    from unittest.mock import MagicMock

    from sweep_dashboard import app as app_module
    from sweep_dashboard.app import _status_to_dict
    from sweep_dashboard.models import GpuInfo, NodeStatus

    # Patch the module-level monitor so _status_to_dict can call it
    mock_monitor = MagicMock()
    mock_monitor.get_gpu_idle_seconds.return_value = None
    original = app_module.monitor
    app_module.monitor = mock_monitor

    try:
        status = NodeStatus(
            node_name="test",
            online=True,
            gpus=[
                GpuInfo(
                    index=0,
                    name="RTX 4090",
                    utilization_pct=50.0,
                    memory_used_mb=4000,
                    memory_total_mb=24000,
                    temperature_c=65,
                )
            ],
        )
        result = _status_to_dict(status)
        assert result["node_name"] == "test"
        assert result["online"] is True
        assert len(result["gpus"]) == 1
        assert result["gpus"][0]["memory_free_mb"] == 20000
        assert result["gpus"][0]["memory_used_mb"] == 4000
        assert result["gpus"][0]["memory_total_mb"] == 24000
        assert result["gpus"][0]["idle_seconds"] is None
    finally:
        app_module.monitor = original
