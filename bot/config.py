import os

# Secrets are supplied by the runtime, never from committed .env files.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000/api/v1")
API_HEADERS = {"X-Bot-Token": BOT_TOKEN}
