"""Hierarchical directorates flow scoped access downward, never upward."""
from test_app import TEST_PASSWORD, login, system
from app.models.complaint import Complaint


def make_directorate(client, name, parent_id=None):
    response = client.post(
        "/api/v1/admin/directorates",
        json={
            "name": name,
            "description": "",
            "location": "",
            "parent_id": parent_id,
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def make_employee(client, username, phone, directorate_id):
    response = client.post(
        "/api/v1/admin/employees",
        json={
            "first_name": "موظف",
            "last_name": "اختبار",
            "phone": phone,
            "username": username,
            "password": TEST_PASSWORD,
            "directorate_id": directorate_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_parent_grant_flows_to_descendants_but_child_cannot_see_parent_or_sibling(system):
    client, factory = system
    login(client, "governor")
    root = make_directorate(client, "الإدارة الإقليمية")
    branch = make_directorate(client, "فرع المياه", root["id"])
    leaf = make_directorate(client, "مكتب الصيانة", branch["id"])
    sibling = make_directorate(client, "فرع الكهرباء", root["id"])
    outside = make_directorate(client, "إدارة مستقلة")

    role_response = client.post(
        "/api/v1/admin/roles",
        json={
            "code": "tree_complaint_reader",
            "name": "قارئ نطاق الشجرة",
            "permissions": ["complaints.view", "reports.view"],
        },
    )
    assert role_response.status_code == 201, role_response.text
    role_id = role_response.json()["id"]
    parent_employee = make_employee(client, "parent_reader", "0991112011", root["id"])
    child_employee = make_employee(client, "child_reader", "0991112012", branch["id"])
    for employee, directorate_id in (
        (parent_employee, root["id"]),
        (child_employee, branch["id"]),
    ):
        response = client.post(
            f"/api/v1/admin/employees/{employee['id']}/roles",
            json={
                "role_id": role_id,
                "scope_type": "directorate",
                "directorate_id": directorate_id,
            },
        )
        assert response.status_code == 201, response.text

    with factory() as db:
        existing = db.query(Complaint).order_by(Complaint.id).all()
        existing[0].directorate_id = root["id"]
        existing[1].directorate_id = branch["id"]
        citizen_id = existing[0].citizen_id
        for code, directorate_id in (
            ("CMP-HIER-LEAF", leaf["id"]),
            ("CMP-HIER-SIBLING", sibling["id"]),
            ("CMP-HIER-OUTSIDE", outside["id"]),
        ):
            db.add(
                Complaint(
                    citizen_id=citizen_id,
                    directorate_id=directorate_id,
                    tracking_code=code,
                    title="شكوى اختبارية ضمن النطاق",
                    details="هذه شكوى اصطناعية لاختبار نطاق الصلاحيات.",
                    category="اختبار",
                )
            )
        db.commit()

    login(client, "parent_reader")
    parent_session = client.get("/api/v1/auth/me").json()
    assert parent_session["permissions"]["complaints.view"]["directorate_ids"] == sorted(
        [root["id"], branch["id"], leaf["id"], sibling["id"]]
    )
    parent_complaints = client.get("/api/v1/complaints/").json()
    parent_codes = {item["tracking_code"] for item in parent_complaints}
    assert parent_codes == {
        "CMP-GOVERNOR",
        "CMP-SERVICES",
        "CMP-HIER-LEAF",
        "CMP-HIER-SIBLING",
    }
    assert client.get("/api/v1/complaints/1").status_code == 200
    assert client.get("/api/v1/complaints/2").status_code == 200
    assert client.get("/api/v1/admin/roles").status_code == 403

    client.cookies.clear()
    login(client, "child_reader")
    child_session = client.get("/api/v1/auth/me").json()
    assert child_session["permissions"]["complaints.view"]["directorate_ids"] == sorted(
        [branch["id"], leaf["id"]]
    )
    child_complaints = client.get("/api/v1/complaints/").json()
    assert {item["tracking_code"] for item in child_complaints} == {
        "CMP-SERVICES",
        "CMP-HIER-LEAF",
    }
    assert client.get("/api/v1/complaints/1").status_code == 403
    assert client.get("/api/v1/complaints/2").status_code == 200
    assert client.get("/api/v1/complaints/4").status_code == 403
    assert client.get("/api/v1/complaints/5").status_code == 403
    assert client.get(f"/api/v1/analytics?directorate_id={root['id']}").status_code == 403
    assert client.get(f"/api/v1/analytics?directorate_id={leaf['id']}").status_code == 200


def test_directorate_parent_validation_rejects_cycles_and_parent_deletion(system):
    client, _ = system
    login(client, "governor")
    parent = make_directorate(client, "المديرية العليا")
    child = make_directorate(client, "المديرية التابعة", parent["id"])
    sibling = make_directorate(client, "مديرية أخرى")

    listed = client.get("/api/v1/admin/directorates").json()
    child_data = next(item for item in listed if item["id"] == child["id"])
    assert child_data["parent_id"] == parent["id"]
    assert child_data["parent_name"] == "المديرية العليا"
    assert child_data["hierarchy_path"] == "المديرية العليا / المديرية التابعة"

    invalid = client.put(
        f"/api/v1/admin/directorates/{parent['id']}",
        json={
            "name": parent["name"],
            "description": "",
            "location": "",
            "is_active": True,
            "parent_id": child["id"],
        },
    )
    assert invalid.status_code == 422
    self_parent = client.put(
        f"/api/v1/admin/directorates/{sibling['id']}",
        json={
            "name": sibling["name"],
            "description": "",
            "location": "",
            "is_active": True,
            "parent_id": sibling["id"],
        },
    )
    assert self_parent.status_code == 422
    missing_parent = client.post(
        "/api/v1/admin/directorates",
        json={"name": "مديرية غير صالحة", "parent_id": 999999},
    )
    assert missing_parent.status_code == 422
    assert client.delete(f"/api/v1/admin/directorates/{parent['id']}").status_code == 409
    assert client.delete(f"/api/v1/admin/directorates/{sibling['id']}").status_code == 200
