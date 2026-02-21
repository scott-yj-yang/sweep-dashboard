import os
import tempfile
import pytest
from sweep_dashboard.crypto import generate_key, load_key, encrypt_password, decrypt_password


def test_generate_and_load_key():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as f:
        key_path = f.name
    try:
        key = generate_key(key_path)
        assert isinstance(key, bytes)
        loaded = load_key(key_path)
        assert key == loaded
        mode = oct(os.stat(key_path).st_mode)[-3:]
        assert mode == "600"
    finally:
        os.unlink(key_path)


def test_encrypt_decrypt_roundtrip():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as f:
        key_path = f.name
    try:
        key = generate_key(key_path)
        original = "my_secret_password_123!"
        encrypted = encrypt_password(original, key)
        assert encrypted != original
        assert encrypted.startswith("gAAAAA")
        decrypted = decrypt_password(encrypted, key)
        assert decrypted == original
    finally:
        os.unlink(key_path)


def test_load_key_missing_file():
    with pytest.raises(FileNotFoundError):
        load_key("/nonexistent/key.txt")
