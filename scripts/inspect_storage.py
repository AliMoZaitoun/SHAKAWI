"""Read-only consistency report. Does not print paths, personal names or delete."""
from pathlib import Path
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.foundations import StoredFile, ComplaintFile, CitizenFile, EvidenceReplyFile
from app.services.uploads import UPLOAD_DIR


def inspect_storage(db):
    references = set()
    missing = unsafe = 0
    ids = set()
    for file in db.query(StoredFile):
        ids.add(file.id)
        path = Path(file.storage_key).resolve()
        if not path.is_relative_to(UPLOAD_DIR.resolve()):
            unsafe += 1
            continue
        references.add(path)
        missing += not path.is_file()
    linked = set()
    for model in (ComplaintFile, CitizenFile, EvidenceReplyFile):
        linked.update(db.scalars(select(model.file_id)))
    physical = {path.resolve() for path in UPLOAD_DIR.rglob("*") if path.is_file() and path.name != ".gitkeep"}
    return {"catalog_files": len(ids), "missing_bytes": missing, "unsafe_references": unsafe,
            "unlinked_catalog_files": len(ids - linked), "uncatalogued_physical_files": len(physical - references)}


if __name__ == "__main__":
    import json
    with SessionLocal() as db:
        print(json.dumps(inspect_storage(db), indent=2))
