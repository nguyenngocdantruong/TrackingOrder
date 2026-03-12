from flask import Blueprint, render_template, url_for, flash, redirect, request, current_app
from flask_login import current_user, login_required
from app.settings.forms import SettingsForm
from app.repos.users_repo import UsersRepo
from app.notifications.registry import registry

settings_bp = Blueprint('settings', __name__)

@settings_bp.route("/", methods=['GET', 'POST'])
@login_required
def index():
    form = SettingsForm()
    if form.validate_on_submit():
        settings = {
            'telegramChatId': form.telegram_chat_id.data,
            'zaloAccountId': form.zalo_chat_id.data,  # backward compatible key
            'zalo': {
                'name': None,
                'chatId': form.zalo_chat_id.data,
            },
            'notifyEnabled': form.notify_enabled.data,
            'channels': current_user.settings.get('channels', ['telegram'])
        }
        UsersRepo.update_settings(current_user.id, settings)
        flash('Settings updated!', 'success')
        return redirect(url_for('settings.index'))
    elif request.method == 'GET':
        form.telegram_chat_id.data = current_user.settings.get('telegramChatId')
        zalo_settings = current_user.settings.get('zalo') or {}
        form.zalo_chat_id.data = zalo_settings.get('chatId') or current_user.settings.get('zaloAccountId')
        form.notify_enabled.data = current_user.settings.get('notifyEnabled')
    telegram_username = current_app.config.get('TELEGRAM_BOT_USERNAME') or 'orderskibidi_bot'
    telegram_handle = telegram_username if telegram_username.startswith('@') else f"@{telegram_username}"
    telegram_link = f"https://t.me/{telegram_handle.lstrip('@')}"

    zalo_bot_uid = current_app.config.get('ZALO_BOT_UID') or '2787361938619367790'
    zalo_bot_link = f"https://zalo.me/{zalo_bot_uid}"

    return render_template(
        'settings/index.html',
        title='Settings',
        form=form,
        telegram_handle=telegram_handle,
        telegram_link=telegram_link,
        zalo_bot_uid=zalo_bot_uid,
        zalo_bot_link=zalo_bot_link,
    )

@settings_bp.route("/test-telegram", methods=['POST'])
@login_required
def test_telegram():
    chat_id = current_user.settings.get('telegramChatId')
    if chat_id:
        telegram_provider = registry.get_provider('telegram')
        if telegram_provider and telegram_provider.is_configured():
            result = telegram_provider.send_message(
                chat_id, 
                "🔔 Test notification from Order Tracking Hub!"
            )
            if result.success:
                flash('Test notification sent!', 'success')
            else:
                flash(f'Failed to send test notification: {result.error_message}', 'danger')
        else:
            flash('Telegram provider not configured', 'danger')
    else:
        flash('Please set a Telegram Chat ID first.', 'warning')
    return redirect(url_for('settings.index'))


@settings_bp.route("/test-zalo", methods=['POST'])
@login_required
def test_zalo():
    zalo_settings = current_user.settings.get('zalo') or {}
    chat_id = zalo_settings.get('chatId') or current_user.settings.get('zaloAccountId')
    if chat_id:
        zalo_provider = registry.get_provider('zalo')
        if zalo_provider and zalo_provider.is_configured():
            result = zalo_provider.send_message(
                chat_id,
                "🔔 Test notification from Order Tracking Hub!"
            )
            if result.success:
                flash('Test Zalo notification sent!', 'success')
            else:
                flash(f'Failed to send Zalo notification: {result.error_message}', 'danger')
        else:
            flash('Zalo provider not configured', 'danger')
    else:
        flash('Please set a Zalo Chat ID first.', 'warning')
    return redirect(url_for('settings.index'))
