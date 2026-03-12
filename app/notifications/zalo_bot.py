import asyncio
import threading
from urllib.parse import urlencode

from flask import Blueprint, request, current_app
import zalo_bot


_bot_thread = None
_stop_event = threading.Event()
_webhook_bp = Blueprint('zalo_webhook', __name__)
_zalo_bot_token = None
_zalo_secret_token = None


def _build_link_url(app, zalo_id, link_token):
    base_url = (app.config.get('WEBSITE_URL') or 'http://127.0.0.1:5000').rstrip('/')
    query = urlencode({'zalo_id': str(zalo_id), 'token': link_token or ''})
    return f"{base_url}/link/zalo?{query}"


def _is_webhook_mode(app):
    webhook_url = (app.config.get('ZALO_BOT_WEBHOOK_URL') or '').strip()
    return bool(webhook_url)


async def _handle_update(app, bot: zalo_bot.Bot, update: zalo_bot.Update):
    message = getattr(update, 'message', None)
    if not message:
        return

    chat = getattr(message, 'chat', None)
    zalo_id = getattr(chat, 'id', None)
    text = (getattr(message, 'text', '') or '').strip()

    if not zalo_id:
        return

    with app.app_context():
        from app.repos.users_repo import UsersRepo

        user = UsersRepo.get_or_create_temp_by_zalo_account_id(zalo_id)
        link_url = _build_link_url(app, zalo_id, user.link_token)

        if text.lower().startswith('/start'):
            reply = (
                "🤖 Zalo Tracking Bot\n"
                "Nhấn liên kết bên dưới để gắn Zalo vào tài khoản.\n"
                "Bạn có thể đăng nhập tài khoản sẵn có hoặc tạo tài khoản mới.\n"
                f"{link_url}"
            )
        else:
            reply = (
                "Mình đã nhận tin nhắn. Nhấn vào liên kết để hoàn tất liên kết Zalo với tài khoản hệ thống \n"
                f"{link_url}"
            )

    try:
        await bot.send_message(str(zalo_id), reply)
        app.logger.info("[Zalo Bot] Sent link message to %s", zalo_id)
    except Exception as exc:  # pragma: no cover - network errors
        app.logger.error("[Zalo Bot] Send failed: %s", exc)


async def _poll_updates(app, token: str):
    bot = zalo_bot.Bot(token)
    async with bot:
        app.logger.info("Zalo bot polling started")
        while not _stop_event.is_set():
            try:
                update = await bot.get_update(timeout=25)
                if update:
                    await _handle_update(app, bot, update)
            except Exception as exc:  # pragma: no cover - network errors
                app.logger.error("[Zalo Bot] Polling error: %s", exc)
                await asyncio.sleep(3)


def _register_webhook_routes(app):
    @_webhook_bp.route('/zalo/webhook', methods=['POST'])
    def zalo_webhook():
        # Basic shared-secret check (optional but recommended)
        if _zalo_secret_token:
            incoming_secret = request.headers.get('X-Zalo-Secret-Token') or request.args.get('secret_token')
            if incoming_secret != _zalo_secret_token:
                return 'forbidden', 403

        data = request.get_json(silent=True) or {}
        update_json = data.get('result') or data
        if not update_json:
            return 'no data', 400

        async def _handle():
            bot = zalo_bot.Bot(_zalo_bot_token)
            update = zalo_bot.Update.de_json(update_json, bot)
            await _handle_update(app, bot, update)

        asyncio.run(_handle())
        return 'ok'

    if 'zalo_webhook' not in app.blueprints:
        app.register_blueprint(_webhook_bp)


def start_zalo_bot(app):
    """Start Zalo bot in webhook or polling mode depending on config."""
    global _bot_thread, _zalo_bot_token, _zalo_secret_token

    _zalo_bot_token = app.config.get('ZALO_BOT_TOKEN')
    _zalo_secret_token = app.config.get('ZALO_BOT_SECRET_TOKEN')

    if not _zalo_bot_token:
        app.logger.warning("ZALO_BOT_TOKEN is empty. Zalo bot will not start.")
        return None

    if _is_webhook_mode(app):
        webhook_url = app.config.get('ZALO_BOT_WEBHOOK_URL')

        async def _setup_webhook():
            bot = zalo_bot.Bot(_zalo_bot_token)
            async with bot:
                await bot.set_webhook(url=webhook_url, secret_token=_zalo_secret_token)

        try:
            asyncio.run(_setup_webhook())
            _register_webhook_routes(app)
            app.logger.info("Zalo bot webhook configured at %s", webhook_url)
            return None
        except Exception as exc:  # pragma: no cover - network errors
            app.logger.error("Failed to set Zalo webhook, falling back to polling: %s", exc)
            # fall through to polling

    if _bot_thread and _bot_thread.is_alive():
        return _bot_thread

    _stop_event.clear()

    def _run():
        asyncio.run(_poll_updates(app, _zalo_bot_token))

    _bot_thread = threading.Thread(target=_run, daemon=True)
    _bot_thread.start()
    app.logger.info("Zalo bot polling started")
    return _bot_thread


def stop_zalo_chat_bot():
    _stop_event.set()
