"""Hierarchical directorates flow scoped access downward, never upward."""
import pytest

from test_app import TEST_PASSWORD, login, system
from app.models.complaint import Complaint


@pytest.fixture(autouse=True)
def isolated_rate_limits():
    from app.core.security import _attempts

    _attempts.clear()
    yield
    _attempts.clear()


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


def test_employee_management_scope_includes_descendants_but_not_siblings(system):
    client, _ = system
    login(client, "governor")
    root = make_directorate(client, "إدارة نطاق الموظفين")
    child = make_directorate(client, "فرع تابع", root["id"])
    leaf = make_directorate(client, "مكتب تابع", child["id"])
    sibling = make_directorate(client, "فرع شقيق", root["id"])
    outside = make_directorate(client, "مديرية مستقلة")

    role = client.post(
        "/api/v1/admin/roles",
        json={
            "code": "employee_tree_manager",
            "name": "مدير موظفي الشجرة",
            "permissions": ["employees.manage"],
        },
    )
    assert role.status_code == 201, role.text
    manager = make_employee(client, "tree_manager", "0991113011", root["id"])
    child_manager = make_employee(client, "tree_child_mgr", "0991113018", child["id"])
    child_employee = make_employee(client, "tree_child", "0991113012", child["id"])
    leaf_employee = make_employee(client, "tree_leaf", "0991113013", leaf["id"])
    sibling_employee = make_employee(client, "tree_sibling", "0991113014", sibling["id"])
    outside_employee = make_employee(client, "tree_outside", "0991113015", outside["id"])
    grant_response = client.post(
        f"/api/v1/admin/employees/{manager['id']}/roles",
        json={
            "role_id": role.json()["id"],
            "scope_type": "directorate",
            "directorate_id": root["id"],
        },
    )
    assert grant_response.status_code == 201, grant_response.text
    child_grant = client.post(
        f"/api/v1/admin/employees/{child_manager['id']}/roles",
        json={
            "role_id": role.json()["id"],
            "scope_type": "directorate",
            "directorate_id": child["id"],
        },
    )
    assert child_grant.status_code == 201, child_grant.text

    client.cookies.clear()
    login(client, "tree_manager")
    managed_directories = client.get("/api/v1/admin/employees/directorates")
    assert managed_directories.status_code == 200, managed_directories.text
    assert {item["id"] for item in managed_directories.json()} == {
        root["id"],
        child["id"],
        leaf["id"],
        sibling["id"],
    }
    listing = client.get("/api/v1/admin/employees?page_size=100")
    assert listing.status_code == 200, listing.text
    listed_ids = {item["id"] for item in listing.json()["items"]}
    assert listed_ids == {
        manager["id"],
        child_manager["id"],
        child_employee["id"],
        leaf_employee["id"],
        sibling_employee["id"],
    }
    assert listing.json()["total"] == 5

    created = client.post(
        "/api/v1/admin/employees",
        json={
            "first_name": "موظف",
            "last_name": "جديد",
            "phone": "0991113016",
            "username": "tree_new",
            "password": TEST_PASSWORD,
            "directorate_id": leaf["id"],
        },
    )
    assert created.status_code == 201, created.text
    forbidden_create = client.post(
        "/api/v1/admin/employees",
        json={
            "first_name": "موظف",
            "last_name": "خارج",
            "phone": "0991113017",
            "username": "tree_forbidden",
            "password": TEST_PASSWORD,
            "directorate_id": outside["id"],
        },
    )
    assert forbidden_create.status_code == 403

    update_body = {
        "first_name": "موظف",
        "last_name": "نُقل",
        "phone": "0991113012",
        "email": None,
        "directorate_id": leaf["id"],
        "is_active": True,
    }
    assert client.put(
        f"/api/v1/admin/employees/{child_employee['id']}", json=update_body
    ).status_code == 200
    update_body["directorate_id"] = outside["id"]
    assert client.put(
        f"/api/v1/admin/employees/{child_employee['id']}", json=update_body
    ).status_code == 403
    assert client.put(
        f"/api/v1/admin/employees/{sibling_employee['id']}", json=update_body
    ).status_code == 403
    assert client.put(
        f"/api/v1/admin/employees/{outside_employee['id']}", json=update_body
    ).status_code == 404
    assert client.get("/api/v1/admin/roles").status_code == 403
    assert client.post(
        f"/api/v1/admin/employees/{child_employee['id']}/roles",
        json={
            "role_id": role.json()["id"],
            "scope_type": "directorate",
            "directorate_id": child["id"],
        },
    ).status_code == 403

    client.cookies.clear()
    login(client, "tree_child_mgr")
    child_directories = client.get("/api/v1/admin/employees/directorates")
    assert child_directories.status_code == 200, child_directories.text
    assert {item["id"] for item in child_directories.json()} == {
        child["id"],
        leaf["id"],
    }
    child_listing = client.get("/api/v1/admin/employees?page_size=100")
    assert child_listing.status_code == 200, child_listing.text
    child_ids = {item["id"] for item in child_listing.json()["items"]}
    assert child_ids == {
        child_manager["id"],
        child_employee["id"],
        leaf_employee["id"],
        created.json()["id"],
    }
    assert child_listing.json()["total"] == 4
    assert client.put(
        f"/api/v1/admin/employees/{manager['id']}", json=update_body
    ).status_code == 404
    assert client.put(
        f"/api/v1/admin/employees/{sibling_employee['id']}", json=update_body
    ).status_code == 404
