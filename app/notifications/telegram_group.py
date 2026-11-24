"""
Isolated Telegram Group, CallbackQuery, and Personal InlineQuery flow.

Keeps private 1-on-1 chat behavior untouched while enabling multi-user group usage
with strict per-user ownership checks (actor = message['from']['id']) and
privacy-preserving responses (Popup show_alert=True, is_personal Inline Query, and DM routing).
"""
import re
import time
from typing import Optional
import requests

from app.providers.registry import registry
from app.repos.trackings_repo import TrackingsRepo
from app.repos.users_repo import UsersRepo
from app.tracking.services import TrackingService

_bot_info_cache: dict = {'username': None, 'supports_inline': False, 'fetched_at': 0.0}
_DM_PAGE_SIZE = 5
_POPUP_MAX_LEN = 198


def tg_api_call(app, method: str, payload: dict, timeout: int = 12, quiet: bool = False) -> dict:
    """Invoke a Telegram Bot HTTP API method directly."""
    token = app.config.get('TELEGRAM_BOT_TOKEN')
    if not token:
        return {'ok': False, 'description': 'TELEGRAM_BOT_TOKEN not configured'}

    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        data = resp.json() if resp.text else {'ok': False, 'status_code': resp.status_code}
        if not data.get('ok') and not quiet:
            app.logger.warning("[TelegramGroup] API %s returned error: %s", method, data)
        return data
    except Exception as exc:
        app.logger.error("[TelegramGroup] API %s failed: %s", method, exc)
        return {'ok': False, 'description': str(exc)}


def get_bot_info(app) -> dict:
    """
    Fetch & cache real bot metadata from Telegram `getMe` (refreshed every 120s).
    Always prefers the real `getMe` username over .env typos like `order_skibidi_bot` vs `orderskibidi_bot`.
    """
    now = time.time()
    if _bot_info_cache['username'] and (now - _bot_info_cache['fetched_at'] < 120):
        return _bot_info_cache

    if not app.config.get('TESTING'):
        data = tg_api_call(app, 'getMe', {}, timeout=8, quiet=True)
        if data.get('ok') and isinstance(data.get('result'), dict):
            res = data['result']
            uname = (res.get('username') or '').strip().lstrip('@')
            if uname:
                _bot_info_cache['username'] = uname
                _bot_info_cache['supports_inline'] = bool(res.get('supports_inline_queries'))
                _bot_info_cache['fetched_at'] = now
                return _bot_info_cache

    fallback_uname = (app.config.get('TELEGRAM_BOT_USERNAME') or '').strip().lstrip('@')
    return {
        'username': fallback_uname,
        'supports_inline': bool(app.config.get('TESTING', False)),
        'fetched_at': now,
    }


def get_bot_username(app) -> str:
    """Resolve the bot's exact @username."""
    return get_bot_info(app).get('username') or ''


def build_bot_dm_url(app, start_param: str = '') -> Optional[str]:
    """Build https://t.me/<bot_username>?start=<param> deep link if username is available."""
    uname = get_bot_username(app)
    if not uname:
        return None
    if start_param:
        return f"https://t.me/{uname}?start={start_param}"
    return f"https://t.me/{uname}"


def register_bot_command_scopes(app) -> None:
    """Best-effort registration of command autocomplete menus & Mini App button."""
    private_commands = [
        {'command': 'add', 'description': 'Thêm mã vận đơn mới'},
        {'command': 'edit', 'description': 'Đổi tên gợi nhớ của đơn hàng'},
        {'command': 'list', 'description': 'Xem danh sách vận đơn'},
        {'command': 'app', 'description': 'Mở giao diện Mini App'},
        {'command': 'remove', 'description': 'Xóa theo dõi vận đơn'},
        {'command': 'stats', 'description': 'Thống kê đơn hàng cá nhân'},
        {'command': 'providers', 'description': 'Danh sách hãng vận chuyển'},
        {'command': 'help', 'description': 'Hướng dẫn sử dụng'},
    ]
    group_commands = [
        {'command': 'list', 'description': 'Tra cứu riêng vận đơn của bạn'},
        {'command': 'add', 'description': 'Thêm vận đơn vào tài khoản cá nhân'},
        {'command': 'edit', 'description': 'Đổi tên gợi nhớ đơn của bạn'},
        {'command': 'remove', 'description': 'Ngừng theo dõi vận đơn của bạn'},
        {'command': 'providers', 'description': 'Danh sách hãng vận chuyển hỗ trợ'},
        {'command': 'help', 'description': 'Hướng dẫn dùng Bot trong nhóm'},
    ]
    tg_api_call(app, 'setMyCommands', {
        'commands': private_commands,
        'scope': {'type': 'all_private_chats'},
    }, quiet=True)
    tg_api_call(app, 'setMyCommands', {
        'commands': group_commands,
        'scope': {'type': 'all_group_chats'},
    }, quiet=True)

    base_url = (app.config.get('WEBSITE_URL') or '').strip().rstrip('/')
    if base_url.lower().startswith('https://'):
        tg_api_call(app, 'setChatMenuButton', {
            'menu_button': {
                'type': 'web_app',
                'text': '📱 Đơn hàng',
                'web_app': {'url': f'{base_url}/webapp'},
            }
        }, quiet=True)


def mask_tracking_for_group(tracking_number: str) -> str:
    """Mask phone-number suffixes (e.g. J&T 841092837465-4829 -> 841092837465-**29) in group chat."""
    raw = (tracking_number or '').strip()
    m = re.match(r'^(.+?[\-\s:])(\d{2})(\d{2})$', raw)
    if m:
        return f"{m.group(1)}**{m.group(3)}"
    return raw


def _display_sender_name(from_user: dict) -> str:
    uname = (from_user.get('username') or '').strip()
    if uname:
        return f"@{uname}"
    first = (from_user.get('first_name') or '').strip()
    last = (from_user.get('last_name') or '').strip()
    full = f"{first} {last}".strip()
    return full or "bạn"


def extract_group_command(app, text: str) -> tuple[Optional[str], str]:
    """
    Parse (/command, normalized_text) in group chats:
    - `/list` or `/list@MyBot` -> ('/list', '/list ...')
    - `@MyBot /add SPX...` -> ('/add', '/add SPX...')
    - `@MyBot` -> ('/help', '/help')
    - `/list@OtherBot` -> (None, '')
    """
    stripped = (text or '').strip()
    if not stripped:
        return None, ''

    my_username = get_bot_username(app)
    tokens = stripped.split()

    # Handle leading @MyBot mention (e.g. "@orderskibidi_bot" or "@orderskibidi_bot /list")
    if my_username and tokens[0].lower() == f"@{my_username.lower()}":
        if len(tokens) == 1:
            return '/help', '/help'
        stripped = " ".join(tokens[1:]).strip()
        tokens = stripped.split()
        if not stripped.startswith('/'):
            return '/help', '/help'

    if not stripped.startswith('/'):
        return None, ''

    first_token = tokens[0]
    rest = stripped[len(first_token):].strip()
    if '@' in first_token:
        cmd_part, target_bot = first_token.split('@', 1)
        if my_username and target_bot.lower() != my_username.lower():
            return None, ''
        cmd = cmd_part.lower()
    else:
        cmd = first_token.lower()

    normalized_text = f"{cmd} {rest}".strip() if rest else cmd
    return cmd, normalized_text


def _send_group_reply(
    app,
    chat_id,
    text: str,
    reply_to_message_id: Optional[int] = None,
    message_thread_id: Optional[int] = None,
    reply_markup: Optional[dict] = None,
) -> dict:
    payload = {
        'chat_id': chat_id,
        'text': text,
    }
    if message_thread_id is not None:
        payload['message_thread_id'] = message_thread_id
    if reply_to_message_id is not None:
        payload['reply_parameters'] = {
            'message_id': reply_to_message_id,
            'allow_sending_without_reply': True,
        }
    if reply_markup:
        payload['reply_markup'] = reply_markup
    return tg_api_call(app, 'sendMessage', payload)


def _try_send_dm(app, actor_id: str, text: str, reply_markup: Optional[dict] = None) -> bool:
    payload = {
        'chat_id': str(actor_id),
        'text': text,
    }
    if reply_markup:
        payload['reply_markup'] = reply_markup
    res = tg_api_call(app, 'sendMessage', payload, quiet=True)
    return bool(res.get('ok'))


def _group_privacy_list_markup(app) -> dict:
    """
    Neutral 100%-private lookup panel for Group chat:
    - Zero order names or codes on button labels
    - Automatically includes `switch_inline_query_current_chat` when `@BotFather` inline mode is enabled!
    """
    info = get_bot_info(app)
    if info.get('supports_inline'):
        return {
            'inline_keyboard': [
                [
                    {'text': '👁 Xem nhanh (Popup)', 'callback_data': 'grp:popup'},
                    {'text': '🔎 Mở danh sách riêng', 'switch_inline_query_current_chat': ''},
                ],
                [
                    {'text': '📩 Gửi menu quản lý vào DM', 'callback_data': 'grp:dm_list'},
                ],
            ]
        }
    return {
        'inline_keyboard': [
            [
                {'text': '👁 Xem nhanh (Popup)', 'callback_data': 'grp:popup'},
                {'text': '📩 Gửi menu quản lý vào DM', 'callback_data': 'grp:dm_list'},
            ]
        ]
    }


def _build_dm_management_view(user, page: int = 0) -> tuple[str, Optional[dict]]:
    """Build an interactive personal parcel menu (sent inside private DM)."""
    trackings = TrackingsRepo.get_user_trackings(user.id)
    if not trackings:
        return ("📭 Bạn chưa có vận đơn nào đang theo dõi.\nChọn Thêm đơn trong menu hoặc dùng /add để bắt đầu.", None)

    total = len(trackings)
    total_pages = max(1, (total + _DM_PAGE_SIZE - 1) // _DM_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * _DM_PAGE_SIZE
    subset = trackings[start:start + _DM_PAGE_SIZE]

    lines = [f"📦 Danh sách vận đơn của bạn ({total} đơn · Trang {page + 1}/{total_pages}):\n"]
    rows = []
    for t in subset:
        tid = t.get('id')
        code = t.get('trackingNumber', 'N/A')
        alias = t.get('alias')
        status = t.get('currentStatus', 'Pending')
        icon = '🚚' if t.get('isActive', True) else '✅'
        title_label = f"{alias} ({code})" if alias else code
        lines.append(f"{icon} {title_label}\n   └ {status}")

        btn_title = (alias or code)[:22]
        if tid and len(f"dm:v:{tid}".encode('utf-8')) <= 64:
            rows.append([
                {'text': f"{icon} {btn_title}", 'callback_data': f"dm:v:{tid}"},
            ])

    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append({'text': '◀ Trước', 'callback_data': f"dm:p:{page - 1}"})
        nav_row.append({'text': f"{page + 1}/{total_pages}", 'callback_data': 'grp:noop'})
        if page < total_pages - 1:
            nav_row.append({'text': 'Tiếp ▶', 'callback_data': f"dm:p:{page + 1}"})
        rows.append(nav_row)

    return ("\n".join(lines), {'inline_keyboard': rows} if rows else None)


def _build_dm_tracking_detail(tracking):
    code = tracking.get('trackingNumber') or 'Vận đơn'
    lines = [str(tracking.get('alias') or code)[:100], f"Mã: {code}",
             f"Trạng thái: {tracking.get('currentStatus') or 'Đang chờ'}"]
    events = tracking.get('events') or []
    if events:
        lines.append('Cập nhật gần đây')
        for event in events[:4]:
            description = event.get('descBuyer') or event.get('name') or event.get('code')
            if description:
                lines.append(f"• {str(description)[:200]}")
    return "\n".join(lines)


def send_dm_management_menu(app, actor_id: str) -> bool:
    """Send the interactive personal tracking menu to the user's private DM."""
    user = UsersRepo.get_or_create_temp_by_telegram_chat_id(actor_id)
    text, markup = _build_dm_management_view(user, page=0)
    return _try_send_dm(app, actor_id, text, reply_markup=markup)


def build_popup_summary_for_user(actor_id: str) -> str:
    """
    Build a <= 200-char private alert text for answerCallbackQuery(show_alert=True).
    """
    user = UsersRepo.get_by_telegram_chat_id(actor_id)
    if not user:
        return "📭 Bạn chưa có vận đơn nào.\nGõ /add <mã vận đơn> [tên gợi nhớ] để bắt đầu theo dõi!"

    trackings = TrackingsRepo.get_user_trackings(user.id)
    if not trackings:
        return "📭 Bạn chưa có vận đơn nào đang theo dõi.\nGõ /add <mã vận đơn> [tên gợi nhớ] để thêm mới!"

    header = f"📦 Đơn của bạn ({len(trackings)}):\n"
    acc = header
    shown = 0
    total = len(trackings)

    for idx, t in enumerate(trackings):
        remaining_after = total - (idx + 1)
        reserve = 38 if remaining_after > 0 else 0
        label = (t.get('alias') or t.get('trackingNumber') or 'Đơn')[:18].strip()
        status = (t.get('currentStatus') or 'Đang chờ')[:24].strip()
        icon = '🚚' if t.get('isActive', True) else '✅'
        line = f"{icon} {label}: {status}\n"

        if len(acc) + len(line) + reserve <= _POPUP_MAX_LEN:
            acc += line
            shown += 1
        else:
            break

    leftover = total - shown
    if leftover > 0:
        tail = f"… +{leftover} đơn khác (mở Danh sách riêng/DM)"
        acc = (acc.rstrip() + "\n" + tail)[:_POPUP_MAX_LEN]

    return acc.strip()[:_POPUP_MAX_LEN]


def _group_help_text() -> str:
    return (
        "🤖 Order Tracker Bot (Chế độ Nhóm)\n\n"
        "Mọi vận đơn đều được phân quyền riêng theo tài khoản cá nhân của người gõ lệnh:\n"
        "• /list — Mở bảng tra cứu kín (Popup riêng / Khay cá nhân / Gửi vào DM)\n"
        "• /add <mã đơn> [tên gợi nhớ] — Thêm đơn vào tài khoản của bạn (bắn thông báo về DM)\n"
        "• /remove <mã đơn> — Xóa đơn hàng của chính bạn\n"
        "• /stats — Gửi thống kê cá nhân qua DM\n"
        "• /providers — Danh sách hãng vận chuyển hỗ trợ"
    )


def handle_group_message(app, message: dict) -> None:
    """Handle incoming commands inside 'group' and 'supergroup' chats."""
    chat = message.get('chat') or {}
    chat_id = chat.get('id')
    msg_id = message.get('message_id')
    thread_id = message.get('message_thread_id')
    text = (message.get('text') or '').strip()

    if not chat_id or not text:
        return

    command, text = extract_group_command(app, text)
    if not command:
        return

    from_user = message.get('from') or {}
    # Reject anonymous group/channel sender identities so ownership stays strictly personal
    if message.get('sender_chat') or from_user.get('is_bot') or not from_user.get('id'):
        _send_group_reply(
            app,
            chat_id,
            "⚠️ Vui lòng tắt chế độ ẩn danh (Remain Anonymous) hoặc nhắn bằng tài khoản cá nhân để xác định quyền sở hữu đơn hàng.",
            reply_to_message_id=msg_id,
            message_thread_id=thread_id,
        )
        return

    actor_id = str(from_user['id'])
    sender_tag = _display_sender_name(from_user)

    with app.app_context():
        if command in ('/start', '/help'):
            dm_url = build_bot_dm_url(app, 'help')
            markup = {'inline_keyboard': [[{'text': '💬 Mở chat riêng với Bot', 'url': dm_url}]]} if dm_url else None
            _send_group_reply(
                app,
                chat_id,
                _group_help_text(),
                reply_to_message_id=msg_id,
                message_thread_id=thread_id,
                reply_markup=markup,
            )
            return

        if command == '/author':
            _send_group_reply(
                app,
                chat_id,
                "Tác giả: Nguyễn Ngọc Đan Trường",
                reply_to_message_id=msg_id,
                message_thread_id=thread_id,
            )
            return

        if command == '/providers':
            providers = registry.list_providers()
            if not providers:
                _send_group_reply(app, chat_id, "Hiện chưa có đơn vị vận chuyển nào được cấu hình.", msg_id, thread_id)
                return
            lines = ["🚚 Các đơn vị vận chuyển đang hỗ trợ:"]
            for pid, pname in providers:
                lines.append(f"• {pname} ({pid})")
            _send_group_reply(app, chat_id, "\n".join(lines), msg_id, thread_id)
            return

        if command == '/admin':
            from app.admin import create_admin_link
            # Strictly check actor_id (NEVER group chat_id!) and NEVER post admin token in group!
            link = create_admin_link(app, actor_id)
            if not link:
                _send_group_reply(
                    app,
                    chat_id,
                    "⛔ Tài khoản Telegram của bạn không có quyền quản trị hệ thống.",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
                return

            if _try_send_dm(app, actor_id, f"🔐 Xác nhận quyền quản trị (hết hạn sau 10 phút):\n{link}"):
                _send_group_reply(
                    app,
                    chat_id,
                    f"🔐 {sender_tag} Đã gửi liên kết xác thực quản trị vào tin nhắn riêng (DM) của bạn.",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
            else:
                dm_url = build_bot_dm_url(app, 'admin')
                markup = {'inline_keyboard': [[{'text': '💬 Mở DM nhận link Admin', 'url': dm_url}]]} if dm_url else None
                _send_group_reply(
                    app,
                    chat_id,
                    f"⚠️ {sender_tag} Vui lòng mở chat riêng với Bot để nhận liên kết xác thực an toàn (không gửi link bảo mật ra nhóm).",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                    reply_markup=markup,
                )
            return

        if command == '/list':
            _send_group_reply(
                app,
                chat_id,
                (
                    "📦 Tra cứu vận đơn cá nhân\n"
                    "Chọn cách xem bên dưới (chỉ hiển thị dữ liệu riêng của tài khoản bạn):"
                ),
                reply_to_message_id=msg_id,
                message_thread_id=thread_id,
                reply_markup=_group_privacy_list_markup(app),
            )
            return

        if command == '/add':
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                _send_group_reply(
                    app,
                    chat_id,
                    "Cú pháp: /add <mã vận đơn> [tên gợi nhớ]",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
                return

            tracking_number = parts[1].strip()
            alias = parts[2].strip() if len(parts) >= 3 else None
            user = UsersRepo.get_or_create_temp_by_telegram_chat_id(actor_id)

            result = TrackingService.create_tracking_for_user(
                user=user,
                tracking_number=tracking_number,
                alias=alias,
                carrier_id='auto',
                send_notification=False,
            )

            if not result.get('success'):
                if result.get('duplicate'):
                    _send_group_reply(
                        app,
                        chat_id,
                        f"ℹ️ {sender_tag} Mã vận đơn {mask_tracking_for_group(tracking_number)} đã có sẵn trong danh sách theo dõi của bạn.",
                        reply_to_message_id=msg_id,
                        message_thread_id=thread_id,
                    )
                    return
                _send_group_reply(
                    app,
                    chat_id,
                    f"❌ {sender_tag} {result.get('error') or 'Không thể nhận diện hoặc tra cứu mã vận đơn này. Dùng /providers để xem định dạng hỗ trợ.'}",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
                return

            tracking = TrackingsRepo.get_by_id(result['tracking_id'])
            status = tracking.get('currentStatus', 'Pending') if tracking else 'Pending'
            masked_code = mask_tracking_for_group(tracking_number)

            # Send full details (and private web-link button if temporary account) exclusively to DM
            from app.notifications.telegram_bot import _link_button_markup
            dm_sent = _try_send_dm(
                app,
                actor_id,
                (
                    f"✅ Đã thêm vận đơn thành công!\n"
                    f"Mã: {tracking_number}\n"
                    f"Tên gợi nhớ: {alias or 'Không có'}\n"
                    f"Đơn vị vận chuyển: {result['carrier_id']}\n"
                    f"Trạng thái hiện tại: {status}\n\n"
                    f"🔔 Mọi cập nhật mới của đơn này sẽ được gửi trực tiếp vào đây."
                ),
                reply_markup=_link_button_markup(app, user, actor_id),
            )

            if dm_sent:
                _send_group_reply(
                    app,
                    chat_id,
                    f"✅ {sender_tag} Đã thêm đơn {masked_code} vào tài khoản của bạn. Chi tiết và thông báo tự động đã được chuyển về tin nhắn riêng (DM).",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
            else:
                dm_url = build_bot_dm_url(app, 'list')
                markup = {'inline_keyboard': [[{'text': '🔔 Bấm Start ở DM để nhận thông báo', 'url': dm_url}]]} if dm_url else None
                _send_group_reply(
                    app,
                    chat_id,
                    (
                        f"✅ {sender_tag} Đã lưu đơn {masked_code} vào tài khoản của bạn.\n"
                        f"⚠️ Bạn chưa mở chat riêng với Bot nên Bot chưa thể bắn thông báo về DM — hãy bấm nút bên dưới và nhấn Start 1 lần nhé!"
                    ),
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                    reply_markup=markup,
                )
            return

        if command in ('/edit', '/rename'):
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                _send_group_reply(
                    app,
                    chat_id,
                    "Cú pháp: /edit <mã vận đơn> <tên gợi nhớ mới>",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
                return
            user = UsersRepo.get_by_telegram_chat_id(actor_id)
            found = TrackingsRepo.find_by_user_and_number(user.id, parts[1].strip()) if user else None
            if not found:
                _send_group_reply(
                    app,
                    chat_id,
                    f"⛔ {sender_tag} Không tìm thấy đơn hàng này trong danh sách cá nhân của bạn.",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
                return
            new_alias = parts[2].strip()[:80]
            TrackingsRepo.update(found['id'], {'alias': new_alias})
            _send_group_reply(
                app,
                chat_id,
                f"✏️ {sender_tag} Đã cập nhật tên gợi nhớ cho đơn {mask_tracking_for_group(found['trackingNumber'])}.",
                reply_to_message_id=msg_id,
                message_thread_id=thread_id,
            )
            return

        if command == '/app':
            dm_url = build_bot_dm_url(app, 'app')
            markup = {'inline_keyboard': [[{'text': '📱 Mở Mini App qua Chat riêng', 'url': dm_url}]]} if dm_url else None
            _send_group_reply(
                app,
                chat_id,
                f"📱 {sender_tag} Nhấn nút bên dưới để mở ứng dụng Mini App riêng tư trong Telegram:",
                reply_to_message_id=msg_id,
                message_thread_id=thread_id,
                reply_markup=markup,
            )
            return

        if command == '/remove':
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                _send_group_reply(
                    app,
                    chat_id,
                    "Cú pháp: /remove <mã vận đơn>",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
                return

            tracking_number = parts[1].strip()
            user = UsersRepo.get_by_telegram_chat_id(actor_id)
            trackings = TrackingsRepo.get_user_trackings(user.id) if user else []
            found = next((t for t in trackings if t.get('trackingNumber') == tracking_number), None)

            if not found:
                _send_group_reply(
                    app,
                    chat_id,
                    f"⛔ {sender_tag} Không tìm thấy đơn hàng này trong danh sách cá nhân của bạn.",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
                return

            TrackingsRepo.delete(found['id'])
            masked_code = mask_tracking_for_group(tracking_number)
            _send_group_reply(
                app,
                chat_id,
                f"🗑 {sender_tag} Đã xóa theo dõi đơn hàng {masked_code} khỏi danh sách của bạn.",
                reply_to_message_id=msg_id,
                message_thread_id=thread_id,
            )
            return

        if command == '/stats':
            user = UsersRepo.get_or_create_temp_by_telegram_chat_id(actor_id)
            total_trackings = TrackingsRepo.count_user_trackings(user.id)
            active_trackings = TrackingsRepo.count_user_active_trackings(user.id)
            join_date = UsersRepo.get_user_created_date(user.id)
            stats_msg = (
                "📊 Thống kê cá nhân\n\n"
                f"👤 User: {user.username}\n"
                f"📅 Ngày tham gia: {join_date}\n"
                f"📦 Tổng số đơn hàng: {total_trackings}\n"
                f"🚚 Đang theo dõi: {active_trackings}\n"
                f"✅ Đã hoàn thành: {total_trackings - active_trackings}"
            )
            if _try_send_dm(app, actor_id, stats_msg):
                _send_group_reply(
                    app,
                    chat_id,
                    f"📊 {sender_tag} Đã gửi thống kê cá nhân vào tin nhắn riêng (DM) của bạn.",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
            else:
                _send_group_reply(
                    app,
                    chat_id,
                    f"📊 Thống kê của {sender_tag}: Tổng {total_trackings} đơn (Đang theo dõi: {active_trackings}, Hoàn thành: {total_trackings - active_trackings}).",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
            return

        if command == '/link':
            user = UsersRepo.get_or_create_temp_by_telegram_chat_id(actor_id)
            if not user.is_temporary:
                _send_group_reply(
                    app,
                    chat_id,
                    f"✅ {sender_tag} Tài khoản Telegram của bạn đã được liên kết với tài khoản web ({user.username}).",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
                return

            from app.notifications.telegram_bot import _link_button_markup
            if _try_send_dm(
                app,
                actor_id,
                "🔗 Bấm nút bên dưới để đặt tên đăng nhập & mật khẩu liên kết lên Web (không chia sẻ liên kết này cho người khác):",
                reply_markup=_link_button_markup(app, user, actor_id),
            ):
                _send_group_reply(
                    app,
                    chat_id,
                    f"🔗 {sender_tag} Đã gửi liên kết bảo mật vào tin nhắn riêng (DM) của bạn.",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                )
            else:
                dm_url = build_bot_dm_url(app, 'link')
                markup = {'inline_keyboard': [[{'text': '🔗 Mở DM để liên kết tài khoản', 'url': dm_url}]]} if dm_url else None
                _send_group_reply(
                    app,
                    chat_id,
                    f"⚠️ {sender_tag} Bấm nút bên dưới để mở chat riêng với Bot và nhận liên kết tài khoản an toàn.",
                    reply_to_message_id=msg_id,
                    message_thread_id=thread_id,
                    reply_markup=markup,
                )
            return


def _verify_tracking_ownership(actor_id: str, tracking_id: str) -> tuple[Optional[dict], Optional[object]]:
    """Return (tracking, owner_user) ONLY if actor_id owns tracking_id; otherwise (None, None)."""
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking:
        return None, None
    owner = UsersRepo.get_by_id(tracking.get('userId'))
    if not owner:
        return None, None
    owner_tg = str((owner.settings or {}).get('telegramChatId') or '')
    if owner_tg != str(actor_id):
        return None, None
    return tracking, owner


def handle_callback_query(app, callback_query: dict) -> None:
    """Handle button clicks from both Group lookup cards and DM management menus."""
    cb_id = callback_query.get('id')
    from_user = callback_query.get('from') or {}
    actor_id = str(from_user.get('id') or '')
    data = (callback_query.get('data') or '').strip()

    if not cb_id or not actor_id:
        return

    with app.app_context():
        if data == 'grp:noop':
            tg_api_call(app, 'answerCallbackQuery', {'callback_query_id': cb_id})
            return

        if data == 'grp:popup':
            popup_text = build_popup_summary_for_user(actor_id)
            tg_api_call(app, 'answerCallbackQuery', {
                'callback_query_id': cb_id,
                'text': popup_text,
                'show_alert': True,
            })
            return

        if data == 'grp:dm_list':
            if send_dm_management_menu(app, actor_id):
                tg_api_call(app, 'answerCallbackQuery', {
                    'callback_query_id': cb_id,
                    'text': '📩 Đã gửi danh sách quản lý chi tiết vào tin nhắn riêng (DM) của bạn!',
                    'show_alert': False,
                })
            else:
                dm_url = build_bot_dm_url(app, 'list')
                if dm_url:
                    tg_api_call(app, 'answerCallbackQuery', {
                        'callback_query_id': cb_id,
                        'url': dm_url,
                    })
                else:
                    tg_api_call(app, 'answerCallbackQuery', {
                        'callback_query_id': cb_id,
                        'text': '⚠️ Hãy mở chat riêng với Bot và bấm /start trước để Bot có thể gửi tin nhắn cho bạn!',
                        'show_alert': True,
                    })
            return

        if data.startswith('dm:p:'):
            try:
                page = int(data.split(':', 2)[2])
            except ValueError:
                page = 0
            msg = callback_query.get('message') or {}
            msg_chat = msg.get('chat') or {}
            if msg_chat.get('type') != 'private' or str(msg_chat.get('id')) != actor_id:
                tg_api_call(app, 'answerCallbackQuery', {
                    'callback_query_id': cb_id,
                    'text': '⛔ Bạn chỉ được thao tác trên danh sách của chính mình!',
                    'show_alert': True,
                })
                return

            user = UsersRepo.get_or_create_temp_by_telegram_chat_id(actor_id)
            new_text, new_markup = _build_dm_management_view(user, page=page)
            tg_api_call(app, 'editMessageText', {
                'chat_id': msg_chat['id'],
                'message_id': msg.get('message_id'),
                'text': new_text,
                'reply_markup': new_markup or {'inline_keyboard': []},
            })
            tg_api_call(app, 'answerCallbackQuery', {'callback_query_id': cb_id})
            return

        if data.startswith(('dm:v:', 'dm:r:', 'dm:n:', 'dm:d:', 'dm:x:')):
            action = data[3]
            tracking_id = data[5:]
            tracking, owner = _verify_tracking_ownership(actor_id, tracking_id)
            msg = callback_query.get('message') or {}
            chat = msg.get('chat') or {}
            if (not tracking or not owner or getattr(owner, 'suspended', False)
                    or chat.get('type') != 'private' or str(chat.get('id')) != actor_id
                    or not msg.get('message_id')):
                tg_api_call(app, 'answerCallbackQuery', {
                    'callback_query_id': cb_id,
                    'text': 'Vận đơn không tồn tại hoặc bạn không có quyền thao tác.',
                    'show_alert': True,
                })
                return

            tg_api_call(app, 'answerCallbackQuery', {'callback_query_id': cb_id})
            if action == 'n':
                from app.notifications.telegram_bot import request_dm_input
                request_dm_input(app, actor_id, 'rename', tracking_id)
                return

            code = tracking.get('trackingNumber') or 'Vận đơn'
            if action == 'd':
                text = f'Xóa theo dõi vận đơn {code}?'
                markup = {'inline_keyboard': [[
                    {'text': 'Xác nhận xóa', 'callback_data': f'dm:x:{tracking_id}'},
                    {'text': 'Giữ vận đơn', 'callback_data': f'dm:v:{tracking_id}'},
                ]]}
            elif action == 'x':
                TrackingsRepo.delete(tracking_id)
                text, markup = _build_dm_management_view(owner)
                text = f'Đã xóa theo dõi vận đơn {code}.\n\n{text}'
            else:
                result = ''
                if action == 'r':
                    try:
                        if TrackingService.refresh_tracking(tracking_id):
                            tracking = TrackingsRepo.get_by_id(tracking_id) or tracking
                            result = 'Đã đồng bộ.\n\n'
                        else:
                            result = 'Hiện không thể đồng bộ vận đơn.\n\n'
                    except Exception:
                        result = 'Đồng bộ thất bại. Hãy thử lại sau.\n\n'
                text = result + _build_dm_tracking_detail(tracking)
                markup = {'inline_keyboard': [
                    [{'text': 'Đồng bộ', 'callback_data': f'dm:r:{tracking_id}'},
                     {'text': 'Đổi tên', 'callback_data': f'dm:n:{tracking_id}'}],
                    [{'text': 'Xóa', 'callback_data': f'dm:d:{tracking_id}'},
                     {'text': 'Danh sách', 'callback_data': 'dm:p:0'}],
                ]}

            tg_api_call(app, 'editMessageText', {
                'chat_id': chat['id'], 'message_id': msg['message_id'], 'text': text,
                'reply_markup': markup or {'inline_keyboard': []},
            })
            return

        tg_api_call(app, 'answerCallbackQuery', {'callback_query_id': cb_id})


def handle_inline_query(app, inline_query: dict) -> None:
    """
    Personal Inline Query handler (`is_personal=True`).
    Displays a private floating drawer of ONLY the caller's parcels right above their chat input.
    """
    iq_id = inline_query.get('id')
    from_user = inline_query.get('from') or {}
    actor_id = str(from_user.get('id') or '')
    query_text = (inline_query.get('query') or '').strip().lower()

    if not iq_id or not actor_id:
        return

    with app.app_context():
        user = UsersRepo.get_by_telegram_chat_id(actor_id)
        trackings = TrackingsRepo.get_user_trackings(user.id) if user else []

        if query_text:
            trackings = [
                t for t in trackings
                if query_text in (t.get('alias') or '').lower()
                or query_text in (t.get('trackingNumber') or '').lower()
                or query_text in (t.get('currentStatus') or '').lower()
            ]

        results = []
        for idx, t in enumerate(trackings[:50]):
            tid = str(t.get('id') or idx)
            code = t.get('trackingNumber', 'N/A')
            masked = mask_tracking_for_group(code)
            alias = t.get('alias')
            status = t.get('currentStatus', 'Pending')
            carrier = (t.get('carrierId') or '').upper()
            is_active = t.get('isActive', True)
            icon = '🚚' if is_active else '✅'

            title = f"{icon} {alias} ({masked})" if alias else f"{icon} {masked}"
            desc = f"{carrier} · {status}"
            share_body = (
                f"📦 Vận đơn: {alias or masked}\n"
                f"Mã: {masked} ({carrier})\n"
                f"Trạng thái: {status}"
            )

            results.append({
                'type': 'article',
                'id': tid[:64],
                'title': title,
                'description': desc,
                'input_message_content': {
                    'message_text': share_body,
                },
            })

        payload = {
            'inline_query_id': iq_id,
            'results': results,
            'cache_time': 2,
            'is_personal': True,
        }
        if not results:
            payload['button'] = {
                'text': '➕ Mở Bot để thêm vận đơn mới',
                'start_parameter': 'add_guide',
            }

        tg_api_call(app, 'answerInlineQuery', payload)
