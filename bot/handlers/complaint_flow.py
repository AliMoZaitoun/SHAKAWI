import random
import secrets
import aiohttp
from html import escape
from urllib.parse import urlsplit
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile,
)
from aiogram.fsm.context import FSMContext
from bot.states.complaint_states import ComplaintForm
from bot.keyboards.inline import get_directorates_keyboard, get_categories_keyboard
from bot.config import API_BASE_URL, API_HEADERS
from bot.locales import get_txt

router = Router()
MAX_EVIDENCE_DOWNLOAD_BYTES = 10 * 1024 * 1024
MAX_EVIDENCE_FILES_PER_DETAIL = 20

def actor_headers(event):
    # Telegram identity comes from the authenticated update, never from FSM data.
    return {**API_HEADERS, "X-Telegram-Id": str(event.from_user.id)}


def in_private_chat(event):
    message = getattr(event, "message", None) or event
    chat = getattr(message, "chat", None)
    return chat is None or getattr(chat, "type", None) == "private"


def _chunks(text, limit=3500):
    text = str(text or "")
    return [text[index:index + limit] for index in range(0, len(text), limit)] or [""]


def complaint_detail_sections(complaint, lang):
    status = get_txt(lang, f"status_{str(complaint.get('status', '')).lower()}")
    priority = get_txt(lang, f"priority_{str(complaint.get('priority', '')).lower()}")
    visibility = get_txt(
        lang, "visibility_public" if complaint.get("is_public") else "visibility_private",
    )
    summary = (
        f"{get_txt(lang, 'complaint_details_title')}\n\n"
        f"{get_txt(lang, 'comp_title_label')} {escape(str(complaint.get('title', '')))}\n"
        f"{get_txt(lang, 'comp_cat_label')} {escape(str(complaint.get('category', '')))}\n"
        f"{get_txt(lang, 'comp_status_label')} <b>{escape(status)}</b>\n"
        f"{get_txt(lang, 'comp_priority_label')} <b>{escape(priority)}</b>\n"
        f"{get_txt(lang, 'comp_code_label')} <code>{escape(str(complaint.get('tracking_code', '')))}</code>\n"
        f"{get_txt(lang, 'comp_progress_label')} <b>{complaint.get('progress', 0)}%</b>\n"
        f"{get_txt(lang, 'comp_privacy_label')} <b>{escape(visibility)}</b>"
    )

    sections = [
        (get_txt(lang, "comp_details_label"), str(complaint.get("details") or "")),
    ]
    visible_notes = [
        note for note in complaint.get("notes") or []
        if note.get("audience") != "internal" and not note.get("is_internal")
    ]
    if visible_notes:
        notes_text = "\n\n".join(
            f"{get_txt(lang, 'note_audience_public' if note.get('audience') == 'public' else 'note_audience_private')}\n"
            f"{note.get('note', '')}"
            for note in visible_notes
        )
        sections.append((get_txt(lang, "updates_label"), notes_text))
    elif complaint.get("admin_notes"):
        sections.append((get_txt(lang, "admin_note_label"), str(complaint["admin_notes"])))
    if complaint.get("resolution_report"):
        sections.append((get_txt(lang, "resolution_report_label"), str(complaint["resolution_report"])))

    attachments = complaint.get("attachments") or []
    attachment_text = "\n".join(
        f"• {item.get('name') or get_txt(lang, 'evidence_file_label')} "
        f"({item.get('file_type') or 'unknown'})"
        for item in attachments
    ) or get_txt(lang, "no_attachments")
    sections.append((get_txt(lang, "attachments_label"), attachment_text))

    requests = complaint.get("evidence_requests") or []
    evidence_lines = []
    for request in requests:
        status_key = f"evidence_status_{str(request.get('status', '')).lower()}"
        request_status = get_txt(lang, status_key) or str(request.get("status", ""))
        evidence_lines.extend([
            f"{get_txt(lang, 'evidence_request_label')} · {request_status}",
            str(request.get("prompt") or ""),
        ])
        for reply in request.get("replies") or []:
            if reply.get("text"):
                evidence_lines.extend([
                    get_txt(lang, "evidence_reply_label"),
                    str(reply["text"]),
                ])
            for item in reply.get("attachments") or []:
                evidence_lines.append(
                    f"• {item.get('name') or get_txt(lang, 'evidence_file_label')} "
                    f"({item.get('file_type') or 'unknown'})"
                )
    evidence_text = "\n\n".join(evidence_lines) or get_txt(lang, "no_evidence_requests")
    sections.append((get_txt(lang, "evidence_requests_label"), evidence_text))
    return summary, sections


def evidence_reply_keyboard(complaint, lang, enabled):
    if not enabled:
        return None
    pending = [
        request for request in complaint.get("evidence_requests") or []
        if request.get("status") == "pending"
    ]
    if not pending:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_txt(lang, "btn_reply_evidence"),
            callback_data=f"evidence_{complaint['id']}_{request['id']}",
        )]
        for request in pending
    ])


def _safe_file_url(file_url):
    if not isinstance(file_url, str):
        return None
    api = urlsplit(API_BASE_URL)
    path = urlsplit(file_url)
    if (api.scheme not in {"http", "https"} or not api.netloc or path.scheme or path.netloc
            or path.query or path.fragment
            or not path.path.startswith(("/api/v1/files/", "/api/v1/evidence-files/"))):
        return None
    return f"{api.scheme}://{api.netloc}{path.path}"


def complaint_evidence_files(complaint):
    files = list(complaint.get("attachments") or [])
    for request in complaint.get("evidence_requests") or []:
        for reply in request.get("replies") or []:
            files.extend(reply.get("attachments") or [])
    return files


async def send_complaint_evidence_files(message, session, complaint, lang):
    files = complaint_evidence_files(complaint)
    failed = 0
    for item in files[:MAX_EVIDENCE_FILES_PER_DETAIL]:
        url = _safe_file_url(item.get("file_url"))
        if not url:
            failed += 1
            continue
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    failed += 1
                    continue
                content_length = int(response.headers.get("Content-Length", "0") or 0)
                if content_length > MAX_EVIDENCE_DOWNLOAD_BYTES:
                    failed += 1
                    continue
                content = await response.content.read(MAX_EVIDENCE_DOWNLOAD_BYTES + 1)
            if not content or len(content) > MAX_EVIDENCE_DOWNLOAD_BYTES:
                failed += 1
                continue
            filename = str(item.get("name") or "evidence")
            filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
            filename = "".join(char for char in filename if ord(char) >= 32)[:120] or "evidence"
            await message.answer_document(BufferedInputFile(content, filename=filename))
        except Exception:
            failed += 1
    omitted = max(0, len(files) - MAX_EVIDENCE_FILES_PER_DETAIL)
    if failed or omitted:
        await message.answer(get_txt(
            lang, "evidence_delivery_partial", failed=failed, omitted=omitted,
        ))


async def send_complaint_detail(
    message, complaint, lang, *, session=None, edit=False, allow_evidence_reply=False,
):
    summary, sections = complaint_detail_sections(complaint, lang)
    keyboard = evidence_reply_keyboard(complaint, lang, allow_evidence_reply)
    if edit:
        await message.edit_text(summary, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(summary, reply_markup=keyboard, parse_mode="HTML")
    for label, body in sections:
        for index, chunk in enumerate(_chunks(body)):
            heading = label if index == 0 else get_txt(lang, "continued_label")
            await message.answer(f"{heading}\n{escape(chunk)}", parse_mode="HTML")
    if session is not None:
        await send_complaint_evidence_files(message, session, complaint, lang)


async def current_citizen(event, state):
    """FSM data is a draft/cache, not an authorization capability."""
    data = await state.get_data()
    try:
        async with aiohttp.ClientSession(headers=actor_headers(event)) as session:
            async with session.get(
                f"{API_BASE_URL}/citizens/telegram/{event.from_user.id}"
            ) as response:
                citizen = await response.json() if response.status == 200 else None
    except (aiohttp.ClientError, TimeoutError, ValueError):
        citizen = None
    if not citizen or (data.get("citizen_id") and data["citizen_id"] != citizen["id"]):
        await state.clear()
        target = getattr(event, "message", event)
        await target.answer("تعذر إثبات الربط الحالي. استخدم /start أو استعد الوصول من الموقع.")
        return None
    await state.update_data(citizen_id=citizen["id"])
    return citizen["id"]

@router.message(F.text == "/myid")
async def show_telegram_id(message: Message):
    if message.chat.type == "private":
        await message.answer(f"معرّف حسابك الرقمي: {message.from_user.id}")

@router.message(F.text.startswith("/recover ") | F.text.startswith("/link "))
async def ownership_command(message: Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer("استعادة الوصول والربط متاحان في المحادثة الخاصة مع البوت فقط.")
        return
    command, token = message.text.strip().split(maxsplit=1)
    if command not in {"/recover", "/link"} or not 32 <= len(token) <= 100:
        await message.answer("الطلب غير صالح. أنشئ طلبًا جديدًا من الموقع.")
        return
    nonce = secrets.token_hex(8)
    await state.update_data(ownership_token=token, ownership_action=command,
                            ownership_nonce=nonce)
    text = (
        "هل بدأت طلب استعادة في الموقع؟ الموافقة ستسمح لذلك المتصفح بالوصول إلى شكاواك. "
        "لا توافق على طلب أرسله لك شخص آخر."
        if command == "/recover" else
        "هل أنشأت رمز الربط بنفسك من جلستك الموثوقة في الموقع؟ "
        "الموافقة ستربط سجل المواطن بهذا الحساب وتستبدل حساب تيليغرام السابق إن وجد."
    )
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="أوافق", callback_data=f"ownership_yes_{nonce}"),
         InlineKeyboardButton(text="رفض", callback_data=f"ownership_no_{nonce}")]
    ]))


@router.callback_query(F.data.startswith("ownership_"))
async def ownership_confirmation(callback: CallbackQuery, state: FSMContext):
    if not callback.message or callback.message.chat.type != "private":
        await callback.answer("استخدم المحادثة الخاصة.", show_alert=True)
        return
    data = await state.get_data()
    nonce = callback.data.rsplit("_", 1)[-1]
    if nonce != data.get("ownership_nonce"):
        await callback.answer("انتهى هذا الطلب. ابدأ من الموقع مجددًا.", show_alert=True)
        return
    await state.update_data(ownership_nonce=None)
    if callback.data.startswith("ownership_no_"):
        await state.update_data(ownership_token=None)
        await callback.message.edit_text("تم رفض الطلب دون تغيير الوصول أو الربط.")
        await callback.answer()
        return
    action = data.get("ownership_action")
    path = "approve" if action == "/recover" else "confirm-link"
    try:
        async with aiohttp.ClientSession(headers=API_HEADERS) as session:
            async with session.post(
                f"{API_BASE_URL}/citizens/recovery/telegram/{path}",
                json={"token": data["ownership_token"], "telegram_id": callback.from_user.id},
            ) as response:
                result = await response.json()
                if response.status == 200:
                    if path == "confirm-link":
                        # Drop stale complaint/identity state from any previous registration.
                        await state.clear()
                        await state.update_data(citizen_id=result["id"], lang=data.get("lang", "ar"))
                    text = ("تم ربط الحساب. استخدم /start لعرض شكاواك."
                            if path == "confirm-link" else result["message"])
                else:
                    text = result.get("detail", "تعذر التحقق. ابدأ طلبًا جديدًا من الموقع.")
    except (aiohttp.ClientError, TimeoutError, ValueError):
        text = "تعذر الاتصال. تحقق من حالة الربط في الموقع قبل إعادة المحاولة."
    await state.update_data(ownership_token=None)
    await callback.message.edit_text(text)
    await callback.answer()

@router.message(F.text == "/cancel")
async def cmd_cancel(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    await state.clear()
    await message.answer(
        get_txt(lang, "cancel_success"),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )

def get_language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇸🇾 العربية", callback_data="set_lang_ar"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")]
    ])

@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    
    async with aiohttp.ClientSession(headers=API_HEADERS) as session:
        try:
            async with session.get(f"{API_BASE_URL}/citizens/telegram/{telegram_id}") as response:
                if response.status == 200:
                    citizen_data = await response.json()
                    lang = (await state.get_data()).get("lang", "ar")
                    await state.update_data(citizen_id=citizen_data["id"], lang=lang)
                    
                    menu_kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=get_txt(lang, "btn_new_complaint"), callback_data="action_new_complaint")],
                        [InlineKeyboardButton(text=get_txt(lang, "btn_my_complaints"), callback_data="action_my_complaints")],
                        [InlineKeyboardButton(text=get_txt(lang, "btn_change_lang"), callback_data="action_change_lang")]
                    ])
                    await message.answer(
                        get_txt(lang, "welcome_back", name=citizen_data['first_name']),
                        reply_markup=menu_kb,
                        parse_mode="HTML"
                    )
                    return
        except Exception:
            pass

    await state.clear()
    await message.answer(
        "🌐 <b>Choose Language / اختر اللغة:</b>",
        reply_markup=get_language_keyboard(),
        parse_mode="HTML"
    )

async def show_directorates(message, state, lang, edit=False):
    """Use the same translated, active directory as web/API clients."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(f"{API_BASE_URL}/directorates", params={"lang": lang}) as response:
                if response.status != 200:
                    raise RuntimeError("Directory service unavailable")
                rows = await response.json()
        if not rows:
            raise RuntimeError("No active directorates")
        keyboard = get_directorates_keyboard(lang, rows)
        await state.update_data(
            allowed_directorates=[row["id"] for row in rows],
            directorate_catalog=rows,
            current_directorate_id=None,
        )
        sender = message.edit_text if edit else message.answer
        await sender(get_txt(lang, "ask_directorate"), reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(ComplaintForm.directorate_id)
        return True
    except (aiohttp.ClientError, TimeoutError, RuntimeError, ValueError, KeyError):
        await message.answer(get_txt(lang, "reg_error"))
        return False


@router.message(F.text == "/new")
async def cmd_new_complaint_shortcut(message: Message, state: FSMContext):
    if not await current_citizen(message, state):
        return
    data = await state.get_data()
    lang = data.get("lang", "ar")
    citizen_id = data.get("citizen_id")
    
    if not citizen_id:
        await message.answer(get_txt(lang, "please_start_first"), parse_mode="HTML")
        return

    await show_directorates(message, state, lang)

@router.callback_query(F.data.startswith("set_lang_"))
async def set_language(callback: CallbackQuery, state: FSMContext):
    selected_lang = callback.data.split("_")[2] # ar or en
    await state.update_data(lang=selected_lang)
    
    telegram_id = callback.from_user.id
    
    async with aiohttp.ClientSession(headers=API_HEADERS) as session:
        try:
            async with session.get(f"{API_BASE_URL}/citizens/telegram/{telegram_id}") as response:
                if response.status == 200:
                    citizen_data = await response.json()
                    await state.update_data(citizen_id=citizen_data["id"])
                    
                    menu_kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=get_txt(selected_lang, "btn_new_complaint"), callback_data="action_new_complaint")],
                        [InlineKeyboardButton(text=get_txt(selected_lang, "btn_my_complaints"), callback_data="action_my_complaints")],
                        [InlineKeyboardButton(text=get_txt(selected_lang, "btn_change_lang"), callback_data="action_change_lang")]
                    ])
                    await callback.message.edit_text(
                        get_txt(selected_lang, "welcome_back", name=citizen_data['first_name']),
                        reply_markup=menu_kb,
                        parse_mode="HTML"
                    )
                    await callback.answer()
                    return
        except Exception:
            pass

    contact_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=get_txt(selected_lang, "btn_share_phone"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback.message.answer(
        get_txt(selected_lang, "welcome_new"),
        reply_markup=contact_keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ComplaintForm.phone)
    await callback.answer()

@router.callback_query(F.data == "action_change_lang")
async def action_change_lang(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🌐 Choose Language / اختر اللغة:", reply_markup=get_language_keyboard())
    await callback.answer()

@router.message(ComplaintForm.phone)
async def process_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    if not message.contact or message.contact.user_id != message.from_user.id:
        await message.answer(
            "يرجى مشاركة رقم هاتفك عبر زر مشاركة جهة الاتصال، وليس رقم شخص آخر."
            if lang == "ar" else
            "Please use the share-contact button to share your own phone number."
        )
        return
    phone = message.contact.phone_number
    await state.update_data(phone=phone)

    await message.answer(
        get_txt(lang, "ask_first_name"),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintForm.first_name)

@router.message(ComplaintForm.first_name)
async def process_first_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    await state.update_data(first_name=message.text)
    await message.answer(get_txt(lang, "ask_last_name"), parse_mode="HTML")
    await state.set_state(ComplaintForm.last_name)

@router.message(ComplaintForm.last_name)
async def process_last_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    await state.update_data(last_name=message.text)
    await message.answer(get_txt(lang, "ask_national_id"), parse_mode="HTML")
    await state.set_state(ComplaintForm.national_id)

@router.message(ComplaintForm.national_id)
async def process_national_id(message: Message, state: FSMContext):
    await state.update_data(national_id=message.text)
    data = await state.get_data()
    lang = data.get("lang", "ar")
    
    # نطلب صورة الهوية الشخصية بناءً على لغة المستخدم
    await message.answer(
        get_txt(lang, "ask_id_image"),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintForm.waiting_for_id_image)

# استقبال صورة الهوية وإتمام إنشاء الحساب
@router.message(ComplaintForm.waiting_for_id_image, F.photo)
async def process_id_image(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    
    # جلب صورة الهوية من تليجرام
    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)
    file_bytes_io = await message.bot.download_file(file_info.file_path)
    file_bytes = file_bytes_io.read()
    
    citizen_payload = {
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "phone": data["phone"],
        "national_id": data["national_id"],
        "telegram_id": message.from_user.id
    }

    async with aiohttp.ClientSession(headers=actor_headers(message)) as session:
        try:
            # 1. إنشاء الحساب في الباك إند
            async with session.post(f"{API_BASE_URL}/citizens/", json=citizen_payload) as response:
                if response.status == 200:
                    res_data = await response.json()
                    citizen_id = res_data["id"]
                    await state.update_data(citizen_id=citizen_id)
                    
                    # 2. إرسال صورة الهوية كمرفق خاص بالمواطن
                    form = aiohttp.FormData()
                    form.add_field('file', file_bytes, filename="id_card.jpg", content_type='image/jpeg')
                    async with session.post(f"{API_BASE_URL}/citizens/{citizen_id}/id-image/", data=form) as image_response:
                        if image_response.status != 200:
                            await message.answer(get_txt(lang, "reg_error"))
                            return
                    
                    # رسالة النجاح والتوثيق المترجمة
                    await message.answer(
                        get_txt(lang, "id_success"),
                        parse_mode="HTML"
                    )
                    
                    # الانتقال مباشرة لخطوة اختيار المديرية باللغة المختارة
                    await show_directorates(message, state, lang)
                else:
                    await message.answer(get_txt(lang, "reg_error"))
                    await state.clear()
        except Exception as e:
            await message.answer(get_txt(lang, "conn_error", error=str(e)))
            await state.clear()

@router.callback_query(F.data == "action_new_complaint")
async def action_new_complaint(callback: CallbackQuery, state: FSMContext):
    if not await current_citizen(callback, state):
        await callback.answer()
        return
    data = await state.get_data()
    lang = data.get("lang", "ar")
    await show_directorates(callback.message, state, lang, edit=True)
    await callback.answer()

@router.callback_query(F.data.startswith("dir_"), ComplaintForm.directorate_id)
async def process_directorate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")

    allowed = {int(identifier) for identifier in data.get("allowed_directorates", [])}
    catalog = data.get("directorate_catalog", [])
    selected_id = None
    action = callback.data
    try:
        if action.startswith("dir_open_"):
            selected_id = int(action.removeprefix("dir_open_"))
            action_type = "open"
        elif action.startswith("dir_select_"):
            selected_id = int(action.removeprefix("dir_select_"))
            action_type = "select"
        elif action == "dir_root":
            action_type = "root"
        else:
            # Accept numeric buttons sent before the hierarchical keyboard was deployed.
            selected_id = int(action.removeprefix("dir_"))
            action_type = "select"
    except ValueError:
        selected_id = None
        action_type = "invalid"

    if action_type == "root":
        try:
            keyboard = get_directorates_keyboard(lang, catalog)
        except ValueError:
            await callback.answer(get_txt(lang, "reg_error"), show_alert=True)
            return
        await state.update_data(current_directorate_id=None)
        await callback.message.edit_text(
            get_txt(lang, "ask_directorate"), reply_markup=keyboard, parse_mode="HTML",
        )
        await callback.answer()
        return

    if action_type not in {"open", "select"} or selected_id not in allowed:
        await callback.answer(get_txt(lang, "reg_error"), show_alert=True)
        return

    directorate = next(
        (row for row in catalog if int(row["id"]) == selected_id),
        None,
    )
    if action_type == "open":
        if directorate is None:
            await callback.answer(get_txt(lang, "reg_error"), show_alert=True)
            return
        try:
            keyboard = get_directorates_keyboard(lang, catalog, selected_id=selected_id)
        except ValueError:
            await callback.answer(get_txt(lang, "reg_error"), show_alert=True)
            return
        await state.update_data(current_directorate_id=selected_id)
        await callback.message.edit_text(
            get_txt(
                lang, "ask_directorate_children",
                name=escape(str(directorate.get("name", ""))),
            ),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await state.update_data(directorate_id=selected_id, current_directorate_id=None)
    await callback.message.edit_text(
        get_txt(lang, "ask_category"),
        reply_markup=get_categories_keyboard(lang),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintForm.category)
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"), ComplaintForm.category)
async def process_category(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    
    category_map = {
        "cat_roads": "طرق",
        "cat_construction": "مخالفات بناء",
        "cat_digging": "حفريات",
        "cat_opening_roads": "فتح طرق",
        "cat_outage": "انقطاع خدمة",
        "cat_technical": "عطل فني",
        "cat_admin": "شكوى إدارية",
        "cat_other": "أخرى"
    }
    selected_cat = category_map.get(callback.data, "أخرى")
    await state.update_data(category=selected_cat)
    
    # خيارات تحديد الموقع: جي بي إس أو يدوياً
    location_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_txt(lang, "btn_share_geo"), request_location=True)],
            [KeyboardButton(text=get_txt(lang, "btn_manual_address"))]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.answer(
        get_txt(lang, "ask_location"),
        reply_markup=location_keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ComplaintForm.waiting_for_location)
    await callback.answer()

# 1. استقبال الموقع عبر الـ GPS
@router.message(ComplaintForm.waiting_for_location, F.location)
async def process_location_geo(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    
    await state.update_data(latitude=message.location.latitude, longitude=message.location.longitude)
    await message.answer(
        get_txt(lang, "ask_title"),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintForm.title)

# 2. اختيار الإدخال اليدوي للموقع
@router.message(ComplaintForm.waiting_for_location, F.text.contains("يدوياً") | F.text.contains("Manually"))
async def process_location_manual_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    await message.answer(
        get_txt(lang, "ask_manual_address"),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )

@router.message(ComplaintForm.waiting_for_location, F.text, ~F.text.startswith("/"))
async def process_location_manual_input(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    
    await state.update_data(manual_address=message.text)
    await message.answer(
        get_txt(lang, "ask_title"),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintForm.title)

@router.message(ComplaintForm.title)
async def process_title(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    await state.update_data(title=message.text)
    await message.answer(get_txt(lang, "ask_details"), parse_mode="HTML")
    await state.set_state(ComplaintForm.details)

@router.message(ComplaintForm.details)
async def process_details(message: Message, state: FSMContext):
    if not await current_citizen(message, state):
        return
    data = await state.get_data()
    lang = data.get("lang", "ar")
    
    full_details = message.text
    if data.get("manual_address"):
        full_details += f"\n📍 [موقع مدخل يدوياً]: {data.get('manual_address')}"

    payload = {
        "citizen_id": data["citizen_id"], 
        "directorate_id": data["directorate_id"],
        "title": data["title"],
        "details": full_details,
        "is_public": False,
        "category": data["category"],
        "priority": "MEDIUM",
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude")
    }

    async with aiohttp.ClientSession(headers=actor_headers(message)) as session:
        try:
            async with session.post(f"{API_BASE_URL}/complaints/", json=payload) as response:
                if response.status == 200:
                    res_data = await response.json()
                    complaint_id = res_data.get("id")
                    tracking_code = res_data.get("tracking_code")
                    await message.answer(
                        "خصوصية الشكوى: خاصة. لن تُنشر في دليل الشكاوى العامة."
                        if lang == "ar" else
                        "Privacy: private. This complaint will not appear in the public directory."
                    )
                    
                    await state.update_data(complaint_id=complaint_id, tracking_code=tracking_code)
                    
                    skip_keyboard = ReplyKeyboardMarkup(
                        keyboard=[[KeyboardButton(text=get_txt(lang, "btn_skip_attachment"))]],
                        resize_keyboard=True,
                        one_time_keyboard=True
                    )
                    await message.answer(
                        get_txt(lang, "complaint_created", code=tracking_code) + "\n\n" + get_txt(lang, "ask_attachment"),
                        reply_markup=skip_keyboard,
                        parse_mode="HTML"
                    )
                    await state.set_state(ComplaintForm.waiting_for_attachment)
                else:
                    await message.answer("❌ Server Error.")
                    await state.clear()
        except Exception as e:
            await message.answer(f"❌ Connection error: {str(e)}")
            await state.clear()

@router.message(ComplaintForm.waiting_for_attachment, F.photo | F.document)
async def process_attachment(message: Message, state: FSMContext):
    if not await current_citizen(message, state):
        return
    data = await state.get_data()
    lang = data.get("lang", "ar")
    complaint_id = data.get("complaint_id")
    
    document = message.photo[-1] if message.photo else message.document
    file_info = await message.bot.get_file(document.file_id)
    file_bytes_io = await message.bot.download_file(file_info.file_path)
    file_bytes = file_bytes_io.read()
    filename = file_info.file_path.split("/")[-1] or "attachment.jpg"
    
    async with aiohttp.ClientSession(headers=actor_headers(message)) as session:
        form = aiohttp.FormData()
        mime_type = 'image/jpeg' if message.photo else (message.document.mime_type or 'application/octet-stream')
        form.add_field('file', file_bytes, filename=filename, content_type=mime_type)
        
        try:
            async with session.post(f"{API_BASE_URL}/complaints/{complaint_id}/attachments/", data=form) as response:
                if response.status == 200:
                    more_keyboard = ReplyKeyboardMarkup(
                        keyboard=[
                            [KeyboardButton(text=get_txt(lang, "btn_finish_upload"))]
                        ],
                        resize_keyboard=True,
                        one_time_keyboard=True
                    )
                    await message.answer(
                        get_txt(lang, "attachment_saved_more"),
                        reply_markup=more_keyboard,
                        parse_mode="HTML"
                    )
                else:
                    await message.answer("⚠️ Attachment upload failed.", reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            await message.answer(f"❌ Error: {str(e)}", reply_markup=ReplyKeyboardRemove())

@router.message(ComplaintForm.waiting_for_attachment, F.text.contains("إنهاء") | F.text.contains("تخطي") | F.text.contains("Finish") | F.text.contains("Skip"))
async def finish_attachment_process(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    tracking_code = data.get('tracking_code')
    
    await message.answer(
        get_txt(lang, "final_complaint_done", code=tracking_code),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.clear()

@router.message(F.text == "/track")
async def cmd_track_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    if not in_private_chat(message):
        await message.answer(get_txt(lang, "private_chat_required"))
        return
    await message.answer(get_txt(lang, "ask_track_code"), parse_mode="HTML")
    await state.set_state(ComplaintForm.waiting_for_track_code)

@router.message(ComplaintForm.waiting_for_track_code, ~F.text.startswith("/"))
async def process_track_code_input(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    if not in_private_chat(message):
        await message.answer(get_txt(lang, "private_chat_required"))
        await state.clear()
        return
    tracking_code = message.text.strip()
    
    async with aiohttp.ClientSession(headers=API_HEADERS) as session:
        try:
            async with session.get(f"{API_BASE_URL}/complaints/track/{tracking_code}") as response:
                if response.status == 200:
                    comp = await response.json()
                    await send_complaint_detail(message, comp, lang, session=session)
                else:
                    await message.answer(get_txt(lang, "track_not_found"))
        except Exception as e:
            await message.answer(get_txt(lang, "conn_error", error=str(e)))
    
    await state.clear()

@router.callback_query(F.data == "action_my_complaints")
async def action_my_complaints(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    if not in_private_chat(callback):
        await callback.answer(get_txt(lang, "private_chat_required"), show_alert=True)
        return
    if not await current_citizen(callback, state):
        await callback.answer()
        return
    citizen_id = data.get("citizen_id")
    
    async with aiohttp.ClientSession(headers=actor_headers(callback)) as session:
        try:
            async with session.get(f"{API_BASE_URL}/complaints/citizen/{citizen_id}") as response:
                if response.status == 200:
                    complaints = await response.json()
                    if not complaints:
                        await callback.message.edit_text(get_txt(lang, "no_complaints"))
                        await callback.answer()
                        return
                    
                    buttons = []
                    for comp in complaints:
                        buttons.append([
                            InlineKeyboardButton(
                                text=f"📌 {comp['title']} ({comp['status']})", 
                                callback_data=f"comp_detail_{comp['id']}"
                            )
                        ])
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                    await callback.message.edit_text(
                        get_txt(lang, "my_complaints_title"),
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                else:
                    await callback.message.edit_text("❌ Connection error.")
        except Exception as e:
            await callback.message.edit_text(f"❌ Error: {str(e)}")
            
    await callback.answer()


@router.callback_query(F.data.startswith("comp_detail_"))
async def show_complaint_detail(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    if not in_private_chat(callback):
        await callback.answer(get_txt(lang, "private_chat_required"), show_alert=True)
        return
    if not await current_citizen(callback, state):
        await callback.answer()
        return
    comp_id = callback.data.split("_")[2]
    
    async with aiohttp.ClientSession(headers=actor_headers(callback)) as session:
        try:
            async with session.get(f"{API_BASE_URL}/complaints/{comp_id}") as response:
                if response.status == 200:
                    comp = await response.json()
                    await send_complaint_detail(
                        callback.message,
                        comp,
                        lang,
                        session=session,
                        edit=True,
                        allow_evidence_reply=True,
                    )
                else:
                    await callback.message.edit_text("❌ Error.")
        except Exception:
            await callback.message.edit_text("❌ Error.")
            
    await callback.answer()


@router.message(F.text == "/mystatus")
async def cmd_mystatus(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    if not in_private_chat(message):
        await message.answer(get_txt(lang, "private_chat_required"))
        return
    if not await current_citizen(message, state):
        return
    citizen_id = data.get("citizen_id")
    telegram_id = message.from_user.id

    async with aiohttp.ClientSession(headers=actor_headers(message)) as session:
        if not citizen_id:
            try:
                async with session.get(f"{API_BASE_URL}/citizens/telegram/{telegram_id}") as citizen_res:
                    if citizen_res.status == 200:
                        citizen_data = await citizen_res.json()
                        citizen_id = citizen_data["id"]
                        await state.update_data(citizen_id=citizen_id)
                    else:
                        await message.answer(get_txt(lang, "welcome_new"), parse_mode="HTML")
                        return
            except Exception as e:
                await message.answer(get_txt(lang, "conn_error", error=str(e)), parse_mode="HTML")
                return

        # 2. جلب الشكاوى الخاصة بالمواطن وترجمة الحالة والأزرار
        try:
            async with session.get(f"{API_BASE_URL}/complaints/citizen/{citizen_id}") as response:
                if response.status == 200:
                    complaints = await response.json()
                    if not complaints:
                        await message.answer(get_txt(lang, "no_complaints"), parse_mode="HTML")
                        return
                    
                    buttons = []
                    for comp in complaints:
                        # ترجمة حالة الشكوى للأزرار
                        raw_status = comp['status'].lower()
                        status_txt = get_txt(lang, f"status_{raw_status}")
                        
                        buttons.append([
                            InlineKeyboardButton(
                                text=f"📌 {comp['title']} ({status_txt})", 
                                callback_data=f"comp_detail_{comp['id']}"
                            )
                        ])
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                    await message.answer(
                        get_txt(lang, "my_complaints_title"),
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                else:
                    await message.answer(get_txt(lang, "conn_error", error="Server Error"), parse_mode="HTML")
        except Exception as e:
            await message.answer(get_txt(lang, "conn_error", error=str(e)), parse_mode="HTML")


@router.message()
async def catch_all(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    await message.answer(get_txt(lang, "unknown_command"), parse_mode="HTML")