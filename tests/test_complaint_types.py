from test_app import login, system


def test_complaint_type_catalog_permissions_translations_and_other_rule(system):
    client, _ = system
    assert client.get("/api/v1/complaint-types?lang=en").status_code == 200
    defaults = client.get("/api/v1/complaint-types?lang=en").json()
    roads = next(item for item in defaults if item["code"] == "roads")
    other = next(item for item in defaults if item["code"] == "other")
    assert roads["name"] == "Roads"
    assert other["name"] == "Other" and other["sla_duration_minutes"] is None

    login(client, "services")
    assert client.get("/api/v1/admin/complaint-types").status_code == 403
    assert client.post("/api/v1/admin/complaint-types", json={
        "name": "نظافة", "description": "اذكر موقع المشكلة", "sla_duration_minutes": 20160,
    }).status_code == 403

    login(client, "system_admin")
    created = client.post("/api/v1/admin/complaint-types", json={
        "name": "نظافة", "description": "اذكر موقع المشكلة", "sla_duration_minutes": 20160,
    })
    assert created.status_code == 201, created.text
    complaint_type = created.json()
    assert complaint_type["sla_duration_minutes"] == 20160

    assert client.post("/api/v1/admin/languages", json={
        "code": "fr", "name": "Français", "direction": "ltr",
    }).status_code == 201
    translated = client.put(
        f"/api/v1/admin/translations/complaint_types/{complaint_type['id']}/fr",
        json={"name": "Propreté", "description": "Indiquez le lieu"},
    )
    assert translated.status_code == 200, translated.text
    french_types = client.get("/api/v1/complaint-types?lang=fr").json()
    assert next(item for item in french_types if item["id"] == complaint_type["id"])["name"] == "Propreté"

    invalid_other = client.put(f"/api/v1/admin/complaint-types/{other['id']}", json={
        "name": "أخرى", "description": "", "sla_duration_minutes": 1440, "is_active": True,
    })
    assert invalid_other.status_code == 422
    deactivate_other = client.put(f"/api/v1/admin/complaint-types/{other['id']}", json={
        "name": "أخرى", "description": "", "sla_duration_minutes": None, "is_active": False,
    })
    assert deactivate_other.status_code == 409


def test_complaint_saves_type_and_sla_snapshot_without_rewriting_history(system):
    client, factory = system
    login(client, "system_admin")
    created = client.post("/api/v1/admin/complaint-types", json={
        "name": "معالجة الطرق", "description": "اذكر الشارع", "sla_duration_minutes": 20160,
    })
    assert created.status_code == 201, created.text
    complaint_type = created.json()
    assert client.put(
        f"/api/v1/admin/translations/complaint_types/{complaint_type['id']}/en",
        json={"name": "Road repair", "description": "Include the street"},
    ).status_code == 200

    client.post("/api/v1/auth/logout")
    citizen = client.post("/api/v1/citizens/", json={
        "first_name": "مواطن", "last_name": "تجريبي", "phone": "0998765401",
        "national_id": "98765432109",
    })
    assert citizen.status_code == 200, citizen.text
    complaint = client.post("/api/v1/complaints/", headers={"Accept-Language": "en"}, json={
        "citizen_id": citizen.json()["id"],
        "directorate_id": 2,
        "title": "Road repair request",
        "details": "Please repair this road near the main school.",
        "complaint_type_id": complaint_type["id"],
        "is_public": True,
    })
    assert complaint.status_code == 200, complaint.text
    result = complaint.json()
    assert result["category"] == "Road repair"
    assert result["complaint_type"]["sla_duration_minutes"] == 20160

    login(client, "system_admin")
    assert client.put(f"/api/v1/admin/complaint-types/{complaint_type['id']}", json={
        "name": "معالجة الطرق", "description": "اذكر الشارع",
        "sla_duration_minutes": 30240, "is_active": True,
    }).status_code == 200
    tracked = client.get(
        f"/api/v1/complaints/track/{result['tracking_code']}?lang=en",
    )
    assert tracked.status_code == 200
    assert tracked.json()["complaint_type"]["name"] == "Road repair"
    assert tracked.json()["complaint_type"]["sla_duration_minutes"] == 20160

    public = client.get("/api/v1/complaints/public?category=Road%20repair", headers={
        "Accept-Language": "en",
    })
    assert public.status_code == 200
    assert any(item["id"] == result["id"] for item in public.json()["items"])
    with factory() as db:
        from app.models.complaint import Complaint
        stored = db.get(Complaint, result["id"])
        assert stored.category == "معالجة الطرق"
        assert stored.sla_duration_minutes == 20160
