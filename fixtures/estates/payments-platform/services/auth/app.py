"""Citizen authentication service for the payments platform."""
import hashlib
import random

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
DEVICE_KEY = ec.generate_private_key(ec.SECP256R1())


def session_token(user_id: str, secret: str) -> str:
    return jwt.encode({"sub": user_id}, secret, algorithm="HS256")


def password_hash(password: bytes, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000)
    return kdf.derive(password)


def seal_profile(key: bytes, nonce: bytes, profile: bytes) -> bytes:
    return AESGCM(key).encrypt(nonce, profile, None)


def legacy_checksum(document: bytes) -> str:
    return hashlib.md5(document).hexdigest()


def sign_consent(payload: bytes) -> bytes:
    return SIGNING_KEY.sign(payload, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())


def reset_code() -> str:
    reset_token = "".join(random.choice("0123456789") for _ in range(6))
    return reset_token


def vault() -> Fernet:
    return Fernet(Fernet.generate_key())
