# SHAKWA — imported complaints MVP

## React interface (same repository)

The React+TypeScript frontend lives in `frontend/`; FastAPI and the Telegram bot
remain Python. See `docs/react-frontend-ar.md`. Use pnpm workspace scripts:
`pnpm install --frozen-lockfile`, `pnpm typecheck`, `pnpm build`.
FastAPI serves the built SPA and deep links on the existing port 5000.
`pnpm dev` optionally runs Vite on 5173 with a same-origin API proxy for local
development. Do not create another backend/auth/database for the frontend.
Keep the old UI at `/legacy`; `SHAKWA_UI=legacy` selects it at `/` for regression.
React is the primary interface for all new UI work. Do not duplicate new features
in the legacy UI unless the user explicitly asks; keep legacy only for compatibility
and regression checks.
Keep the citizen and employee interfaces in separate layouts. Citizen navigation
must not link to the employee portal; employee login remains at `/employee/login`.
Staff APIs accept 15-minute JWT Bearer access tokens. React keeps them in memory
and renews through the signed HTTP-only session cookie; never store JWTs in
browser storage. The backend still accepts the session cookie for compatibility.
Never expose secrets through VITE_* or persist citizen credentials in browser
storage. Removing the legacy interface needs separate approval after parity.

## Versioned database foundations

Read `docs/database-foundations-ar.md` and `docs/local-setup-ar.md` for the current
schema/API contracts and local upgrade instructions. Startup now uses Alembic
through `app.db.upgrade`, not create_all followed by ad-hoc migrations. Existing
SQLite remains; migration SQL snapshots are immutable and destructive downgrade
is disabled. Stop all other writers before upgrading. Pre-upgrade database and
uploads backups are private in ignored `generated-artifacts/backups/`.

Languages and per-entity translation tables are extensible without per-language
columns. Shared user attributes read from users; legacy columns remain mirrors
until an explicitly approved removal. A private file catalog has real complaint,
citizen and evidence FK links; old attachment IDs/routes remain compatible.
New `audit_events` and `complaint_history` are transactional and append-only in
the ORM; old events are imported honestly, not reconstructed. New audit/identity/
transfer capabilities are not automatically granted to existing roles.

## Identity and scoped RBAC foundation

See `docs/identity-rbac.md` for the relational model, compatibility migration,
administration API, permission catalog and React integration contract. Backend
management is implemented; the React management UI is intentionally deferred.
The four organizational roles exist, but new branch roles have no presumed
permission matrix. Legacy department staff keep a transitional scoped role.
New employee accounts receive no permissions until explicitly assigned.

Shared user records and profile links coexist with old columns during an
additive compatibility phase. Do not drop/independently update old identity
columns or reset passwords. Legacy staff with missing phone/surname are flagged
for completion, not given invented values. Initial file-based SQLite migration
backs up to ignored `generated-artifacts/db-backups/` (sensitive, never publish).
Existing profile IDs and complaint/recovery/Telegram references are preserved.

## Stack and run command

Keep the existing Python/FastAPI, SQLAlchemy, aiogram and vanilla HTML/CSS/JS stack.
Run `python run.py` using the **Start application** workflow. FastAPI serves both
the API and the frontend on port 5000. The runner starts Telegram polling only
when `BOT_TOKEN` is configured. Do not run another poller for the same bot.

The public frontend is `/`; the original `/Shakwa.html` link also works.
Frontend files are in `static/index.html`, `static/css/`, and `static/js/`.
All browser requests are relative, same-origin `/api/v1/...` requests.

## Database and uploaded files

The imported `gov_complaints.db` SQLite database is intentionally retained.
The app does **not** automatically adopt an unrelated platform `DATABASE_URL`.
An explicit `SHAKWA_DATABASE_URL` may override the SQLite connection when a
database change is intentionally configured. Do not migrate databases without
the owner's approval.

Startup performs versioned additive migrations and does not delete or rebuild
existing tables. Uploads remain in `uploads/`, indexed by a unified private file
catalog with explicit links. Old identity paths remain compatibility mirrors.
Complaint file downloads enforce owner or scoped employee access. Back up both
the SQLite file and uploads before using the MVP with real complaints.
No public static mount exposes the database, identity files, or upload directory.

## Authentication and permissions

The imported employee table and roles are retained; no identity-provider
migration is needed for the internal accounts.

- `system_admin`: dedicated global technical administrator; can manage all system capabilities.
- `governor`: governorate account, can read and manage complaints across all directorates, but is not the technical system administrator.
- `services`: services account, can read and manage directorate **2** only.
- Directorate **1** is governorate, matching the existing Telegram bot mapping.
- There is no public staff registration. All staff routes enforce access in Python,
  including notes, updates, retry notifications, and attachment downloads.

Configure these in Replit **Secrets**, never in source, chat, or a committed `.env`:

- `SESSION_SECRET`: required cookie signing secret.
- `SYSTEM_ADMIN_PASSWORD`: required until the dedicated `system_admin` account exists; at least 12 characters, never demo-seeded or reset at startup.
- `GOVERNOR_PASSWORD`: at least 12 characters, provisions missing `governor`.
- `SERVICES_PASSWORD`: at least 12 characters, provisions missing `services`.
- `BOT_TOKEN`: newly rotated Telegram BotFather token.

### Requested temporary development accounts

The user explicitly requested temporary passwords for testing. Development
configuration sets `ENABLE_DEMO_ACCOUNTS=1` in the development environment only.
When this flag is on, missing `governor` and `services` accounts are provisioned
with the requested temporary password `123456`, hashed with scrypt. Existing
accounts are never reset. Explicit strong password secrets take precedence.
The dedicated `system_admin` account always requires `SYSTEM_ADMIN_PASSWORD`;
it never uses the demo password.
This is intentionally weak and is not permission to use the app with real data
or publish it. The UI shows a warning and a **تغيير كلمة المرور** action.
Changing a password requires the current password and a new password of at least
12 characters; it invalidates other sessions and retains the current session.

Production startup refuses a demo-enabled flag or any account still marked as
demo (and checks for the known temporary password hash). Change both passwords
and disable the demo flag before production. Production is detected by
`REPLIT_DEPLOYMENT=1` or explicit `APP_ENV=production`.

Restart the workflow after configuring secrets. Startup hashes passwords with
scrypt and creates missing accounts only; it never silently resets existing
passwords when environment values change. Use the authenticated
**تغيير كلمة المرور** account action to rotate an existing password; editing a
startup secret is not a password reset.

Sessions are HttpOnly, expire after eight hours, and use secure cookies in the
hosted Replit environment. Unsafe requests reject foreign browser origins.
Login attempts are rate-limited in-process for this single-worker MVP.

## Notes and Telegram

Notes are stored in `complaint_notes` with their real employee author and explicit
`internal`, `private`, or `public` audience. Legacy non-internal notes migrate as
private: they remain visible to their owner but are not publication consent.
Only explicitly public notes on public complaints enter the public serializer.
The complaint update and new note commit together **before** notifying Telegram.
Notification delivery is checked using both HTTP status and Telegram's `ok`
response. A failure does not erase the note or falsely report successful delivery.
Internal notes are excluded from citizen tracking and never sent.

Notification outcomes: `sent`, `failed`, `not_linked`, `not_configured`, and
`not_requested`. Failed citizen-visible notes can be retried without creating another note.

A website-only citizen does not automatically have a Telegram chat ID.
The bot requires the sender's own Telegram contact during initial registration.
Returning bot users must use the Telegram account already linked to their record.
Matching personal details alone never authorizes linking an existing record to a
new Telegram account or claiming an existing citizen record from a fresh browser.
The existing recovery-key and Telegram approval/linking flows provide explicit
ownership proofs; personal details alone never restore access.
New browser registrations receive a signed, versioned session capability and can
submit complaints or upload identity documents only for the record they created.
Only authenticated bot requests can submit Telegram IDs. The browser cannot submit
arbitrary Telegram IDs. The bot uses `X-Bot-Token` on its private API requests.
`API_BASE_URL` defaults to the runner's internal port 5000.

## Private evidence requests and replies

Authorized staff create requests at `POST /api/v1/complaints/{id}/evidence`.
The request is committed before notification and records the author, date and
notification result. Retry uses `/{request_id}/retry`, with a durable 30-second
claim/cooldown and no duplicate request creation. Already-sent notifications are
not resent; answered requests cannot be notified again. External delivery is
best effort: a process crash after Telegram accepts but before recording success
can cause a repeated notification, not repeated complaint data.

Secret tracking grants a bounded, complaint-specific signed-session capability.
It does not grant citizen identity, recovery access or other complaint history.
The existing unpredictable secret tracking code is the complaint credential,
not the public numeric complaint id or national id. Registered account ownership
and server-verified Telegram ownership are also supported. Staff readers and
downloads always enforce department scope; the governor can access all.

Citizen answers use multipart `POST /api/v1/complaints/{id}/evidence/{request_id}/reply`
with `text`, `submission_key` and optional repeated `files` fields. Text or files
are required. One atomic answer per request preserves a clear audit trail;
staff can create another request for another round. Stable submission keys and
content digests confirm retries after a lost response without duplicate answers.
Requests and answers never change complaint status, progress or public consent.

Evidence permits up to five JPEG, PNG, WebP or PDF files, each at most 10 MiB.
The server decodes images/parses PDFs, rejects mismatched types/extensions,
unsafe names, and active PDF features it detects. This is not malware scanning.
Files use random paths under private `uploads/evidence/`; authorized attachment
downloads use `application/octet-stream`, attachment disposition and `nosniff`.
No public view or analytics response contains evidence or private notes.
The database, original uploads and evidence directory need coordinated backups.

The evidence bot router runs before complaint creation handlers, uses private
chats only, checks the update sender's current binding on each API operation,
and serializes events per conversation. `/send` saves the complete reply,
`/cancel` pauses without sending, and `/discard` explicitly drops the draft.
Paused drafts resume only for the same request and sender. Drafts are temporary
in-memory data and do not survive a bot restart; only a confirmed API save is
durable. A network-uncertain send locks content for an identical retry.
If Telegram is unavailable/unlinked, website tracking and replies still work;
the UI asks citizens to check their tracking page periodically.

Evidence API and bot simulations are in `tests/test_evidence.py`.
`PYTHONPATH=. python tests/browser_flow.py` additionally tests staff request,
mobile guest reply, partial-invalid-file rejection, lost-response retry,
private file download and public non-disclosure, using synthetic data only.
Real Telegram delivery has not been tested: it requires a newly configured
secure token and an explicitly consenting test account. Never use real citizens
for automated tests or start a second polling process.

Any credential previously hardcoded in the imported source or `.env` should be
revoked at its provider. Removing it from current code does not revoke it or
remove old Git history. The app no longer loads the imported `.env` file.

## Checks

Install development dependencies from `requirements-dev.txt` using the project
package manager. Run `python -m pytest tests -q`.
Tests use a separate, in-memory database and fake Telegram services, never the
imported citizen records or live messages. The unauthenticated frontend can be
visually checked at `/`. Real Telegram delivery requires a configured token and
a citizen who has started the bot.

The inherited Tailwind/font/icon CDN dependencies are retained for this MVP.
Demo file exports were removed rather than claiming nonexistent downloads.

## Transparency and analytics

`is_public` is an independent opt-in flag, not a complaint category. Existing
records migrate as private. Website submission defaults to private; the current
bot explicitly creates private complaints and tells the citizen this.
The bot and website use matching topic categories for new submissions.

Public browsing uses `/api/v1/complaints/public` with pagination and category,
status, and directorate filters, and `/api/v1/complaints/public/{id}` for a detail.
Both queries enforce `is_public` in SQL. Public responses are allow-listed and
exclude the tracking code, citizen fields, coordinates, attachments, internal
notes, staff authors, and notification metadata. Known owner identity strings,
tracking codes, emails, and phone/ID-like numbers are redacted from public text.
Citizens are warned not to put personal data in public text. Automatic redaction
is not a general-purpose review of all possible third-party personal information.
Secret-code tracking remains separate and is not used to fetch public details.

Staff analytics are available at `/api/v1/analytics` and in the statistics tab.
The server applies directorate authorization before all aggregations.
The default period is the last 30 days; filters include both endpoint days in
UTC and allow a maximum span of 366 days. Charts are not required: the UI uses
summary cards and accessible tables for statuses, categories, priorities and
daily counts (including zero days).

Resolution rate = resolved complaints / all complaints in the selected creation
date range × 100, including rejected complaints in the denominator. Estimated
average progress is a different metric based on staff-entered percentages.
There is no fabricated resolution-time metric. `RESOLVED` forces 100%, other
states reject explicit 100%, and reopening without a new estimate resets to 0%.

For interactive regression checks, install development requirements and a
Chromium executable, then run `PYTHONPATH=. python tests/browser_flow.py`.
This starts an isolated temporary database and test server, checks public views
on desktop/mobile, both roles, statistics, logout, and password changes.
Screenshots/logs are generated under ignored `generated-artifacts/`.

## Post-merge setup

Configure the post-merge hook to run `scripts/post-merge.sh`. It checks the
existing runtime requirements without upgrading satisfied packages, imports
the application, creates missing tables and applies the idempotent additive
migrations to the existing configured database. It never starts a duplicate
web server or bot; managed workflow reconciliation restarts the application.
It runs non-interactively and fails immediately if setup fails.
Dependency installation uses the existing project-local `.pythonlibs` prefix,
not the immutable Nix interpreter environment or a virtual environment.
After reconciliation, verify a new runtime endpoint; if Python still serves old
routes while static files are updated, restart the existing managed workflow.

### Saving a citizen recovery key

After a successful web submission, the visible tracking tab offers an optional
recovery-key save panel. It explains the difference from the single-complaint
tracking code. Only a trusted citizen session can issue the account-wide key.
Issuance is explicit, never automatic; replacing an existing key requires
confirmation. Copy and text-file download are user-initiated, and the secret
remains in the current page only, not browser storage or URLs. The existing
submission-tab recovery section remains available for later access.

`PYTHONPATH=. python tests/browser_recovery.py` now checks real form submission,
visible post-submission issuance, download, cancelled and confirmed replacement,
secret cleanup, single-use recovery, and mobile layout on a temporary database.
