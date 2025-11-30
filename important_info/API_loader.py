from dotenv import load_dotenv
import os
from pathlib import Path

env_path = Path(__file__).resolve().parent/ ".env"
load_dotenv(dotenv_path=env_path)

def env(key : str) -> str:
    value = os.getenv(key)
    if value is None:
        raise KeyError(f"Environment variable {key} not found.")
    return value