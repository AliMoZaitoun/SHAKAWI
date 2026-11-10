from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.locales import get_txt


def _button_text(text):
    text = str(text)
    return text if len(text) <= 64 else f"{text[:63]}…"


def get_directorates_keyboard(
    lang: str = "ar", directorates=None, selected_id: int | None = None,
) -> InlineKeyboardMarkup:
    if directorates is None:
        raise ValueError("Fetch the active translated directorate catalog before building the keyboard")
    rows = [row for row in directorates if row.get("is_active", True)]
    by_id = {int(row["id"]): row for row in rows}

    if selected_id is None:
        roots = [
            row for row in rows
            if row.get("parent_id") is None or int(row["parent_id"]) not in by_id
        ]
        if not roots:
            roots = rows
        buttons = [
            [InlineKeyboardButton(text=_button_text(row["name"]), callback_data=f"dir_open_{row['id']}")]
            for row in roots
        ]
    else:
        current = by_id.get(int(selected_id))
        if current is None:
            raise ValueError("Selected directorate is not in the active catalog")
        buttons = [[InlineKeyboardButton(
            text=get_txt(lang, "btn_select_directorate"),
            callback_data=f"dir_select_{current['id']}",
        )]]
        children = [row for row in rows if row.get("parent_id") == current["id"]]
        buttons.extend(
            [InlineKeyboardButton(text=_button_text(f"↳ {row['name']}"), callback_data=f"dir_open_{row['id']}")]
            for row in children
        )
        parent_id = current.get("parent_id")
        if parent_id is not None and int(parent_id) in by_id:
            parent = by_id[int(parent_id)]
            buttons.append([InlineKeyboardButton(
                text=_button_text(get_txt(lang, "btn_back_to_parent", name=parent["name"])),
                callback_data=f"dir_open_{parent['id']}",
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=get_txt(lang, "btn_back_to_root"),
                callback_data="dir_root",
            )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_categories_keyboard(lang: str = "ar") -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_txt(lang, "cat_roads"), callback_data="cat_roads")],
        [InlineKeyboardButton(text=get_txt(lang, "cat_construction"), callback_data="cat_construction")],
        [InlineKeyboardButton(text=get_txt(lang, "cat_digging"), callback_data="cat_digging")],
        [InlineKeyboardButton(text=get_txt(lang, "cat_opening_roads"), callback_data="cat_opening_roads")],
        [InlineKeyboardButton(text=get_txt(lang, "cat_other"), callback_data="cat_other")]
    ])
    return keyboard