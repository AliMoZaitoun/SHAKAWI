from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

UPLOAD_DIR = Path("uploads")
MAX_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "application/pdf": ".pdf", "audio/ogg": ".ogg", "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a", "video/mp4": ".mp4",
}


async def save_upload(file: UploadFile, identity=False) -> str:
    allowed = {k: v for k, v in ALLOWED_TYPES.items() if k.startswith("image/")} if identity else ALLOWED_TYPES
    if file.content_type not in allowed:
        raise HTTPException(415, "نوع الملف غير مدعوم")
    UPLOAD_DIR.mkdir(exist_ok=True)
    path = UPLOAD_DIR / f"{uuid4().hex}{allowed[file.content_type]}"
    size = 0
    try:
        with path.open("wb") as output:
            while chunk := await file.read(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "حجم الملف يجب ألا يتجاوز 10 ميغابايت")
                output.write(chunk)
        if size == 0:
            raise HTTPException(400, "الملف فارغ")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return str(path)
