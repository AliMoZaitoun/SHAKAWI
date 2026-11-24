import asyncio
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers
from sqlalchemy import inspect

from test_app import TEST_PASSWORD, login, system
from app.models.complaint import (
    Complaint,
    EvidenceFile,
    EvidenceReply,
    EvidenceRequest,
    StatusEnum,
)
from app.models.foundations import (
    AuditEvent,
    CitizenFile,
    ComplaintFile,
    EvidenceReplyFile,
    FilePolicy,
    RetentionRun,
    StoredFile,
)
from app.services.retention import run_retention
from app.services.uploads import HARD_MAX_BYTES, save_upload
from app.services.evidence import validate_files
from bot.upload_policy import LimitedBuffer


def png_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (3, 3), color="blue").save(stream, format="PNG")
    return stream.getvalue()


def test_public_upload_policy_and_global_admin_permission(system):
    client, factory = system
    public = client.get("/api/v1/upload-policy")
    assert public.status_code == 200
    assert len(public.json()["mime_types"]) == 8
    assert all(row["max_bytes"] == HARD_MAX_BYTES for row in public.json()["mime_types"])
    assert client.get("/api/v1/admin/settings/files").status_code == 401

    login(client, "services")
    assert client.get("/api/v1/admin/settings/files").status_code == 403

    login(client, "system_admin")
    settings = client.get("/api/v1/admin/settings/files")
    assert settings.status_code == 200, settings.text
    assert settings.json()["retention"]["days"] == 30
    assert settings.json()["retention"]["scope"] == [
        "complaint_files", "evidence_reply_files",
    ]
    assert settings.json()["retention"]["enabled"] is False

    limits = {
        row["mime_type"]: row["max_bytes"] for row in settings.json()["mime_types"]
    }
    limits["image/png"] = 1024
    updated = client.put("/api/v1/admin/settings/files/limits", json={"mime_limits": limits})
    assert updated.status_code == 200, updated.text
    assert client.get("/api/v1/upload-policy").json()["mime_types"][1]["max_bytes"] == 1024

    unsupported = {**limits, "text/plain": 10}
    assert client.put(
        "/api/v1/admin/settings/files/limits", json={"mime_limits": unsupported},
    ).status_code == 422
    limits["image/png"] = HARD_MAX_BYTES + 1
    assert client.put(
        "/api/v1/admin/settings/files/limits", json={"mime_limits": limits},
    ).status_code == 422
    with factory() as db:
        assert db.get(FilePolicy, 1).retention_enabled is False


def test_website_identity_and_evidence_uploads_share_configured_mime_cap(system):
    _, factory = system
    with factory() as db:
        policy = db.get(FilePolicy, 1)
        policy.mime_limits = {**policy.mime_limits, "image/png": 1}
        db.commit()
        with pytest.raises(HTTPException) as direct_error:
            asyncio.run(save_upload(
                UploadFile(
                    io.BytesIO(b"some bytes"),
                    filename="complaint.png",
                    headers=Headers({"content-type": "image/png"}),
                ),
                db,
            ))
        assert direct_error.value.status_code == 413

        with pytest.raises(HTTPException) as identity_error:
            asyncio.run(save_upload(
                UploadFile(
                    io.BytesIO(b"some bytes"),
                    filename="identity.png",
                    headers=Headers({"content-type": "image/png"}),
                ),
                db,
                identity=True,
            ))
        assert identity_error.value.status_code == 413

        with pytest.raises(HTTPException) as evidence_error:
            asyncio.run(validate_files([
                UploadFile(
                    io.BytesIO(png_bytes()),
                    filename="evidence.png",
                    headers=Headers({"content-type": "image/png"}),
                ),
            ], db))
        assert evidence_error.value.status_code == 413


def test_telegram_download_buffer_stops_at_configured_limit():
    buffer = LimitedBuffer(3, "en")
    buffer.write(b"abc")
    with pytest.raises(ValueError, match="configured limit"):
        buffer.write(b"d")


def _linked_file(db, complaint_id, path, raw, created_at, *, scope="complaint"):
    file = StoredFile(
        storage_disk="local",
        storage_key=str(path),
        original_name=path.name,
        mime_type="image/png",
        size_bytes=len(raw),
        created_at=created_at,
    )
    db.add(file)
    db.flush()
    if scope == "complaint":
        db.add(ComplaintFile(file_id=file.id, complaint_id=complaint_id))
    return file


def test_retention_requires_preview_then_removes_only_file_bytes(system, tmp_path):
    client, factory = system
    login(client, "system_admin")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    resolved_at = now - timedelta(days=31)
    file_created = now - timedelta(days=40)
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(exist_ok=True)
    direct_bytes = b"complaint-content"
    reply_bytes = b"evidence-content"
    identity_bytes = b"identity-content"
    direct_path = upload_dir / "complaint.png"
    reply_path = upload_dir / "evidence.png"
    identity_path = upload_dir / "identity.png"
    direct_path.write_bytes(direct_bytes)
    reply_path.write_bytes(reply_bytes)
    identity_path.write_bytes(identity_bytes)

    with factory() as db:
        baseline_complaint_links = db.query(ComplaintFile).count()
        baseline_evidence_links = db.query(EvidenceReplyFile).count()
        complaint = db.get(Complaint, 1)
        complaint.status = StatusEnum.RESOLVED
        complaint.resolved_at = resolved_at
        direct = _linked_file(db, complaint.id, direct_path, direct_bytes, file_created)
        identity = _linked_file(db, complaint.id, identity_path, identity_bytes, file_created)
        db.add(CitizenFile(
            file_id=identity.id, citizen_id=complaint.citizen_id, purpose="identity",
        ))

        request = EvidenceRequest(
            complaint_id=complaint.id, author_id=1, prompt="أرسل صورة",
            submission_key="retention-request",
        )
        db.add(request)
        db.flush()
        reply = EvidenceReply(
            request_id=request.id, submission_key="retention-reply",
            payload_digest="a" * 64, text="مرفق", channel="web",
        )
        db.add(reply)
        db.flush()
        db.add(EvidenceFile(
            reply_id=reply.id, file_path=str(reply_path),
            name="evidence.png", file_type="image/png",
        ))
        db.flush()
        evidence_link = db.query(EvidenceReplyFile).filter_by(reply_id=reply.id).one()
        evidence_file = db.get(StoredFile, evidence_link.file_id)
        evidence_file.created_at = file_created
        evidence_file.size_bytes = len(reply_bytes)
        db.commit()
        direct_id, evidence_id, identity_id = direct.id, evidence_file.id, identity.id

    # The policy is configured, but a scheduled run cannot act before review.
    disabled = run_retention(factory, now=now)
    assert disabled["status"] == "disabled"
    assert direct_path.exists() and reply_path.exists() and identity_path.exists()

    preview_response = client.post("/api/v1/admin/settings/files/retention/preview")
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["file_count"] == 2
    assert preview["bytes_total"] == len(direct_bytes) + len(reply_bytes)
    assert preview["includes_identity_files"] is False
    assert len(preview["complaints"]) == 1

    enabled_response = client.post(
        "/api/v1/admin/settings/files/retention/enable",
        json={"preview_token": preview["preview_token"]},
    )
    assert enabled_response.status_code == 200, enabled_response.text
    assert enabled_response.json()["retention_enabled"] is True
    # Enabling the reviewed policy does not run deletion immediately.
    assert direct_path.exists() and reply_path.exists() and identity_path.exists()

    result = run_retention(factory, now=now)
    assert result == {
        "status": "completed",
        "files_scanned": 2,
        "files_purged": 2,
        "bytes_purged": len(direct_bytes) + len(reply_bytes),
        "failures": 0,
    }
    assert not direct_path.exists() and not reply_path.exists()
    assert identity_path.read_bytes() == identity_bytes
    complaint_detail = client.get("/api/v1/complaints/1")
    assert complaint_detail.status_code == 200
    removed_attachment = next(
        row for row in complaint_detail.json()["attachments"] if row["file_id"] == direct_id
    )
    assert removed_attachment["is_available"] is False
    assert removed_attachment["file_url"] is None
    evidence_detail = client.get("/api/v1/complaints/1/evidence")
    assert evidence_detail.status_code == 200
    reply_attachment = evidence_detail.json()[0]["replies"][0]["attachments"][0]
    assert reply_attachment["is_available"] is False and reply_attachment["file_url"] is None
    assert client.get(f"/api/v1/files/{direct_id}/download").status_code == 410
    assert client.post(
        "/api/v1/admin/settings/files/retention/enable",
        json={"preview_token": preview["preview_token"]},
    ).status_code == 409

    with factory() as db:
        assert db.get(StoredFile, direct_id).purged_at is not None
        assert db.get(StoredFile, evidence_id).purged_at is not None
        assert db.get(StoredFile, identity_id).purged_at is None
        assert db.query(ComplaintFile).count() == baseline_complaint_links + 2
        assert db.query(EvidenceReplyFile).count() == baseline_evidence_links + 1
        assert db.query(Complaint).filter_by(id=1).one().status == StatusEnum.RESOLVED
        assert db.query(RetentionRun).one().files_purged == 2
        assert db.query(AuditEvent).filter(
            AuditEvent.action == "file_policy.retention_enabled",
        ).count() == 1
        assert "purged_at" in {
            column["name"] for column in inspect(db.bind).get_columns("files")
        }


def test_preview_expires_and_policy_changes_require_a_new_review(system, tmp_path):
    client, factory = system
    login(client, "system_admin")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    path = tmp_path / "uploads" / "old.png"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b"old file")
    with factory() as db:
        complaint = db.get(Complaint, 1)
        complaint.status = StatusEnum.RESOLVED
        complaint.resolved_at = now - timedelta(days=40)
        file = _linked_file(
            db, complaint.id, path, b"old file", now - timedelta(days=45),
        )
        db.commit()
        file_id = file.id

    preview = client.post("/api/v1/admin/settings/files/retention/preview").json()
    policy = client.get("/api/v1/admin/settings/files").json()["retention"]
    changed = client.put("/api/v1/admin/settings/files/retention", json={
        "retention_days": policy["days"] + 1,
        "retention_scope": policy["scope"],
    })
    assert changed.status_code == 200
    assert changed.json()["retention"]["enabled"] is False
    assert client.post(
        "/api/v1/admin/settings/files/retention/enable",
        json={"preview_token": preview["preview_token"]},
    ).status_code == 409
    assert run_retention(factory, now=now)["status"] == "disabled"
    assert path.exists()
    with factory() as db:
        assert db.get(StoredFile, file_id).purged_at is None


def test_resolution_timestamp_starts_and_resets_with_status(system):
    client, factory = system
    login(client, "system_admin")
    resolved = client.patch(
        "/api/v1/complaints/1/status?new_status=RESOLVED",
        json={"reason": "تمت المعالجة"},
    )
    assert resolved.status_code == 200, resolved.text
    with factory() as db:
        first_resolved_at = db.get(Complaint, 1).resolved_at
        assert first_resolved_at is not None

    again = client.patch(
        "/api/v1/complaints/1/status?new_status=RESOLVED",
        json={"reason": "تأكيد المعالجة"},
    )
    assert again.status_code == 200
    with factory() as db:
        assert db.get(Complaint, 1).resolved_at == first_resolved_at

    reopened = client.patch(
        "/api/v1/complaints/1/status?new_status=IN_PROGRESS",
        json={"reason": "إعادة فتح"},
    )
    assert reopened.status_code == 200
    with factory() as db:
        assert db.get(Complaint, 1).resolved_at is None
