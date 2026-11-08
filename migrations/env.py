"""Uses the same explicit database as the app; never reads .env implicitly."""
from alembic import context
from app.db.session import engine
from app.db.base import Base
from app.models import user, complaint, recovery, access, foundations

connection = context.config.attributes.get("connection")
if connection is not None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
else:
    from sqlalchemy import inspect, text
    from app.db.backup import create_backup
    tables = inspect(engine).get_table_names()
    with engine.connect() as probe:
        current = probe.execute(text("SELECT version_num FROM alembic_version")).scalar() if "alembic_version" in tables else None
    if current != "0002_foundations" and "complaints" in tables:
        create_backup(engine)
    with engine.begin() as connection:
        if engine.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
        if engine.dialect.name == "sqlite" and connection.exec_driver_sql("PRAGMA foreign_key_check").first():
            raise RuntimeError("Foreign key validation failed; restore verified backup instead of deleting data")
