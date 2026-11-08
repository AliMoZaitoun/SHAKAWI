"""Scoped RBAC and identity-transition checks; all people/data are synthetic."""
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from test_app import system, login, TEST_PASSWORD
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.db.migrations import migrate
from app.models.access import AccessAudit, Directorate, Role, RoleAssignment, User
from app.models.user import Citizen, Employee
from app.services.access import bootstrap_access


@pytest.fixture(autouse=True)
def isolated_rate_limits():
    from app.core.security import _attempts
    _attempts.clear()
    yield
    _attempts.clear()


def admin(client):
    login(client, "governor")
    return client


def new_employee(client, username="receiver", phone="0991112233"):
    response = client.post("/api/v1/admin/employees", json={
        "first_name": "موظف", "last_name": "تجريبي", "phone": phone,
        "username": username, "password": TEST_PASSWORD, "directorate_id": 2,
    })
    assert response.status_code == 201, response.text
    assert "password" not in response.text
    return response.json()


def new_role(client, permissions, code="test_reader"):
    response = client.post("/api/v1/admin/roles", json={
        "code": code, "name": "دور تجريبي", "permissions": permissions,
    })
    assert response.status_code == 201, response.text
    return response.json()


def grant(client, employee_id, role_id, directorate_id=2):
    return client.post(f"/api/v1/admin/employees/{employee_id}/roles", json={
        "role_id": role_id, "scope_type": "global" if directorate_id is None else "directorate",
        "directorate_id": directorate_id,
    })


def test_catalog_and_new_roles_are_not_a_guessed_permission_matrix(system):
    client, factory = system
    assert client.get("/api/v1/admin/roles").status_code == 401
    login(client, "services")
    assert client.get("/api/v1/admin/roles").status_code == 403
    admin(client)
    roles = {row["code"]: row for row in client.get("/api/v1/admin/roles").json()}
    for code in ("technical_assistant", "complaint_receiver", "branch_manager"):
        assert roles[code]["permissions"] == []
    assert "rbac.manage" in roles["governor"]["permissions"]
    assert "rbac.manage" not in roles["legacy_department_staff"]["permissions"]
    with factory() as db:
        assert db.query(User).count() == 3
        assert db.get(Citizen, 1).user.phone == "0912345678"
        employee = db.get(Employee, 1)
        assert verify_password(TEST_PASSWORD, employee.user.hashed_password)
        assert employee.user.needs_profile_completion is True
        bootstrap_access(db)
        assert db.query(User).count() == 3
        assert db.query(RoleAssignment).count() == 2


def test_explicit_grants_filter_queries_and_revoke_live(system):
    client, factory = system
    admin(client)
    employee = new_employee(client)
    reader = new_role(client, ["complaints.view", "reports.view"])
    assert grant(client, employee["id"], reader["id"]).status_code == 201
    login(client, "receiver")
    assert len(client.get("/api/v1/complaints/").json()) == 1
    assert client.get("/api/v1/complaints/1").status_code == 403
    assert client.get("/api/v1/complaints/2").status_code == 200
    assert client.patch("/api/v1/complaints/2/status?new_status=IN_PROGRESS", json={}).status_code == 403
    assert client.get("/api/v1/analytics").json()["total"] == 1
    assert client.get("/api/v1/analytics?directorate_id=1").status_code == 403
    # Permission evaluation must not be frozen into a session cookie.
    with factory() as db:
        role = db.get(Role, reader["id"])
        role.permissions = []
        db.commit()
    assert client.get("/api/v1/complaints/").status_code == 403
    assert client.get("/api/v1/analytics").status_code == 403
    assert client.get("/api/v1/admin/roles").status_code == 403


def test_new_employee_has_no_inherited_legacy_rights_and_no_escalation(system):
    client, factory = system
    admin(client)
    employee = new_employee(client)
    login(client, "receiver")
    assert client.get("/api/v1/complaints/").status_code == 403
    assert client.post("/api/v1/admin/roles", json={
        "code": "escalate", "name": "تصعيد", "permissions": ["rbac.manage"],
    }).status_code == 403
    with factory() as db:
        bootstrap_access(db)
        assert db.get(Employee, employee["id"]).role_assignments == []
    assert client.get("/api/v1/complaints/").status_code == 403


def test_last_admin_guards_and_failed_mutations_rollback(system):
    client, factory = system
    admin(client)
    role = next(row for row in client.get("/api/v1/admin/roles").json() if row["code"] == "governor")
    assert client.put(f"/api/v1/admin/roles/{role['id']}", json={
        "name": "المحافظ", "permissions": [],
    }).status_code == 409
    assert "rbac.manage" in next(row for row in client.get("/api/v1/admin/roles").json()
                               if row["id"] == role["id"])["permissions"]
    with factory() as db:
        assignment = db.query(RoleAssignment).filter_by(employee_id=1).one()
        assignment_id = assignment.id
    assert client.delete(f"/api/v1/admin/employees/1/roles/{assignment_id}").status_code == 409
    assert client.put("/api/v1/admin/employees/1", json={
        "first_name": "مدير", "last_name": "تجريبي", "phone": "0998887766",
        "directorate_id": None, "is_active": False,
    }).status_code == 409
    assert client.get("/api/v1/admin/roles").status_code == 200
    assert client.delete(f"/api/v1/admin/roles/{role['id']}").status_code == 409
    with factory() as db:
        assert db.query(AccessAudit).count() == 0


def test_duplicate_scope_and_branch_admin_cannot_manage_global_access(system):
    client, factory = system
    admin(client)
    employee = new_employee(client)
    role = new_role(client, ["rbac.manage", "complaints.view"])
    assert grant(client, employee["id"], role["id"]).status_code == 201
    assert grant(client, employee["id"], role["id"]).status_code == 409
    assert client.post(f"/api/v1/admin/employees/{employee['id']}/roles", json={
        "role_id": role["id"], "scope_type": "global", "directorate_id": 2,
    }).status_code == 422
    login(client, "receiver")
    assert client.get("/api/v1/complaints/2").status_code == 200
    assert client.get("/api/v1/admin/roles").status_code == 403


def test_dynamic_directorates_manager_relationship_and_referenced_delete(system):
    client, factory = system
    admin(client)
    response = client.post("/api/v1/admin/directorates", json={"name": "فرع ثالث", "location": "موقع تجريبي"})
    assert response.status_code == 201
    directorate_id = response.json()["id"]
    assert directorate_id > 2
    employee = new_employee(client)
    manager = next(row for row in client.get("/api/v1/admin/roles").json() if row["code"] == "branch_manager")
    assert grant(client, employee["id"], manager["id"], directorate_id).status_code == 201
    directories = client.get("/api/v1/admin/directorates").json()
    assert next(row for row in directories if row["id"] == directorate_id)["current_manager"]["employee_id"] == employee["id"]
    assert grant(client, 1, manager["id"], directorate_id).status_code == 409
    assert client.delete(f"/api/v1/admin/directorates/{directorate_id}").status_code == 409
    public = client.get("/api/v1/directorates").json()
    assert all("current_manager" not in row for row in public)
    with factory() as db:
        assert db.query(AccessAudit).count() == 3
        assert "hashed_password" not in "".join(row.details for row in db.query(AccessAudit))


def test_profile_edit_syncs_canonical_user_and_legacy_login(system):
    client, factory = system
    admin(client)
    employee = new_employee(client)
    response = client.put(f"/api/v1/admin/employees/{employee['id']}", json={
        "first_name": "اسم", "last_name": "جديد", "phone": "0991113344",
        "email": "synthetic@example.invalid", "directorate_id": 2, "is_active": True,
    })
    assert response.status_code == 200, response.text
    with factory() as db:
        row = db.get(Employee, employee["id"])
        assert row.full_name == "اسم جديد"
        assert row.user.email == "synthetic@example.invalid"
        citizen = db.get(Citizen, 1)
        citizen.first_name = "مواطن"
        db.commit()
        assert citizen.user.first_name == "مواطن"
    assert login(client, "receiver")["user_id"] == employee["user_id"]


def test_employee_can_have_citizen_profile_only_with_account_ownership(system):
    client, factory = system
    admin(client)
    employee = new_employee(client)
    login(client, "receiver")
    data = {"first_name": "موظف", "last_name": "تجريبي", "phone": "0991112233",
            "national_id": "44455566677"}
    response = client.post("/api/v1/citizens/", json=data)
    assert response.status_code == 200, response.text
    with factory() as db:
        citizen = db.get(Citizen, response.json()["id"])
        assert citizen.user_id == employee["user_id"]
        assert db.query(User).count() == 4
    client.post("/api/v1/auth/logout")
    assert client.post("/api/v1/citizens/", json=data).status_code == 409


def test_multi_branch_scope_and_permission_specific_details(system):
    client, factory = system
    admin(client)
    employee = new_employee(client)
    reader = new_role(client, ["complaints.view", "reports.view", "complaints.update"])
    assert grant(client, employee["id"], reader["id"], 1).status_code == 201
    assert grant(client, employee["id"], reader["id"], 2).status_code == 201
    login(client, "receiver")
    assert len(client.get("/api/v1/complaints/").json()) == 2
    assert client.get("/api/v1/analytics").json()["total"] == 2
    detail = client.get("/api/v1/complaints/2").json()
    assert detail["evidence_requests"] == []
    assert detail["attachments"] == []
    assert client.get("/api/v1/complaints/2/evidence").status_code == 403
    assert client.patch("/api/v1/complaints/2/status?new_status=IN_PROGRESS", json={"progress": 20}).status_code == 200
    assert client.patch("/api/v1/complaints/2/status?new_status=RESOLVED", json={}).status_code == 403


def test_catalog_metadata_role_lifecycle_and_unused_directorate_delete(system):
    client, factory = system
    admin(client)
    assert client.post("/api/v1/admin/roles", json={
        "code": "unknown_permission", "name": "صلاحية وهمية", "permissions": ["unsupported.action"],
    }).status_code == 422
    assert client.patch("/api/v1/admin/permissions/complaints.view", json={
        "name": "عرض تفاصيل الشكوى", "description": "وصف تجريبي",
    }).status_code == 200
    role = new_role(client, ["complaints.view"], code="temporary_role")
    assert client.put(f"/api/v1/admin/roles/{role['id']}", json={
        "name": "اسم معدل", "description": "", "permissions": ["reports.view"],
    }).status_code == 200
    assert client.delete(f"/api/v1/admin/roles/{role['id']}").status_code == 200
    directory = client.post("/api/v1/admin/directorates", json={"name": "فرع مؤقت"}).json()
    assert client.put(f"/api/v1/admin/directorates/{directory['id']}", json={
        "name": "فرع معطل", "is_active": False,
    }).status_code == 200
    assert directory["id"] not in [row["id"] for row in client.get("/api/v1/directorates").json()]
    assert client.delete(f"/api/v1/admin/directorates/{directory['id']}").status_code == 200
    with factory() as db:
        assert not db.query(Role).filter_by(code="unknown_permission").first()
        assert not db.query(Role).filter_by(code="temporary_role").first()


def test_identity_backfill_is_repeatable_and_preserves_legacy_ids_and_hash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = create_engine("sqlite:///legacy.db")
    password_hash = hash_password(TEST_PASSWORD)
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE citizens (
            id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL, national_id TEXT UNIQUE NOT NULL, telegram_id BIGINT,
            identity_card_url TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"""))
        conn.execute(text("""CREATE TABLE employees (
            id BIGINT PRIMARY KEY, full_name TEXT NOT NULL, username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL, role TEXT NOT NULL, directorate_id BIGINT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"""))
        conn.execute(text("""CREATE TABLE complaints (
            id INTEGER PRIMARY KEY, title TEXT, status TEXT, directorate_id INTEGER)"""))
        conn.execute(text("CREATE TABLE complaint_notes (id INTEGER PRIMARY KEY, note TEXT, is_internal BOOLEAN)"))
        conn.execute(text("""INSERT INTO citizens
            (id,first_name,last_name,phone,national_id,telegram_id,identity_card_url)
            VALUES (501,'اسم','قديم','0991234567','12345678900',12345,'uploads/legacy.png')"""))
        conn.execute(text("""INSERT INTO employees
            (id,full_name,username,hashed_password,role,directorate_id)
            VALUES (91,'اسم موظف قديم','legacy',:password,'EMPLOYEE',7)"""), {"password": password_hash})
    Base.metadata.create_all(engine)
    migrate(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        bootstrap_access(db)
        assert db.get(Citizen, 501).user.phone == "0991234567"
        assert db.get(Citizen, 501).telegram_id == 12345
        assert db.get(Citizen, 501).identity_card_url == "uploads/legacy.png"
        assert db.get(Employee, 91).user.hashed_password == password_hash
        assert db.get(Employee, 91).user.phone is None
        assert db.get(Employee, 91).user.needs_profile_completion
        assert db.get(Directorate, 7)
    migrate(engine)
    with factory() as db:
        bootstrap_access(db)
        assert db.query(User).count() == 2
        assert db.query(RoleAssignment).count() == 1
        assert db.get(Employee, 91).user.hashed_password == password_hash
    assert len(list((tmp_path / "generated-artifacts/db-backups").glob("*.sqlite"))) == 1
    assert "user_id" in {column["name"] for column in inspect(engine).get_columns("citizens")}
    engine.dispose()
