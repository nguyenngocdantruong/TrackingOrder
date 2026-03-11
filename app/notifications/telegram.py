import requests
from flask import current_app

class TelegramNotifier:
    @staticmethod
    def send_message(chat_id, text, parse_mode='Markdown', reply_markup=None):
        token = current_app.config.get('TELEGRAM_BOT_TOKEN')
        if not token:
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text
        }

        if parse_mode:
            payload['parse_mode'] = parse_mode

        if reply_markup:
            payload['reply_markup'] = reply_markup

        try:
            response = requests.post(url, json=payload, timeout=10)
            current_app.logger.info("[BOT] Telegram send message to %s with content: %s", chat_id, text)
            return response.status_code == 200
        except Exception as e:
            current_app.logger.error(f"Telegram error: {e}")
            return False
