import json

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.payments.base import DonationRequest
from app.payments.forms import SupportForm
from app.payments.registry import get_default_gateway, registry
from app.notifications.telegram import TelegramNotifier
from app.repos.users_repo import UsersRepo

payments_bp = Blueprint('payments', __name__)
_pending_donations = {}


@payments_bp.route('/support', methods=['GET', 'POST'])
def support():
    form = SupportForm()
    donation_default = current_app.config.get('PAYOS_DONATION_AMOUNT', 50000)
    gateway = registry.get_gateway('payos') or get_default_gateway()

    if request.method == 'GET' and form.amount.data is None:
        form.amount.data = donation_default

    if form.validate_on_submit():
        if not gateway:
            flash('Cổng thanh toán chưa sẵn sàng. Vui lòng thử lại sau.', 'danger')
            return redirect(url_for('payments.support'))

        donation = DonationRequest(
            name=form.name.data.strip(),
            email=form.email.data.strip(),
            message=form.message.data.strip() if form.message.data else '',
            amount=form.amount.data,
        )

        try:
            payment_link = gateway.create_donation_link(donation)
        except Exception as exc:  # pragma: no cover - bubble up user-friendly message only
            current_app.logger.exception("Failed to create donation link: %s", exc)
            flash('Không thể tạo liên kết thanh toán. Vui lòng thử lại.', 'danger')
            return redirect(url_for('payments.support'))

        current_app.logger.info("[Payment] Created donation link for %s amount=%s", donation.email, _format_amount(donation.amount))
        # Store pending donation info by order_code for webhook enrichment
        try:
            order_code = getattr(payment_link, 'order_code', None)
            if order_code:
                _pending_donations[order_code] = {
                    'name': donation.name,
                    'email': donation.email,
                    'message': donation.message,
                    'amount': donation.amount,
                }
                current_app.logger.info('[Payment] Pending donation stored order_code=%s', order_code)
        except Exception as exc:
            current_app.logger.warning('[Payment] Failed to store pending donation: %s', exc)
        return redirect(payment_link.url)

    return render_template('payments/support.html', title='Ủng hộ', form=form, gateway_ready=bool(gateway))


@payments_bp.route('/return')
def return_result():
    flash('Cảm ơn bạn đã ủng hộ!', 'success')
    if current_user.is_authenticated:
        return redirect(url_for('tracking.dashboard'))
    return redirect(url_for('index'))


@payments_bp.route('/cancel')
def cancel():
    flash('Giao dịch đã được hủy.', 'warning')
    if current_user.is_authenticated:
        return redirect(url_for('payments.support'))
    return redirect(url_for('index'))


@payments_bp.route('/webhook', methods=['POST'])
def webhook():
    if not _is_secure_webhook_request():
        current_app.logger.warning('Rejecting webhook: insecure transport and not localhost testing')
        return {'error': 'Webhook requires HTTPS or localhost testing'}, 400

    gateway = registry.get_gateway('payos') or get_default_gateway()
    if not gateway:
        current_app.logger.error('No payment gateway configured for webhook')
        return {'error': 'Gateway not configured'}, 503

    raw_payload = request.get_data()
    raw_json = None
    try:
        raw_decoded = raw_payload.decode('utf-8', errors='replace')
        current_app.logger.info('[Payment] Webhook raw payload: %s', raw_decoded)
        raw_json = json.loads(raw_decoded)
    except Exception as exc:
        current_app.logger.warning('[Payment] Unable to decode raw payload: %s', exc)
    try:
        result = gateway.verify_webhook(raw_payload)
    except Exception as exc:
        current_app.logger.warning('Webhook signature validation failed: %s', exc)
        return {'error': 'Invalid signature'}, 400

    code = _get_attr(result, 'code')
    success = _get_attr(result, 'success', None)
    if success is None:
        success = (code == '00')
    data = _get_attr(result, 'data', {}) or {}

    if (not data) and isinstance(raw_json, dict):
        data = raw_json.get('data', {}) or data
        current_app.logger.info('[Payment] Fallback to raw_json data keys=%s', list(data.keys()) if isinstance(data, dict) else type(data))

    current_app.logger.info('[Payment] Webhook parsed code=%s success=%s data_keys=%s', code, success, list(data.keys()) if isinstance(data, dict) else type(data))
    try:
        current_app.logger.info('[Payment] Webhook data preview=%s', data)
    except Exception:
        pass

    if code != '00' or not success:
        current_app.logger.info('Webhook not successful: code=%s success=%s payload=%s', code, success, data)
        return {'error': 'Webhook not successful'}, 400

    order_code = _get_attr(data, 'orderCode')
    current_app.logger.info('[Payment] Webhook verified: orderCode=%s amount=%s', order_code, _format_amount(_get_attr(data, 'amount', 0)))
    _notify_donation_payload(data, order_code)
    return {'status': 'ok'}


def _format_amount(amount: int) -> str:
    try:
        return f"{amount:,.0f} VND".replace(",", ".")
    except Exception:
        return f"{amount} VND"


def _notify_donation_payload(data, order_code=None):
    raw_amount = _get_attr(data, 'amount', 0)
    amount = _coerce_amount(raw_amount)
    name = _get_attr(data, 'buyerName') or _get_attr(data, 'buyer_name') or _get_attr(data, 'customerName') or 'bạn'
    note = _get_attr(data, 'description')

    # Enrich from pending map if available
    if order_code and order_code in _pending_donations:
        pending = _pending_donations.pop(order_code, {})
        name = pending.get('name') or name
        note = pending.get('message') or note
        if not raw_amount:
            raw_amount = pending.get('amount', raw_amount)
            amount = _coerce_amount(raw_amount)
        current_app.logger.info('[Payment] Enriched from pending order_code=%s name=%s amount=%s note=%s', order_code, name, amount, note)

    current_app.logger.info('[Payment] Notify payload: amount_raw=%s amount_parsed=%s name=%s note=%s', raw_amount, amount, name, note)

    msg_lines = [f"🎉 Cảm ơn đại gia {name} đã ủng hộ {_format_amount(amount)} cho tại hạ!"]
    if note:
        msg_lines.append(f"📝 Lời nhắn: {note}")
    msg = "\n".join(msg_lines)

    notify_all = current_app.config.get('DONATE_NOTIFY_ALL', False)
    recipients = set()
    if notify_all:
        recipients.update(UsersRepo.list_telegram_chat_ids())
    else:
        admin_id = current_app.config.get('ADMIN_TELEGRAM_USER_ID')
        if admin_id:
            recipients.add(str(admin_id))

    current_app.logger.info('[Payment] Notify recipients: %s', list(recipients))

    for chat_id in recipients:
        TelegramNotifier.send_message(chat_id, msg, parse_mode=None)


def _is_secure_webhook_request() -> bool:
    website_url = current_app.config.get('WEBSITE_URL', '')
    if website_url.startswith('https://'):
        return True

    host = (request.host or '').split(':')[0]
    return host in ['127.0.0.1', 'localhost']


def _get_attr(obj, key, default=None):
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def _coerce_amount(value):
    try:
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        value_str = str(value).strip().replace(',', '').replace('.', '')
        return int(value_str)
    except Exception:
        return 0
