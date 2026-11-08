"""SPA delivery must never turn failed API/file requests into successful HTML."""
from pathlib import Path
from test_app import system
import app.main as main


def test_spa_deep_links_preserve_api_and_legacy_routes(system, tmp_path, monkeypatch):
    client, _ = system
    build = tmp_path / "react-build"
    build.mkdir()
    (build / "index.html").write_text("<html><body>react-entry-test</body></html>")
    monkeypatch.setattr(main, "FRONTEND_DIST", build)
    monkeypatch.delenv("SHAKWA_UI", raising=False)
    Path("static").mkdir(exist_ok=True)
    Path("static/index.html").write_text("<html><body>legacy-entry-test</body></html>")
    assert "react-entry-test" in client.get("/").text
    assert "react-entry-test" in client.get("/employee/complaints/123").text
    assert "legacy-entry-test" in client.get("/legacy").text
    assert "legacy-entry-test" in client.get("/Shakwa.html").text
    for path in ("/api/v1/not-a-route", "/assets/missing.js", "/missing.css", "/docs/not-a-route"):
        response = client.get(path)
        assert response.status_code == 404
        assert "react-entry-test" not in response.text
    assert client.get("/health").json() == {"status": "ok"}
    monkeypatch.setenv("SHAKWA_UI", "legacy")
    assert "legacy-entry-test" in client.get("/").text


def test_missing_build_has_explicit_deep_link_error(system, tmp_path, monkeypatch):
    client, _ = system
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path / "absent")
    response = client.get("/employee/complaints")
    assert response.status_code == 404 and "pnpm build" in response.text
