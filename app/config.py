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
    POWER_OUTAGE_ENABLED = os.getenv('POWER_OUTAGE_ENABLED', 'true').lower() == 'true'
    POWER_OUTAGE_INTERVAL_SECONDS = int(os.getenv('POWER_OUTAGE_INTERVAL_SECONDS', 21600))

    OIL_PRICE_URL = os.getenv('OIL_PRICE_URL', 'https://giaxanghomnay.com/tinh-tp/ha-noi')
    OIL_NOTIFY_ENABLED = os.getenv('OIL_NOTIFY_ENABLED', 'true').lower() == 'true'
    TIME_NOTIFY_OIL = os.getenv('TIME_NOTIFY_OIL', '07:30')

    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME', 'orderskibidi_bot')
    ZALO_BOT_TOKEN = os.getenv('ZALO_BOT_TOKEN')
    ZALO_BOT_WEBHOOK_URL = os.getenv('ZALO_BOT_WEBHOOK_URL')
    ZALO_BOT_SECRET_TOKEN = os.getenv('ZALO_BOT_SECRET_TOKEN')
    ZALO_BOT_UID = os.getenv('ZALO_BOT_UID', '2787361938619367790')
    ADMIN_TELEGRAM_USER_ID = os.getenv('ADMIN_TELEGRAM_USER_ID')
    WEBSITE_URL = os.getenv('WEBSITE_URL', 'http://127.0.0.1:5000').rstrip('/')

    PAYOS_CLIENT_ID = os.getenv('PAYOS_CLIENT_ID')
    PAYOS_API_KEY = os.getenv('PAYOS_API_KEY')
    PAYOS_CHECKSUM_KEY = os.getenv('PAYOS_CHECKSUM_KEY')
    PAYOS_RETURN_URL = os.getenv('PAYOS_RETURN_URL', f"{WEBSITE_URL}/payments/return")
    PAYOS_CANCEL_URL = os.getenv('PAYOS_CANCEL_URL', f"{WEBSITE_URL}/payments/cancel")
    PAYOS_DONATION_AMOUNT = int(os.getenv('PAYOS_DONATION_AMOUNT', 50000))

    DONATE_NOTIFY_ALL = os.getenv('DONATE_NOTIFY_ALL', '0').lower() in ['1', 'true', 'yes']

    LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
