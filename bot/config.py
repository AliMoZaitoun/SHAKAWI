import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "9248290183:AAGlvRnbH8bFR1OJ1WH8D746c2pI06uxlQ8")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")