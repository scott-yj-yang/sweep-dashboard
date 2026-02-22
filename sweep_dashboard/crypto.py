"""Fernet-based password encryption for node configurations."""

import os
from cryptography.fernet import Fernet


def generate_key(key_path: str) -> bytes:
    """Generate a new Fernet key and save to file with restrictive permissions."""
    key = Fernet.generate_key()
    with open(key_path, "wb") as f:
        f.write(key)
    os.chmod(key_path, 0o600)
    return key


def load_key(key_path: str) -> bytes:
    """Load a Fernet key from file."""
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"Key file not found: {key_path}")
    with open(key_path, "rb") as f:
        return f.read().strip()


def encrypt_password(password: str, key: bytes) -> str:
    """Encrypt a plaintext password, returning a Fernet token string."""
    f = Fernet(key)
    return f.encrypt(password.encode()).decode()


def decrypt_password(token: str, key: bytes) -> str:
    """Decrypt a Fernet token back to plaintext password."""
    f = Fernet(key)
    return f.decrypt(token.encode()).decode()
