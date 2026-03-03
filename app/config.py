import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-123')
    FIREBASE_SERVICE_ACCOUNT_JSON_PATH = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON_PATH')
    FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID')

    MAX_EVENTS_PER_TRACKING = int(os.getenv('MAX_EVENTS_PER_TRACKING', 50))
    SCHEDULER_ENABLED = os.getenv('SCHEDULER_ENABLED', 'true').lower() == 'true'
    POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', 300))

    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    ADMIN_TELEGRAM_USER_ID = os.getenv('ADMIN_TELEGRAM_USER_ID')
    WEBSITE_URL = os.getenv('WEBSITE_URL', 'http://127.0.0.1:5000').rstrip('/')
