from flask import Blueprint, render_template, url_for, flash, redirect, request
from flask_login import current_user, login_required
from app.settings.forms import SettingsForm
from app.repos.users_repo import UsersRepo
from app.notifications.telegram import TelegramNotifier

settings_bp = Blueprint('settings', __name__)

@settings_bp.route("/", methods=['GET', 'POST'])
@login_required
def index():
    form = SettingsForm()
    if form.validate_on_submit():
        settings = {
            'telegramChatId': form.telegram_chat_id.data,
            'notifyEnabled': form.notify_enabled.data,
            'channels': current_user.settings.get('channels', ['telegram'])
        }
        UsersRepo.update_settings(current_user.id, settings)
        flash('Settings updated!', 'success')
        return redirect(url_for('settings.index'))
    elif request.method == 'GET':
        form.telegram_chat_id.data = current_user.settings.get('telegramChatId')
        form.notify_enabled.data = current_user.settings.get('notifyEnabled')
    return render_template('settings/index.html', title='Settings', form=form)

@settings_bp.route("/test-telegram", methods=['POST'])
@login_required
def test_telegram():
    chat_id = current_user.settings.get('telegramChatId')
    if chat_id:
        success = TelegramNotifier.send_message(chat_id, "🔔 Test notification from Order Tracking Hub!")
        if success:
            flash('Test notification sent!', 'success')
        else:
            flash('Failed to send test notification. Check bot token and chat ID.', 'danger')
    else:
        flash('Please set a Telegram Chat ID first.', 'warning')
    return redirect(url_for('settings.index'))
