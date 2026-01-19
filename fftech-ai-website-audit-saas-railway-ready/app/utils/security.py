import os, hmac, hashlib
from typing import Tuple

def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
    if not salt:
        salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), 100_000)
    return dk.hex(), salt

def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    calc, _ = hash_password(password, salt)
    return hmac.compare_digest(calc, stored_hash)
