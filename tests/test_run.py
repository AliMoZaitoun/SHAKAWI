import os
import pytest

from run import configure_bot_api_url, runtime_port


def test_runtime_port_defaults_to_local_port(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert runtime_port() == 5000


def test_runtime_port_uses_render_port(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    assert runtime_port() == 10000


def test_bot_api_url_uses_local_render_port_unless_overridden(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:5000/api/v1")
    configure_bot_api_url(10000)
    assert os.environ["API_BASE_URL"] == "http://127.0.0.1:10000/api/v1"

    monkeypatch.setenv("API_BASE_URL", "https://shakawi.onrender.com/api/v1")
    configure_bot_api_url(20000)
    assert os.environ["API_BASE_URL"] == "https://shakawi.onrender.com/api/v1"


def test_runtime_port_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("PORT", "not-a-port")
    with pytest.raises(RuntimeError, match="PORT"):
        runtime_port()
