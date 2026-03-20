from flask import Blueprint, render_template, url_for, flash, redirect, request, current_app
from flask_login import current_user, login_required
from app.settings.forms import (
    SettingsForm,
    PowerOutageSubscriptionForm,
    DeletePowerOutageSubscriptionForm,
)
from app.repos.users_repo import UsersRepo
from app.notifications.registry import registry
from app.power_outage.service import PowerOutageService

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
                'enabled': form.zalo_enabled.data,
            },
            'notifyEnabled': form.notify_enabled.data,
            'telegramEnabled': form.telegram_enabled.data,
            'zaloEnabled': form.zalo_enabled.data,
            'channels': current_user.settings.get('channels', ['telegram'])
        }
        UsersRepo.update_settings(current_user.id, settings)
        flash('Settings updated!', 'success')
        return redirect(url_for('settings.index'))
    elif request.method == 'GET':
        form.telegram_chat_id.data = current_user.settings.get('telegramChatId')
        zalo_settings = current_user.settings.get('zalo') or {}
        form.zalo_chat_id.data = zalo_settings.get('chatId') or current_user.settings.get('zaloAccountId')
        form.notify_enabled.data = current_user.settings.get('notifyEnabled', True)
        form.telegram_enabled.data = current_user.settings.get('telegramEnabled', True)
        form.zalo_enabled.data = zalo_settings.get('enabled')
        if form.zalo_enabled.data is None:
            form.zalo_enabled.data = current_user.settings.get('zaloEnabled', True)
    return render_template(
        'settings/notifications.html',
        title='Settings',
        form=form,
    )


@settings_bp.route("/power-outage", methods=['GET', 'POST'])
@login_required
def power_outage_settings():
    form = PowerOutageSubscriptionForm()
    delete_power_form = DeletePowerOutageSubscriptionForm()
    power_units = PowerOutageService.list_units()
    power_subscriptions = PowerOutageService.list_subscriptions(current_user.id)

    if request.method == 'POST':
        if form.validate_on_submit():
            result = PowerOutageService.add_subscription(
                current_user,
                form.province_id.data,
                form.district_id.data or None,
            )
            if result.get('success'):
                flash('Đã thêm khu vực cắt điện cần theo dõi.', 'success')
            else:
                flash(result.get('error') or 'Không thể thêm khu vực.', 'danger')
        else:
            flash('Vui lòng chọn tỉnh/thành và quận/huyện hợp lệ.', 'warning')
        return redirect(url_for('settings.power_outage_settings'))

    return render_template(
        'settings/power_outage.html',
        title='Lịch cắt điện',
        power_form=form,
        delete_power_form=delete_power_form,
        power_units=power_units,
        power_subscriptions=power_subscriptions,
    )


@settings_bp.route("/power-outage/<subscription_id>/delete", methods=['POST'])
@login_required
def delete_power_outage(subscription_id):
    form = DeletePowerOutageSubscriptionForm()
    if form.validate_on_submit():
        if form.subscription_id.data and form.subscription_id.data != subscription_id:
            flash('Thông tin không khớp, vui lòng thử lại.', 'danger')
            return redirect(url_for('settings.power_outage_settings'))

        result = PowerOutageService.remove_subscription(current_user, subscription_id)
        if result.get('success'):
            flash('Đã xóa khu vực khỏi danh sách theo dõi.', 'success')
        else:
            flash(result.get('error') or 'Không thể xóa khu vực.', 'danger')
    else:
        flash('Yêu cầu không hợp lệ.', 'warning')
    return redirect(url_for('settings.power_outage_settings'))

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
