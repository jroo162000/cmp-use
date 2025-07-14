import os
import json
import toml
import base64
import hashlib
from cryptography.fernet import Fernet

CONFIG_PATH = os.path.expanduser("~/.config/jarvis_agent/config.toml")

def load_config():
    if os.path.exists(CONFIG_PATH):
        return toml.load(CONFIG_PATH)
    return {}

config = load_config()

def aes_encrypt(data: bytes, passphrase: str) -> bytes:
    key = hashlib.sha256(passphrase.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key)).encrypt(data)

def aes_decrypt(token: bytes, passphrase: str) -> bytes:
    key = hashlib.sha256(passphrase.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key)).decrypt(token)

def get_llm():
    if config.get('use_local_model'):
        from models.local_model import LocalLLM
        return LocalLLM()
    import openai
    openai.api_key = os.getenv('OPENAI_API_KEY')
    return openai
