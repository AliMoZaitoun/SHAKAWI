"""Foundation contracts against isolated synthetic databases, never live citizens."""
import io
from pathlib import Path
from unittest.mock import patch
import pytest
from PIL import Image
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from test_app import system, login, TEST_PASSWORD
from app.core.security import _attempts, hash_password
from app.db.upgrade import upgrade_database
from app.models.access import Directorate, Role, Permission, User
from app.models.user import Citizen, Employee
from app.models.complaint import Complaint, Attachment, StatusEnum
from app.models.foundations import (
    AuditEvent, ComplaintHistory, StoredFile, ComplaintFile, CitizenFile,
)


@pytest.fixture(autouse=True)
def reset_rate_limit():
    _attempts.clear()
    yield
    _attempts.clear()


def png():
    stream = io.BytesIO()
    Image.new("RGB", (3, 3), color="blue").save(stream, format="PNG")
    return stream.getvalue()


def grant(client, *permissions):
    roles = client.get("/api/v1/admin/roles").json()
    governor = next(role for role in roles if role["code"] == "governor")
    result = client.put(f"/api/v1/admin/roles/{governor['id']}", json={
        "name": governor["name"], "description": governor["description"],
        "permissions": sorted(set(governor["permissions"]) | set(permissions)),
    })
    assert result.status_code == 200, result.text


def test_dynamic_languages_names_and_priority(system):
    client, factory = system
    login(client, "governor")
    result = client.post("/api/v1/admin/languages", json={
        "code": "fr", "name": "Français", "direction": "ltr",
    })
    assert result.status_code == 201, result.text
    assert client.post("/api/v1/admin/languages", json={
        "code": "fr", "name": "French",
    }).status_code == 409
    assert client.put("/api/v1/admin/translations/directorates/2/fr", json={
        "name": "Services municipaux", "description": "Description française", "location": "Centre",
    }).status_code == 200
    assert client.get("/api/v1/directorates?lang=fr").json()[1]["name"] == "Services municipaux"
    assert client.get("/api/v1/directorates", headers={
        "Accept-Language": "de;q=0.9,fr-CA;q=0.8,en;q=0.1",
    }).json()[1]["name"] == "Services municipaux"
    assert client.put("/api/v1/language-preference", json={"language_code": "fr"}).status_code == 200
    assert client.get("/api/v1/directorates", headers={"Accept-Language": "en"}).json()[1]["name"] == "Services municipaux"
    assert client.get("/api/v1/directorates?lang=ar").json()[1]["name"] == "الخدمات"
    response = client.get("/api/v1/directorates?lang=fr")
    assert response.headers["Content-Language"] == "fr" and response.headers["X-Request-ID"]
    with factory() as db:
        assert "name_fr" not in {column["name"] for column in inspect(db.bind).get_columns("directorates")}


def test_translation_fallback_edit_delete_and_authorization(system):
    client, factory = system
    assert client.get("/api/v1/admin/translations/roles/1").status_code == 401
    login(client, "services")
    assert client.post("/api/v1/admin/languages", json={"code": "fr", "name": "French"}).status_code == 403
    login(client, "governor")
    roles = client.get("/api/v1/admin/roles").json()
    role = next(row for row in roles if row["code"] == "governor")
    assert client.put(f"/api/v1/admin/translations/roles/{role['id']}/en", json={
        "name": "Governor office", "description": "Administrative role",
    }).status_code == 200
    assert client.get("/api/v1/auth/me?lang=en").json()["roles"][0]["name"] == "Governor office"
    assert client.put("/api/v1/admin/translations/permissions/complaints.view/en", json={
        "name": "Read complaints",
    }).status_code == 200
    assert next(row for row in client.get("/api/v1/admin/permissions?lang=en").json()
                if row["code"] == "complaints.view")["name"] == "Read complaints"
    assert client.delete(f"/api/v1/admin/translations/roles/{role['id']}/en").status_code == 200
    assert client.get("/api/v1/auth/me?lang=en").json()["roles"][0]["name"] == "المحافظ"
    assert client.delete(f"/api/v1/admin/translations/roles/{role['id']}/ar").status_code == 409
    assert client.put("/api/v1/admin/languages/ar", json={
        "name": "Arabic", "direction": "rtl", "is_active": False,
    }).status_code == 409
    assert client.put("/api/v1/admin/translations/directorates/2/xx", json={"name": "Unknown"}).status_code == 422
    assert client.put("/api/v1/admin/translations/directorates/999/en", json={"name": "Unknown"}).status_code == 404
    assert client.put("/api/v1/admin/languages/en", json={
        "name": "English", "direction": "ltr", "is_active": False,
    }).status_code == 200
    assert client.get("/api/v1/directorates?lang=en").headers["Content-Language"] == "ar"


def test_arabic_compatibility_writes_sync_without_duplicate_translations(system):
    client, factory = system
    login(client, "governor")
    result = client.post("/api/v1/admin/directorates", json={"name": "مديرية جديدة"})
    assert result.status_code == 201, result.text
    identifier = result.json()["id"]
    for _ in range(2):
        result = client.put(f"/api/v1/admin/translations/directorates/{identifier}/ar", json={
            "name": "الاسم العربي", "description": "الوصف", "location": "العنوان",
        })
        assert result.status_code == 200, result.text
    assert client.get("/api/v1/directorates").json()[-1]["name"] == "الاسم العربي"
    assert client.delete(f"/api/v1/admin/directorates/{identifier}").status_code == 200


def test_catalog_upload_identity_protection_and_legacy_ids(system):
    client, factory = system
    citizen = client.post("/api/v1/citizens/", json={
        "first_name": "مواطن", "last_name": "جديد", "phone": "0990000001",
        "national_id": "98765432100",
    }).json()
    result = client.post(f"/api/v1/citizens/{citizen['id']}/id-image/",
                         files={"file": ("id.png", png(), "image/png")})
    assert result.status_code == 200, result.text
    identity_url = result.json()["file_url"]
    assert client.get(identity_url).content == png()
    complaint = client.post("/api/v1/complaints/", json={
        "citizen_id": citizen["id"], "directorate_id": 2, "title": "شكوى اختبار الملفات",
        "details": "تفاصيل كاملة لاختبار الملفات", "category": "طرق", "is_public": True,
    }).json()
    result = client.post(f"/api/v1/complaints/{complaint['id']}/attachments/",
                         files={"file": ("evidence.png", png(), "image/png")})
    assert result.status_code == 200, result.text
    file = result.json()
    assert client.get(file["file_url"]).content == png()
    with factory() as db:
        stored = db.get(StoredFile, file["file_id"])
        assert stored.original_name == "evidence.png" and stored.checksum and stored.size_bytes == len(png())
        assert db.query(ComplaintFile).filter_by(legacy_attachment_id=file["id"]).one().complaint_id == complaint["id"]
        assert db.query(CitizenFile).filter_by(citizen_id=citizen["id"], is_current=True).count() == 1
    client.cookies.clear()
    assert client.get(file["file_url"]).status_code == 403
    assert client.get(identity_url).status_code == 401
    public = client.get(f"/api/v1/complaints/public/{complaint['id']}")
    assert "file_url" not in public.text and "storage_key" not in public.text
    assert client.get("/api/v1/complaints/track/" + complaint["tracking_code"]).status_code == 200
    assert client.get(file["file_url"]).status_code == 200
    assert client.get(identity_url).status_code == 401
    login(client, "services")
    assert client.get(identity_url).status_code == 403
    assert client.get(f"/api/v1/complaints/attachments/{file['id']}/download").status_code == 200


def test_invalid_content_and_failed_commit_do_not_leave_files(system, monkeypatch):
    client, factory = system
    client.get("/api/v1/complaints/track/CMP-SERVICES")
    # A track capability can answer evidence, not impersonate account ownership for uploads.
    login(client, "services")
    assert client.post("/api/v1/complaints/2/attachments/",
                       files={"file": ("fake.png", b"not an image", "image/png")}).status_code == 415
    assert not list(Path("uploads").glob("*"))
    from sqlalchemy.orm import Session
    original = Session.commit

    def fail(self):
        if any(isinstance(row, Attachment) for row in self.new):
            raise RuntimeError("synthetic commit failure")
        original(self)

    with patch.object(Session, "commit", fail):
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            client.post("/api/v1/complaints/2/attachments/",
                        files={"file": ("valid.png", png(), "image/png")})
    assert not list(Path("uploads").glob("*"))
    with factory() as db:
        assert db.query(StoredFile).count() == 0


def test_history_composite_updates_transfer_and_private_fields(system):
    client, factory = system
    login(client, "governor")
    grant(client, "complaints.transfer", "audit.view")
    response = client.patch("/api/v1/complaints/2/status?new_status=IN_PROGRESS", json={
        "progress": 45, "admin_notes": "ملاحظة خاصة لا تسجل بالتدقيق",
    })
    assert response.status_code == 200
    result = client.post("/api/v1/complaints/2/transfer", json={
        "directorate_id": 1, "reason": "سبب داخلي خاص",
    })
    assert result.status_code == 200, result.text
    staff_history = client.get("/api/v1/complaints/2/history").json()["items"]
    assert staff_history[-1]["old_directorate_id"] == 2 and staff_history[-1]["new_directorate_id"] == 1
    assert staff_history[-1]["old_status"] == "IN_PROGRESS" and staff_history[-1]["old_progress"] == 45
    assert staff_history[-1]["reason"] == "سبب داخلي خاص"
    assert staff_history[-1]["actor_user_id"] is not None
    events = client.get("/api/v1/admin/audit-events?entity_type=complaints").json()
    assert events["total"] >= 2
    assert "ملاحظة خاصة" not in str(events) and "سبب داخلي" not in str(events)
    assert all(row["request_id"] and row["source"] in {"system", "web", "migration"} for row in events["items"])
    login(client, "services")
    assert client.get("/api/v1/complaints/2/history").status_code == 403
    assert client.get("/api/v1/admin/audit-events").status_code == 403
    client.cookies.clear()
    assert client.get("/api/v1/complaints/2/history").status_code == 403
    client.get("/api/v1/complaints/track/CMP-SERVICES")
    owner = client.get("/api/v1/complaints/2/history").json()
    assert all("actor_user_id" not in row and "reason" not in row and "request_id" not in row for row in owner["items"])


def test_audit_rollback_append_only_and_canonical_user(system):
    client, factory = system
    with factory() as db:
        before = db.query(AuditEvent).count()
        before_history = db.query(ComplaintHistory).count()
        complaint = db.get(Complaint, 2)
        complaint.progress = 25
        db.flush()
        assert db.query(AuditEvent).count() > before
        db.rollback()
        assert db.get(Complaint, 2).progress == 0
        assert db.query(AuditEvent).count() == before
        assert db.query(ComplaintHistory).count() == before_history
        record = db.query(AuditEvent).first()
        record.action = "tampered"
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
        db.rollback()
        citizen = db.get(Citizen, 1)
        canonical_name = citizen.user.first_name
        db.execute(text("UPDATE citizens SET first_name='legacy stale' WHERE id=1"))
        db.commit()
        db.expire_all()
        assert db.get(Citizen, 1).first_name == canonical_name
        citizen = db.get(Citizen, 1)
        citizen.user.first_name = "الاسم المركزي"
        db.commit()
        assert citizen.first_name == "الاسم المركزي"
        assert db.execute(text("SELECT first_name FROM citizens WHERE id=1")).scalar() == "الاسم المركزي"
        employee = db.get(Employee, 1)
        employee.user.hashed_password = hash_password("new-test-password-only")
        db.commit()
    assert client.post("/api/v1/auth/login", json={
        "username": "governor", "password": "new-test-password-only",
    }).status_code == 200
    with factory() as db:
        event_row = db.query(AuditEvent).filter_by(action="auth.login").order_by(AuditEvent.id.desc()).first()
        assert event_row.actor_user_id == db.get(Employee, 1).user_id
        assert event_row.changes == {} and event_row.source == "web"


def test_bot_directory_uses_database_ids_and_localized_names():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from bot.handlers.complaint_flow import show_directorates, process_directorate
    from bot.keyboards.inline import get_directorates_keyboard
    from aiogram import Router
    rows = [{"id": 7, "name": "Direction française"}]
    keyboard = get_directorates_keyboard("fr", rows)
    assert keyboard.inline_keyboard[0][0].callback_data == "dir_7"
    assert keyboard.inline_keyboard[0][0].text == "Direction française"
    with pytest.raises(ValueError):
        get_directorates_keyboard("en")
    state = SimpleNamespace(get_data=AsyncMock(return_value={
        "lang": "en", "allowed_directorates": [7],
    }), update_data=AsyncMock(), set_state=AsyncMock())
    callback = SimpleNamespace(data="dir_7", message=SimpleNamespace(edit_text=AsyncMock()), answer=AsyncMock())
    asyncio.run(process_directorate(callback, state))
    state.update_data.assert_awaited_once_with(directorate_id=7)
    callback.data = "dir_999"
    state.update_data.reset_mock()
    asyncio.run(process_directorate(callback, state))
    state.update_data.assert_not_called()


def legacy_database(tmp_path):
    from app.db.schema_snapshot import apply_snapshot
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.sqlite")
    with engine.begin() as conn:
        apply_snapshot(conn, "legacy_schema.sql")
        conn.execute(text("INSERT INTO directorates(id,name) VALUES(2,'الخدمات')"))
        conn.execute(text("""INSERT INTO citizens(id,first_name,last_name,phone,national_id,telegram_id,identity_card_url)
            VALUES(501,'قديم','مواطن','0991234567','12345678900',12345,'uploads/identity.png')"""))
        conn.execute(text("""INSERT INTO employees(id,full_name,username,hashed_password,role,directorate_id)
            VALUES(17,'اسم قديم','old',:password,'EMPLOYEE',2)"""), {"password": hash_password(TEST_PASSWORD)})
        conn.execute(text("""INSERT INTO complaints(id,tracking_code,citizen_id,directorate_id,title,details,category,priority,status)
            VALUES(901,'CMP-LEGACY',501,2,'شكوى قديمة','تفاصيل قديمة','طرق','MEDIUM','PENDING')"""))
        conn.execute(text("""INSERT INTO attachments(id,file_path,file_type,attachable_type,attachable_id)
            VALUES(71,'uploads/evidence.png','image/png','complaint',901)"""))
    return engine


def test_versioned_legacy_migration_backups_repeat_and_restore(tmp_path, monkeypatch):
    from app.db.backup import verify_backup, restore_to_new_directory
    monkeypatch.chdir(tmp_path)
    Path("uploads").mkdir()
    Path("uploads/identity.png").write_bytes(png())
    Path("uploads/evidence.png").write_bytes(png())
    engine = legacy_database(tmp_path)
    with engine.connect() as conn:
        old_hash = conn.execute(text("SELECT hashed_password FROM employees WHERE id=17")).scalar()
    upgrade_database(engine)
    upgrade_database(engine)
    with sessionmaker(bind=engine)() as db:
        assert db.get(Citizen, 501).telegram_id == 12345
        assert db.get(Employee, 17).user.hashed_password == old_hash
        assert db.get(Employee, 17).user.needs_profile_completion
        assert db.get(Complaint, 901).tracking_code == "CMP-LEGACY"
        assert db.query(ComplaintFile).one().legacy_attachment_id == 71
        assert db.query(StoredFile).count() == 2
        assert db.query(ComplaintHistory).one().event == "imported_snapshot"
        assert not db.execute(text("PRAGMA foreign_key_check")).all()
        assert (
            db.execute(text("SELECT version_num FROM alembic_version")).scalar()
            == "0003_directorate_hierarchy"
        )
        assert all(row.parent_id is None for row in db.query(Directorate).all())
        parent_foreign_key = next(
            foreign_key
            for foreign_key in inspect(engine).get_foreign_keys("directorates")
            if foreign_key["constrained_columns"] == ["parent_id"]
        )
        assert parent_foreign_key["referred_table"] == "directorates"
        sqlite_foreign_key = next(
            row
            for row in db.execute(text("PRAGMA foreign_key_list('directorates')")).all()
            if row[3] == "parent_id"
        )
        assert sqlite_foreign_key[6] == "RESTRICT"
    backups = list(Path("generated-artifacts/backups").iterdir())
    assert len(backups) == 1 and verify_backup(backups[0])
    restored = restore_to_new_directory(backups[0], tmp_path / "restored")
    assert (restored / "uploads/identity.png").read_bytes() == png()
    with pytest.raises(FileExistsError):
        restore_to_new_directory(backups[0], restored)
    restored_engine = create_engine(f"sqlite:///{restored}/database.sqlite")
    with restored_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM citizens")).scalar() == 1
        assert "alembic_version" not in inspect(conn).get_table_names()
    engine.dispose()
    restored_engine.dispose()


def test_mid_upgrade_failure_rolls_back_schema_and_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = legacy_database(tmp_path)
    with patch("app.services.file_catalog.backfill_files", side_effect=RuntimeError("synthetic migration failure")):
        with pytest.raises(RuntimeError, match="synthetic migration failure"):
            upgrade_database(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM citizens")).scalar() == 1
        assert conn.execute(text("SELECT user_id FROM citizens WHERE id=501")).scalar() is None
        assert "files" not in inspect(conn).get_table_names()
        assert "alembic_version" not in inspect(conn).get_table_names()
    upgrade_database(engine)
    assert "files" in inspect(engine).get_table_names()
    engine.dispose()


def test_fresh_schema_foreign_keys_and_missing_legacy_bytes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path}/new.sqlite")
    event.listen(engine, "connect", lambda connection, record: connection.execute("PRAGMA foreign_keys=ON"))
    upgrade_database(engine)
    with engine.connect() as conn:
        assert not conn.exec_driver_sql("PRAGMA foreign_key_check").all()
        assert conn.execute(text("SELECT COUNT(*) FROM languages")).scalar() == 2
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("INSERT INTO complaint_files(file_id,complaint_id) VALUES(999,999)"))
    engine.dispose()
    legacy = legacy_database(tmp_path)
    upgrade_database(legacy)
    with sessionmaker(bind=legacy)() as db:
        assert all(file.size_bytes is None and file.checksum is None for file in db.query(StoredFile))
    legacy.dispose()


def test_source_export_excludes_data_and_secrets(tmp_path, monkeypatch):
    import zipfile
    import json
    import scripts.export_source as exporter
    source = tmp_path / "source"
    source.mkdir()
    (source / "app").mkdir()
    (source / "app/main.py").write_text("# synthetic source")
    (source / "app/cache.db").write_bytes(b"private database")
    (source / ".env").write_text("DO_NOT_EXPORT=synthetic")
    (source / ".env.example").write_text("SESSION_SECRET=")
    (source / "uploads").mkdir()
    (source / "uploads/id.png").write_bytes(png())
    monkeypatch.setattr(exporter, "ROOT", source)
    archive = exporter.export_source(tmp_path / "source.zip")
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        assert "shakwa-source/app/main.py" in names
        assert "shakwa-source/.env.example" in names
        assert not any(name.endswith(".db") or name.endswith("/.env") or "/uploads/" in name for name in names)
        manifest = json.loads(zipped.read("shakwa-source/SOURCE-MANIFEST.json"))
        assert set(manifest) == {"app/main.py", ".env.example"}
