import asyncio
import threading
from urllib.parse import urlencode
import logging
import requests

from zalo_bot import Update
from zalo_bot.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.providers.registry import registry
from app.repos.trackings_repo import TrackingsRepo
from app.repos.users_repo import UsersRepo
from app.tracking.services import TrackingService


_bot_thread = None
_stop_event = threading.Event()
_application = None
_flask_app = None


def _build_link_url(app, zalo_id, link_token):
    base_url = (app.config.get('WEBSITE_URL') or 'http://127.0.0.1:5000').rstrip('/')
    query = urlencode({'zalo_id': str(zalo_id), 'token': link_token or ''})
    return f"{base_url}/link/zalo?{query}"


def _help_text():
    return (
        "🤖 Zalo Tracking Bot\n\n"
        "Các lệnh hỗ trợ:\n"
        "/start - hướng dẫn và liên kết tài khoản\n"
        "/add <mã vận đơn> [tên gợi nhớ]\n"
        "/remove <mã vận đơn>\n"
        "/providers - danh sách đơn vị vận chuyển\n"
        "/list - danh sách đơn hàng\n"
        "/stats - thống kê cá nhân\n"
        "/help - hướng dẫn sử dụng\n"
        "/author - tác giả"
    )


def _extract_chat_id(update: Update):
    """Extract chat/user id from update with multiple fallbacks."""
    # Preferred: effective_chat
    chat = getattr(update, 'effective_chat', None)
    if chat and getattr(chat, 'id', None) is not None:
        return str(chat.id)

    # Message-based fallbacks
    message = getattr(update, 'message', None)
    if message:
        chat_obj = getattr(message, 'chat', None)
        if chat_obj and getattr(chat_obj, 'id', None) is not None:
            return str(chat_obj.id)

        sender = getattr(message, 'sender', None) or getattr(message, 'from_user', None)
        if sender and getattr(sender, 'id', None) is not None:
            return str(sender.id)

    # Dictionary fallback
    if hasattr(update, 'to_dict'):
        try:
            data = update.to_dict()
            msg = data.get('message') or {}
            chat_id = (msg.get('chat') or {}).get('id') or msg.get('sender_id') or msg.get('user_id')
            if chat_id:
                return str(chat_id)
        except Exception:
            pass
    return None


async def _send_link_reminder_if_needed(flask_app, update: Update, user):
    if not user or not user.is_temporary:
        return

    link_url = _build_link_url(flask_app, _extract_chat_id(update), user.link_token)
    if update.message:
        await update.message.reply_text(
            "Bạn đang dùng tài khoản tạm. Nhấn liên kết để gắn tài khoản website:\n"
            f"{link_url}"
        )


async def _send_simple_reply(update: Update, text: str):
    if update.message:
        await update.message.reply_text(text)


async def _log_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    flask_app = _flask_app
    if not flask_app:
        return
    try:
        flask_app.logger.info("[Zalo Bot] Update received: %s", repr(update.to_dict() if hasattr(update, 'to_dict') else update))
    except Exception:
        flask_app.logger.info("[Zalo Bot] Update received (repr failed)")


async def _handle_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Chào {update.effective_user.display_name}! Tôi là chatbot!")

async def _handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Handling /start command")
    flask_app = _flask_app
    zalo_id = _extract_chat_id(update)
    print(f"Extracted zalo_id: {zalo_id}")
    print(f"Flask app context: {flask_app}")
    if not flask_app or not zalo_id:
        return

    with flask_app.app_context():
        user = UsersRepo.get_or_create_temp_by_zalo_account_id(zalo_id)
        zalo_settings = user.settings.get('zalo') or {}

        # Nếu đã liên kết rồi thì trả lời ngắn gọn, không gửi lại link
        if not user.is_temporary and (user.settings.get('zaloAccountId') or zalo_settings.get('chatId')):
            await _send_simple_reply(update, (
                "🤖 Zalo Tracking Bot\n"
                "Tài khoản Zalo này đã được liên kết.\n"
                "Dùng /help để xem danh sách lệnh, /list để xem đơn hàng."
            ))
            return

        link_url = _build_link_url(flask_app, zalo_id, user.link_token)

    await _send_simple_reply(update, (
        "🤖 Zalo Tracking Bot\n"
        "Nhấn liên kết bên dưới để gắn Zalo vào tài khoản.\n"
        "Bạn có thể đăng nhập tài khoản sẵn có hoặc tạo tài khoản mới.\n"
        f"{link_url}"
    ))


async def _handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_simple_reply(update, _help_text())


async def _handle_author(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_simple_reply(update, "Tác giả: Nguyễn Ngọc Đan Trường")


async def _handle_providers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    flask_app = _flask_app
    if not flask_app:
        return

    with flask_app.app_context():
        providers = registry.list_providers()
    if not providers:
        await _send_simple_reply(update, "Hiện chưa có đơn vị vận chuyển nào được cấu hình.")
        return

    lines = ["🚚 Danh sách đơn vị vận chuyển đang hỗ trợ:"]
    for provider_id, provider_name in providers:
        lines.append(f"- {provider_name} ({provider_id})")
    await _send_simple_reply(update, "\n".join(lines))


async def _handle_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    flask_app = _flask_app
    zalo_id = _extract_chat_id(update)
    if not flask_app or not zalo_id:
        return

    with flask_app.app_context():
        user = UsersRepo.get_or_create_temp_by_zalo_account_id(zalo_id)
        trackings = TrackingsRepo.get_user_trackings(user.id)

    if not trackings:
        await _send_simple_reply(update, "Bạn chưa có đơn hàng nào đang theo dõi.")
        return

    lines = []
    for tracking in trackings:
        tracking_number = tracking.get('trackingNumber', 'N/A')
        status = tracking.get('currentStatus', 'Pending')
        lines.append(f"#{tracking_number} - {status}")

    await _send_simple_reply(update, "\n".join(lines))
    await _send_link_reminder_if_needed(flask_app, update, user)


async def _handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    flask_app = _flask_app
    zalo_id = _extract_chat_id(update)
    if not flask_app or not zalo_id:
        return

    with flask_app.app_context():
        user = UsersRepo.get_or_create_temp_by_zalo_account_id(zalo_id)
        total_trackings = TrackingsRepo.count_user_trackings(user.id)
        active_trackings = TrackingsRepo.count_user_active_trackings(user.id)
        join_date = UsersRepo.get_user_created_date(user.id)

        admin_id = flask_app.config.get('ADMIN_ZALO_USER_ID')
        is_admin = admin_id and str(admin_id) == str(zalo_id)
        if is_admin:
            total_users = UsersRepo.count_all_users()
            system_total_trackings = TrackingsRepo.count_all_trackings()
            system_active_trackings = TrackingsRepo.count_all_active_trackings()

    personal_stats = (
        "📊 Thống kê cá nhân\n\n"
        f"👤 User: {user.username}\n"
        f"📅 Ngày tham gia: {join_date}\n"
        f"📦 Tổng số đơn hàng: {total_trackings}\n"
        f"🚚 Đang theo dõi: {active_trackings}\n"
        f"✅ Đã hoàn thành: {total_trackings - active_trackings}"
    )
    await _send_simple_reply(update, personal_stats)

    if admin_id and str(admin_id) == str(zalo_id):
        system_stats = (
            "🌐 Thống kê hệ thống (Admin)\n\n"
            f"👥 Tổng số người dùng: {total_users}\n"
            f"📦 Tổng số đơn hàng: {system_total_trackings}\n"
            f"🚚 Đang theo dõi: {system_active_trackings}\n"
            f"✅ Đã hoàn thành: {system_total_trackings - system_active_trackings}"
        )
        await _send_simple_reply(update, system_stats)

    await _send_link_reminder_if_needed(flask_app, update, user)


async def _handle_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    flask_app = _flask_app
    zalo_id = _extract_chat_id(update)
    if not flask_app or not zalo_id:
        return

    if not context.args or len(context.args) < 1:
        await _send_simple_reply(update, "Cú pháp: /add <mã vận đơn> [tên gợi nhớ]")
        return

    tracking_number = context.args[0]
    alias = " ".join(context.args[1:]) if len(context.args) > 1 else None

    with flask_app.app_context():
        user = UsersRepo.get_or_create_temp_by_zalo_account_id(zalo_id)
        result = TrackingService.create_tracking_for_user(
            user=user,
            tracking_number=tracking_number,
            alias=alias,
            carrier_id='auto',
            send_notification=False,
        )

        if result.get('success'):
            tracking = TrackingsRepo.get_by_id(result['tracking_id'])
            status = tracking.get('currentStatus', 'Pending') if tracking else 'Pending'
        else:
            tracking = None

    if not result.get('success'):
        await _send_simple_reply(update, (
            "Không thể tự động nhận diện đơn vị vận chuyển cho mã này. "
            "Kiểm tra mã vận đơn hoặc dùng /providers để xem danh sách hỗ trợ."
        ))
        return

    await _send_simple_reply(update, (
        "Đã thêm đơn hàng thành công.\n"
        f"Mã: {tracking_number}\n"
        f"Tên gợi nhớ: {alias or 'Không có'}\n"
        f"Đơn vị vận chuyển: {result['carrier_id']}\n"
        f"Trạng thái hiện tại: {status}"
    ))
    await _send_link_reminder_if_needed(flask_app, update, user)


async def _handle_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    flask_app = _flask_app
    zalo_id = _extract_chat_id(update)
    if not flask_app or not zalo_id:
        return

    if not context.args or len(context.args) < 1:
        await _send_simple_reply(update, "Cú pháp: /remove <mã vận đơn>")
        return

    tracking_number = context.args[0]

    with flask_app.app_context():
        user = UsersRepo.get_or_create_temp_by_zalo_account_id(zalo_id)
        trackings = TrackingsRepo.get_user_trackings(user.id)
        found_tracking = None
        for t in trackings:
            if t.get('trackingNumber') == tracking_number:
                found_tracking = t
                break

        if not found_tracking:
            await _send_simple_reply(update, f"Không tìm thấy đơn hàng với mã: {tracking_number}")
            return

        try:
            TrackingsRepo.delete(found_tracking['id'])
            await _send_simple_reply(update, f"Đã xóa theo dõi đơn hàng: {tracking_number}")
        except Exception as exc:
            await _send_simple_reply(update, f"Lỗi khi xóa đơn hàng: {exc}")

    await _send_link_reminder_if_needed(flask_app, update, user)


async def _handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    flask_app = _flask_app
    zalo_id = _extract_chat_id(update)
    if not flask_app or not zalo_id or not update.message:
        return

    text = (update.message.text or '').strip()
    if not text:
        return

    if text.startswith('/'):
        await _dispatch_command(update, context, text)
        return

    with flask_app.app_context():
        user = UsersRepo.get_or_create_temp_by_zalo_account_id(zalo_id)
        link_url = _build_link_url(flask_app, zalo_id, user.link_token)

    await _send_simple_reply(update, (
        "Mình đã nhận tin nhắn. Dùng /help để xem danh sách lệnh hỗ trợ.\n"
        f"Liên kết tài khoản tại: {link_url}"
    ))


def _build_application(flask_app, token: str):
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler('test', _handle_test))

    application.add_handler(CommandHandler('start', _handle_start))
    application.add_handler(CommandHandler('help', _handle_help))
    application.add_handler(CommandHandler('author', _handle_author))
    application.add_handler(CommandHandler('providers', _handle_providers))
    application.add_handler(CommandHandler('list', _handle_list))
    application.add_handler(CommandHandler('stats', _handle_stats))
    application.add_handler(CommandHandler('add', _handle_add))
    application.add_handler(CommandHandler('remove', _handle_remove))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))
    try:
        application.add_handler(MessageHandler(filters.ALL, _log_update))
    except Exception:
        application.add_handler(MessageHandler(filters.ALL, _log_update))
    return application


async def _dispatch_command(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Fallback command router when CommandHandler is skipped by platform quirks."""
    cmd = text.split()[0].split('@')[0].lower()
    if cmd == '/start':
        await _handle_start(update, context)
    elif cmd == '/help':
        await _handle_help(update, context)
    elif cmd == '/author':
        await _handle_author(update, context)
    elif cmd == '/providers':
        await _handle_providers(update, context)
    elif cmd == '/list':
        await _handle_list(update, context)
    elif cmd == '/stats':
        await _handle_stats(update, context)
    elif cmd == '/add':
        # mimic context.args parsing
        context.args = text.split()[1:]
        await _handle_add(update, context)
    elif cmd == '/remove':
        context.args = text.split()[1:]
        await _handle_remove(update, context)
    elif cmd == '/test':
        await _handle_test(update, context)


def _run_polling(flask_app, token: str):
    global _application
    global _flask_app

    # Ensure webhook is cleared; polling won't receive updates if webhook is active
    try:
        requests.post(f"https://bot-api.zaloplatforms.com/bot{token}/deleteWebhook", timeout=5)
    except Exception:
        pass

    application = _build_application(flask_app, token)
    _application = application
    _flask_app = flask_app

    # run_polling blocks until stop is called; log all update types for debugging
    allowed = getattr(Update, 'ALL_TYPES', None)
    if allowed is not None:
        application.run_polling(allowed_updates=allowed)
    else:
        application.run_polling()


def start_zalo_bot(app):
    global _bot_thread

    token = app.config.get('ZALO_BOT_TOKEN')
    if not token:
        app.logger.warning("ZALO_BOT_TOKEN is empty. Zalo bot will not start.")
        return None

    if _bot_thread and _bot_thread.is_alive():
        return _bot_thread

    _stop_event.clear()

    def _run():
        _run_polling(app, token)

    _bot_thread = threading.Thread(target=_run, daemon=True)
    _bot_thread.start()
    app.logger.info("Zalo bot polling started")
    return _bot_thread


def stop_zalo_chat_bot():
    _stop_event.set()
    if _bot_thread and _bot_thread.is_alive():
        _bot_thread.join(timeout=5)
