from flask import Blueprint, render_template, url_for, flash, redirect, request, abort
from flask_login import current_user, login_required
from app.tracking.forms import AddTrackingForm
from app.repos.trackings_repo import TrackingsRepo
from app.tracking.services import TrackingService

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
        result = TrackingService.create_tracking_for_user(
            user=current_user,
            tracking_number=form.tracking_number.data,
            alias=form.alias.data,
            carrier_id=form.carrier_id.data,
            send_notification=True
        )

        if not result.get('success'):
            flash(result.get('error', 'Không thể thêm vận đơn mới.'), 'warning')
            return render_template('tracking/add_tracking.html', form=form)

        flash('Thêm vận đơn thành công!', 'success')
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
        flash('Cập nhật trạng thái vận đơn thành công!', 'success')
    else:
        flash('Không thể cập nhật trạng thái vận đơn.', 'danger')
    return redirect(url_for('tracking.detail', tracking_id=tracking_id))

@tracking_bp.route("/tracking/<tracking_id>/delete", methods=['POST'])
@login_required
def delete(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking['userId'] != current_user.id:
        abort(403)
    TrackingsRepo.delete(tracking_id)
    flash('Vận đơn đã bị xóa.', 'success')
    return redirect(url_for('tracking.dashboard'))
