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
from app.core.security import hash_password, verify_password
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


def test_fresh_session_cannot_claim_existing_citizen(system):
    client, factory = system
    details = {"first_name": "محمد", "last_name": "أحمد", "phone": "0912345678",
               "national_id": "12345678901"}
    # All submitted personal data is correct, but is not an ownership credential.
    response = client.post("/api/v1/citizens/", json=details)
    assert response.status_code == 409
    assert "id" not in response.json()
    assert "session" not in client.cookies
    response = client.post("/api/v1/citizens/1/id-image/",
                           files={"file": ("replacement.jpg", b"replacement", "image/jpeg")})
    assert response.status_code == 403
    response = client.post("/api/v1/complaints/", json={
        "citizen_id": 1, "directorate_id": 2, "title": "شكوى منتحلة",
        "details": "هذه شكوى باسم شخص آخر", "category": "عامة"
    })
    assert response.status_code == 403
    response = client.post("/api/v1/complaints/1/attachments/",
                           files={"file": ("replacement.jpg", b"replacement", "image/jpeg")})
    assert response.status_code == 401
    with factory() as db:
        assert db.get(Citizen, 1).identity_card_url is None
        assert db.query(Complaint).count() == 2


def test_browser_ownership_is_session_specific_and_bot_cannot_relink(system, monkeypatch):
    client, factory = system
    details = {"first_name": "سليم", "last_name": "حسن", "phone": "0998765432",
               "national_id": "98765432109"}
    created = client.post("/api/v1/citizens/", json=details)
    assert created.status_code == 200
    citizen_id = created.json()["id"]
    # Same newly registered session may resume its own unfinished form.
    assert client.post("/api/v1/citizens/", json=details).status_code == 200
    client.cookies.clear()
    assert client.post("/api/v1/citizens/", json=details).status_code == 409
    assert client.post(f"/api/v1/citizens/{citizen_id}/id-image/",
                       files={"file": ("id.jpg", b"replacement", "image/jpeg")}).status_code == 403
    monkeypatch.setenv("BOT_TOKEN", "fake-local-test-token")
    response = client.post("/api/v1/citizens/", json={**details, "telegram_id": 987654},
                           headers={"X-Bot-Token": "fake-local-test-token"})
    assert response.status_code == 409
    with factory() as db:
        assert db.get(Citizen, citizen_id).telegram_id is None


def test_legacy_citizen_cookie_does_not_grant_ownership():
    from types import SimpleNamespace
    from app.core.security import owns_citizen
    assert not owns_citizen(SimpleNamespace(session={"citizen_id": 1}), 1)
    assert owns_citizen(SimpleNamespace(session={
        "citizen_id": 1, "citizen_ownership": "registration-v2"
    }), 1)


def test_additive_migration_preserves_existing_records():
    from app.db.migrations import migrate
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE complaints (id INTEGER PRIMARY KEY, title TEXT, status TEXT)"))
        connection.execute(text("CREATE TABLE complaint_notes (id INTEGER PRIMARY KEY, note TEXT)"))
        connection.execute(text("CREATE TABLE employees (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO complaints VALUES (1, 'existing complaint', 'PENDING')"))
        connection.execute(text("INSERT INTO complaint_notes VALUES (1, 'existing note')"))
    migrate(engine)
    migrate(engine)  # Restarting is safe: already-added columns are not added again.
    with engine.connect() as connection:
        assert connection.execute(text("SELECT title FROM complaints")).scalar() == "existing complaint"
        assert connection.execute(text("SELECT note FROM complaint_notes")).scalar() == "existing note"
    assert "notification_status" in {c["name"] for c in inspect(engine).get_columns("complaint_notes")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT is_public FROM complaints")).scalar() == 0
    engine.dispose()


def test_public_directory_excludes_private_records_and_sensitive_data(system):
    import json
    client, factory = system
    assert client.get("/api/v1/complaints/public").json()["items"] == []
    assert client.get("/api/v1/complaints/public/1").status_code == 404
    with factory() as db:
        complaint = db.get(Complaint, 2)
        complaint.is_public = True
        complaint.category = "طرق"
        complaint.title = "شكوى محمد أحمد عن الطريق"
        complaint.details = "الرقم الوطني 12345678901 والهاتف 0912345678 والبريد private@example.com"
        complaint.resolution_report = "تم الحل لصاحب الشكوى محمد ورمزها CMP-SERVICES"
        db.add_all([
            ComplaintNote(complaint_id=2, author_id=2, note="تحديث عام 0912345678", is_internal=False),
            ComplaintNote(complaint_id=2, author_id=2, note="سر الموظف الداخلي", is_internal=True),
        ])
        db.commit()
    result = client.get("/api/v1/complaints/public?category=طرق&page_size=1").json()
    assert result["total"] == 1 and result["pages"] == 1
    detail = client.get("/api/v1/complaints/public/2").json()
    assert detail["id"] == 2 and len(detail["notes"]) == 1
    raw = json.dumps(detail, ensure_ascii=False)
    for secret in ["محمد", "أحمد", "12345678901", "0912345678", "private@example.com",
                   "CMP-SERVICES", "سر الموظف الداخلي", "citizen", "tracking_code", "attachments",
                   "author_name", "telegram_id", "latitude"]:
        assert secret not in raw
    assert client.get("/api/v1/complaints/public?page=2&page_size=1").json()["items"] == []
    assert client.get("/api/v1/complaints/public?page_size=1000").status_code == 422
    assert client.get("/api/v1/complaints/public?directorate_id=1").json()["total"] == 0
    # Secret tracking remains separate and does not expose citizen structured data.
    assert client.get("/api/v1/complaints/track/CMP-GOVERNOR").status_code == 200
    assert client.get("/api/v1/complaints/1").status_code == 401


def test_privacy_is_separate_from_category_and_opt_in(system):
    client, factory = system
    data = {"first_name": "سليم", "last_name": "حسن", "phone": "0998765432", "national_id": "98765432109"}
    citizen_id = client.post("/api/v1/citizens/", json=data).json()["id"]
    payload = {"citizen_id": citizen_id, "directorate_id": 2, "title": "شكوى جديدة",
               "details": "تفاصيل شكوى جديدة كاملة", "category": "طرق"}
    private = client.post("/api/v1/complaints/", json=payload).json()
    public = client.post("/api/v1/complaints/", json={**payload, "is_public": True}).json()
    assert private["is_public"] is False and public["is_public"] is True
    assert private["category"] == public["category"] == "طرق"
    assert client.get(f"/api/v1/complaints/public/{private['id']}").status_code == 404
    assert client.get(f"/api/v1/complaints/public/{public['id']}").status_code == 200


def test_analytics_scoped_counts_dates_and_empty_states(system):
    from datetime import datetime
    client, factory = system
    assert client.get("/api/v1/analytics").status_code == 401
    with factory() as db:
        governor = db.get(Complaint, 1)
        governor.created_at = datetime(2026, 10, 1, 12)
        governor.status = "RESOLVED"
        governor.progress = 100
        governor.category = "طرق"
        services = db.get(Complaint, 2)
        services.created_at = datetime(2026, 10, 2, 23, 59)
        services.status = "IN_PROGRESS"
        services.progress = 40
        services.category = "حفريات"
        db.commit()
    dates = "?start_date=2026-10-01&end_date=2026-10-02"
    login(client, "services")
    stats = client.get("/api/v1/analytics" + dates).json()
    assert stats["total"] == 1 and stats["counts_by_status"]["IN_PROGRESS"] == 1
    assert stats["resolution_rate"] == 0 and stats["average_progress"] == 40
    assert stats["scope"]["directorate_id"] == 2
    assert stats["daily"] == [{"date": "2026-10-01", "count": 0}, {"date": "2026-10-02", "count": 1}]
    assert client.get("/api/v1/analytics" + dates + "&directorate_id=1").status_code == 403
    login(client, "governor")
    stats = client.get("/api/v1/analytics" + dates).json()
    assert stats["total"] == 2 and stats["resolution_rate"] == 50 and stats["average_progress"] == 70
    assert sum(row["count"] for row in stats["counts_by_category"]) == 2
    assert sum(stats["counts_by_priority"].values()) == 2
    assert client.get("/api/v1/analytics" + dates + "&directorate_id=1").json()["total"] == 1
    empty = client.get("/api/v1/analytics?start_date=2026-09-01&end_date=2026-09-02").json()
    assert empty["total"] == 0 and empty["resolution_rate"] == empty["average_progress"] == 0
    assert client.get("/api/v1/analytics?start_date=2026-10-03&end_date=2026-10-01").status_code == 422
    assert client.get("/api/v1/analytics?start_date=2020-01-01&end_date=2026-10-01").status_code == 422


def test_progress_rules_and_reopening(system):
    client, factory = system
    login(client, "services")
    endpoint = "/api/v1/complaints/2/status?new_status="
    assert client.patch(endpoint + "IN_PROGRESS", json={"progress": 100}).status_code == 422
    assert client.patch(endpoint + "IN_PROGRESS", json={"progress": -1}).status_code == 422
    assert client.patch(endpoint + "IN_PROGRESS", json={"progress": 101}).status_code == 422
    assert client.patch(endpoint + "IN_PROGRESS", json={"progress": 99}).status_code == 200
    assert client.patch(endpoint + "RESOLVED", json={"progress": 20}).status_code == 200
    assert client.get("/api/v1/complaints/2").json()["progress"] == 100
    assert client.patch(endpoint + "IN_PROGRESS", json={}).status_code == 200
    assert client.get("/api/v1/complaints/2").json()["progress"] == 0


def test_demo_accounts_only_in_development_and_no_password_resets(monkeypatch):
    from app.api.v1.endpoints.auth import provision_accounts
    for key in ["REPLIT_DEPLOYMENT", "APP_ENV", "GOVERNOR_PASSWORD", "SERVICES_PASSWORD"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENABLE_DEMO_ACCOUNTS", "1")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        provision_accounts(db)
        rows = db.query(Employee).all()
        assert {row.username for row in rows} == {"governor", "services"}
        assert all(row.is_demo and verify_password("123456", row.hashed_password) for row in rows)
        assert all(row.hashed_password != "123456" for row in rows)
        original = rows[0].hashed_password
        provision_accounts(db)
        assert db.get(Employee, rows[0].id).hashed_password == original
        monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
        with pytest.raises(RuntimeError, match="disabled"):
            provision_accounts(db)
        monkeypatch.setenv("ENABLE_DEMO_ACCOUNTS", "0")
        with pytest.raises(RuntimeError, match="temporary"):
            provision_accounts(db)
    engine.dispose()


def test_password_change_and_other_session_revocation(system):
    client, factory = system
    login(client, "services")
    old_client = TestClient(main.app, base_url="https://testserver")
    old_client.cookies.update(client.cookies)
    assert client.post("/api/v1/auth/change-password",
                       json={"current_password": "wrong", "new_password": "a-new-long-test-password"}).status_code == 400
    assert client.post("/api/v1/auth/change-password",
                       json={"current_password": TEST_PASSWORD, "new_password": "short"}).status_code == 422
    changed = client.post("/api/v1/auth/change-password",
                          json={"current_password": TEST_PASSWORD, "new_password": "a-new-long-test-password"})
    assert changed.status_code == 200 and changed.json()["is_demo"] is False
    assert client.get("/api/v1/auth/me").status_code == 200
    assert old_client.get("/api/v1/auth/me").status_code == 401
    assert old_client.get("/api/v1/analytics").status_code == 401
    assert old_client.get("/api/v1/complaints/").status_code == 401
    client.post("/api/v1/auth/logout")
    assert client.post("/api/v1/auth/login", json={"username": "services", "password": TEST_PASSWORD}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "services", "password": "a-new-long-test-password"}).status_code == 200
    old_client.close()
