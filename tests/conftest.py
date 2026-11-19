import os
import sys
import tempfile
from pathlib import Path

os.environ["TRAVEL_DATA_DIR"] = tempfile.mkdtemp(prefix="travel-test-")   # tests never touch your real database
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("LLM_BASE_URL", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def main():
    import main as m
    return m


@pytest.fixture()
def client(main):
    """A fresh, logged-in user for each test."""
    main.limiter._h.clear()   # each test starts with clean rate-limit counters
    c = TestClient(main.app)
    email = f"user{os.urandom(4).hex()}@example.com"
    r = c.post("/api/register", json={"name": "Tester", "email": email, "password": "correct-horse-9"})
    assert r.status_code == 200, r.text
    c.email = email
    return c


@pytest.fixture()
def anon(main):
    main.limiter._h.clear()
    return TestClient(main.app)
