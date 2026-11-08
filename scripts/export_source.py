"""Reproducible allowlisted source ZIP, never a database or citizen-data export."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ("app", "bot", "static", "migrations", "docs", "scripts", "tests", "frontend")
ROOT_FILES = (
    "run.py", "requirements.txt", "requirements-dev.txt", "alembic.ini", ".replit",
    ".env.example", ".gitignore", ".replitignore", "replit.md",
    "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml",
)
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".cache", "node_modules", "dist"}


def export_source(output=None):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = Path(output) if output else ROOT / "generated-artifacts" / "exports" / f"shakwa-foundations-{stamp}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [ROOT / name for name in ROOT_FILES if (ROOT / name).is_file()]
    for directory in DIRECTORIES:
        files.extend(path for path in (ROOT / directory).rglob("*") if path.is_file()
                     and not path.is_symlink() and not EXCLUDED_PARTS.intersection(path.parts)
                     and path.suffix not in {".pyc", ".db", ".sqlite", ".sqlite3", ".zip"})
    manifest = {}
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            name = str(path.relative_to(ROOT))
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                raise ValueError("Source export refuses symlinks")
            if path.name == ".env" or name.startswith(("uploads/", "generated-artifacts/", ".git/")):
                raise ValueError("Unsafe source export candidate")
            data = path.read_bytes()
            archive.writestr(f"shakwa-source/{name}", data)
            manifest[name] = hashlib.sha256(data).hexdigest()
        archive.writestr("shakwa-source/SOURCE-MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        archive.writestr("shakwa-source/START-HERE.txt",
                         "ابدأ بقراءة docs/local-setup-ar.md ثم docs/database-foundations-ar.md.\n"
                         "هذه نسخة كود فقط. لا تستبدل .env أو قاعدة البيانات أو uploads الموجودة على جهازك.\n")
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise ValueError("Source ZIP integrity failure")
    return output


if __name__ == "__main__":
    print(export_source())
