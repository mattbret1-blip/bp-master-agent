"""API smoke tests — run without provider credentials.

/health and the index page must work with zero configuration.
/ready must fail closed (503) rather than crash when no provider is configured.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from web.app import create_app

client = TestClient(create_app(), raise_server_exceptions=False)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_index_serves_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_ready_without_credentials_is_503():
    response = client.get("/ready")
    assert response.status_code == 503
