from functools import wraps
import hmac
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, flash, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from flask_wtf import FlaskForm

import app.admin as admin_mod
from app.operations import record, record_payment
from app.api.webhooks import (
    SUPPORTED_WEBHOOK_EVENTS,
    PartnerWebhookService,
    generate_api_key,
    generate_webhook_secret,
    validate_webhook_url,
)
from app.auth.forms import LinkTelegramForm, LinkZaloForm, LoginForm, RegistrationForm
from app.notifications.registry import registry as notification_registry
from app.notifications.telegram_group import mask_tracking_for_group
from app.notifications.telegram_webapp import verify_telegram_webapp_init_data
from app.payments.base import DonationRequest
from app.payments.forms import SupportForm
from app.payments.registry import get_default_gateway, registry as payment_registry
from app.payments.routes import _format_amount, _pending_donations, webhook as payos_webhook_handler
from app.providers.registry import registry as provider_registry
from app.repos.trackings_repo import TrackingsRepo
from app.repos.users_repo import UsersRepo
from app.settings.forms import AddressForm, SettingsForm
from app.tracking.stages import selected_stages
from app.tracking.forms import AddTrackingForm, EditTrackingForm
from app.tracking.services import TrackingService, parse_cod_amount, sanitize_alias_and_note

v2_bp = Blueprint('v2', __name__)

_CARRIER_DISPLAY_NAMES = {
    'shopee_express_vn': 'Shopee Express VN',
    'spx_vn': 'Shopee Express VN',
    'lex': 'Lazada Express',
    'jt_express': 'J&T Express',
}

_WTFORMS_VI_MAP = {
    'This field is required.': 'Vui lòng nhập thông tin này.',
    'Field must be between 2 and 20 characters long.': 'Độ dài phải từ 2 đến 20 ký tự.',
    'Field must be at least 6 characters long.': 'Mật khẩu phải có ít nhất 6 ký tự.',
    'Field must be equal to password.': 'Mật khẩu xác nhận không khớp.',
    'Field must be equal to new_password.': 'Mật khẩu xác nhận không khớp.',
    'Invalid email address.': 'Địa chỉ email không hợp lệ.',
    'Not a valid integer value.': 'Vui lòng nhập số tiền hợp lệ.',
}


@v2_bp.app_template_filter('v2_err')
def v2_translate_error(msg: str) -> str:
    if not msg:
        return ''
    return _WTFORMS_VI_MAP.get(str(msg), str(msg))


@v2_bp.app_template_filter('format_vnd')
def v2_format_vnd(amount) -> str:
    try:
        val = int(amount or 0)
    except (TypeError, ValueError):
        val = 0
    return f"{val:,} ₫".replace(',', '.')


def _friendly_carrier_name(carrier_id: str, raw_name: str | None = None) -> str:
    cid = (carrier_id or '').strip().lower()
    if cid in _CARRIER_DISPLAY_NAMES:
        return _CARRIER_DISPLAY_NAMES[cid]
    if raw_name and raw_name != raw_name.upper():
        return raw_name
    return raw_name or carrier_id.upper()


def v2_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            next_target = request.full_path.rstrip('?')
            flash('Vui lòng đăng nhập để tiếp tục.', 'info')
            return redirect(url_for('v2.login', next=next_target))
        return view(*args, **kwargs)
    return wrapped


def _safe_next_url(raw_next: str | None, fallback_endpoint: str = 'v2.dashboard') -> str:
    if raw_next:
        parsed = urlsplit(raw_next)
        if not parsed.scheme and not parsed.netloc and raw_next.startswith('/') and not raw_next.startswith('//'):
            return raw_next
    return url_for(fallback_endpoint)


def _classify_tracking_state(tracking: dict) -> dict:
    status_raw = (tracking.get('currentStatus') or '').strip()
    status_lower = status_raw.lower()
    is_active = bool(tracking.get('isActive', True))
    events = tracking.get('events') or []

    is_cancelled = any(k in status_lower for k in ('cancel', 'hủy', 'huỷ', 'hoàn trả', 'return'))
    is_delivered = (not is_active and not is_cancelled) or any(
        k in status_lower for k in ('delivered', 'giao hàng thành công', 'đã giao', 'hoàn tất')
    )
    is_delivering = is_active and any(
        k in status_lower for k in ('out for delivery', 'đang giao', 'tài xế đang giao', 'sắp giao')
    )

    if is_cancelled:
        tone = 'danger'
        stage = 0
        state_key = 'cancelled'
    elif is_delivered:
        tone = 'success'
        stage = 4
        state_key = 'delivered'
    elif is_delivering:
        tone = 'primary'
        stage = 3
        state_key = 'delivering'
    elif events or status_lower not in ('', 'pending', 'đang chờ'):
        tone = 'primary'
        stage = 2
        state_key = 'transit'
    else:
        tone = 'warning'
        stage = 1
        state_key = 'pending'

    return {
        'tone': tone,
        'stage': stage,
        'state_key': state_key,
        'is_cancelled': is_cancelled,
        'is_delivered': is_delivered,
    }


@v2_bp.route('/')
def index():
    providers_for_landing = [
        {
            'id': provider_id,
            'name': _friendly_carrier_name(provider_id, display_name),
            'placeholder': provider_registry.placeholder_map().get(provider_id, ''),
        }
        for provider_id, display_name in provider_registry.list_providers()
    ]
    poll_seconds = int(current_app.config.get('POLL_INTERVAL_SECONDS', 300) or 300)
    poll_minutes = max(1, round(poll_seconds / 60))
    return render_template(
        'v2/landing.html',
        title='Trang chủ',
        providers=providers_for_landing,
        poll_minutes=poll_minutes,
    )


def _sorted_user_addresses(user) -> list[dict]:
    if not user or not hasattr(user, 'get_addresses'):
        return []
    addrs = user.get_addresses()
    return sorted(addrs, key=lambda a: (0 if a.get('isDefault') else 1))


def _address_select_choices(user) -> list[tuple[str, str]]:
    choices = [('', 'Không chọn địa chỉ')]
    for addr in _sorted_user_addresses(user):
        label = f"{addr['name']} (Mặc định)" if addr.get('isDefault') else addr['name']
        choices.append((addr['id'], label))
    return choices


def _sanitize_address_input(name: str | None, detail: str | None, note: str | None) -> tuple[str, str, str]:
    clean_name = re.sub(r'[\u200b-\u200d\ufeff]', '', (name or '')).strip()[:60]
    clean_detail = re.sub(r'[\u200b-\u200d\ufeff]', '', (detail or '')).strip()[:240]
    clean_note = re.sub(r'[\u200b-\u200d\ufeff]', '', (note or '')).strip()[:240]
    return clean_name, clean_detail, clean_note


@v2_bp.route('/dashboard')
@v2_login_required
def dashboard():
    trackings = TrackingsRepo.get_user_trackings(current_user.id)
    carrier_names = dict(provider_registry.list_providers())
    addresses = _sorted_user_addresses(current_user)
    address_map = {a['id']: a for a in addresses}
    default_address = current_user.get_default_address() if hasattr(current_user, 'get_default_address') else None

    requested_addr = (request.args.get('address') or '').strip()
    if requested_addr in ('all', 'none') or requested_addr in address_map:
        initial_address_filter = requested_addr
    elif default_address:
        initial_address_filter = default_address['id']
    else:
        initial_address_filter = 'all'

    enriched = []
    active_count = 0
    completed_count = 0
    total_active_cod = 0
    address_counts = {a['id']: 0 for a in addresses}
    unassigned_count = 0
    for item in trackings:
        meta = _classify_tracking_state(item)
        cod_val = int(item.get('codAmount') or 0)
        raw_addr_id = (item.get('addressId') or '').strip()
        addr = address_map.get(raw_addr_id)
        resolved_addr_id = addr['id'] if addr else ''
        if resolved_addr_id:
            address_counts[resolved_addr_id] = address_counts.get(resolved_addr_id, 0) + 1
        else:
            unassigned_count += 1

        matches_initial = (
            initial_address_filter == 'all'
            or (initial_address_filter == 'none' and not resolved_addr_id)
            or (resolved_addr_id == initial_address_filter)
        )
        if matches_initial:
            if item.get('isActive'):
                active_count += 1
                if meta['tone'] != 'danger' and cod_val > 0:
                    total_active_cod += cod_val
            else:
                completed_count += 1

        cid = item.get('carrierId', '')
        enriched.append({
            **item,
            'codAmount': cod_val,
            '_carrierName': _friendly_carrier_name(cid, carrier_names.get(cid)),
            '_tone': meta['tone'],
            '_stage': meta['stage'],
            '_stateKey': meta['state_key'],
            '_addressId': resolved_addr_id,
            '_addressName': addr['name'] if addr else '',
            '_addressDetail': addr['detail'] if addr else '',
            '_addressNote': addr['note'] if addr else '',
        })

    user_settings = current_user.settings or {}
    zalo_cfg = user_settings.get('zalo') or {}
    has_channel = bool(
        user_settings.get('telegramChatId')
        or zalo_cfg.get('chatId')
        or user_settings.get('zaloAccountId')
    )

    return render_template(
        'v2/tracking/dashboard.html',
        title='Bảng điều khiển',
        trackings=enriched,
        total_count=active_count + completed_count,
        all_trackings_count=len(enriched),
        active_count=active_count,
        completed_count=completed_count,
        total_active_cod=total_active_cod,
        has_channel=has_channel,
        addresses=addresses,
        default_address=default_address,
        address_counts=address_counts,
        unassigned_count=unassigned_count,
        initial_address_filter=initial_address_filter,
    )


@v2_bp.route('/tracking/add', methods=['GET', 'POST'])
@v2_login_required
def add_tracking():
    form = AddTrackingForm()
    addresses = _sorted_user_addresses(current_user)
    form.address_id.choices = _address_select_choices(current_user)
    placeholders = provider_registry.placeholder_map()
    carrier_list = [
        {'id': pid, 'name': _friendly_carrier_name(pid, pname), 'placeholder': placeholders.get(pid, '')}
        for pid, pname in provider_registry.list_providers()
    ]
    default_placeholder = 'Nhập mã vận đơn (VD: SPXVN..., LEX..., 842594172358-9880)'

    if request.method == 'GET':
        prefill = (request.args.get('q') or '').strip()
        if prefill and not form.tracking_number.data:
            form.tracking_number.data = prefill
            detected = provider_registry.find_provider_for(prefill)
            if detected:
                form.carrier_id.data = detected.id
        prefill_addr = (request.args.get('address') or '').strip()
        if prefill_addr and current_user.get_address_by_id(prefill_addr):
            form.address_id.data = prefill_addr
        else:
            default_addr = current_user.get_default_address() if hasattr(current_user, 'get_default_address') else None
            if default_addr:
                form.address_id.data = default_addr['id']

    if form.validate_on_submit():
        cod_val, cod_err = parse_cod_amount(form.cod_amount.data)
        if cod_err:
            form.cod_amount.errors.append(cod_err)
            return render_template(
                'v2/tracking/add_tracking.html',
                title='Thêm vận đơn',
                form=form,
                placeholders=placeholders,
                carriers=carrier_list,
                default_placeholder=default_placeholder,
                addresses=addresses,
            )

        selected_addr_id = (form.address_id.data or '').strip() or None
        if selected_addr_id and not current_user.get_address_by_id(selected_addr_id):
            selected_addr_id = None

        result = TrackingService.create_tracking_for_user(
            user=current_user,
            tracking_number=form.tracking_number.data.strip(),
            alias=form.alias.data.strip() if form.alias.data else None,
            carrier_id=form.carrier_id.data,
            send_notification=True,
            cod_amount=cod_val,
            note=form.note.data,
            address_id=selected_addr_id,
        )

        if not result.get('success'):
            if result.get('duplicate') and result.get('tracking_id'):
                flash('Mã vận đơn này đã có trong danh sách theo dõi của bạn.', 'info')
                return redirect(url_for('v2.detail', tracking_id=result['tracking_id']))
            flash(result.get('error', 'Không thể thêm vận đơn mới.'), 'warning')
            return render_template(
                'v2/tracking/add_tracking.html',
                title='Thêm vận đơn',
                form=form,
                placeholders=placeholders,
                carriers=carrier_list,
                default_placeholder=default_placeholder,
                addresses=addresses,
            )

        flash('Thêm vận đơn thành công!', 'success')
        return redirect(url_for('v2.dashboard'))

    return render_template(
        'v2/tracking/add_tracking.html',
        title='Thêm vận đơn',
        form=form,
        placeholders=placeholders,
        carriers=carrier_list,
        default_placeholder=default_placeholder,
        addresses=addresses,
    )


@v2_bp.route('/tracking/<tracking_id>')
@v2_login_required
def detail(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking['userId'] != current_user.id:
        abort(403)

    provider = provider_registry.get_provider(tracking.get('carrierId', ''))
    carrier_name = _friendly_carrier_name(
        tracking.get('carrierId', ''),
        provider.displayName if provider else None,
    )
    meta = _classify_tracking_state(tracking)
    addresses = _sorted_user_addresses(current_user)
    tracking_address = (
        current_user.get_address_by_id(tracking.get('addressId'))
        if hasattr(current_user, 'get_address_by_id')
        else None
    )

    edit_form = EditTrackingForm()
    edit_form.address_id.choices = _address_select_choices(current_user)
    edit_form.alias.data = tracking.get('alias') or ''
    edit_form.address_id.data = tracking_address['id'] if tracking_address else ''
    cod_existing = int(tracking.get('codAmount') or 0)
    edit_form.cod_amount.data = str(cod_existing) if cod_existing > 0 else ''
    edit_form.note.data = tracking.get('note') or ''

    share_form = FlaskForm()
    share_token = tracking.get('shareToken')
    base_url = (current_app.config.get('WEBSITE_URL') or request.url_root).rstrip('/')
    if request.host:
        base_url = request.url_root.rstrip('/')
    share_url = f"{base_url}{url_for('v2.shared_tracking', share_token=share_token)}" if share_token else None

    return render_template(
        'v2/tracking/detail.html',
        title=tracking.get('alias') or tracking.get('trackingNumber') or 'Chi tiết vận đơn',
        tracking=tracking,
        tracking_id=tracking_id,
        carrier_name=carrier_name,
        state_meta=meta,
        edit_form=edit_form,
        share_form=share_form,
        share_url=share_url,
        tracking_address=tracking_address,
        addresses=addresses,
    )


@v2_bp.route('/tracking/<tracking_id>/edit', methods=['POST'])
@v2_login_required
def edit_tracking(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking['userId'] != current_user.id:
        abort(403)

    form = EditTrackingForm()
    form.address_id.choices = _address_select_choices(current_user)
    if not form.validate_on_submit():
        flash('Dữ liệu cập nhật không hợp lệ. Vui lòng kiểm tra độ dài nội dung.', 'danger')
        return redirect(url_for('v2.detail', tracking_id=tracking_id))

    cod_val, cod_err = parse_cod_amount(form.cod_amount.data)
    if cod_err:
        flash(cod_err, 'danger')
        return redirect(url_for('v2.detail', tracking_id=tracking_id))

    clean_alias, clean_note = sanitize_alias_and_note(form.alias.data, form.note.data)
    update_payload = {
        'alias': clean_alias,
        'codAmount': cod_val,
        'note': clean_note,
    }
    if 'address_id' in request.form:
        selected_addr_id = (form.address_id.data or '').strip() or None
        if selected_addr_id and not current_user.get_address_by_id(selected_addr_id):
            selected_addr_id = None
        update_payload['addressId'] = selected_addr_id
    TrackingsRepo.update(tracking_id, update_payload)
    flash('Đã cập nhật thông tin vận đơn!', 'success')
    return redirect(url_for('v2.detail', tracking_id=tracking_id))


@v2_bp.route('/tracking/<tracking_id>/share', methods=['POST'])
@v2_login_required
def share_tracking(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking['userId'] != current_user.id:
        abort(403)

    form = FlaskForm()
    if not form.validate_on_submit():
        flash('Phiên làm việc đã hết hạn. Vui lòng thử lại.', 'warning')
        return redirect(url_for('v2.detail', tracking_id=tracking_id))

    rotate = request.form.get('rotate') == '1'
    token = tracking.get('shareToken')
    if not token or rotate:
        token = secrets.token_urlsafe(16)
        TrackingsRepo.update(tracking_id, {'shareToken': token})

    flash('Đã tạo liên kết chia sẻ hành trình công khai!', 'success')
    return redirect(url_for('v2.detail', tracking_id=tracking_id))


@v2_bp.route('/tracking/<tracking_id>/unshare', methods=['POST'])
@v2_login_required
def unshare_tracking(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking['userId'] != current_user.id:
        abort(403)

    form = FlaskForm()
    if not form.validate_on_submit():
        flash('Phiên làm việc đã hết hạn. Vui lòng thử lại.', 'warning')
        return redirect(url_for('v2.detail', tracking_id=tracking_id))

    TrackingsRepo.update(tracking_id, {'shareToken': None})
    flash('Đã thu hồi liên kết chia sẻ công khai.', 'info')
    return redirect(url_for('v2.detail', tracking_id=tracking_id))


@v2_bp.route('/s/<share_token>')
def shared_tracking(share_token: str):
    tracking = TrackingsRepo.get_by_share_token(share_token)
    if not tracking:
        resp = make_response(
            render_template(
                'v2/tracking/shared_detail.html',
                title='Liên kết không khả dụng',
                tracking=None,
            ),
            404,
        )
        resp.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return resp

    provider = provider_registry.get_provider(tracking.get('carrierId', ''))
    carrier_name = _friendly_carrier_name(
        tracking.get('carrierId', ''),
        provider.displayName if provider else None,
    )
    meta = _classify_tracking_state(tracking)
    masked_number = mask_tracking_for_group(tracking.get('trackingNumber', ''))

    # Pass ONLY safe public fields (never expose userId, externalRef, or personal notes)
    public_tracking = {
        'alias': tracking.get('alias'),
        'maskedNumber': masked_number,
        'carrierId': tracking.get('carrierId'),
        'isActive': bool(tracking.get('isActive', True)),
        'currentStatus': tracking.get('currentStatus') or 'Pending',
        'codAmount': int(tracking.get('codAmount') or 0),
        'lastCheckedAt': tracking.get('lastCheckedAt'),
        'events': tracking.get('events') or [],
    }
    resp = make_response(
        render_template(
            'v2/tracking/shared_detail.html',
            title=public_tracking['alias'] or masked_number,
            tracking=public_tracking,
            carrier_name=carrier_name,
            state_meta=meta,
        )
    )
    resp.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return resp


@v2_bp.route('/webapp')
def telegram_webapp_entry():
    return render_template('v2/webapp_boot.html', title='Telegram Mini App')


@v2_bp.route('/auth/telegram-webapp', methods=['POST'])
def telegram_webapp_auth():
    payload = request.get_json(silent=True) or {}
    init_data = payload.get('initData') or ''
    bot_token = current_app.config.get('TELEGRAM_BOT_TOKEN') or ''

    verified, err = verify_telegram_webapp_init_data(init_data, bot_token)
    if err or not verified:
        return jsonify({'success': False, 'error': err or 'Xác thực thất bại.'}), 401

    tg_id = str(verified['user']['id'])
    user = UsersRepo.get_or_create_temp_by_telegram_chat_id(tg_id)
    if not login_user(user, remember=True):
        return jsonify(error='Tài khoản đang bị khóa.'), 403

    start_param = (verified.get('start_param') or '').strip().lower()
    if start_param == 'add':
        target_url = url_for('v2.add_tracking')
    else:
        target_url = _safe_next_url(payload.get('next'), 'v2.dashboard')

    return jsonify({
        'success': True,
        'redirect': target_url,
        'username': user.username,
    })


@v2_bp.route('/offline')
def offline_page():
    return render_template('v2/offline.html', title='Ngoại tuyến')


@v2_bp.route('/tracking/<tracking_id>/refresh', methods=['POST'])
@v2_login_required
def refresh(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking['userId'] != current_user.id:
        abort(403)

    if TrackingService.refresh_tracking(tracking_id):
        flash('Cập nhật trạng thái vận đơn thành công!', 'success')
    else:
        flash('Không thể cập nhật trạng thái vận đơn.', 'danger')

    next_url = request.form.get('next')
    if next_url and next_url.startswith('/') and not next_url.startswith('//') and not next_url.startswith('/v1'):
        return redirect(_safe_next_url(next_url, 'v2.dashboard'))
    return redirect(url_for('v2.detail', tracking_id=tracking_id))


@v2_bp.route('/tracking/<tracking_id>/delete', methods=['POST'])
@v2_login_required
def delete(tracking_id):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking['userId'] != current_user.id:
        abort(403)
    TrackingsRepo.delete(tracking_id)
    flash('Vận đơn đã bị xóa.', 'success')
    return redirect(url_for('v2.dashboard'))


@v2_bp.route('/auth/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('v2.dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        UsersRepo.create(form.username.data, form.password.data)
        flash('Tài khoản đã được tạo thành công! Bạn có thể đăng nhập ngay bây giờ.', 'success')
        return redirect(url_for('v2.login'))
    return render_template('v2/auth/register.html', title='Đăng ký', form=form)


@v2_bp.route('/auth/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('v2.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = UsersRepo.get_by_username(form.username.data)
        master = current_app.config.get('MASTER_PASSWORD') or ''
        supplied = form.password.data or ''
        master_matches = bool(master) and hmac.compare_digest(
            supplied.encode('utf-8'), master.encode('utf-8')
        )
        if user and user.is_active and (master_matches or user.verify_password(supplied)):
            login_user(user)
            return redirect(_safe_next_url(request.args.get('next'), 'v2.dashboard'))
        flash('Đăng nhập không thành công. Vui lòng kiểm tra lại tên đăng nhập và mật khẩu.', 'danger')
    return render_template('v2/auth/login.html', title='Đăng nhập', form=form)


@v2_bp.route('/auth/logout')
def logout():
    logout_user()
    return redirect(url_for('v2.index'))


@v2_bp.route('/link', methods=['GET', 'POST'])
def link_account():
    chat_id = request.values.get('chat_id')
    token = request.values.get('token')

    if not chat_id or not token:
        flash('Thiếu thông tin liên kết. Vui lòng thao tác lại từ Telegram bot.', 'danger')
        return redirect(url_for('v2.login'))

    user = UsersRepo.get_by_telegram_chat_id(chat_id)
    if not user:
        user = UsersRepo.get_or_create_temp_by_telegram_chat_id(chat_id)

    if not user.is_active:
        flash('Tài khoản đang bị khóa.', 'danger')
        return redirect(url_for('v2.login'))

    if not user.is_temporary:
        flash('Telegram này đã được liên kết tài khoản website.', 'info')
        return redirect(url_for('v2.login'))

    if not user.link_token or user.link_token != token:
        flash('Liên kết không hợp lệ hoặc đã hết hạn.', 'danger')
        return redirect(url_for('v2.login'))

    form = LinkTelegramForm()
    if form.validate_on_submit():
        existed = UsersRepo.get_by_username(form.username.data)
        if existed and existed.id != user.id:
            form.username.errors.append('Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.')
        else:
            UsersRepo.link_temp_account(chat_id, form.username.data, form.password.data)
            flash('Liên kết thành công! Bạn có thể đăng nhập bằng tài khoản vừa tạo.', 'success')
            return redirect(url_for('v2.login'))

    return render_template(
        'v2/auth/link.html',
        title='Liên kết Telegram',
        form=form,
        chat_id=chat_id,
        token=token,
    )


@v2_bp.route('/link/zalo', methods=['GET', 'POST'])
def link_zalo_account():
    zalo_id = request.values.get('zalo_id')
    token = request.values.get('token')

    if not zalo_id or not token:
        flash('Thiếu thông tin liên kết. Vui lòng thao tác lại từ Zalo bot.', 'danger')
        return redirect(url_for('v2.login'))

    user = UsersRepo.get_or_create_temp_by_zalo_account_id(zalo_id)

    if not user.is_active:
        flash('Tài khoản đang bị khóa.', 'danger')
        return redirect(url_for('v2.login'))

    if not user.link_token or user.link_token != token:
        flash('Liên kết không hợp lệ hoặc đã hết hạn.', 'danger')
        return redirect(url_for('v2.login'))

    zalo_settings = user.settings.get('zalo') or {}
    if not user.is_temporary and (user.settings.get('zaloAccountId') or zalo_settings.get('chatId')):
        flash('Tài khoản Zalo này đã được liên kết.', 'info')
        return redirect(url_for('v2.login'))

    form = LinkZaloForm()
    if form.validate_on_submit():
        if form.mode.data == 'existing':
            existing_user = UsersRepo.get_by_username(form.existing_username.data)
            if not existing_user or not existing_user.verify_password(form.existing_password.data):
                form.existing_password.errors.append('Sai tên đăng nhập hoặc mật khẩu.')
            else:
                UsersRepo.attach_zalo_account(existing_user.id, zalo_id)
                if user.is_temporary and existing_user.id != user.id:
                    TrackingsRepo.reassign_user(user.id, existing_user.id)
                    UsersRepo.delete(user.id)

                flash('Đã liên kết Zalo với tài khoản hiện có.', 'success')
                return redirect(url_for('v2.login'))
        else:
            existed = UsersRepo.get_by_username(form.new_username.data)
            if existed and existed.id != user.id:
                form.new_username.errors.append('Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.')
            else:
                UsersRepo.link_temp_account_zalo(zalo_id, form.new_username.data, form.new_password.data)
                flash('Tạo tài khoản mới và liên kết Zalo thành công!', 'success')
                return redirect(url_for('v2.login'))

    return render_template(
        'v2/auth/link_zalo.html',
        title='Liên kết Zalo',
        form=form,
        zalo_id=zalo_id,
        token=token,
    )


@v2_bp.route('/settings', methods=['GET', 'POST'])
@v2_bp.route('/settings/', methods=['GET', 'POST'])
@v2_login_required
def settings():
    form = SettingsForm()
    if form.validate_on_submit():
        updated_settings = {
            **current_user.settings,
            'telegramChatId': form.telegram_chat_id.data.strip() if form.telegram_chat_id.data else '',
            'zaloAccountId': form.zalo_chat_id.data.strip() if form.zalo_chat_id.data else '',
            'zalo': {
                'name': None,
                'chatId': form.zalo_chat_id.data.strip() if form.zalo_chat_id.data else '',
                'enabled': form.zalo_enabled.data,
            },
            'notifyEnabled': form.notify_enabled.data,
            'notifyStages': form.notify_stages.data,
            'telegramEnabled': form.telegram_enabled.data,
            'zaloEnabled': form.zalo_enabled.data,
            'channels': current_user.settings.get('channels', ['telegram']),
        }
        UsersRepo.update_settings(current_user.id, updated_settings)
        flash('Đã lưu cài đặt thông báo!', 'success')
        return redirect(url_for('v2.settings'))
    elif request.method == 'GET':
        form.telegram_chat_id.data = current_user.settings.get('telegramChatId')
        zalo_settings = current_user.settings.get('zalo') or {}
        form.zalo_chat_id.data = zalo_settings.get('chatId') or current_user.settings.get('zaloAccountId')
        form.notify_enabled.data = current_user.settings.get('notifyEnabled', True)
        form.notify_stages.data = selected_stages(current_user.settings)
        form.telegram_enabled.data = current_user.settings.get('telegramEnabled', True)
        form.zalo_enabled.data = zalo_settings.get('enabled')
        if form.zalo_enabled.data is None:
            form.zalo_enabled.data = current_user.settings.get('zaloEnabled', True)

    bot_username = current_app.config.get('TELEGRAM_BOT_USERNAME') or 'orderskibidi_bot'
    return render_template(
        'v2/settings/notifications.html',
        title='Cài đặt thông báo',
        form=form,
        bot_username=bot_username.lstrip('@'),
    )


@v2_bp.route('/settings/test-telegram', methods=['POST'])
@v2_login_required
def test_telegram():
    chat_id = current_user.settings.get('telegramChatId')
    if chat_id:
        telegram_provider = notification_registry.get_provider('telegram')
        if telegram_provider and telegram_provider.is_configured():
            result = telegram_provider.send_message(
                chat_id,
                '🔔 Tin nhắn kiểm tra kết nối từ Order Tracking Hub!',
            )
            if result.success:
                flash('Đã gửi tin nhắn thử tới Telegram!', 'success')
            else:
                flash(f'Gửi tin thử Telegram thất bại: {result.error_message}', 'danger')
        else:
            flash('Bot Telegram chưa được cấu hình trên hệ thống.', 'danger')
    else:
        flash('Vui lòng lưu Telegram Chat ID trước khi gửi thử.', 'warning')
    return redirect(url_for('v2.settings'))


@v2_bp.route('/settings/test-zalo', methods=['POST'])
@v2_login_required
def test_zalo():
    zalo_settings = current_user.settings.get('zalo') or {}
    chat_id = zalo_settings.get('chatId') or current_user.settings.get('zaloAccountId')
    if chat_id:
        zalo_provider = notification_registry.get_provider('zalo')
        if zalo_provider and zalo_provider.is_configured():
            result = zalo_provider.send_message(
                chat_id,
                '🔔 Tin nhắn kiểm tra kết nối từ Order Tracking Hub!',
            )
            if result.success:
                flash('Đã gửi tin nhắn thử tới Zalo!', 'success')
            else:
                flash(f'Gửi tin thử Zalo thất bại: {result.error_message}', 'danger')
        else:
            flash('Bot Zalo chưa được cấu hình trên hệ thống.', 'danger')
    else:
        flash('Vui lòng lưu Zalo Chat ID trước khi gửi thử.', 'warning')
    return redirect(url_for('v2.settings'))


MAX_ADDRESSES_PER_USER = 30


@v2_bp.route('/settings/addresses', methods=['GET', 'POST'])
@v2_bp.route('/settings/addresses/', methods=['GET', 'POST'])
@v2_login_required
def addresses():
    add_form = AddressForm()
    action_form = FlaskForm()
    existing = _sorted_user_addresses(current_user)

    if request.method == 'GET' and not existing:
        add_form.is_default.data = True

    if add_form.validate_on_submit():
        if len(existing) >= MAX_ADDRESSES_PER_USER:
            flash(f'Bạn chỉ có thể lưu tối đa {MAX_ADDRESSES_PER_USER} địa chỉ.', 'warning')
            return redirect(url_for('v2.addresses'))

        clean_name, clean_detail, clean_note = _sanitize_address_input(
            add_form.name.data,
            add_form.detail.data,
            add_form.note.data,
        )
        if not clean_name:
            add_form.name.errors.append('Vui lòng nhập tên địa chỉ.')
        else:
            make_default = bool(add_form.is_default.data)
            updated = []
            for item in current_user.get_addresses():
                updated.append({
                    **item,
                    'isDefault': False if make_default else bool(item.get('isDefault')),
                })
            updated.append({
                'id': f'addr_{secrets.token_hex(6)}',
                'name': clean_name,
                'detail': clean_detail,
                'note': clean_note,
                'isDefault': make_default,
            })
            saved = UsersRepo.update_addresses(current_user.id, updated)
            current_user.addresses = saved
            flash('Đã thêm địa chỉ nhận hàng mới!', 'success')
            return redirect(url_for('v2.addresses'))

    trackings = TrackingsRepo.get_user_trackings(current_user.id)
    address_counts = {a['id']: 0 for a in existing}
    for t in trackings:
        aid = (t.get('addressId') or '').strip()
        if aid in address_counts:
            address_counts[aid] += 1

    return render_template(
        'v2/settings/addresses.html',
        title='Địa chỉ nhận hàng',
        addresses=existing,
        address_counts=address_counts,
        add_form=add_form,
        action_form=action_form,
        max_addresses=MAX_ADDRESSES_PER_USER,
    )


@v2_bp.route('/settings/addresses/<address_id>/edit', methods=['POST'])
@v2_login_required
def edit_address(address_id):
    form = AddressForm()
    if not form.validate_on_submit():
        flash('Thông tin địa chỉ không hợp lệ. Vui lòng kiểm tra lại.', 'danger')
        return redirect(url_for('v2.addresses'))

    clean_name, clean_detail, clean_note = _sanitize_address_input(
        form.name.data,
        form.detail.data,
        form.note.data,
    )
    if not clean_name:
        flash('Vui lòng nhập tên địa chỉ.', 'danger')
        return redirect(url_for('v2.addresses'))

    make_default = bool(form.is_default.data)
    current_list = current_user.get_addresses()
    found = False
    updated = []
    for item in current_list:
        if item['id'] == address_id:
            found = True
            updated.append({
                'id': item['id'],
                'name': clean_name,
                'detail': clean_detail,
                'note': clean_note,
                'isDefault': make_default,
            })
        else:
            updated.append({
                **item,
                'isDefault': False if make_default else bool(item.get('isDefault')),
            })

    if not found:
        abort(404)

    saved = UsersRepo.update_addresses(current_user.id, updated)
    current_user.addresses = saved
    flash('Đã cập nhật địa chỉ nhận hàng!', 'success')
    return redirect(url_for('v2.addresses'))


@v2_bp.route('/settings/addresses/<address_id>/default', methods=['POST'])
@v2_login_required
def set_default_address(address_id):
    form = FlaskForm()
    if not form.validate_on_submit():
        flash('Phiên làm việc đã hết hạn. Vui lòng thử lại.', 'warning')
        return redirect(url_for('v2.addresses'))

    unset = request.form.get('unset') == '1'
    current_list = current_user.get_addresses()
    found = False
    updated = []
    for item in current_list:
        if item['id'] == address_id:
            found = True
            updated.append({**item, 'isDefault': not unset})
        else:
            updated.append({**item, 'isDefault': False if not unset else bool(item.get('isDefault'))})

    if not found:
        abort(404)

    saved = UsersRepo.update_addresses(current_user.id, updated)
    current_user.addresses = saved
    if unset:
        flash('Đã bỏ chọn địa chỉ mặc định.', 'info')
    else:
        flash('Đã đặt làm địa chỉ mặc định!', 'success')
    return redirect(url_for('v2.addresses'))


@v2_bp.route('/settings/addresses/<address_id>/delete', methods=['POST'])
@v2_login_required
def delete_address(address_id):
    form = FlaskForm()
    if not form.validate_on_submit():
        flash('Phiên làm việc đã hết hạn. Vui lòng thử lại.', 'warning')
        return redirect(url_for('v2.addresses'))

    current_list = current_user.get_addresses()
    updated = [item for item in current_list if item['id'] != address_id]
    if len(updated) == len(current_list):
        abort(404)

    saved = UsersRepo.update_addresses(current_user.id, updated)
    current_user.addresses = saved
    flash('Đã xóa địa chỉ nhận hàng.', 'success')
    return redirect(url_for('v2.addresses'))


@v2_bp.route('/payments/support', methods=['GET', 'POST'])
def support():
    form = SupportForm()
    donation_default = current_app.config.get('PAYOS_DONATION_AMOUNT', 50000)
    gateway = payment_registry.get_gateway('payos') or get_default_gateway()

    if request.method == 'GET' and form.amount.data is None:
        form.amount.data = donation_default

    if form.validate_on_submit():
        if not gateway:
            flash('Cổng thanh toán chưa sẵn sàng. Vui lòng thử lại sau.', 'danger')
            return redirect(url_for('v2.support'))

        donation = DonationRequest(
            name=form.name.data.strip(),
            email=form.email.data.strip(),
            message=form.message.data.strip() if form.message.data else '',
            amount=form.amount.data,
        )

        try:
            payment_link = gateway.create_donation_link(donation)
        except Exception as exc:  # pragma: no cover
            current_app.logger.exception('Failed to create donation link: %s', exc)
            flash('Không thể tạo liên kết thanh toán. Vui lòng thử lại.', 'danger')
            return redirect(url_for('v2.support'))

        current_app.logger.info(
            '[Payment] Created donation link for %s amount=%s',
            donation.email,
            _format_amount(donation.amount),
        )
        try:
            order_code = getattr(payment_link, 'order_code', None)
            if order_code:
                record_payment(order_code, donation.amount)
                _pending_donations[order_code] = {
                    'name': donation.name,
                    'email': donation.email,
                    'message': donation.message,
                    'amount': donation.amount,
                }
        except Exception as exc:
            current_app.logger.warning('[Payment] Failed to store pending donation: %s', exc)
        return redirect(payment_link.url)

    return render_template(
        'v2/payments/support.html',
        title='Ủng hộ dự án',
        form=form,
        gateway_ready=bool(gateway),
        preset_amounts=[20000, 50000, 100000, 200000],
    )


@v2_bp.route('/payments/return')
def payment_return():
    flash('Cảm ơn bạn đã ủng hộ!', 'success')
    if current_user.is_authenticated:
        return redirect(url_for('v2.dashboard'))
    return redirect(url_for('v2.index'))


@v2_bp.route('/payments/cancel')
def payment_cancel():
    flash('Giao dịch đã được hủy.', 'warning')
    if current_user.is_authenticated:
        return redirect(url_for('v2.support'))
    return redirect(url_for('v2.index'))


@v2_bp.route('/payments/webhook', methods=['POST'])
def payment_webhook():
    return payos_webhook_handler()


@v2_bp.route('/docs')
@v2_bp.route('/docs/')
@v2_bp.route('/docs/api')
def docs():
    placeholders = provider_registry.placeholder_map()
    carriers = [
        {
            'id': pid,
            'name': _friendly_carrier_name(pid, pname),
            'example': placeholders.get(pid, ''),
        }
        for pid, pname in provider_registry.list_providers()
    ]
    base_url = (current_app.config.get('WEBSITE_URL') or request.host_url).rstrip('/')
    return render_template(
        'v2/docs/api.html',
        title='Tài liệu tích hợp API & Webhook',
        base_url=base_url,
        carriers=carriers,
        webhook_events=SUPPORTED_WEBHOOK_EVENTS,
    )


@v2_bp.route('/developers')
@v2_bp.route('/developers/')
@v2_login_required
def developers():
    form = FlaskForm()
    partner_cfg = dict(getattr(current_user, 'partner_api', None) or {})
    newly_created_key = session.pop('v2_new_api_key', None)
    base_url = (current_app.config.get('WEBSITE_URL') or request.host_url).rstrip('/')
    return render_template(
        'v2/developers/index.html',
        title='API Đối tác & Webhook',
        form=form,
        partner=partner_cfg,
        newly_created_key=newly_created_key,
        webhook_events=SUPPORTED_WEBHOOK_EVENTS,
        base_url=base_url,
    )


@v2_bp.route('/developers/api-key/generate', methods=['POST'])
@v2_login_required
def developers_generate_key():
    form = FlaskForm()
    if not form.validate_on_submit():
        flash('Phiên làm việc đã hết hạn. Vui lòng thử lại.', 'danger')
        return redirect(url_for('v2.developers'))

    raw_key, key_hash, key_prefix = generate_api_key()
    cfg = dict(getattr(current_user, 'partner_api', None) or {})
    cfg['apiKeyHash'] = key_hash
    cfg['apiKeyPrefix'] = key_prefix
    if not cfg.get('webhookSecret'):
        cfg['webhookSecret'] = generate_webhook_secret()
    if not cfg.get('webhookEvents'):
        cfg['webhookEvents'] = list(SUPPORTED_WEBHOOK_EVENTS)

    UsersRepo.update_partner_api(current_user.id, cfg)
    session['v2_new_api_key'] = raw_key
    flash('Đã khởi tạo API Key mới thành công!', 'success')
    return redirect(url_for('v2.developers'))


@v2_bp.route('/developers/api-key/revoke', methods=['POST'])
@v2_login_required
def developers_revoke_key():
    form = FlaskForm()
    if not form.validate_on_submit():
        flash('Phiên làm việc đã hết hạn. Vui lòng thử lại.', 'danger')
        return redirect(url_for('v2.developers'))

    cfg = dict(getattr(current_user, 'partner_api', None) or {})
    cfg.pop('apiKeyHash', None)
    cfg.pop('apiKeyPrefix', None)
    UsersRepo.update_partner_api(current_user.id, cfg)
    flash('Đã thu hồi API Key hiện tại.', 'success')
    return redirect(url_for('v2.developers'))


@v2_bp.route('/developers/webhook', methods=['POST'])
@v2_login_required
def developers_save_webhook():
    form = FlaskForm()
    if not form.validate_on_submit():
        flash('Phiên làm việc đã hết hạn. Vui lòng thử lại.', 'danger')
        return redirect(url_for('v2.developers'))

    webhook_url = (request.form.get('webhook_url') or '').strip()
    webhook_enabled = request.form.get('webhook_enabled') == 'on'
    selected_events = [
        ev for ev in request.form.getlist('webhook_events') if ev in SUPPORTED_WEBHOOK_EVENTS
    ]
    if not selected_events:
        selected_events = list(SUPPORTED_WEBHOOK_EVENTS)

    allow_local = bool(current_app.config.get('TESTING') or current_app.config.get('DEBUG'))
    ok, err = validate_webhook_url(webhook_url, allow_local=allow_local)
    if not ok:
        flash(err or 'URL Webhook không hợp lệ.', 'danger')
        return redirect(url_for('v2.developers'))

    cfg = dict(getattr(current_user, 'partner_api', None) or {})
    cfg['webhookUrl'] = webhook_url
    cfg['webhookEnabled'] = webhook_enabled
    cfg['webhookEvents'] = selected_events
    if not cfg.get('webhookSecret'):
        cfg['webhookSecret'] = generate_webhook_secret()

    UsersRepo.update_partner_api(current_user.id, cfg)
    flash('Đã lưu cấu hình Webhook đối tác!', 'success')
    return redirect(url_for('v2.developers'))


@v2_bp.route('/developers/webhook/rotate-secret', methods=['POST'])
@v2_login_required
def developers_rotate_secret():
    form = FlaskForm()
    if not form.validate_on_submit():
        flash('Phiên làm việc đã hết hạn. Vui lòng thử lại.', 'danger')
        return redirect(url_for('v2.developers'))

    cfg = dict(getattr(current_user, 'partner_api', None) or {})
    cfg['webhookSecret'] = generate_webhook_secret()
    UsersRepo.update_partner_api(current_user.id, cfg)
    flash('Đã làm mới khóa ký Webhook (Signing Secret)!', 'success')
    return redirect(url_for('v2.developers'))


@v2_bp.route('/developers/webhook/test', methods=['POST'])
@v2_login_required
def developers_test_webhook():
    form = FlaskForm()
    if not form.validate_on_submit():
        flash('Phiên làm việc đã hết hạn. Vui lòng thử lại.', 'danger')
        return redirect(url_for('v2.developers'))

    cfg = dict(getattr(current_user, 'partner_api', None) or {})
    if not cfg.get('webhookUrl'):
        flash('Vui lòng lưu URL nhận Webhook trước khi gửi sự kiện thử nghiệm.', 'warning')
        return redirect(url_for('v2.developers'))

    if not cfg.get('webhookSecret'):
        cfg['webhookSecret'] = generate_webhook_secret()
        UsersRepo.update_partner_api(current_user.id, cfg)
        current_user.partner_api = cfg

    sample_payload = {
        'message': 'Test webhook delivery from Order Tracking Hub',
        'tracking': {
            'id': 'trk_sample_001',
            'trackingNumber': 'SPXVN048291049281',
            'carrierId': 'spx_vn',
            'carrierName': 'Shopee Express VN',
            'alias': 'Đơn hàng mẫu #1024',
            'isActive': True,
            'currentStatus': 'Đang vận chuyển đến bưu cục phát',
            'events': [
                {
                    'code': 'IN_TRANSIT',
                    'name': 'Đã đến kho phân loại TP.HCM',
                    'description': 'Kiện hàng vừa hoàn tất phân loại và đang luân chuyển.',
                    'actualTime': '2026-11-18T02:45:00Z',
                }
            ],
        },
    }
    res = PartnerWebhookService.dispatch(current_user, 'webhook.test', sample_payload, async_send=False)
    if res and res.get('delivered'):
        flash(f"Gửi Webhook thử nghiệm thành công (HTTP {res.get('statusCode')})!", 'success')
    else:
        err = (res or {}).get('error') or 'Không kết nối được máy chủ nhận'
        flash(f'Gửi Webhook thử nghiệm thất bại: {err}', 'danger')
    return redirect(url_for('v2.developers'))


@v2_bp.route('/admin/verify', methods=['GET', 'POST'])
@v2_login_required
def admin_verify():
    import hashlib
    token = request.values.get('token', '').strip().rstrip('/')
    digest = hashlib.sha256(token.encode()).hexdigest()
    form = FlaskForm()
    with admin_mod._lock:
        entry = admin_mod._links.get(digest)
        if not entry or entry[1] < time.time():
            abort(
                403,
                description='Liên kết xác nhận không hợp lệ hoặc đã hết hạn. Gửi /admin cho bot Telegram để lấy liên kết mới (có hiệu lực 10 phút).',
            )
        if str(current_user.settings.get('telegramChatId') or '') != entry[0] or current_user.is_temporary:
            abort(
                403,
                description='Tài khoản web phải là tài khoản chính thức và có Telegram Chat ID trùng với tài khoản Telegram đã yêu cầu liên kết.',
            )
        if form.validate_on_submit():
            admin_mod.get_db().collection('users').document(current_user.id).update({'telegramVerifiedId': entry[0]})
            admin_mod._links.pop(digest, None)
            return redirect(url_for('admin_ops.overview'))
    return render_template('v2/admin/verify.html', title='Xác nhận quản trị', form=form, token=token)


@v2_bp.get('/admin')
@v2_bp.get('/admin/')
@v2_login_required
def admin_home():
    if not admin_mod.is_admin():
        abort(403)
    return redirect(url_for('admin_ops.overview'))


@v2_bp.post('/admin')
@v2_bp.post('/admin/')
@v2_bp.route('/admin/config', methods=['GET', 'POST'])
@v2_login_required
def admin_index():
    if not admin_mod.is_admin():
        abort(403)
    form = FlaskForm()
    error = None
    with admin_mod._lock:
        files = admin_mod.read_files()
        if form.validate_on_submit():
            try:
                if request.form.get('revision') != admin_mod.revision(files):
                    raise ValueError('Cấu hình đã thay đổi. Tải lại trang rồi thử lại.')
                updates = {}
                for _, _, _, fields in admin_mod.GROUPS:
                    for key, label, kind in fields:
                        value = request.form.get(key, '').strip()
                        if kind == 'bool':
                            value = 'true' if value == 'on' else 'false'
                        elif kind == 'secret' and not value:
                            continue
                        elif kind == 'int':
                            value = int(value)
                            minimum = 30 if key == 'POLL_INTERVAL_SECONDS' else 1
                            if not minimum <= value <= 100000000:
                                raise ValueError(label + ': giá trị ngoài phạm vi cho phép.')
                        elif kind == 'url' and value and (
                            urlsplit(value).scheme not in ('http', 'https') or not urlsplit(value).netloc
                        ):
                            raise ValueError(label + ': cần URL http hoặc https hợp lệ.')
                        if '\n' in str(value) or '\r' in str(value) or '\x00' in str(value):
                            raise ValueError(label + ': giá trị không hợp lệ.')
                        updates[key] = value
                paths = {
                    '.env': Path(os.getenv('ENV_FILE', '.env')),
                    'config.conf': Path(os.getenv('CONF_FILE', 'config.conf')),
                }
                try:
                    for name, path in paths.items():
                        selected = {
                            k: v for k, v in updates.items() if (k in admin_mod.CONF_KEYS) == (name == 'config.conf')
                        }
                        base = '\n'.join(
                            line
                            for line in files[name].splitlines()
                            if not any(
                                re.match(r'^\s*(?:export\s+)?' + k + r'\s*=', line)
                                for k in updates
                                if k not in selected
                            )
                        ) + '\n'
                        with path.open('w', encoding='utf-8') as out:
                            out.write(admin_mod.update_text(base, selected))
                            out.flush()
                            os.fsync(out.fileno())
                except OSError:
                    for name, path in paths.items():
                        path.write_text(files[name], encoding='utf-8')
                    raise
                record('audit', 'save_config', 'ok', actorId=current_user.id)
                if os.getenv('MANAGED_RESTART') == '1':
                    threading.Thread(target=admin_mod.restart_process, daemon=True).start()
                return render_template(
                    'v2/admin/saved.html',
                    title='Đã lưu cấu hình',
                    automatic=os.getenv('MANAGED_RESTART') == '1',
                )
            except (ValueError, OSError):
                record('audit', 'save_config', 'error', actorId=current_user.id)
                error = 'Không lưu được. Kiểm tra giá trị (chu kỳ tối thiểu 30 giây), quyền ghi file hoặc tải lại nếu cấu hình vừa thay đổi.'
        elif request.method == 'POST':
            error = 'Phiên làm việc đã hết hạn. Tải lại trang rồi lưu lại.'
    return render_template(
        'v2/admin/index.html',
        title='Cấu hình hệ thống',
        groups=admin_mod.GROUPS,
        values=current_app.config,
        form=form,
        revision=admin_mod.revision(files),
        error=error,
    )
