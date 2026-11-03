"""Send only committed, citizen-visible notes. Never log Telegram URLs or tokens."""
import os
from html import escape

import aiohttp

MESSAGES = {
    "sent": "تم حفظ التحديث وإرسال الإشعار على تيليغرام",
    "failed": "تم الحفظ، لكن تعذر إرسال إشعار تيليغرام. يمكن إعادة المحاولة",
    "not_linked": "تم الحفظ. حساب المواطن غير مرتبط بتيليغرام",
    "not_configured": "تم الحفظ. توكن بوت تيليغرام غير مضبوط في Secrets",
    "not_requested": "تم الحفظ دون إشعار",
}


async def notify(citizen, code, text):
    status = "not_linked"
    if citizen and citizen.telegram_id:
        token = os.environ.get("BOT_TOKEN")
        if not token:
            status = "not_configured"
        else:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
                    async with session.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": citizen.telegram_id,
                              "text": f"تحديث الشكوى {escape(code)}\n{escape(text)}",
                              "parse_mode": "HTML"},
                    ) as response:
                        payload = await response.json()
                        status = "sent" if response.status == 200 and isinstance(payload, dict) and payload.get("ok") is True else "failed"
            except (aiohttp.ClientError, TimeoutError, ValueError):
                status = "failed"
    return {"status": status, "message": MESSAGES[status]}


async def notify_note(db, complaint, note):
    if note.is_internal:
        return {"status": "not_requested", "message": MESSAGES["not_requested"]}
    result = await notify(complaint.citizen, complaint.tracking_code, note.note)
    note.notification_status = result["status"]
    note.notification_error = result["message"] if result["status"] != "sent" else None
    db.commit()
    return result
