import random
import aiohttp
from html import escape
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.states.complaint_states import ComplaintForm
from bot.keyboards.inline import get_directorates_keyboard, get_categories_keyboard
from bot.config import API_BASE_URL, API_HEADERS
from bot.locales import get_txt

router = Router()

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

@router.message(F.text == "/new")
async def cmd_new_complaint_shortcut(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    citizen_id = data.get("citizen_id")
    
    if not citizen_id:
        await message.answer(get_txt(lang, "please_start_first"), parse_mode="HTML")
        return

    await message.answer(
        get_txt(lang, "ask_directorate"),
        reply_markup=get_directorates_keyboard(lang),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintForm.directorate_id)

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

    async with aiohttp.ClientSession(headers=API_HEADERS) as session:
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
                    await session.post(f"{API_BASE_URL}/citizens/{citizen_id}/id-image/", data=form)
                    
                    # رسالة النجاح والتوثيق المترجمة
                    await message.answer(
                        get_txt(lang, "id_success"),
                        parse_mode="HTML"
                    )
                    
                    # الانتقال مباشرة لخطوة اختيار المديرية باللغة المختارة
                    await message.answer(
                        get_txt(lang, "ask_directorate"),
                        reply_markup=get_directorates_keyboard(lang),
                        parse_mode="HTML"
                    )
                    await state.set_state(ComplaintForm.directorate_id)
                else:
                    await message.answer(get_txt(lang, "reg_error"))
                    await state.clear()
        except Exception as e:
            await message.answer(get_txt(lang, "conn_error", error=str(e)))
            await state.clear()

@router.callback_query(F.data == "action_new_complaint")
async def action_new_complaint(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    await callback.message.edit_text(
        get_txt(lang, "ask_directorate"),
        reply_markup=get_directorates_keyboard(lang),
        parse_mode="HTML"
    )
    await state.set_state(ComplaintForm.directorate_id)
    await callback.answer()

@router.callback_query(F.data.startswith("dir_"), ComplaintForm.directorate_id)
async def process_directorate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    
    dir_data = callback.data.split("_")[1] # gov or services
    dir_id = 1 if dir_data == "gov" else 2
    
    await state.update_data(directorate_id=dir_id)
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

    async with aiohttp.ClientSession(headers=API_HEADERS) as session:
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
    data = await state.get_data()
    lang = data.get("lang", "ar")
    complaint_id = data.get("complaint_id")
    
    document = message.photo[-1] if message.photo else message.document
    file_info = await message.bot.get_file(document.file_id)
    file_bytes_io = await message.bot.download_file(file_info.file_path)
    file_bytes = file_bytes_io.read()
    filename = file_info.file_path.split("/")[-1] or "attachment.jpg"
    
    async with aiohttp.ClientSession(headers=API_HEADERS) as session:
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
    await message.answer(get_txt(lang, "ask_track_code"), parse_mode="HTML")
    await state.set_state(ComplaintForm.waiting_for_track_code)

@router.message(ComplaintForm.waiting_for_track_code, ~F.text.startswith("/"))
async def process_track_code_input(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    tracking_code = message.text.strip()
    
    async with aiohttp.ClientSession(headers=API_HEADERS) as session:
        try:
            async with session.get(f"{API_BASE_URL}/complaints/track/{tracking_code}") as response:
                if response.status == 200:
                    comp = await response.json()
                    
                    admin_note_text = ""
                    if comp.get('admin_notes'):
                        admin_note_text = f"\n{get_txt(lang, 'admin_note_label')} {escape(comp['admin_notes'])}"
                    
                    resolution_text = ""
                    if comp.get('resolution_report'):
                        resolution_text = f"\n{get_txt(lang, 'resolution_report_label')} {escape(comp['resolution_report'])}"

                    status_key = f"status_{comp['status'].lower()}"
                    priority_key = f"priority_{comp['priority'].lower()}"

                    translated_status = get_txt(lang, status_key)
                    translated_priority = get_txt(lang, priority_key)

                    detail_text = (
                        f"{get_txt(lang, 'complaint_details_title')}\n\n"
                        f"{get_txt(lang, 'comp_title_label')} {comp['title']}\n"
                        f"{get_txt(lang, 'comp_cat_label')} {comp['category']}\n"
                        f"{get_txt(lang, 'comp_status_label')} <b>{translated_status}</b>\n"
                        f"{get_txt(lang, 'comp_priority_label')} <b>{translated_priority}</b>\n"
                        f"{get_txt(lang, 'comp_code_label')} <code>{comp['tracking_code']}</code>\n"
                        f"{admin_note_text}"
                        f"{resolution_text}\n\n"
                        f"{get_txt(lang, 'comp_details_label')}\n{comp['details']}"
                    )
                    await message.answer(detail_text, parse_mode="HTML")
                else:
                    await message.answer(get_txt(lang, "track_not_found"))
        except Exception as e:
            await message.answer(get_txt(lang, "conn_error", error=str(e)))
    
    await state.clear()

@router.callback_query(F.data == "action_my_complaints")
async def action_my_complaints(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    citizen_id = data.get("citizen_id")
    
    async with aiohttp.ClientSession(headers=API_HEADERS) as session:
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
    comp_id = callback.data.split("_")[2]
    
    async with aiohttp.ClientSession(headers=API_HEADERS) as session:
        try:
            async with session.get(f"{API_BASE_URL}/complaints/{comp_id}") as response:
                if response.status == 200:
                    comp = await response.json()

                    admin_note_text = ""
                    if comp.get('admin_notes'):
                        admin_note_text = f"\n{get_txt(lang, 'admin_note_label')} {escape(comp['admin_notes'])}"
                    
                    resolution_text = ""
                    if comp.get('resolution_report'):
                        resolution_text = f"\n{get_txt(lang, 'resolution_report_label')} {escape(comp['resolution_report'])}"

                    status_key = f"status_{comp['status'].lower()}"
                    priority_key = f"priority_{comp['priority'].lower()}"

                    translated_status = get_txt(lang, status_key)
                    translated_priority = get_txt(lang, priority_key)

                    detail_text = (
                        f"{get_txt(lang, 'complaint_details_title')}\n\n"
                        f"{get_txt(lang, 'comp_title_label')} {comp['title']}\n"
                        f"{get_txt(lang, 'comp_cat_label')} {comp['category']}\n"
                        f"{get_txt(lang, 'comp_status_label')} <b>{translated_status}</b>\n"
                        f"{get_txt(lang, 'comp_priority_label')} <b>{translated_priority}</b>\n"
                        f"{get_txt(lang, 'comp_code_label')} <code>{comp['tracking_code']}</code>\n"
                        f"{admin_note_text}"
                        f"{resolution_text}\n\n"
                        f"{get_txt(lang, 'comp_details_label')}\n{comp['details']}"
                    )
                    await callback.message.edit_text(detail_text, parse_mode="HTML")
                else:
                    await callback.message.edit_text("❌ Error.")
        except Exception:
            await callback.message.edit_text("❌ Error.")
            
    await callback.answer()


@router.message(F.text == "/mystatus")
async def cmd_mystatus(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ar")
    citizen_id = data.get("citizen_id")
    telegram_id = message.from_user.id

    async with aiohttp.ClientSession(headers=API_HEADERS) as session:
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