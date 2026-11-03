"""Regression checks use an isolated database and fake external services."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.models.complaint import Complaint, ComplaintNote
from app.models.user import Citizen, Employee, UserRole
from app.services import notifications

TEST_PASSWORD = "test-only-not-a-live-password"


@pytest.fixture
def system(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.delenv("GOVERNOR_PASSWORD", raising=False)
    monkeypatch.delenv("SERVICES_PASSWORD", raising=False)
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    Base.metadata.create_all(engine)
    with factory() as db:
        db.add_all([
            Employee(id=1, username="governor", full_name="المحافظة",
                     hashed_password=hash_password(TEST_PASSWORD), role=UserRole.GOVERNOR),
            Employee(id=2, username="services", full_name="الخدمات", directorate_id=2,
                     hashed_password=hash_password(TEST_PASSWORD), role=UserRole.EMPLOYEE),
        ])
        citizen = Citizen(first_name="محمد", last_name="أحمد", phone="0912345678",
                          national_id="12345678901", telegram_id=123456)
        db.add(citizen)
        db.flush()
        db.add_all([
            Complaint(citizen_id=citizen.id, tracking_code="CMP-GOVERNOR", directorate_id=1,
                      title="شكوى المحافظة", details="تفاصيل الشكوى التجريبية", category="عامة"),
            Complaint(citizen_id=citizen.id, tracking_code="CMP-SERVICES", directorate_id=2,
                      title="شكوى الخدمات", details="تفاصيل الشكوى التجريبية", category="عامة"),
        ])
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    main.app.dependency_overrides[get_db] = override_db
    with TestClient(main.app, base_url="https://testserver") as client:
        yield client, factory
    main.app.dependency_overrides.clear()
    engine.dispose()


def login(client, username):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()


def test_auth_and_role_boundaries(system):
    client, factory = system
    assert client.get("/api/v1/complaints/").status_code == 401
    assert client.patch("/api/v1/complaints/1/status?new_status=RESOLVED", json={}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "services", "password": "wrong"}).status_code == 401
    assert login(client, "services")["role"] == "employee"
    assert len(client.get("/api/v1/complaints/").json()) == 1
    assert client.get("/api/v1/complaints/1").status_code == 403
    assert client.patch("/api/v1/complaints/1/status?new_status=RESOLVED", json={}).status_code == 403
    assert client.post("/api/v1/complaints/1/notes", json={"note": "ملاحظة"}).status_code == 403
    assert client.post("/api/v1/complaints/1/notes/1/retry").status_code == 403
    assert client.patch("/api/v1/complaints/2/status?new_status=IN_PROGRESS", json={"progress": 30}).status_code == 200
    login(client, "governor")
    assert len(client.get("/api/v1/complaints/").json()) == 2
    assert client.get("/api/v1/complaints/1").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_notes_persist_even_when_notification_fails(system, monkeypatch):
    client, factory = system
    login(client, "governor")
    result = client.patch("/api/v1/complaints/1/status?new_status=IN_PROGRESS",
                          json={"admin_notes": "ملاحظة للمواطن", "progress": 45})
    assert result.status_code == 200
    assert result.json()["notification"]["status"] == "not_configured"
    with factory() as db:
        note = db.query(ComplaintNote).one()
        assert note.note == "ملاحظة للمواطن"
        assert note.author_id == 1
        assert db.get(Complaint, 1).progress == 45
    monkeypatch.setattr(notifications, "notify", AsyncMock(return_value={
        "status": "failed", "message": "فشل الإرسال"
    }))
    response = client.post("/api/v1/complaints/1/notes", json={"note": "ملاحظة ثانية"})
    assert response.json()["notification"]["status"] == "failed"
    with factory() as db:
        assert db.query(ComplaintNote).count() == 2
        assert db.get(ComplaintNote, 2).notification_status == "failed"
    public = client.get("/api/v1/complaints/track/CMP-GOVERNOR").json()
    assert len(public["notes"]) == 2
    assert "citizen" not in public
    assert "author_name" not in public["notes"][0]


def test_internal_notes_and_no_duplicate_on_status_only(system):
    client, factory = system
    login(client, "services")
    response = client.post("/api/v1/complaints/2/notes", json={"note": "سري داخلي", "is_internal": True})
    assert response.json()["notification"]["status"] == "not_requested"
    assert len(client.get("/api/v1/complaints/2").json()["notes"]) == 1
    assert client.get("/api/v1/complaints/track/CMP-SERVICES").json()["notes"] == []
    for _ in range(2):
        assert client.patch("/api/v1/complaints/2/status?new_status=RESOLVED", json={}).status_code == 200
    with factory() as db:
        assert db.query(ComplaintNote).count() == 1
        assert db.get(Complaint, 2).progress == 100


def test_telegram_api_result_and_escaping(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "test-token-not-real")
    captured = []

    class Response:
        status = 200
        async def json(self):
            return {"ok": True}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    class Session:
        def __init__(self, **kwargs):
            pass
        def post(self, url, json):
            captured.append(json)
            return Response()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(notifications.aiohttp, "ClientSession", Session)
    citizen = Citizen(telegram_id=123)
    assert asyncio.run(notifications.notify(citizen, "CMP-TEST", "<b>نص</b>"))["status"] == "sent"
    assert captured[0]["chat_id"] == 123
    assert "&lt;b&gt;" in captured[0]["text"]
    async def rejected(self):
        return {"ok": False}
    monkeypatch.setattr(Response, "json", rejected)
    assert asyncio.run(notifications.notify(citizen, "CMP-TEST", "نص"))["status"] == "failed"


def test_citizen_submission_upload_and_identity_conflict(system):
    client, factory = system
    data = {"first_name": "سليم", "last_name": "حسن", "phone": "0998765432", "national_id": "98765432109"}
    assert client.post("/api/v1/citizens/", json={**data, "first_name": "123"}).status_code == 422
    citizen = client.post("/api/v1/citizens/", json=data)
    assert citizen.status_code == 200, citizen.text
    citizen_id = citizen.json()["id"]
    assert client.post("/api/v1/citizens/", json={**data, "national_id": "00000000000"}).status_code == 409
    assert client.post("/api/v1/citizens/", json={**data, "telegram_id": 999}).status_code == 403
    response = client.post(f"/api/v1/citizens/{citizen_id}/id-image/",
                           files={"file": ("../../identity.jpg", b"test image", "image/jpeg")})
    assert response.status_code == 200
    with factory() as db:
        path = db.get(Citizen, citizen_id).identity_card_url
        assert Path(path).is_file()
        assert ".." not in path
    payload = {"citizen_id": citizen_id, "directorate_id": 2, "title": "شكوى جديدة",
               "details": "تفاصيل شكوى جديدة كاملة", "category": "عامة"}
    created = client.post("/api/v1/complaints/", json=payload)
    assert created.status_code == 200, created.text
    complaint_id = created.json()["id"]
    file = client.post(f"/api/v1/complaints/{complaint_id}/attachments/",
                      files={"file": ("test.pdf", b"%PDF-test", "application/pdf")})
    assert file.status_code == 200
    attachment_id = file.json()["id"]
    assert client.get(f"/api/v1/complaints/attachments/{attachment_id}/download").status_code == 401
    login(client, "services")
    assert client.get(f"/api/v1/complaints/attachments/{attachment_id}/download").status_code == 200
    assert client.post("/api/v1/complaints/", json={**payload, "citizen_id": 1}).status_code == 403


def test_cross_origin_and_bot_routes(system, monkeypatch):
    client, _ = system
    assert client.post("/api/v1/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/v1/citizens/telegram/123456").status_code == 401
    monkeypatch.setenv("BOT_TOKEN", "fake-local-test-token")
    assert client.get("/api/v1/citizens/telegram/123456",
                      headers={"X-Bot-Token": "fake-local-test-token"}).status_code == 200


def test_additive_migration_preserves_existing_records():
    from app.db.migrations import migrate
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE complaints (id INTEGER PRIMARY KEY, title TEXT)"))
        connection.execute(text("CREATE TABLE complaint_notes (id INTEGER PRIMARY KEY, note TEXT)"))
        connection.execute(text("INSERT INTO complaints VALUES (1, 'existing complaint')"))
        connection.execute(text("INSERT INTO complaint_notes VALUES (1, 'existing note')"))
    migrate(engine)
    migrate(engine)  # Restarting is safe: already-added columns are not added again.
    with engine.connect() as connection:
        assert connection.execute(text("SELECT title FROM complaints")).scalar() == "existing complaint"
        assert connection.execute(text("SELECT note FROM complaint_notes")).scalar() == "existing note"
    assert "notification_status" in {c["name"] for c in inspect(engine).get_columns("complaint_notes")}
    engine.dispose()
