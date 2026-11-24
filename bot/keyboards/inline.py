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

def format_complaint_duration(minutes, lang):
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return ""
    for factor, unit in ((10080, "week"), (1440, "day"), (60, "hour")):
        if minutes >= factor and minutes % factor == 0:
            amount = minutes // factor
            break
    else:
        amount, unit = minutes, "minute"
    if lang == "en":
        label = unit if amount == 1 else f"{unit}s"
        return f"{amount} {label}"
    labels = {
        "week": ("أسبوع", "أسبوعان", "أسابيع"),
        "day": ("يوم", "يومان", "أيام"),
        "hour": ("ساعة", "ساعتان", "ساعات"),
        "minute": ("دقيقة", "دقيقتان", "دقائق"),
    }
    singular, dual, plural = labels[unit]
    if amount == 1:
        return singular
    if amount == 2:
        return dual
    return f"{amount} {plural}"


def get_complaint_types_keyboard(lang: str, complaint_types, page: int = 0) -> InlineKeyboardMarkup:
    rows = [row for row in complaint_types if row.get("is_active", True)]
    page_size = 8
    page_count = max(1, (len(rows) + page_size - 1) // page_size)
    page = max(0, min(page, page_count - 1))
    start = page * page_size
    visible = rows[start:start + page_size]
    buttons = []
    for item in visible:
        label = str(item.get("name") or "")
        duration = item.get("sla_duration_minutes")
        if duration:
            label += f" · {format_complaint_duration(duration, lang)}"
        buttons.append([
            InlineKeyboardButton(
                text=_button_text(label),
                callback_data=f"ct_{int(item['id'])}",
            )
        ])
    if page_count > 1:
        navigation = []
        if page:
            navigation.append(InlineKeyboardButton(
                text="⬅️" if lang == "ar" else "⬅️",
                callback_data=f"ct_page_{page - 1}",
            ))
        navigation.append(InlineKeyboardButton(
            text=f"{page + 1}/{page_count}",
            callback_data="ct_page_noop",
        ))
        if page + 1 < page_count:
            navigation.append(InlineKeyboardButton(
                text="➡️" if lang == "ar" else "➡️",
                callback_data=f"ct_page_{page + 1}",
            ))
        buttons.append(navigation)
    return InlineKeyboardMarkup(inline_keyboard=buttons)