import os
import tempfile
import pytest
from sweep_dashboard.config import NodeConfigManager
from sweep_dashboard.crypto import generate_key


@pytest.fixture
def tmp_env():
    """Create temporary key and config files."""
    tmpdir = tempfile.mkdtemp()
    key_path = os.path.join(tmpdir, "master_key.txt")
    config_path = os.path.join(tmpdir, "nodes.yaml")
    key = generate_key(key_path)
    return tmpdir, key_path, config_path


def test_add_and_list_nodes(tmp_env):
    _, key_path, config_path = tmp_env
    mgr = NodeConfigManager(config_path, key_path)
    mgr.add_node(
        name="test-node",
        hostname="10.0.0.1",
        user="root",
        password="secret123",
        work_dir="/root/project",
    )
    nodes = mgr.list_nodes()
    assert len(nodes) == 1
    assert nodes[0].name == "test-node"
    assert nodes[0].hostname == "10.0.0.1"
    assert nodes[0].password_encrypted != "secret123"


def test_get_decrypted_password(tmp_env):
    _, key_path, config_path = tmp_env
    mgr = NodeConfigManager(config_path, key_path)
    mgr.add_node(name="n1", hostname="1.2.3.4", user="u", password="hunter2",
                 work_dir="/tmp")
    password = mgr.get_password("n1")
    assert password == "hunter2"


def test_remove_node(tmp_env):
    _, key_path, config_path = tmp_env
    mgr = NodeConfigManager(config_path, key_path)
    mgr.add_node(name="n1", hostname="1.1.1.1", user="u", password="p", work_dir="/tmp")
    mgr.add_node(name="n2", hostname="2.2.2.2", user="u", password="p", work_dir="/tmp")
    assert len(mgr.list_nodes()) == 2
    mgr.remove_node("n1")
    nodes = mgr.list_nodes()
    assert len(nodes) == 1
    assert nodes[0].name == "n2"


def test_update_node(tmp_env):
    _, key_path, config_path = tmp_env
    mgr = NodeConfigManager(config_path, key_path)
    mgr.add_node(name="n1", hostname="1.1.1.1", user="u", password="p",
                 work_dir="/old/path")
    mgr.update_node("n1", work_dir="/new/path", gpu_count=4)
    node = mgr.get_node("n1")
    assert node.work_dir == "/new/path"
    assert node.gpu_count == 4


def test_persistence(tmp_env):
    _, key_path, config_path = tmp_env
    mgr1 = NodeConfigManager(config_path, key_path)
    mgr1.add_node(name="persist", hostname="5.5.5.5", user="u", password="pw",
                  work_dir="/tmp")
    mgr2 = NodeConfigManager(config_path, key_path)
    nodes = mgr2.list_nodes()
    assert len(nodes) == 1
    assert nodes[0].name == "persist"
    assert mgr2.get_password("persist") == "pw"


def test_duplicate_name_raises(tmp_env):
    _, key_path, config_path = tmp_env
    mgr = NodeConfigManager(config_path, key_path)
    mgr.add_node(name="dup", hostname="1.1.1.1", user="u", password="p", work_dir="/tmp")
    with pytest.raises(ValueError, match="already exists"):
        mgr.add_node(name="dup", hostname="2.2.2.2", user="u", password="p",
                     work_dir="/tmp")
