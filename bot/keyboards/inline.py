from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.locales import get_txt

def get_directorates_keyboard(lang: str = "ar") -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_txt(lang, "dir_gov"), callback_data="dir_gov")],
        [InlineKeyboardButton(text=get_txt(lang, "dir_services"), callback_data="dir_services")]
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