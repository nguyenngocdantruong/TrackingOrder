import json
import threading
import time
import requests
from urllib.parse import urlencode

from app.notifications.telegram import TelegramNotifier
from app.notifications.telegram_group import (
    handle_callback_query,
    handle_group_message,
    handle_inline_query,
    register_bot_command_scopes,
    send_dm_management_menu,
)
from app.notifications.telegram_webapp import build_private_webapp_button
from app.providers.registry import registry
from app.repos.trackings_repo import TrackingsRepo
from app.repos.users_repo import UsersRepo
from app.tracking.services import TrackingService, sanitize_alias_and_note


_bot_thread = None
_stop_event = threading.Event()


DM_ADD = '➕ Thêm đơn'
DM_ORDERS = '📦 Đơn của tôi'
DM_STATS = '📊 Thống kê'
DM_HELP = '❔ Trợ giúp'
DM_CANCEL = 'Hủy nhập'
_DM_INPUT_TIMEOUT = 600


def _dm_keyboard(entering=False):
    rows = [[DM_CANCEL]] if entering else [[DM_ADD, DM_ORDERS], [DM_STATS, DM_HELP]]
    return {'keyboard': [[{'text': label} for label in row] for row in rows],
            'resize_keyboard': True, 'is_persistent': True}


def request_dm_input(app, chat_id, action, tracking_id=None):
    pending = app.extensions.setdefault('telegram_dm_input', {})
    now = time.monotonic()
    for key, (expires, _, _) in list(pending.items()):
        if expires <= now:
            pending.pop(key, None)
    pending[str(chat_id)] = (now + _DM_INPUT_TIMEOUT, action, tracking_id)
    prompt = ('Gửi mã vận đơn, có thể kèm tên gợi nhớ sau dấu cách.'
              if action == 'add' else 'Gửi tên gợi nhớ mới cho vận đơn.')
    TelegramNotifier.send_message(chat_id, prompt, parse_mode=None, reply_markup=_dm_keyboard(True))


def _finish_dm_input(app, chat_id, text, action, tracking_id):
    if action == 'add':
        _handle_add_command(app, chat_id, '/add ' + text, reply_markup=_dm_keyboard())
        return
    user = _get_chat_user(app, chat_id)
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not user.is_active or not tracking or tracking.get('userId') != user.id:
        reply = 'Vận đơn không còn tồn tại hoặc bạn không có quyền sửa.'
    else:
        alias, _ = sanitize_alias_and_note(text, None)
        if not alias:
            request_dm_input(app, chat_id, action, tracking_id)
            return
        TrackingsRepo.update(tracking_id, {'alias': alias})
        reply = f"Đã đổi tên đơn {tracking['trackingNumber']} thành {alias}."
    TelegramNotifier.send_message(chat_id, reply, parse_mode=None, reply_markup=_dm_keyboard())


def _normalize_command(text):
    first_token = text.strip().split()[0]
    command = first_token.split('@')[0].lower()
    return command


def _help_text():
    return (
        "🤖 Telegram Tracking Bot\n\n"
        "Các lệnh hỗ trợ:\n"
        "/add <mã vận đơn> [tên gợi nhớ] - thêm đơn hàng\n"
        "/edit <mã vận đơn> <tên mới> - đổi tên gợi nhớ\n"
        "/remove <mã vận đơn> - xóa đơn hàng\n"
        "/providers - hiển thị danh sách đơn vị vận chuyển\n"
        "/list - hiển thị danh sách đơn hàng\n"
        "/app - mở ứng dụng Mini App trực quan\n"
        "/stats - xem thống kê cá nhân\n"
        "/admin - xác nhận quyền quản trị\n"
        "/help - hướng dẫn sử dụng\n"
        "/author - tác giả"
    )


def _build_link_url(app, user, chat_id):
    base_url = (app.config.get('WEBSITE_URL') or 'http://127.0.0.1:5000').rstrip('/')
    query = urlencode({'chat_id': str(chat_id), 'token': user.link_token or ''})
    return f"{base_url}/link?{query}"


def _link_button_markup(app, user, chat_id):
    rows = []
    webapp_btn = build_private_webapp_button(app)
    if webapp_btn:
        rows.append([webapp_btn])
    if user.is_temporary:
        link_url = _build_link_url(app, user, chat_id)
        rows.append([{'text': '🔗 Liên kết tài khoản', 'url': link_url}])
    return {'inline_keyboard': rows} if rows else None


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


def _handle_add_command(app, chat_id, text, reply_markup=None):
    user = _get_chat_user(app, chat_id)
    markup = {"reply_markup": reply_markup} if reply_markup else {}

    parts = text.strip().split(maxsplit=2)
    if len(parts) < 2:
        TelegramNotifier.send_message(
            chat_id,
            "Cú pháp: /add <mã vận đơn> [tên gợi nhớ]",
            parse_mode=None,
            **markup,
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
        if result.get('duplicate'):
            TelegramNotifier.send_message(
                chat_id,
                f"ℹ️ {result.get('error', 'Mã vận đơn này đã có trong danh sách theo dõi của bạn.')}",
                parse_mode=None,
                **markup,
            )
            return
        TelegramNotifier.send_message(
            chat_id,
            result.get('error') or (
                "Không thể tự động nhận diện đơn vị vận chuyển cho mã này. "
                "Vui lòng kiểm tra lại mã vận đơn hoặc dùng /providers để xem danh sách hỗ trợ."
            ),
            parse_mode=None,
            **markup,
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
        **markup,
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


def _handle_message(app, message):
    chat = message.get('chat') or {}
    chat_type = chat.get('type')
    if chat_type in ('group', 'supergroup'):
        handle_group_message(app, message)
        return

    chat_id = chat.get('id')
    text = (message.get('text') or '').strip()

    if chat_type != 'private' or str((message.get('from') or {}).get('id')) != str(chat_id):
        return

    if not chat_id or not text:
        return

    with app.app_context():
        pending = app.extensions.setdefault('telegram_dm_input', {})
        key = str(chat_id)
        if text == DM_CANCEL or text.split()[0].lower() == '/cancel':
            pending.pop(key, None)
            TelegramNotifier.send_message(chat_id, 'Đã hủy thao tác.', parse_mode=None,
                                          reply_markup=_dm_keyboard())
            return
        entry = pending.pop(key, None)
        if text == DM_ADD:
            request_dm_input(app, chat_id, 'add')
            return
        if text == DM_ORDERS:
            send_dm_management_menu(app, key)
            if entry:
                TelegramNotifier.send_message(chat_id, 'Menu chính', parse_mode=None,
                                              reply_markup=_dm_keyboard())
            return
        if text in (DM_STATS, DM_HELP):
            text = '/stats' if text == DM_STATS else '/help'
        if not text.startswith('/'):
            if entry:
                expires, action, tracking_id = entry
                if expires > time.monotonic():
                    _finish_dm_input(app, chat_id, text, action, tracking_id)
                else:
                    TelegramNotifier.send_message(chat_id, 'Thao tác đã hết hạn. Hãy chọn lại từ menu.',
                                                  parse_mode=None, reply_markup=_dm_keyboard())
                return
            _get_chat_user(app, chat_id, remind_link=True)
            TelegramNotifier.send_message(
                chat_id,
                "Chọn một mục bên dưới hoặc dùng /help để xem danh sách lệnh.",
                parse_mode=None,
                reply_markup=_dm_keyboard(),
            )
            return

        if entry and text not in ('/start', '/help'):
            TelegramNotifier.send_message(chat_id, 'Menu chính', parse_mode=None, reply_markup=_dm_keyboard())

        if text.split()[0].lower() == '/admin':
            from app.admin import create_admin_link
            link = create_admin_link(app, chat_id)
            if link:
                TelegramNotifier.send_message(chat_id, 'Xác nhận quyền quản trị (hết hạn sau 10 phút): ' + link, parse_mode=None)
            return

        command = _normalize_command(text)
        user = _get_chat_user(app, chat_id)

        if command in ('/start', '/help', '/app'):
            parts = text.split(maxsplit=1)
            start_arg = parts[1].strip().lower() if (command == '/start' and len(parts) == 2) else ''
            if command == '/app' or start_arg == 'app':
                webapp_btn = build_private_webapp_button(app)
                if webapp_btn:
                    TelegramNotifier.send_message(
                        chat_id,
                        "📱 Nhấn nút bên dưới để mở bảng điều khiển Order Tracker ngay trong Telegram:",
                        parse_mode=None,
                        reply_markup={'inline_keyboard': [[webapp_btn]]},
                    )
                else:
                    base_url = (app.config.get('WEBSITE_URL') or '').rstrip('/')
                    TelegramNotifier.send_message(
                        chat_id,
                        f"🌐 Mở bảng điều khiển trên trình duyệt: {base_url}/dashboard",
                        parse_mode=None,
                    )
                return
            if start_arg == 'list':
                send_dm_management_menu(app, str(chat_id))
                _send_link_reminder_if_needed(app, user, chat_id)
                return
            if start_arg == 'admin':
                from app.admin import create_admin_link
                link = create_admin_link(app, chat_id)
                if link:
                    TelegramNotifier.send_message(chat_id, 'Xác nhận quyền quản trị (hết hạn sau 10 phút): ' + link, parse_mode=None)
                    return

            TelegramNotifier.send_message(
                chat_id,
                _help_text(),
                parse_mode=None,
                reply_markup=_dm_keyboard(),
            )
            if user.is_temporary:
                _send_link_reminder_if_needed(app, user, chat_id)
            elif markup := _link_button_markup(app, user, chat_id):
                TelegramNotifier.send_message(chat_id, 'Mở bảng điều khiển trong Telegram.',
                                              parse_mode=None, reply_markup=markup)
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


        if command == '/add':
            _handle_add_command(app, chat_id, text)
            return

        if command in ('/edit', '/rename'):
            parts = text.strip().split(maxsplit=2)
            if len(parts) < 3:
                TelegramNotifier.send_message(chat_id, "Cú pháp: /edit <mã vận đơn> <tên gợi nhớ mới>", parse_mode=None)
                return
            found = TrackingsRepo.find_by_user_and_number(user.id, parts[1].strip())
            if not found:
                TelegramNotifier.send_message(chat_id, f"Không tìm thấy đơn hàng với mã: {parts[1].strip()}", parse_mode=None)
                return
            new_alias = parts[2].strip()[:80]
            TrackingsRepo.update(found['id'], {'alias': new_alias})
            TelegramNotifier.send_message(chat_id, f"✅ Đã đổi tên đơn {found['trackingNumber']} thành: {new_alias}", parse_mode=None)
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
    try:
        register_bot_command_scopes(app)
    except Exception:
        pass

    while not _stop_event.is_set():
        try:
            response = requests.get(
                f"{base_url}/getUpdates",
                params={
                    'offset': offset,
                    'timeout': 25,
                    'allowed_updates': json.dumps(['message', 'callback_query', 'inline_query']),
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
                actor = next((update[k].get('from', {}).get('id')
                              for k in ('message', 'callback_query', 'inline_query') if update.get(k)), None)
                if actor:
                    with app.app_context():
                        account = UsersRepo.get_by_telegram_chat_id(actor)
                    if account and account.suspended:
                        continue
                if update.get('message'):
                    _handle_message(app, update['message'])
                elif update.get('callback_query'):
                    handle_callback_query(app, update['callback_query'])
                elif update.get('inline_query'):
                    handle_inline_query(app, update['inline_query'])
        except Exception as exc:
            app.logger.error(f"Telegram polling error: {exc}")
            time.sleep(3)


def start_telegram_chat_bot(app):
    if not app.config.get('TELEGRAM_ENABLED', True):
        return None
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
