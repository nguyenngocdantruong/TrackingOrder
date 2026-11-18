"""
Telegram Mini App (`Telegram.WebApp`) cryptographic verification and button helpers.

Implements official HMAC-SHA256 validation per:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from typing import Optional
from urllib.parse import parse_qsl


DEFAULT_MAX_AGE_SECONDS = 86400  # 24 hours


def verify_telegram_webapp_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> tuple[Optional[dict], Optional[str]]:
    """
    Validate raw `Telegram.WebApp.initData` against `bot_token`.
    Returns `(user_dict, None)` on success, or `(None, error_message)` on failure.
    """
    raw = (init_data or '').strip()
    token = (bot_token or '').strip()
    if not raw:
        return None, 'Thiếu dữ liệu xác thực Telegram Mini App (initData).'
    if not token:
        return None, 'Hệ thống chưa cấu hình TELEGRAM_BOT_TOKEN.'

    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=False)
    except Exception:
        return None, 'Định dạng initData không hợp lệ.'

    if not pairs:
        return None, 'Dữ liệu initData rỗng.'

    received_hash = None
    filtered_pairs = []
    params_map = {}

    for k, v in pairs:
        if k == 'hash':
            received_hash = v
        else:
            filtered_pairs.append((k, v))
            params_map[k] = v

    if not received_hash or len(received_hash) != 64:
        return None, 'Thiếu chữ ký bảo mật từ Telegram.'

    # Replay / clock-skew protection
    auth_date_raw = params_map.get('auth_date', '')
    if not auth_date_raw.isdigit():
        return None, 'Thiếu mốc thời gian xác thực (auth_date).'
    auth_date = int(auth_date_raw)
    now = int(time.time())
    if auth_date > now + 300:
        return None, 'Mốc thời gian xác thực không hợp lệ.'
    if max_age_seconds > 0 and (now - auth_date) > max_age_seconds:
        return None, 'Phiên Mini App đã hết hạn. Vui lòng đóng và mở lại từ Telegram.'

    filtered_pairs.sort(key=lambda item: item[0])
    data_check_string = '\n'.join(f'{k}={v}' for k, v in filtered_pairs)

    secret_key = hmac.new(
        b'WebAppData',
        token.encode('utf-8'),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash.lower()):
        return None, 'Chữ ký xác thực Telegram Mini App không hợp lệ.'

    user_raw = params_map.get('user')
    if not user_raw:
        return None, 'Không tìm thấy thông tin người dùng Telegram trong initData.'

    try:
        user_obj = json.loads(user_raw)
    except (ValueError, TypeError):
        return None, 'Dữ liệu người dùng Telegram không hợp lệ.'

    if not isinstance(user_obj, dict) or not user_obj.get('id'):
        return None, 'Thiếu định danh người dùng Telegram.'
    if user_obj.get('is_bot'):
        return None, 'Tài khoản Bot không thể đăng nhập Mini App.'

    return {
        'user': user_obj,
        'auth_date': auth_date,
        'start_param': params_map.get('start_param') or '',
    }, None


def build_private_webapp_button(app) -> Optional[dict]:
    """
    Return a private-chat `InlineKeyboardButton` opening `/webapp` if `WEBSITE_URL` uses HTTPS.
    (Telegram Bot API requires HTTPS for Mini Apps and restricts `web_app` inline buttons to private chats.)
    """
    base_url = (app.config.get('WEBSITE_URL') or '').strip().rstrip('/')
    if not base_url.lower().startswith('https://'):
        return None
    return {
        'text': '📱 Mở Mini App',
        'web_app': {'url': f'{base_url}/webapp'},
    }
