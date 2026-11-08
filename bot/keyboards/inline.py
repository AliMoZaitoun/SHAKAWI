from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.locales import get_txt

def get_directorates_keyboard(lang: str = "ar", directorates=None) -> InlineKeyboardMarkup:
    if directorates is None:
        raise ValueError("Fetch the active translated directorate catalog before building the keyboard")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=row["name"], callback_data=f"dir_{row['id']}")]
        for row in directorates
    ])
    return keyboard

def get_categories_keyboard(lang: str = "ar") -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_txt(lang, "cat_roads"), callback_data="cat_roads")],
        [InlineKeyboardButton(text=get_txt(lang, "cat_construction"), callback_data="cat_construction")],
        [InlineKeyboardButton(text=get_txt(lang, "cat_digging"), callback_data="cat_digging")],
        [InlineKeyboardButton(text=get_txt(lang, "cat_opening_roads"), callback_data="cat_opening_roads")],
        [InlineKeyboardButton(text=get_txt(lang, "cat_other"), callback_data="cat_other")]
    ])
    return keyboard