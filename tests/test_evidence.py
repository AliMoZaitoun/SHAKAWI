"""Evidence regression tests: synthetic data, no real Telegram delivery."""
import asyncio
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from test_app import system, login
from app.models.complaint import Complaint, ComplaintNote, EvidenceRequest, EvidenceReply, EvidenceFile
from app.core.security import _attempts


@pytest.fixture
def evidence_system(system):
    _attempts.clear()
    return system


def create(client, cid=2, key="request-key-00000001"):
    return client.post(f"/api/v1/complaints/{cid}/evidence",
                       json={"prompt": "أرسل صورة واضحة للموقع", "submission_key": key})


def reply(client, rid, cid=2, text="توضيح المواطن", key="reply-key-0000000001", files=None, headers=None):
    return client.post(f"/api/v1/complaints/{cid}/evidence/{rid}/reply",
                       data={"text": text, "submission_key": key}, files=files, headers=headers or {})


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, "PNG")
    return buffer.getvalue()


def setup_request(client):
    login(client, "services")
    result = create(client)
    assert result.status_code == 200, result.text
    client.cookies.clear()
    return result.json()["request"]["id"]


def test_bot_owner_detail_lists_direct_and_requested_evidence(evidence_system, monkeypatch):
    client, _ = evidence_system
    monkeypatch.setenv("BOT_TOKEN", "test-only-bot-token")
    owner_headers = {
        "X-Bot-Token": "test-only-bot-token",
        "X-Telegram-Id": "123456",
    }
    uploaded = client.post(
        "/api/v1/complaints/2/attachments/",
        headers=owner_headers,
        files={"file": ("direct-photo.png", png(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text

    request_id = setup_request(client)
    response = reply(
        client,
        request_id,
        cid=2,
        text="صورة توضيحية جديدة",
        key="reply-key-0000000020",
        files=[("files", ("reply-photo.png", png(), "image/png"))],
        headers=owner_headers,
    )
    assert response.status_code == 200, response.text

    detail = client.get("/api/v1/complaints/2", headers=owner_headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["attachments"][0]["name"] == "direct-photo.png"
    evidence = payload["evidence_requests"][0]
    assert evidence["prompt"] == "أرسل صورة واضحة للموقع"
    assert evidence["replies"][0]["text"] == "صورة توضيحية جديدة"
    assert evidence["replies"][0]["attachments"][0]["name"] == "reply-photo.png"

    unauthorized = client.get("/api/v1/complaints/2", headers={
        "X-Bot-Token": "test-only-bot-token",
        "X-Telegram-Id": "999999",
    })
    assert unauthorized.status_code == 403


def test_guest_single_complaint_capability_and_staff_scope(evidence_system):
    client, factory = evidence_system
    assert create(client).status_code == 401
    login(client, "services")
    assert create(client, 1).status_code == 403
    result = create(client)
    rid = result.json()["request"]["id"]
    assert result.json()["notification"]["status"] == "not_configured"
    assert create(client).json()["request"]["id"] == rid
    assert client.post("/api/v1/complaints/2/evidence", json={
        "prompt": "مضمون مختلف", "submission_key": "request-key-00000001"}).status_code == 409
    client.cookies.clear()
    assert reply(client, rid).status_code == 403
    assert client.get("/api/v1/complaints/track/2").status_code == 404
    assert client.get("/api/v1/complaints/track/12345678901").status_code == 404
    assert client.get("/api/v1/complaints/track/CMP-GOVERNOR").status_code == 200
    assert reply(client, rid).status_code == 403
    assert client.get("/api/v1/complaints/track/CMP-SERVICES").status_code == 200
    assert client.get("/api/v1/complaints/citizen/1").status_code == 403
    assert client.get("/api/v1/citizens/recovery/me").status_code == 403
    assert reply(client, rid, cid=1).status_code == 404
    assert reply(client, rid).status_code == 200
    with factory() as db:
        row = db.get(Complaint, 2)
        assert row.progress == 0 and row.status.value == "PENDING"
        assert db.get(EvidenceRequest, rid).status == "answered"
    login(client, "services")
    follow = create(client, key="request-key-00000002")
    assert follow.status_code == 200 and follow.json()["request"]["status"] == "pending"
    login(client, "system_admin")
    assert create(client, 1).status_code == 200


def test_atomic_files_idempotency_and_private_download(evidence_system):
    client, factory = evidence_system
    rid = setup_request(client)
    client.get("/api/v1/complaints/track/CMP-SERVICES")
    files = [("files", ("safe.png", png(), "image/png")),
             ("files", ("bad.html", b"<html>bad</html>", "image/png"))]
    assert reply(client, rid, files=files).status_code == 415
    with factory() as db:
        assert db.query(EvidenceReply).count() == 0 and db.query(EvidenceFile).count() == 0
        assert db.get(EvidenceRequest, rid).status == "pending"
    assert not list(Path("uploads/evidence").glob("*"))
    files = [("files", ("safe.png", png(), "image/png"))]
    result = reply(client, rid, files=files)
    assert result.status_code == 200, result.text
    saved = result.json()["reply"]
    assert reply(client, rid, files=files).json()["reply"]["id"] == saved["id"]
    assert reply(client, rid, text="تغيير بعد الحفظ", files=files).status_code == 409
    assert reply(client, rid, key="different-key-0000000", files=files).status_code == 409
    url = saved["attachments"][0]["file_url"]
    download = client.get(url)
    assert download.content == png()
    assert "attachment;" in download.headers["content-disposition"]
    assert "file_path" not in result.text
    client.cookies.clear()
    assert client.get(url).status_code == 403
    client.get("/api/v1/complaints/track/CMP-GOVERNOR")
    assert client.get(url).status_code == 403
    login(client, "services")
    assert client.get(url).status_code == 200
    with factory() as db:
        db.get(Complaint, 2).directorate_id = 1
        db.commit()
    assert client.get(url).status_code == 403
    assert client.get("/api/v1/complaints/2/evidence").status_code == 403
    login(client, "system_admin")
    assert client.get(url).status_code == 200
    assert len(list(Path("uploads/evidence").glob("*"))) == 1


@pytest.mark.parametrize("name,raw,mime,expected", [
    ("../../evil.png", b"a", "image/png", 422),
    ("evil.svg", b"<svg onload='alert(1)'/>", "image/svg+xml", 415),
    ("evil.jpg", b"MZ executable", "image/jpeg", 415),
    ("fake.pdf", b"%PDF-test", "application/pdf", 415),
    ("empty.png", b"", "image/png", 413),
    ("large.png", b"x" * (10 * 1024 * 1024 + 1), "image/png", 413),
    ("wrong.jpg", b"PNG placeholder", "image/jpeg", 415),
])
def test_reject_unsafe_files(evidence_system, name, raw, mime, expected):
    client, _ = evidence_system
    rid = setup_request(client)
    client.get("/api/v1/complaints/track/CMP-SERVICES")
    assert reply(client, rid, files=[("files", (name, raw, mime))]).status_code == expected


def test_file_count_and_file_only_answer(evidence_system):
    client, _ = evidence_system
    rid = setup_request(client)
    client.get("/api/v1/complaints/track/CMP-SERVICES")
    assert reply(client, rid, text="").status_code == 422
    files = [("files", (f"{n}.png", png(), "image/png")) for n in range(6)]
    assert reply(client, rid, text="", files=files).status_code == 422
    assert reply(client, rid, text="", files=files[:1]).status_code == 200


def test_public_views_never_contain_private_correspondence(evidence_system):
    client, factory = evidence_system
    with factory() as db:
        db.get(Complaint, 2).is_public = True
        db.add(ComplaintNote(complaint_id=2, author_id=2, note="مراسلة قديمة خاصة", is_internal=False))
        db.commit()
    rid = setup_request(client)
    client.get("/api/v1/complaints/track/CMP-SERVICES")
    assert reply(client, rid, files=[("files", ("safe.png", png(), "image/png"))]).status_code == 200
    for url in ["/api/v1/complaints/public", "/api/v1/complaints/public/2"]:
        body = client.get(url).text
        for secret in ["أرسل صورة", "توضيح المواطن", "مراسلة قديمة", "evidence", "safe.png", "12345678901"]:
            assert secret not in body
    owner = client.get("/api/v1/complaints/track/CMP-SERVICES").json()
    assert owner["notes"][0]["note"] == "مراسلة قديمة خاصة"
    login(client, "services")
    assert client.post("/api/v1/complaints/2/notes", json={
        "note": "معلومة منشورة صراحة", "audience": "public"}).status_code == 200
    assert client.post("/api/v1/complaints/2/notes", json={
        "note": "معلومة للموظفين", "audience": "internal"}).status_code == 200
    assert "معلومة منشورة صراحة" in client.get("/api/v1/complaints/public/2").text
    assert "معلومة للموظفين" not in client.get("/api/v1/complaints/public/2").text


def test_bot_sender_checked_server_side_and_replay(evidence_system, monkeypatch):
    client, _ = evidence_system
    rid = setup_request(client)
    monkeypatch.setenv("BOT_TOKEN", "fake-only-test")
    base = {"X-Bot-Token": "fake-only-test"}
    assert reply(client, rid, headers=base).status_code == 403
    assert reply(client, rid, headers={**base, "X-Telegram-Id": "999"}).status_code == 403
    actor = {**base, "X-Telegram-Id": "123456"}
    result = reply(client, rid, headers=actor)
    assert result.status_code == 200 and result.json()["reply"]["channel"] == "telegram"
    assert reply(client, rid, headers=actor).json() == result.json()
    assert reply(client, rid, headers={**base, "X-Telegram-Id": "999"}).status_code == 403


def test_notification_failure_retry_cooldown_and_no_duplicate(evidence_system, monkeypatch):
    from app.api.v1.endpoints import evidence
    client, factory = evidence_system
    sender = AsyncMock(return_value={"status": "failed", "message": "تعذر التنبيه"})
    monkeypatch.setattr(evidence, "notify", sender)
    login(client, "services")
    result = create(client)
    assert result.status_code == 200
    rid = result.json()["request"]["id"]
    assert sender.call_args.kwargs["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"evidence_2_{rid}"
    path = f"/api/v1/complaints/2/evidence/{rid}/retry"
    assert client.post(path).status_code == 429
    assert create(client).json()["request"]["id"] == rid
    assert sender.await_count == 1
    with factory() as db:
        db.get(EvidenceRequest, rid).notification_attempted_at = 0
        db.commit()
    sender.return_value = {"status": "sent", "message": "تم التنبيه"}
    assert client.post(path).json()["status"] == "sent"
    assert client.post(path).json()["status"] == "sent"
    assert sender.await_count == 2
    with factory() as db:
        assert db.query(EvidenceRequest).count() == 1


def test_migration_preserves_private_legacy_notes():
    from sqlalchemy import create_engine, text
    from app.db.migrations import migrate
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE complaints (id INTEGER PRIMARY KEY, status TEXT)"))
        conn.execute(text("CREATE TABLE employees (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE complaint_notes (id INTEGER PRIMARY KEY, note TEXT, is_internal BOOLEAN)"))
        conn.execute(text("INSERT INTO complaint_notes VALUES (1, 'owner visible', 0), (2, 'internal', 1)"))
    migrate(engine)
    migrate(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT audience FROM complaint_notes ORDER BY id")).scalars().all() == ["private", "internal"]


def test_bot_draft_cancel_isolation_and_save_confirmation(monkeypatch):
    from bot.handlers import evidence
    class State:
        def __init__(self):
            self.data = {}
            self.state = None
        async def get_data(self):
            return self.data.copy()
        async def update_data(self, **kw):
            self.data.update(kw)
        async def get_state(self):
            return self.state
        async def set_state(self, value):
            self.state = getattr(value, "state", value)

    async def scenario():
        state = State()
        actor = SimpleNamespace(id=123456)
        msg = SimpleNamespace(chat=SimpleNamespace(type="private"), from_user=actor,
                              answer=AsyncMock(), text="دليل المواطن", photo=None, document=None)
        cb = SimpleNamespace(message=msg, from_user=actor, data="evidence_2_7", answer=AsyncMock())
        check = AsyncMock(return_value={"id": 7, "status": "pending", "prompt": "مطلوب دليل"})
        monkeypatch.setattr(evidence, "authorized", check)
        await evidence.begin(cb, state)
        await evidence.collect(msg, state)
        draft = state.data["evidence_draft"].copy()
        assert draft["text"] == "دليل المواطن"
        await evidence.cancel(msg, state)
        assert state.data["evidence_draft"] == draft and state.state is None
        msg.text = "/start"
        await evidence.protect_paused_draft(msg, state)
        assert state.data["evidence_draft"] == draft and state.state is None
        assert "/discard" in msg.answer.call_args.args[0]
        cb.data = "action_new_complaint"
        await evidence.protect_paused_callback(cb, state)
        assert state.data["evidence_draft"] == draft
        cb.data = "evidence_2_8"
        await evidence.begin(cb, state)
        assert state.state is None and state.data["evidence_draft"]["rid"] == 7
        cb.data = "evidence_2_7"
        await evidence.begin(cb, state)
        assert state.state == evidence.EvidenceFlow.drafting.state
        # An unrelated command never feeds the complaint-creation state machine.
        msg.text = "/new"
        await evidence.collect(msg, state)
        assert state.data["evidence_draft"]["rid"] == 7
        check.side_effect = ValueError("ownership")
        msg.text = "نص ممنوع"
        await evidence.collect(msg, state)
        assert state.data["evidence_draft"]["text"] == draft["text"]
        assert check.call_args.args[0].from_user.id == 123456
    asyncio.run(scenario())


def test_bot_full_flow_uses_api_and_recovers_lost_response(evidence_system, monkeypatch):
    """Real API authorization, multipart validation and persistence behind fake transport."""
    from bot.handlers import evidence
    client, factory = evidence_system
    rid = setup_request(client)
    monkeypatch.setenv("BOT_TOKEN", "local-test-bot")
    monkeypatch.setattr(evidence, "API_HEADERS", {"X-Bot-Token": "local-test-bot"})
    sent = []
    lose_once = [True]

    class Response:
        def __init__(self, response, lose=False):
            self.response = response
            self.status = response.status_code
            self.lose = lose
        async def __aenter__(self):
            if self.lose:
                raise evidence.aiohttp.ClientConnectionError("lost response")
            return self
        async def __aexit__(self, *args):
            pass
        async def json(self):
            return self.response.json()

    class Session:
        def __init__(self, headers=None, **kwargs):
            self.headers = headers
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def get(self, url):
            return Response(client.get("/api/v1/" + url.split("/api/v1/")[1], headers=self.headers))
        def post(self, url, data):
            fields, files = {}, []
            for options, _, value in data._fields:
                if options["name"] == "files":
                    files.append(("files", (options["filename"], value, "image/png")))
                else:
                    fields[options["name"]] = value
            result = client.post("/api/v1/" + url.split("/api/v1/")[1], data=fields,
                                 files=files, headers=self.headers)
            sent.append(result.status_code)
            lose = lose_once[0]
            lose_once[0] = False
            return Response(result, lose)
    monkeypatch.setattr(evidence.aiohttp, "ClientSession", Session)

    class State:
        def __init__(self):
            self.data = {}
            self.state = None
        async def get_data(self):
            return self.data.copy()
        async def update_data(self, **kw):
            self.data.update(kw)
        async def get_state(self):
            return self.state
        async def set_state(self, value):
            self.state = getattr(value, "state", value)

    async def scenario():
        state = State()
        msg = SimpleNamespace(chat=SimpleNamespace(type="private"),
                              from_user=SimpleNamespace(id=999), answer=AsyncMock(),
                              text=None, photo=None, document=None)
        cb = SimpleNamespace(message=msg, from_user=msg.from_user,
                             data=f"evidence_2_{rid}", answer=AsyncMock())
        await evidence.begin(cb, state)
        assert state.state is None  # Forged/forwarded callback cannot open another owner's request.
        cb.from_user = msg.from_user = SimpleNamespace(id=123456)
        await evidence.begin(cb, state)
        msg.text = "رد موثق من البوت"
        await evidence.collect(msg, state)
        msg.text = None
        msg.document = SimpleNamespace(file_id="telegram-file", file_name="proof.png",
                                       mime_type="image/png", file_size=len(png()))
        msg.bot = SimpleNamespace(download=AsyncMock(side_effect=lambda fid, destination: destination.write(png())))
        await evidence.collect(msg, state)
        msg.document = None
        msg.text = "/send"
        await evidence.collect(msg, state)
        assert state.data["evidence_draft"] and state.data["evidence_draft"]["attempted"]
        assert "لم تُحذف المسودة" in msg.answer.call_args.args[0]
        await evidence.collect(msg, state)
        assert state.data["evidence_draft"] is None and state.state is None
        assert "تم حفظ الرد" in msg.answer.call_args.args[0]
        assert sent == [200, 200]
    asyncio.run(scenario())
    with factory() as db:
        assert db.query(EvidenceReply).count() == 1
        assert db.query(EvidenceFile).count() == 1
        assert db.query(EvidenceReply).one().channel == "telegram"
        assert db.get(EvidenceRequest, rid).status == "answered"
