"""Fetch authoritative upload limits and bound Telegram downloads before buffering."""
from io import BytesIO

import aiohttp

from bot.config import API_BASE_URL
from bot.locales import get_txt


class LimitedBuffer(BytesIO):
    def __init__(self, max_bytes: int, lang="ar"):
        super().__init__()
        self.max_bytes = max_bytes
        self.lang = lang

    def write(self, value):
        if self.tell() + len(value) > self.max_bytes:
            raise ValueError(get_txt(
                self.lang, "upload_file_too_large", limit=format_limit(self.max_bytes, self.lang),
            ))
        return super().write(value)


def format_limit(limit: int, lang="ar") -> str:
    amount = f"{limit / (1024 * 1024):.1f}".rstrip("0").rstrip(".")
    return f"{amount} MiB" if lang == "en" else f"{amount} ميغابايت"


async def fetch_upload_policy(lang="ar"):
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
        ) as session:
            async with session.get(f"{API_BASE_URL}/upload-policy") as response:
                if response.status != 200:
                    raise ValueError
                data = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError):
        raise ValueError(get_txt(lang, "upload_limit_unavailable"))
    limits = {
        item.get("mime_type"): item.get("max_bytes")
        for item in data.get("mime_types", [])
        if isinstance(item.get("mime_type"), str)
    }
    if not limits:
        raise ValueError(get_txt(lang, "upload_limit_unavailable"))
    return limits


async def download_telegram_file(
    bot, file_id, mime_type, limits, *, reported_size=None, lang="ar",
):
    limit = limits.get(mime_type)
    if not isinstance(limit, int) or not 0 < limit <= 10 * 1024 * 1024:
        raise ValueError(get_txt(lang, "upload_type_unsupported"))
    if reported_size and reported_size > limit:
        raise ValueError(get_txt(lang, "upload_file_too_large", limit=format_limit(limit, lang)))
    buffer = LimitedBuffer(limit, lang)
    await bot.download(file_id, destination=buffer)
    return buffer.getvalue()
