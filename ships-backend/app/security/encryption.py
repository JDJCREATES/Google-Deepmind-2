"""
Encryption service for securing sensitive data at rest.
"""
import os
from cryptography.fernet import Fernet
from functools import lru_cache

@lru_cache
def get_cipher_suite() -> Fernet:
    """
    Get or create a Fernet cipher suite.
    Uses ENCRYPTION_KEY from env or generates a default (WARNING: ephemeral).
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # For dev: generate key if missing (but log warning)
        # In prod: this should error or prompt
        import logging
        logging.warning("No ENCRYPTION_KEY found! Using ephemeral key (data will move lost on restart)")
        key = Fernet.generate_key().decode()
        
    return Fernet(key.encode() if isinstance(key, str) else key)

def encrypt_token(token: str) -> str:
    """Encrypt a token."""
    if not token:
        return None
    cipher = get_cipher_suite()
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a token."""
    if not encrypted_token:
        return None
    cipher = get_cipher_suite()
    return cipher.decrypt(encrypted_token.encode()).decode()
