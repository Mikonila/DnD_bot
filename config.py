import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in os.getenv("ADMIN_IDS", "").split(",") if admin_id.strip()]
DM_CONTACT = os.getenv("DM_CONTACT", "@nmyaso")
DB_NAME = os.getenv("DB_NAME", "dnd_bot.db")

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env файле")

