import threading
import time
import requests
from urllib.parse import urlencode

from app.notifications.telegram import TelegramNotifier
from app.providers.registry import registry
from app.repos.trackings_repo import TrackingsRepo
from app.repos.users_repo import UsersRepo
from app.tracking.services import TrackingService


_bot_thread = None
_stop_event = threading.Event()


def _normalize_command(text):
    first_token = text.strip().split()[0]
    command = first_token.split('@')[0].lower()
    return command


def _help_text():
    return (
        "🤖 Telegram Tracking Bot\n\n"
        "Các lệnh hỗ trợ:\n"
        "/add <mã vận đơn> [tên gợi nhớ] - thêm đơn hàng\n"
        "/remove <mã vận đơn> - xóa đơn hàng\n"
        "/providers - hiển thị danh sách đơn vị vận chuyển\n"
        "/list - hiển thị danh sách đơn hàng\n"
        "/oil - nhận giá xăng dầu hôm nay\n"
        "/stats - xem thống kê cá nhân\n"
        "/help - hướng dẫn sử dụng\n"
        "/author - tác giả"
    )


def _build_link_url(app, user, chat_id):
    base_url = (app.config.get('WEBSITE_URL') or 'http://127.0.0.1:5000').rstrip('/')
    query = urlencode({'chat_id': str(chat_id), 'token': user.link_token or ''})
    return f"{base_url}/link?{query}"


def _link_button_markup(app, user, chat_id):
    if not user.is_temporary:
        return None

    link_url = _build_link_url(app, user, chat_id)
    return {
        'inline_keyboard': [[
            {
                'text': '🔗 Liên kết tài khoản',
                'url': link_url
            }
        ]]
    }


def _get_chat_user(app, chat_id, remind_link=False):
    user = UsersRepo.get_or_create_temp_by_telegram_chat_id(chat_id)

    if remind_link and user.is_temporary:
        TelegramNotifier.send_message(
            chat_id,
            "Bạn đang dùng tài khoản tạm qua Telegram. "
            "Dữ liệu vẫn được lưu bình thường. "
            "Hãy liên kết để đặt tài khoản/mật khẩu đăng nhập website.",
            parse_mode=None,
            reply_markup=_link_button_markup(app, user, chat_id),
        )

    return user


def _send_link_reminder_if_needed(app, user, chat_id):
    if not user.is_temporary:
        return

    TelegramNotifier.send_message(
        chat_id,
        "Bạn đang ở chế độ tài khoản tạm. Dữ liệu đã được lưu cho Telegram ID này.",
        parse_mode=None,
        reply_markup=_link_button_markup(app, user, chat_id),
    )


def _handle_add_command(app, chat_id, text):
    user = _get_chat_user(app, chat_id)

    parts = text.strip().split(maxsplit=2)
    if len(parts) < 2:
        TelegramNotifier.send_message(
            chat_id,
            "Cú pháp: /add <mã vận đơn> [tên gợi nhớ]",
            parse_mode=None,
        )
        return

    tracking_number = parts[1].strip()
    alias = parts[2].strip() if len(parts) >= 3 else None

    result = TrackingService.create_tracking_for_user(
        user=user,
        tracking_number=tracking_number,
        alias=alias,
        carrier_id='auto',
        send_notification=False,
    )

    if not result['success']:
        TelegramNotifier.send_message(
            chat_id,
            "Không thể tự động nhận diện đơn vị vận chuyển cho mã này. "
            "Vui lòng kiểm tra lại mã vận đơn hoặc dùng /providers để xem danh sách hỗ trợ.",
            parse_mode=None,
        )
        return

    tracking = TrackingsRepo.get_by_id(result['tracking_id'])
    status = tracking.get('currentStatus', 'Pending') if tracking else 'Pending'

    TelegramNotifier.send_message(
        chat_id,
        (
            f"Đã thêm đơn hàng thành công.\n"
            f"Mã: {tracking_number}\n"
            f"Tên gợi nhớ: {alias or 'Không có'}\n"
            f"Đơn vị vận chuyển: {result['carrier_id']}\n"
            f"Trạng thái hiện tại: {status}"
        ),
        parse_mode=None,
    )

    _send_link_reminder_if_needed(app, user, chat_id)


def _handle_remove_command(app, chat_id, text):
    user = _get_chat_user(app, chat_id)

    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        TelegramNotifier.send_message(
            chat_id,
            "Cú pháp: /remove <mã vận đơn>",
            parse_mode=None,
        )
        return

    tracking_number = parts[1].strip()
    
    # Find tracking for user
    trackings = TrackingsRepo.get_user_trackings(user.id)
    found_tracking = None
    for t in trackings:
        if t.get('trackingNumber') == tracking_number:
            found_tracking = t
            break
    
    if not found_tracking:
        TelegramNotifier.send_message(
            chat_id,
            f"Không tìm thấy đơn hàng với mã: {tracking_number}",
            parse_mode=None,
        )
        return

    try:
        TrackingsRepo.delete(found_tracking['id'])
        TelegramNotifier.send_message(
            chat_id,
            f"Đã xóa theo dõi đơn hàng: {tracking_number}",
            parse_mode=None,
        )
    except Exception as e:
        TelegramNotifier.send_message(
            chat_id,
            f"Lỗi khi xóa đơn hàng: {str(e)}",
            parse_mode=None,
        )

    _send_link_reminder_if_needed(app, user, chat_id)


def _handle_providers_command(app, chat_id, user=None):
    providers = registry.list_providers()
    if not providers:
        TelegramNotifier.send_message(chat_id, "Hiện chưa có đơn vị vận chuyển nào được cấu hình.", parse_mode=None)
        return

    lines = ["🚚 Danh sách đơn vị vận chuyển đang hỗ trợ:"]
    for provider_id, provider_name in providers:
        lines.append(f"- {provider_name} ({provider_id})")

    TelegramNotifier.send_message(chat_id, "\n".join(lines), parse_mode=None)

    if user:
        _send_link_reminder_if_needed(app, user, chat_id)


def _handle_list_command(app, chat_id):
    user = _get_chat_user(app, chat_id)

    trackings = TrackingsRepo.get_user_trackings(user.id)
    if not trackings:
        TelegramNotifier.send_message(chat_id, "Bạn chưa có đơn hàng nào đang theo dõi.", parse_mode=None)
        return

    lines = []
    for tracking in trackings:
        tracking_number = tracking.get('trackingNumber', 'N/A')
        status = tracking.get('currentStatus', 'Pending')
        lines.append(f"#{tracking_number} - {status}")

    TelegramNotifier.send_message(chat_id, "\n".join(lines), parse_mode=None)
    _send_link_reminder_if_needed(app, user, chat_id)


def _handle_stats_command(app, chat_id):
    """Xử lý lệnh /stats để hiển thị thống kê"""
    user = _get_chat_user(app, chat_id)
    
    # Lấy thống kê cá nhân
    total_trackings = TrackingsRepo.count_user_trackings(user.id)
    active_trackings = TrackingsRepo.count_user_active_trackings(user.id)
    join_date = UsersRepo.get_user_created_date(user.id)
    
    # Tin nhắn thống kê cá nhân
    personal_stats = (
        "📊 Thống kê cá nhân\n\n"
        f"👤 User: {user.username}\n"
        f"📅 Ngày tham gia: {join_date}\n"
        f"📦 Tổng số đơn hàng: {total_trackings}\n"
        f"🚚 Đang theo dõi: {active_trackings}\n"
        f"✅ Đã hoàn thành: {total_trackings - active_trackings}"
    )
    
    TelegramNotifier.send_message(chat_id, personal_stats, parse_mode=None)
    
    # Kiểm tra xem có phải admin không
    admin_id = app.config.get('ADMIN_TELEGRAM_USER_ID')
    chat_id_str = str(chat_id)
    
    if admin_id and chat_id_str == str(admin_id):
        # Lấy thống kê hệ thống nếu là admin
        total_users = UsersRepo.count_all_users()
        system_total_trackings = TrackingsRepo.count_all_trackings()
        system_active_trackings = TrackingsRepo.count_all_active_trackings()
        
        system_stats = (
            "🌐 Thống kê hệ thống (Admin)\n\n"
            f"👥 Tổng số người dùng: {total_users}\n"
            f"📦 Tổng số đơn hàng: {system_total_trackings}\n"
            f"🚚 Đang theo dõi: {system_active_trackings}\n"
            f"✅ Đã hoàn thành: {system_total_trackings - system_active_trackings}"
        )
        
        TelegramNotifier.send_message(chat_id, system_stats, parse_mode=None)
    
    _send_link_reminder_if_needed(app, user, chat_id)


def _handle_oil_command(app, chat_id, user=None):
    from app.notifications.oil_price_service import OilPriceService

    try:
        with app.app_context():
            data = OilPriceService.fetch_latest(app)

            if user and (user.settings or {}):
                settings = user.settings or {}
                suppliers = settings.get('oilSuppliers') or ['petrolimex', 'pvoil']
                product_map = settings.get('oilProducts') or {}
                data = OilPriceService._filter_data_for_user(data, suppliers, product_map)

            message = OilPriceService.build_message(data)
    except Exception as exc:
        TelegramNotifier.send_message(chat_id, f"Không lấy được giá xăng dầu: {exc}", parse_mode=None)
        return

    if not message:
        TelegramNotifier.send_message(chat_id, "Chưa có dữ liệu giá xăng dầu theo lựa chọn của bạn.", parse_mode=None)
        return

    TelegramNotifier.send_message(chat_id, message, parse_mode='Markdown')


def _handle_message(app, message):
    chat = message.get('chat') or {}
    chat_id = chat.get('id')
    text = (message.get('text') or '').strip()

    if not chat_id or not text:
        return

    with app.app_context():
        if not text.startswith('/'):
            user = _get_chat_user(app, chat_id, remind_link=True)
            TelegramNotifier.send_message(
                chat_id,
                "Mình đã nhận tin nhắn. Dùng /help để xem danh sách lệnh hỗ trợ.",
                parse_mode=None,
                reply_markup=_link_button_markup(app, user, chat_id),
            )
            return

        command = _normalize_command(text)
        user = _get_chat_user(app, chat_id)

        if command in ('/start', '/help'):
            TelegramNotifier.send_message(
                chat_id,
                _help_text(),
                parse_mode=None,
                reply_markup=_link_button_markup(app, user, chat_id),
            )
            return

        if command == '/author':
            TelegramNotifier.send_message(chat_id, "Tác giả: Nguyễn Ngọc Đan Trường", parse_mode=None)
            _send_link_reminder_if_needed(app, user, chat_id)
            return

        if command == '/providers':
            _handle_providers_command(app, chat_id, user)
            return

        if command == '/list':
            _handle_list_command(app, chat_id)
            return

        if command == '/stats':
            _handle_stats_command(app, chat_id)
            return

        if command == '/oil':
            _handle_oil_command(app, chat_id, user)
            return

        if command == '/add':
            _handle_add_command(app, chat_id, text)
            return

        if command == '/remove':
            _handle_remove_command(app, chat_id, text)
            return

        TelegramNotifier.send_message(
            chat_id,
            "Lệnh không hợp lệ. Dùng /help để xem danh sách lệnh.",
            parse_mode=None,
        )


def _poll_updates_loop(app):
    token = app.config.get('TELEGRAM_BOT_TOKEN')
    if not token:
        return

    base_url = f"https://api.telegram.org/bot{token}"
    offset = 0

    app.logger.info("Telegram chat bot polling started")

    while not _stop_event.is_set():
        try:
            response = requests.get(
                f"{base_url}/getUpdates",
                params={
                    'offset': offset,
                    'timeout': 25,
                    'allowed_updates': ['message']
                },
                timeout=30,
            )
            data = response.json()
            if not data.get('ok'):
                time.sleep(2)
                continue

            updates = data.get('result', [])
            for update in updates:
                offset = max(offset, update.get('update_id', 0) + 1)
                message = update.get('message')
                if message:
                    _handle_message(app, message)
        except Exception as exc:
            app.logger.error(f"Telegram polling error: {exc}")
            time.sleep(3)


def start_telegram_chat_bot(app):
    global _bot_thread

    if _bot_thread and _bot_thread.is_alive():
        return _bot_thread

    if not app.config.get('TELEGRAM_BOT_TOKEN'):
        app.logger.warning("TELEGRAM_BOT_TOKEN is empty. Telegram chat bot will not start.")
        return None

    _stop_event.clear()
    _bot_thread = threading.Thread(target=_poll_updates_loop, args=(app,), daemon=True)
    _bot_thread.start()
    return _bot_thread
