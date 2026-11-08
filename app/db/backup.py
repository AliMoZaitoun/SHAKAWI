"""Private local backups. Stop web/bot writers for DB+uploads consistency."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import shutil


def create_backup(engine, root=Path("generated-artifacts/backups"), uploads=Path("uploads")):
    if engine.dialect.name != "sqlite" or engine.url.database in (None, "", ":memory:"):
        if engine.dialect.name != "sqlite":
            raise RuntimeError("Configure an explicit verified backup procedure before upgrading a non-SQLite database")
        return None
    destination = Path(root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination.mkdir(parents=True, mode=0o700)
    os.chmod(destination, 0o700)
    database = destination / "database.sqlite"
    raw = engine.raw_connection()
    try:
        with sqlite3.connect(database) as target:
            raw.driver_connection.backup(target)
    finally:
        raw.close()
    os.chmod(database, 0o600)
    if uploads.exists():
        # Reject symlinks rather than accidentally copying data outside uploads.
        if any(path.is_symlink() for path in uploads.rglob("*")):
            raise RuntimeError("Symlink in uploads; backup stopped for manual review")
        shutil.copytree(uploads, destination / "uploads")
        for path in (destination / "uploads").rglob("*"):
            os.chmod(path, 0o700 if path.is_dir() else 0o600)
    manifest = {"database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
                "uploads": {}}
    for path in (destination / "uploads").rglob("*") if (destination / "uploads").exists() else []:
        if path.is_file():
            manifest["uploads"][str(path.relative_to(destination / "uploads"))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (destination / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return destination


def verify_backup(directory):
    directory = Path(directory)
    data = json.loads((directory / "manifest.json").read_text())
    if hashlib.sha256((directory / "database.sqlite").read_bytes()).hexdigest() != data["database_sha256"]:
        raise ValueError("Database backup checksum mismatch")
    with sqlite3.connect(directory / "database.sqlite") as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database backup integrity failure")
    for name, digest in data["uploads"].items():
        path = (directory / "uploads" / name).resolve()
        if not path.is_relative_to((directory / "uploads").resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Uploads backup checksum mismatch")
    return True


def restore_to_new_directory(backup, destination):
    """Never overwrite a live database or existing folder."""
    backup, destination = Path(backup), Path(destination)
    verify_backup(backup)
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    shutil.copy2(backup / "database.sqlite", destination / "database.sqlite")
    if (backup / "uploads").exists():
        shutil.copytree(backup / "uploads", destination / "uploads")
    return destination


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Private offline backup and non-overwriting restore")
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("create")
    backup.add_argument("--writers-stopped", action="store_true", required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("backup")
    restore.add_argument("new_directory")
    arguments = parser.parse_args()
    if arguments.command == "create":
        from app.db.session import engine
        result = create_backup(engine)
        print("Backup created and verified." if result and verify_backup(result) else "No file-backed SQLite database.")
        if result:
            print(result)
    else:
        restore_to_new_directory(arguments.backup, arguments.new_directory)
        print("Restored into a new directory. No live database or uploads were overwritten.")
