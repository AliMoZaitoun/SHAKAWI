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

Restart the workflow after configuring secrets. Startup hashes passwords with
scrypt and creates missing accounts only; it never silently resets existing
passwords when environment values change. Password rotation for existing
accounts requires an explicit administrative procedure; editing a startup secret
is not a password reset.

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
