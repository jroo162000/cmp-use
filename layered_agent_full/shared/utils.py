import toml, os, json, base64, hashlib
from pathlib import Path
from cryptography.fernet import Fernet

def load_secrets(dir: Path):
    p=dir/"secrets.toml"
    return toml.loads(p.read_text()) if p.exists() else {}

def aes_decrypt(token:bytes, passphrase:str):
    key=hashlib.sha256(passphrase.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key)).decrypt(token)
