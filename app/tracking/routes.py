from flask import Blueprint, render_template, url_for, flash, redirect, request, abort
from flask_login import current_user, login_required
from app.tracking.forms import AddTrackingForm
from app.repos.trackings_repo import TrackingsRepo
from app.tracking.services import TrackingService
from app.providers.registry import registry
from app.notifications.telegram import TelegramNotifier

tracking_bp = Blueprint('tracking', __name__)

@tracking_bp.route("/dashboard")
@login_required
def dashboard():
    trackings = TrackingsRepo.get_user_trackings(current_user.id)
    return render_template('tracking/dashboard.html', trackings=trackings)

@tracking_bp.route("/tracking/add", methods=['GET', 'POST'])
@login_required
def add_tracking():
    form = AddTrackingForm()
    if form.validate_on_submit():
        carrier_id = form.carrier_id.data
        if carrier_id == 'auto':
            provider = registry.find_provider_for(form.tracking_number.data)
            if not provider:
                flash('Could not auto-detect carrier. Please select manually.', 'warning')
                return render_template('tracking/add_tracking.html', form=form)
            carrier_id = provider.id

        tracking_data = {
            'userId': current_user.id,
            'trackingNumber': form.tracking_number.data,
            'carrierId': carrier_id,
            'alias': form.alias.data,
            'isActive': True,
            'events': [],
            'lastEventHash': None,
            'currentStatus': 'Pending',
            'lastEventTime': None,
            'lastCheckedAt': None
        }
        tracking_id = TrackingsRepo.create(tracking_data)

        # 1. Gửi thông báo xác nhận thêm đơn hàng trước
        if current_user.settings.get('notifyEnabled') and current_user.settings.get('telegramChatId'):
            msg = f"➕ *Đã thêm vận đơn mới thành công!*\n" \
                  f"Mã: `{form.tracking_number.data}`\n" \
                  f"Tên: {form.alias.data or 'Không có'}\n" \
                  f"Hãng: {carrier_id.upper()}\n\n" \
                  f"Hệ thống sẽ bắt đầu đồng bộ dữ liệu ngay bây giờ."
            TelegramNotifier.send_message(current_user.settings['telegramChatId'], msg)

        # 2. Sau đó mới thực hiện quét dữ liệu lần đầu
        isSuccess = TrackingService.refresh_tracking(tracking_id)

        flash('Tracking item added!', 'success')
        return redirect(url_for('tracking.dashboard'))
    return render_template('tracking/add_tracking.html', form=form)

@tracking_bp.route("/tracking/<tracking_id>")
@login_required
def detail(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking['userId'] != current_user.id:
        abort(403)
    return render_template('tracking/detail.html', tracking=tracking, tracking_id=tracking_id)

@tracking_bp.route("/tracking/<tracking_id>/refresh", methods=['POST'])
@login_required
def refresh(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking['userId'] != current_user.id:
        abort(403)

    if TrackingService.refresh_tracking(tracking_id):
        flash('Tracking refreshed!', 'success')
    else:
        flash('Failed to refresh tracking.', 'danger')
    return redirect(url_for('tracking.detail', tracking_id=tracking_id))

@tracking_bp.route("/tracking/<tracking_id>/delete", methods=['POST'])
@login_required
def delete(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking['userId'] != current_user.id:
        abort(403)
    TrackingsRepo.delete(tracking_id)
    flash('Tracking deleted.', 'success')
    return redirect(url_for('tracking.dashboard'))
