"""Execute immutable SQLite migration statements without executescript auto-commit."""
from pathlib import Path
import sqlite3


def apply_snapshot(connection, name):
    if connection.dialect.name != "sqlite":
        raise RuntimeError("This imported SQLite schema needs a separately approved migration for other database engines")
    source = Path(__file__).resolve().parents[2] / "migrations" / name
    statement = ""
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("--"):
            continue
        statement += line + "\n"
        if sqlite3.complete_statement(statement):
            connection.exec_driver_sql(statement)
            statement = ""
    if statement.strip():
        raise RuntimeError("Incomplete migration schema snapshot")
