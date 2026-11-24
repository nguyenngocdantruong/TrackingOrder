from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from google.cloud.firestore_v1.base_query import FieldFilter
from wtforms import PasswordField, StringField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Length

from app.admin import is_admin
from app.auth.forms import RegistrationForm
from app.firebase import get_db
from app.operations import record
from app.notifications.service import NotificationService
from app.payments.registry import registry as payment_registry
from app.providers.registry import registry
from app.repos.trackings_repo import TrackingsRepo
from app.repos.users_repo import UsersRepo
from app.tracking.services import TrackingService, normalize_tracking_number, sanitize_alias_and_note
from app.tracking.stages import STAGE_CHOICES, STAGE_IDS, STAGE_LABELS, selected_stages, classify_event
from app.notifications.messages import build_test_shipment_notification

admin_ops = Blueprint('admin_ops', __name__, url_prefix='/admin')
PAGE_SIZE = 25
USER_FIELDS = ('username', 'isTemporary', 'suspended', 'createdAt', 'telegramVerifiedId')
TRACKING_FIELDS = ('userId', 'trackingNumber', 'carrierId', 'currentStatus', 'isActive',
                   'createdAt', 'lastCheckedAt', 'alias', 'adminPaused')


class TrackingInfoForm(FlaskForm):
    alias = StringField('Tên gợi nhớ', validators=[Length(max=80)])
    note = TextAreaField('Ghi chú', validators=[Length(max=240)])


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Mật khẩu mới', validators=[DataRequired(), Length(min=8, max=128)])
    confirmation = PasswordField('Nhập lại mật khẩu mới', validators=[DataRequired(), EqualTo('password')])


class CreateUserForm(RegistrationForm):
    def __init__(self):
        super().__init__()
        self.password.validators = [*self.password.validators, Length(min=8, max=128)]


@admin_ops.before_request
@login_required
def authorize():
    if not is_admin():
        abort(403)


@admin_ops.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def matches(row, filters):
    for key, op, expected in filters:
        actual = row.get(key)
        if op == '==' and actual != expected:
            return False
        if op == 'flag' and bool(actual) != expected:
            return False
        if op == 'stale' and actual is not None and actual >= expected:
            return False
        if op == '>=' and (actual is None or actual < expected):
            return False
        if op == '<' and (actual is None or actual >= expected):
            return False
    return True


def page(collection, fields, filters=(), sort=None):
    # Read one bounded window using single-field indexes. Apply combined
    # filters to the projected rows so no composite index rollout is needed.
    source = get_db().collection(collection)
    query = source.select(fields)
    exact_lookup = next((item for item in filters if item[1] == '==' and item[0] in
                         ('username', 'trackingNumber', 'orderCode')), None)
    if exact_lookup:
        # Exact searches use the automatic index and skip the global timeline.
        query = query.where(filter=FieldFilter(*exact_lookup))
        sort = None
    if sort:
        for field, op, value in filters:
            if field == sort and op in ('>=', '<'):
                query = query.where(filter=FieldFilter(field, op, value))
        query = query.order_by(sort, direction='DESCENDING')
    query = query.order_by('__name__', direction='DESCENDING' if sort else 'ASCENDING')
    cursor = request.args.get('after', '')
    if cursor and '/' not in cursor and len(cursor) <= 200:
        snapshot = source.document(cursor).get(field_paths=fields)
        if snapshot.exists and (not sort or sort in snapshot.to_dict()):
            query = query.start_after(snapshot)
    scan_limit = PAGE_SIZE * 8 if filters and not exact_lookup else PAGE_SIZE
    rows = []
    for position, doc in enumerate(query.limit(scan_limit + 1).stream()):
        if position == scan_limit or len(rows) == PAGE_SIZE:
            return rows, last_id
        row = {**doc.to_dict(), 'id': doc.id}
        if matches(row, filters):
            rows.append(row)
        last_id = doc.id
    return rows, None


def count(collection):
    return get_db().collection(collection).count().get()[0][0].value


def screen(section, **data):
    return render_template('v2/admin/operations.html', section=section, stage_labels=STAGE_LABELS, **data)


@admin_ops.post('/notifications/test/<stage>')
def test_telegram_notification(stage):
    if stage not in STAGE_IDS:
        abort(404)
    form = FlaskForm()
    if not form.validate_on_submit():
        abort(400)
    chat_id = str(current_app.config.get('ADMIN_TELEGRAM_USER_ID') or '').strip()
    if not chat_id:
        flash('Chưa cấu hình Telegram admin.', 'warning')
        return redirect(url_for('admin_ops.overview'))
    result = NotificationService.send_to_chat_id(
        chat_id, build_test_shipment_notification(stage), parse_mode='HTML')
    if result and result.success:
        record('audit', 'test_telegram_notification', 'ok', actorId=current_user.id,
               channel='telegram', stage=stage)
        flash(f'Đã gửi tin thử “{STAGE_LABELS[stage]}” tới Telegram admin.', 'success')
    else:
        record('audit', 'test_telegram_notification', 'error', actorId=current_user.id,
               channel='telegram', stage=stage)
        flash('Không gửi được tin thử. Kiểm tra bot token và Telegram admin.', 'warning')
    return redirect(url_for('admin_ops.overview'))


@admin_ops.get('/overview')
def overview():
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(
        3 * current_app.config.get('POLL_INTERVAL_SECONDS', 300), 1800))
    active_rows = get_db().collection('trackings').where(
        filter=FieldFilter('isActive', '==', True)).select(['lastCheckedAt', 'adminPaused']).stream()
    active_count = stale = 0
    for doc in active_rows:
        row = doc.to_dict()
        if row.get('adminPaused'):
            continue
        active_count += 1
        checked = row.get('lastCheckedAt')
        if checked is None or checked < cutoff:
            stale += 1
    latest = get_db().collection('operation_state').document('scheduler').get()
    return screen('overview', latest_poll=latest.to_dict() if latest.exists else None,
                  users_count=count('users'),
                  active_count=active_count,
                  stale_count=stale,
                  cutoff=cutoff.isoformat(),
                  test_stages=STAGE_CHOICES,
                  test_form=FlaskForm(),
                  scheduler_enabled=current_app.config.get('SCHEDULER_ENABLED'),
                  tracking_enabled=current_app.config.get('TRACKING_ENABLED'))


def can_manage_user(user_id, verified_telegram_id):
    owner_id = str(current_app.config.get('ADMIN_TELEGRAM_USER_ID') or '')
    return user_id != current_user.id and (
        not owner_id or str(verified_telegram_id or '') != owner_id
    )


@admin_ops.route('/users', methods=['GET', 'POST'])
def users():
    form = CreateUserForm()
    if form.validate_on_submit():
        user = UsersRepo.create(form.username.data, form.password.data)
        record('audit', 'create_user', 'ok', actorId=current_user.id, userId=user.id)
        flash('Đã tạo tài khoản.', 'success')
        return redirect(url_for('admin_ops.user_detail', user_id=user.id))
    filters = []
    if name := request.args.get('username', '').strip()[:100]:
        filters.append(('username', '==', name))
    if kind := request.args.get('type'):
        if kind in ('temporary', 'regular'):
            filters.append(('isTemporary', '==', kind == 'temporary'))
    rows, cursor = page('users', USER_FIELDS, filters)
    for row in rows:
        row['canManage'] = can_manage_user(row['id'], row.get('telegramVerifiedId'))
    return screen('users', rows=rows, cursor=cursor, form=form, row_form=FlaskForm())


@admin_ops.route('/users/<user_id>', methods=['GET', 'POST'])
def user_detail(user_id):
    user = UsersRepo.get_by_id(user_id)
    if not user:
        abort(404)
    can_manage = can_manage_user(user.id, user.telegram_verified_id)
    action_form = FlaskForm()
    password_form = ResetPasswordForm()
    if request.method == 'POST':
        if not can_manage:
            abort(403)
        action = request.form.get('action')
        if action in ('suspend', 'unsuspend'):
            if not action_form.validate_on_submit():
                abort(400)
            UsersRepo.set_suspended(user_id, action == 'suspend')
            message = 'Đã khóa tài khoản.' if action == 'suspend' else 'Đã mở khóa tài khoản.'
        elif action == 'reset_password' and not user.is_temporary:
            if password_form.validate_on_submit():
                UsersRepo.reset_password(user_id, password_form.password.data)
                message = 'Đã đặt lại mật khẩu.'
            else:
                message = None
        else:
            abort(400)
        if message:
            record('audit', action, 'ok', actorId=current_user.id, userId=user_id)
            flash(message, 'success')
            return redirect(url_for('admin_ops.users') if request.form.get('from_list')
                            else url_for('admin_ops.user_detail', user_id=user_id))
    settings = user.settings
    zalo = settings.get('zalo') or {}
    telegram_on = bool(settings.get('telegramChatId') and settings.get('telegramEnabled', True))
    zalo_on = bool((zalo.get('chatId') or settings.get('zaloAccountId'))
                   and zalo.get('enabled', settings.get('zaloEnabled', True)))
    return screen('user', user_id=user.id, username=user.username, temporary=user.is_temporary,
                  suspended=user.suspended, can_manage=can_manage, action_form=action_form,
                  password_form=password_form,
                  notifications=settings.get('notifyEnabled', True), telegram_on=telegram_on,
                  zalo_on=zalo_on, stages=[STAGE_LABELS[s] for s in selected_stages(settings)],
                  webhook_at=user.partner_api.get('lastDeliveryAt'),
                  webhook_ok=user.partner_api.get('lastDeliveryOk'),
                  webhook_status=user.partner_api.get('lastDeliveryStatus'))


def date_filter(filters, field, arg, op):
    try:
        value = datetime.fromisoformat(request.args.get(arg, '')).replace(tzinfo=timezone.utc)
    except ValueError:
        return
    filters.append((field, op, value))


@admin_ops.get('/trackings')
def trackings():
    filters = []
    for arg, field in [('user', 'userId'), ('carrier', 'carrierId'), ('status', 'currentStatus')]:
        if value := request.args.get(arg, '').strip()[:150]:
            filters.append((field, '==', value))
    if value := request.args.get('number', '').strip()[:150]:
        filters.append(('trackingNumber', '==', normalize_tracking_number(value)))
    active = request.args.get('active')
    if active in ('1', '0', 'paused'):
        filters.append(('isActive', '==', active != '0'))
        if active != '0':
            filters.append(('adminPaused', 'flag', active == 'paused'))
    stale = request.args.get('stale')
    if stale == '1':
        filters.append(('adminPaused', 'flag', False))
        try:
            cutoff = datetime.fromisoformat(request.args.get('cutoff', '')).replace(tzinfo=timezone.utc)
        except ValueError:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        filters.append(('lastCheckedAt', 'stale', cutoff))
    date_filter(filters, 'createdAt', 'from', '>=')
    date_filter(filters, 'createdAt', 'to', '<')
    rows, cursor = page('trackings', TRACKING_FIELDS, filters, 'createdAt')
    return screen('trackings', rows=rows, cursor=cursor, providers=registry.list_providers(),
                  row_form=FlaskForm())


@admin_ops.route('/trackings/<tracking_id>', methods=['GET', 'POST'])
def tracking_detail(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking:
        abort(404)
    form = FlaskForm()
    edit_form = TrackingInfoForm(data={'alias': tracking.get('alias'), 'note': tracking.get('note')})
    action = request.form.get('action', 'refresh_tracking')
    if request.method == 'POST':
        if action == 'edit_tracking':
            if edit_form.validate_on_submit():
                alias, note = sanitize_alias_and_note(edit_form.alias.data, edit_form.note.data)
                TrackingsRepo.update(tracking_id, {'alias': alias, 'note': note})
                audit_tracking(action, 'ok', tracking_id, tracking)
                flash('Đã cập nhật vận đơn.', 'success')
                return redirect(url_for('admin_ops.tracking_detail', tracking_id=tracking_id))
        else:
            if not form.validate_on_submit():
                abort(400)
            if action in ('pause_tracking', 'resume_tracking') and tracking.get('isActive'):
                paused = action == 'pause_tracking'
                TrackingsRepo.update(tracking_id, {'adminPaused': paused})
                outcome = 'ok'
                flash('Đã tạm dừng đồng bộ tự động.' if paused else 'Đã bật lại đồng bộ tự động.', 'success')
            elif action == 'refresh_tracking':
                try:
                    outcome = 'ok' if TrackingService.refresh_tracking(tracking_id) else 'skipped'
                except Exception:
                    outcome = 'error'
                message = {'ok': 'Đã đồng bộ vận đơn.', 'skipped': 'Hiện không thể đồng bộ vận đơn này.',
                           'error': 'Đồng bộ thất bại. Xem nhật ký để kiểm tra.'}
                flash(message[outcome], 'success' if outcome == 'ok' else 'warning')
            else:
                abort(400)
            audit_tracking(action, outcome, tracking_id, tracking)
            return redirect(url_for('admin_ops.trackings') if request.form.get('from_list')
                            else url_for('admin_ops.tracking_detail', tracking_id=tracking_id))
    events = [(event, STAGE_LABELS.get(classify_event(tracking.get('carrierId'), event)))
              for event in tracking.get('events', [])]
    summary = {key: tracking.get(key) for key in TRACKING_FIELDS}
    return screen('tracking', tracking=summary, tracking_id=tracking_id, events=events, form=form, edit_form=edit_form)


def audit_tracking(action, outcome, tracking_id, tracking):
    record('audit', action, outcome, actorId=current_user.id,
           trackingId=tracking_id, userId=tracking.get('userId'), carrierId=tracking.get('carrierId'))


LOG_FIELDS = ('createdAt', 'kind', 'action', 'outcome', 'actorId', 'userId', 'trackingId',
              'carrierId', 'channel', 'stage', 'statusCode', 'processed', 'failed', 'deliveryId')
PAYMENT_FIELDS = ('createdAt', 'updatedAt', 'amount', 'status', 'orderCode')


def read_detail(collection, id, fields):
    snapshot = get_db().collection(collection).document(id).get(field_paths=fields)
    if not snapshot.exists:
        abort(404)
    return snapshot.to_dict()


@admin_ops.get('/logs/<event_id>')
def log_detail(event_id):
    return screen('log', item=read_detail('operation_events', event_id, LOG_FIELDS))


@admin_ops.route('/payments/<order_code>', methods=['GET', 'POST'])
def payment_detail(order_code):
    if not order_code.isascii() or not order_code.isdigit() or len(order_code) > 20:
        abort(404)
    item = read_detail('donation_history', order_code, PAYMENT_FIELDS)
    form = FlaskForm()
    if request.method == 'POST':
        if not form.validate_on_submit():
            abort(400)
        gateway = payment_registry.get_gateway('payos')
        if not gateway:
            flash('PayOS chưa được cấu hình.', 'warning')
        else:
            try:
                result = gateway.get_payment_status(int(order_code))
                raw = result.get('status') if isinstance(result, dict) else result.status
                status = {'PAID': 'Đã thanh toán', 'PENDING': 'Chờ thanh toán', 'CANCELLED': 'Đã hủy',
                          'EXPIRED': 'Hết hạn', 'PROCESSING': 'Đang xử lý', 'FAILED': 'Thất bại'}
                flash('Trạng thái từ PayOS: ' + status.get(getattr(raw, 'value', raw), 'Chưa xác định'), 'info')
            except Exception:
                flash('Không thể kiểm tra trạng thái trên PayOS lúc này.', 'warning')
        return redirect(url_for('admin_ops.payment_detail', order_code=order_code))
    return screen('payment', item=item, form=form, order_code=order_code)


@admin_ops.get('/logs')
def logs():
    filters = []
    for arg, field in [('kind', 'kind'), ('outcome', 'outcome'), ('tracking', 'trackingId'),
                       ('user', 'userId'), ('carrier', 'carrierId')]:
        if value := request.args.get(arg, '').strip()[:150]:
            filters.append((field, '==', value))
    date_filter(filters, 'createdAt', 'from', '>=')
    date_filter(filters, 'createdAt', 'to', '<')
    rows, cursor = page('operation_events',
                        LOG_FIELDS,
                        filters, 'createdAt')
    return screen('logs', rows=rows, cursor=cursor, providers=registry.list_providers())


@admin_ops.get('/payments')
def payments():
    filters = []
    if status := request.args.get('status', '').strip()[:30]:
        filters.append(('status', '==', status))
    if code := request.args.get('code', '').strip()[:30]:
        filters.append(('orderCode', '==', code))
    date_filter(filters, 'updatedAt', 'from', '>=')
    date_filter(filters, 'updatedAt', 'to', '<')
    rows, cursor = page('donation_history', PAYMENT_FIELDS,
                        filters, 'updatedAt')
    return screen('payments', rows=rows, cursor=cursor, row_form=FlaskForm())
