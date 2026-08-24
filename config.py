import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
REFERRAL_BONUS = int(os.getenv("REFERRAL_BONUS", 10))
