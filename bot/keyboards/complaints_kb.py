from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# كيبورد طلب الموقع الجغرافي
location_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📍 مشاركة موقعي الحالي", request_location=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# كيبورد تخطي المرفقات
skip_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⏭️ تخطي المرفقات")]],
    resize_keyboard=True,
    one_time_keyboard=True
)