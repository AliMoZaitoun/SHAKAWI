"""Isolated evidence drafts. Telegram update sender is checked on every API call."""
import io
import secrets

import aiohttp
from aiogram import F, Router
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from bot.config import API_BASE_URL, API_HEADERS

router = Router()
MAX_BYTES = 10 * 1024 * 1024
MIME_SUFFIX = {"image/jpeg": ".jpg", "image/png": ".png",
               "image/webp": ".webp", "application/pdf": ".pdf"}


class EvidenceFlow(StatesGroup):
    drafting = State()


def headers(event):
    return {**API_HEADERS, "X-Telegram-Id": str(event.from_user.id)}


async def authorized(event, cid, rid, allow_answered=False):
    async with aiohttp.ClientSession(headers=headers(event),
                                    timeout=aiohttp.ClientTimeout(total=15)) as session:
        async with session.get(f"{API_BASE_URL}/complaints/{cid}/evidence") as response:
            if response.status != 200:
                raise ValueError("ownership")
            rows = await response.json()
    row = next((r for r in rows if r["id"] == rid), None)
    if not row or (row["status"] != "pending" and not allow_answered):
        raise ValueError("request")
    return row


@router.callback_query(F.data.startswith("evidence_"))
async def begin(callback: CallbackQuery, state: FSMContext):
    if not callback.message or callback.message.chat.type != "private":
        await callback.answer("استخدم المحادثة الخاصة مع البوت.", show_alert=True)
        return
    if await state.get_state():
        await callback.answer("أكمل العملية الحالية أو استخدم /cancel أولًا.", show_alert=True)
        return
    try:
        _, cid, rid = callback.data.split("_")
        cid, rid = int(cid), int(rid)
        data = await state.get_data()
        saved = data.get("evidence_draft")
        same = saved and (saved["cid"], saved["rid"], saved["actor"]) == (cid, rid, callback.from_user.id)
        row = await authorized(callback, cid, rid, allow_answered=bool(same))
    except (ValueError, aiohttp.ClientError, TimeoutError):
        await callback.answer("تعذر إثبات ملكية طلب منتظر. تحقق من الربط وحاول مجددًا.", show_alert=True)
        return
    data = await state.get_data()
    draft = data.get("evidence_draft")
    if not draft or (draft["cid"], draft["rid"], draft["actor"]) != (cid, rid, callback.from_user.id):
        if draft:
            await callback.answer("لديك مسودة محفوظة لطلب آخر؛ أكملها أو احذفها بـ /discard.", show_alert=True)
            return
        draft = {"cid": cid, "rid": rid, "actor": callback.from_user.id,
                 "text": "", "files": [], "key": secrets.token_hex(20)}
    await state.update_data(evidence_draft=draft)
    await state.set_state(EvidenceFlow.drafting)
    await callback.message.answer(
        "طلب استكمال خاص:\n" + row["prompt"] +
        "\nأرسل النص والصور أو مستندات PDF، ثم /send لحفظ الرد. "
        "حتى 5 ملفات، 10 ميغابايت لكل ملف؛ JPEG وPNG وWebP وPDF فقط."
        "\nلن تُنشر الأدلة ولن تتغير حالة الشكوى تلقائيًا."
        "\n/cancel يوقف العملية ويحفظ المسودة؛ افتح زر الطلب نفسه لاستئنافها. /discard يحذف المسودة."
    )
    await callback.answer()


@router.message(F.text == "/discard")
async def discard(message: Message, state: FSMContext):
    if message.chat.type != "private":
        return
    await state.update_data(evidence_draft=None)
    if await state.get_state() == EvidenceFlow.drafting.state:
        await state.set_state(None)
    await message.answer("حُذفت مسودة الأدلة دون إرسال.")


@router.message(EvidenceFlow.drafting, F.text == "/cancel")
async def cancel(message: Message, state: FSMContext):
    await state.set_state(None)
    await message.answer("توقفت العملية دون إرسال. المسودة محفوظة؛ افتح زر الطلب نفسه لاستئنافها.")


class LimitedBuffer(io.BytesIO):
    def write(self, value):
        if self.tell() + len(value) > MAX_BYTES:
            raise ValueError("حجم الملف يتجاوز 10 ميغابايت")
        return super().write(value)


@router.message(EvidenceFlow.drafting)
async def collect(message: Message, state: FSMContext):
    data = await state.get_data()
    draft = data.get("evidence_draft")
    if message.chat.type != "private" or not draft or draft["actor"] != message.from_user.id:
        return
    try:
        # No draft field, callback id, or previously linked account is trusted as ownership.
        await authorized(message, draft["cid"], draft["rid"], allow_answered=message.text == "/send")
        if message.text == "/send":
            if not draft["text"] and not draft["files"]:
                await message.answer("أضف نصًا أو مرفقًا أولًا.")
                return
            form = aiohttp.FormData()
            form.add_field("text", draft["text"])
            form.add_field("submission_key", draft["key"])
            for item in draft["files"]:
                buffer = LimitedBuffer()
                await message.bot.download(item["file_id"], destination=buffer)
                form.add_field("files", buffer.getvalue(), filename=item["name"], content_type=item["mime"])
            draft["attempted"] = True
            await state.update_data(evidence_draft=draft)
            async with aiohttp.ClientSession(headers=headers(message),
                                            timeout=aiohttp.ClientTimeout(total=90)) as session:
                async with session.post(
                    f"{API_BASE_URL}/complaints/{draft['cid']}/evidence/{draft['rid']}/reply", data=form
                ) as response:
                    result = await response.json()
                    if response.status != 200:
                        detail = result.get("detail")
                        raise ValueError(detail if isinstance(detail, str) else "لم يُحفظ الرد")
            await state.update_data(evidence_draft=None)
            await state.set_state(None)
            await message.answer("تم حفظ الرد وكل مرفقاته في سجل الشكوى الخاص. لا يعني ذلك إغلاق الشكوى.")
            return
        if message.text and message.text.startswith("/"):
            await message.answer("أنت في رد الأدلة؛ استخدم /send أو /cancel قبل بدء عملية أخرى.")
            return
        if draft.get("attempted"):
            await message.answer("تمت محاولة إرسال هذه المسودة؛ أعد /send للتحقق من الحفظ دون تغيير المحتوى.")
            return
        if message.photo or message.document:
            item = message.photo[-1] if message.photo else message.document
            mime = "image/jpeg" if message.photo else item.mime_type
            if mime not in MIME_SUFFIX or (item.file_size or 0) > MAX_BYTES or len(draft["files"]) >= 5:
                raise ValueError("نوع أو حجم أو عدد الملفات غير مسموح")
            name = "photo.jpg" if message.photo else (item.file_name or "document" + MIME_SUFFIX[mime])
            draft["files"].append({"file_id": item.file_id, "name": name, "mime": mime})
            note = "أضيف الملف للمسودة فقط؛ الحفظ النهائي بعد /send."
        elif message.text:
            text = (draft["text"] + "\n" + message.text).strip()
            if len(text) > 10000:
                raise ValueError("النص يتجاوز 10000 حرف")
            draft["text"] = text
            note = "أضيف النص للمسودة؛ أرسل المرفقات أو /send للحفظ."
        else:
            raise ValueError("أرسل نصًا أو صورة أو مستندًا مدعومًا")
        await state.update_data(evidence_draft=draft)
        await message.answer(note)
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        # Never echo network exceptions: they may contain service URLs.
        detail = str(exc) if isinstance(exc, ValueError) and str(exc) not in {"ownership", "request"} else "تعذر التحقق أو الاتصال"
        await message.answer(detail + ". لم تُحذف المسودة. أعد /send أو /cancel ثم راجع الطلب في الموقع.")


@router.callback_query(EvidenceFlow.drafting)
async def block_switch(callback: CallbackQuery):
    await callback.answer("أكمل رد الأدلة أو استخدم /cancel أولًا.", show_alert=True)


@router.message()
async def protect_paused_draft(message: Message, state: FSMContext):
    # Legacy /start and complaint handlers clear FSM data. Require an explicit
    # discard rather than silently destroying a paused evidence draft.
    if not (await state.get_data()).get("evidence_draft"):
        return UNHANDLED
    if message.chat.type == "private":
        await message.answer(
            "لديك مسودة أدلة متوقفة لم تُرسل. افتح زر الطلب نفسه لاستئنافها، "
            "أو /discard لحذفها قبل بدء عملية أخرى."
        )


@router.callback_query()
async def protect_paused_callback(callback: CallbackQuery, state: FSMContext):
    if not (await state.get_data()).get("evidence_draft"):
        return UNHANDLED
    await callback.answer("استأنف مسودة الأدلة أو احذفها بـ /discard أولًا.", show_alert=True)
