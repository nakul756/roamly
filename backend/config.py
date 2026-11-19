"""Paths and settings. Reads an optional .env file in the project root (see .env.example).
Real environment variables always win over .env."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def _load_env():
    p = BASE / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()
CSV = BASE / "data" / "europe_travel_dataset_v2.csv"
DB_DIR = Path(os.getenv("TRAVEL_DATA_DIR", BASE / "data"))   # where travel.db and chat.db live
DB_DIR.mkdir(parents=True, exist_ok=True)
MODELS = BASE / "models"
FRONTEND = BASE / "frontend"
