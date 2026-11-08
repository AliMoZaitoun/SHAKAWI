#!/usr/bin/env bash
# Non-interactive reconciliation for the existing Python app, not a new service.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "Checking application dependencies..."
# Nix's interpreter is externally managed; never write to /nix/store or
# override that protection. Use Replit's existing project-local package prefix.
python -m pip install --prefix "$PWD/.pythonlibs" \
  --disable-pip-version-check --no-input -r requirements.txt
python_version="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
export PYTHONPATH="$PWD/.pythonlibs/lib/python${python_version}/site-packages${PYTHONPATH:+:$PYTHONPATH}"

echo "Applying idempotent database setup..."
python - <<'PY'
# Import the application to register all current models without starting
# uvicorn or Telegram polling. Never print configuration or credentials.
from app.main import app
from app.db.base import Base
from app.db.upgrade import upgrade_database
from app.db.session import engine, SessionLocal
from app.services.access import bootstrap_access

upgrade_database(engine)
with SessionLocal() as db:
    bootstrap_access(db)
print("Application import and database setup succeeded.")
PY

echo "Setup complete; managed workflows will now be reconciled."
