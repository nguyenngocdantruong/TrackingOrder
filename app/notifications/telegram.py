import requests
from flask import current_app

class TelegramNotifier:
    @staticmethod
    def send_message(chat_id, text):
        token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        if not token:
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            current_app.logger.error(f"Telegram error: {e}")
            return False
