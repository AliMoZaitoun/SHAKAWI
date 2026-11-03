# SHAKWA — imported complaints MVP

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

Startup performs additive migrations for processing progress, resolution reports,
and note notification results. It does not delete or rebuild existing tables.
Uploads remain in `uploads/`; identity paths are stored on the citizen, and
complaint attachment downloads require employee authorization. Back up both
the SQLite file and uploads before using the MVP with real complaints.
No public static mount exposes the database, identity files, or upload directory.

## Authentication and permissions

The imported employee table and roles are retained; no identity-provider
migration is needed for the two requested internal accounts.

- `governor`: governorate account, can read and manage all complaints.
- `services`: services account, can read and manage directorate **2** only.
- Directorate **1** is governorate, matching the existing Telegram bot mapping.
- There is no public staff registration. All staff routes enforce access in Python,
  including notes, updates, retry notifications, and attachment downloads.

Configure these in Replit **Secrets**, never in source, chat, or a committed `.env`:

- `SESSION_SECRET`: required cookie signing secret.
- `GOVERNOR_PASSWORD`: at least 12 characters, provisions missing `governor`.
- `SERVICES_PASSWORD`: at least 12 characters, provisions missing `services`.
- `BOT_TOKEN`: newly rotated Telegram BotFather token.

### Requested temporary development accounts

The user explicitly requested temporary passwords for testing. Development
configuration sets `ENABLE_DEMO_ACCOUNTS=1` in the development environment only.
When this flag is on, missing `governor` and `services` accounts are provisioned
with the requested temporary password `123456`, hashed with scrypt. Existing
accounts are never reset. Explicit strong password secrets take precedence.
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

Public notes are stored in `complaint_notes` with their real employee author.
The complaint update and new note commit together **before** notifying Telegram.
Notification delivery is checked using both HTTP status and Telegram's `ok`
response. A failure does not erase the note or falsely report successful delivery.
Internal notes are excluded from public tracking and never sent.

Notification outcomes: `sent`, `failed`, `not_linked`, `not_configured`, and
`not_requested`. Failed public notes can be retried without creating another note.

A website-only citizen does not automatically have a Telegram chat ID.
The bot requires the sender's own Telegram contact during initial registration.
Returning bot users must use the Telegram account already linked to their record.
Matching personal details alone never authorizes linking an existing record to a
new Telegram account or claiming an existing citizen record from a fresh browser.
A separate verified ownership/recovery flow is required for lost browser sessions
and linking website-only records; no such verification service is configured yet.
New browser registrations receive a signed, versioned session capability and can
submit complaints or upload identity documents only for the record they created.
Only authenticated bot requests can submit Telegram IDs. The browser cannot submit
arbitrary Telegram IDs. The bot uses `X-Bot-Token` on its private API requests.
`API_BASE_URL` defaults to the runner's internal port 5000.

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
