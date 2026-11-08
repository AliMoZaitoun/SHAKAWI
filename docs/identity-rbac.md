# Identity, directorates and scoped RBAC

## Scope

Backend foundation only. The current HTML frontend and Telegram API contracts
remain supported. The requested React management interface is deferred.
No authentication provider or database platform was replaced.

## Relationships

```text
users 1 ── 0..1 citizens 1 ── * complaints
  │
  └── 0..1 employees * ── 0..1 directorates
                │
                └── * employee_role_assignments * ── 1 roles
                               │                       │
                               └── 0..1 directorates   └── * role_permissions * ── 1 permissions

employees 1 ── * access_audit
directorates 1 ── * complaints
```

- `users`: shared first/last name, mobile, optional email, optional staff
  username, password hash, active state and primary `user_type`.
- `citizens`: stable existing ID, unique `user_id`, national ID, identity
  document path and Telegram link. Existing complaint/recovery foreign keys
  continue to reference the same citizen IDs.
- `employees`: stable existing ID, unique `user_id`, home directorate,
  session password version, development-account marker.
- `directorates`: name, description, location, active state.
- `roles` and `permissions`: role metadata and supported server operations.
- `employee_role_assignments`: employee, role, explicit global/department
  scope. An employee may hold multiple roles in multiple departments.
- `access_audit`: actor, action, target, safe metadata and timestamp.

An employee may also have a citizen profile for the **same user**. `user_type`
is a primary classification, not an authorization shortcut. The legacy
registration endpoint links that profile only through the employee's authenticated
session and matching account data, never just a matching phone or national ID.
Anonymous registration cannot claim an existing user by matching personal data.

## Transition, not a destructive schema replacement

Shared legacy columns are deliberately retained on citizens/employees for this
compatibility phase. `app/services/identity.py` synchronizes legacy application
writes and the shared account in the same ORM transaction. All new management
profile writes go through the shared user. Do not independently update the
compatibility columns with raw SQL.

`migrate()` adds links and performs repeatable backfill:

1. Existing citizen/employee IDs remain unchanged.
2. Password hashes are copied unchanged, not reset or re-hashed.
3. National IDs, identity paths, Telegram IDs, complaint ownership and recovery
   records remain where they are.
4. No legacy employee phone or surname is guessed. These users have
   `needs_profile_completion=true` until actual data is supplied.
5. Existing directorate IDs, including IDs beyond the original 1/2, are retained.
6. Re-running migration/seed does not duplicate users or grants.
7. Existing file-based SQLite databases receive a consistent backup before the
   first addition of identity-link columns, in
   `generated-artifacts/db-backups/`. These backups contain sensitive data:
   never serve, publish or commit them.

Fresh databases have declared foreign keys, uniqueness and scope checks. SQLite
foreign-key enforcement is enabled on the application's engine. Existing tables
are **not rebuilt** to retrofit every new metadata constraint; their old
directorate fields are validated in the application. Removing compatibility
columns and retrofitting remaining physical constraints needs a separately
approved, backed-up final migration after consumer compatibility is confirmed.
New profile links are nullable at schema level during backfill; application
registration and staff administration create the user/profile together.

## Authorization rules

Effective access = supported permission **and** matching assignment scope:

- `scope_type=global` requires no department and uses `scope_key=0`.
- `scope_type=directorate` requires a positive existing department, with
  `scope_key=directorate_id`.
- A null department never silently means global.
- A checked scope key plus a unique constraint prevents duplicate grants,
  including duplicate global grants on SQLite.
- Department grants only operate while that department is active.
- A user's home department does not itself grant permissions.
- Permissions are read from the database on every request, not trusted from
  stale session or frontend role data.
- Lists and analytics are filtered by all permitted departments.
- Download, evidence, note, resolution and moderation operations have their
  own permission checks. Complaint-view permission alone does not expose
  evidence, evidence downloads or attachment download URLs.

Dependencies and policy helpers live in `app/services/access.py`. The old
`role` response remains for the existing frontend; it is no longer the authority
for complaint scope. `/api/v1/auth/me` also returns `roles` and effective
`permissions` with scopes for future React navigation.

## Bootstrap and administration

The four requested roles are seeded:

- `governor`: preserves existing governor access and bootstraps global
  administrative permissions.
- `technical_assistant`, `complaint_receiver`, `branch_manager`: initially have
  **no assumed permission matrix**; an authorized administrator configures them.
- `legacy_department_staff`: transitional role preserving the old department
  account's business access without global administrative rights.

Only employees not previously initialized receive legacy grants. Editing a role
or revoking a grant is never undone by restart or seed.

Administrative APIs require explicit **global** management permissions. A
department-scoped grant of `rbac.manage` does not open global administration.
Security mutations acquire a shared database write lock and recheck the actor.
Removing/deactivating the last active global `rbac.manage` holder is rejected and
rolled back. System roles cannot be deleted, and assigned custom roles cannot
be deleted before their assignments are removed.

The current directorate manager is derived from an explicit department-scoped
`branch_manager` assignment, not a second, potentially contradictory manager
column. A directorate has at most one such assignment through the serialized
API. Replace a manager by revoking the previous assignment and assigning the new
one. Directorates in use cannot be deleted; deactivate them instead.

### Permission catalog

```text
complaints.view
complaints.update
complaints.resolve
complaints.files.read
complaints.notes.create
notifications.retry
evidence.request
evidence.read
evidence.files.read
public.review
reports.view
rbac.manage
employees.manage
directorates.manage
```

The UI can edit permission labels/descriptions and distribute catalog permissions
among roles. It cannot invent a permission string and thereby create a new
server operation. Adding a capability requires implementing its server check
and catalog definition first.

## API contract for React

Existing same-origin signed-cookie authentication remains in use. Do not store
credentials in localStorage or treat hidden buttons as authorization.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/directorates` | Public active-directorate catalog; no staff personal data |
| GET, POST | `/api/v1/admin/directorates` | List/create directorates |
| PUT, DELETE | `/api/v1/admin/directorates/{id}` | Edit/delete an unused directorate |
| GET | `/api/v1/admin/permissions` | Supported permission catalog |
| PATCH | `/api/v1/admin/permissions/{code}` | Edit label/description, not permission identity |
| GET, POST | `/api/v1/admin/roles` | List/create roles |
| PUT, DELETE | `/api/v1/admin/roles/{id}` | Edit role's metadata and permissions/delete unused custom role |
| GET, POST | `/api/v1/admin/employees` | Paginated list/create employee account and profile |
| PUT | `/api/v1/admin/employees/{id}` | Update shared profile, home department and active state |
| POST | `/api/v1/admin/employees/{id}/roles` | Assign role and explicit scope |
| DELETE | `/api/v1/admin/employees/{id}/roles/{assignment_id}` | Revoke a particular assignment |
| GET | `/api/v1/admin/audit` | Paginated access-change history |

Staff creation requires real first/last names and mobile, optional email,
username and a password of at least 12 characters. New employees have no roles
or business access until explicitly assigned. Disabling/editing an account
invalidates its existing employee sessions. No hard-delete employee operation is
provided because notes and audit records reference employees.

Role create/update example:

```json
{
  "code": "branch_reader",
  "name": "قراءة شكاوى الفرع",
  "description": "صلاحيات قراءة فقط",
  "permissions": ["complaints.view", "reports.view"]
}
```

`code` is supplied on creation only; update uses the other three fields.

Assignment example:

```json
{
  "role_id": 6,
  "scope_type": "directorate",
  "directorate_id": 2
}
```

IDs in examples are illustrative; read actual IDs from catalog responses.
See `/docs` for validated request schemas. Passwords, password hashes, identity
documents and tokens are never returned by the administrative serializers or
stored in access audit metadata.

## Verification

```bash
PYTHONPATH=. python -m pytest tests -q
PYTHONPATH=. python tests/browser_flow.py
PYTHONPATH=. python tests/browser_recovery.py
```

Tests use synthetic isolated databases. They cover additive migration twice,
hash/ID preservation, conservative role seed, explicit and multi-branch scope,
immediate permission revocation, unauthorized management, last-admin protection,
role/directorate lifecycle, shared employee/citizen profiles, existing complaint
flows, recovery and desktop/mobile browser compatibility. Telegram transport
is mocked/authenticated backend calls, not a claim of live Telegram delivery.
