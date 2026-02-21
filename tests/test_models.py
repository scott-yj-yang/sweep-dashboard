from sweep_dashboard.models import NodeConfig, NodeStatus, GpuInfo, JobInfo


def test_node_config_creation():
    node = NodeConfig(
        name="test-node",
        hostname="10.0.0.1",
        port=22,
        user="root",
        password_encrypted="gAAAAA...",
        work_dir="/root/project",
        venv_activate="/root/venv/bin/activate",
        gpu_count=2,
        network="infranet",
        tags=["test"],
    )
    assert node.name == "test-node"
    assert node.port == 22
    assert node.gpu_count == 2


def test_node_config_defaults():
    node = NodeConfig(
        name="simple",
        hostname="1.2.3.4",
        user="user",
        password_encrypted="enc",
        work_dir="/home/user/project",
    )
    assert node.port == 22
    assert node.gpu_count == 1
    assert node.network == "unknown"
    assert node.tags == []
    assert node.venv_activate is None


def test_gpu_info():
    gpu = GpuInfo(
        index=0,
        name="RTX 4090",
        utilization_pct=85.0,
        memory_used_mb=20000,
        memory_total_mb=24576,
        temperature_c=72,
    )
    assert gpu.memory_free_mb == 4576


def test_node_status():
    status = NodeStatus(
        node_name="test",
        online=True,
        gpus=[
            GpuInfo(index=0, name="RTX 4090", utilization_pct=50.0,
                    memory_used_mb=10000, memory_total_mb=24576, temperature_c=60)
        ],
        running_jobs=[
            JobInfo(pid=1234, command="python -m vnl_playground.train_highlvl",
                    gpu_index=0, screen_name="sweep_p1a", runtime_seconds=3600)
        ],
        cpu_percent=45.0,
        memory_used_mb=16000,
        memory_total_mb=64000,
        uptime="5 days",
        last_poll_time="2026-02-21T10:00:00",
    )
    assert status.online is True
    assert len(status.gpus) == 1
    assert len(status.running_jobs) == 1


def test_job_info_optional_fields():
    job = JobInfo(pid=5678, command="python train.py")
    assert job.gpu_index is None
    assert job.screen_name is None
    assert job.runtime_seconds is None
