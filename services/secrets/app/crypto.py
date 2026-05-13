from cryptography.fernet import Fernet


def build_fernet(key: str) -> Fernet:
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(fernet: Fernet, value: str) -> bytes:
    return fernet.encrypt(value.encode("utf-8"))


def decrypt(fernet: Fernet, ciphertext: bytes) -> str:
    return fernet.decrypt(ciphertext).decode("utf-8")
