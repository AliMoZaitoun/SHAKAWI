from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

UPLOAD_DIR = Path("uploads")
HARD_MAX_BYTES = 10 * 1024 * 1024
# Compatibility alias for integrations that still need the absolute ceiling.
MAX_BYTES = HARD_MAX_BYTES
ALLOWED_TYPES = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "application/pdf": ".pdf", "audio/ogg": ".ogg", "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a", "video/mp4": ".mp4",
}


def format_file_limit(limit: int) -> str:
    megabytes = limit / (1024 * 1024)
    amount = f"{megabytes:.1f}".rstrip("0").rstrip(".")
    return f"{amount} ميغابايت"


async def save_upload(file: UploadFile, db, identity=False) -> str:
    from app.services.file_policy import max_upload_bytes

    allowed = {k: v for k, v in ALLOWED_TYPES.items() if k.startswith("image/")} if identity else ALLOWED_TYPES
    if file.content_type not in allowed:
        raise HTTPException(415, "نوع الملف غير مدعوم")
    limit = max_upload_bytes(db, file.content_type)
    UPLOAD_DIR.mkdir(exist_ok=True)
    path = UPLOAD_DIR / f"{uuid4().hex}{allowed[file.content_type]}"
    size = 0
    try:
        with path.open("wb") as output:
            while chunk := await file.read(65536):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        413, f"حجم الملف يتجاوز الحد المحدد لهذا النوع ({format_file_limit(limit)})"
                    )
                output.write(chunk)
        if size == 0:
            raise HTTPException(400, "الملف فارغ")
        # MIME supplied by a browser is not proof of the actual content.
        if file.content_type.startswith("image/") or file.content_type == "application/pdf":
            import io
            from starlette.datastructures import Headers
            from app.services.evidence import validate_files
            safe_name = Path((file.filename or path.name).replace("\\", "/")).name
            probe = UploadFile(io.BytesIO(path.read_bytes()), filename=safe_name,
                               headers=Headers({"content-type": file.content_type}))
            await validate_files([probe], db=db)
        else:
            head = path.read_bytes()[:32]
            supported = (
                (file.content_type == "audio/ogg" and head.startswith(b"OggS")) or
                (file.content_type == "audio/mpeg" and (head.startswith(b"ID3") or
                  len(head) > 1 and head[0] == 255 and head[1] & 224 == 224)) or
                (file.content_type in {"video/mp4", "audio/mp4"} and head[4:8] == b"ftyp")
            )
            if not supported:
                raise HTTPException(415, "محتوى الملف لا يطابق نوعه")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return str(path)
