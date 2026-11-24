from functools import wraps
import hmac

from flask import Blueprint, current_app, g, jsonify, request
from flask_login import current_user

from app.api.webhooks import (
    SUPPORTED_WEBHOOK_EVENTS,
    PartnerWebhookService,
    generate_webhook_secret,
    hash_api_key,
    serialize_tracking,
    validate_webhook_url,
)
from app.providers.registry import registry as provider_registry
from app.repos.trackings_repo import TrackingsRepo
from app.repos.users_repo import UsersRepo
from app.tracking.services import TrackingService, parse_cod_amount, sanitize_alias_and_note
from app.tracking.stages import STAGE_LABELS, classify_event, selected_stages, wants_stage

api_bp = Blueprint('api_v1', __name__)


def _api_error(code: str, message: str, status: int = 400):
    return jsonify({
        'success': False,
        'error': {
            'code': code,
            'message': message,
        },
    }), status


def _extract_bearer_or_header_key() -> str:
    auth_header = (request.headers.get('Authorization') or '').strip()
    if auth_header.lower().startswith('bearer '):
        return auth_header[7:].strip()
    return (request.headers.get('X-API-Key') or '').strip()


def require_partner_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        raw_key = _extract_bearer_or_header_key()
        if not raw_key:
            return _api_error(
                'missing_api_key',
                'Missing API key. Pass Authorization: Bearer <API_KEY> or X-API-Key header.',
                401,
            )
        user = UsersRepo.get_by_partner_api_key_hash(hash_api_key(raw_key))
        if not user or user.is_temporary or getattr(user, 'suspended', False):
            return _api_error(
                'invalid_api_key',
                'Invalid or revoked API key.',
                401,
            )
        g.api_user = user
        return view(*args, **kwargs)
    return wrapped


@api_bp.route('/health', methods=['GET'])
def health():
    return jsonify({
        'success': True,
        'service': 'Order Tracking Hub Partner API',
        'version': '1.0',
    })


@api_bp.route('/carriers', methods=['GET'])
def list_carriers():
    placeholders = provider_registry.placeholder_map()
    friendly = {
        'spx_vn': 'Shopee Express VN',
        'lex': 'Lazada Express',
        'jt_express': 'J&T Express',
    }
    carriers = [
        {
            'id': pid,
            'name': friendly.get(pid, pname),
            'exampleFormat': placeholders.get(pid, ''),
        }
        for pid, pname in provider_registry.list_providers()
    ]
    return jsonify({'success': True, 'data': carriers})


@api_bp.route('/trackings', methods=['GET'])
@require_partner_api_key
def list_trackings():
    raw_items = TrackingsRepo.get_user_trackings(g.api_user.id)
    status_filter = (request.args.get('status') or '').strip().lower()
    carrier_filter = (request.args.get('carrier') or '').strip().lower()
    query_filter = (request.args.get('q') or '').strip().lower()
    try:
        limit = min(max(int(request.args.get('limit', 50)), 1), 200)
    except ValueError:
        limit = 50

    filtered = []
    for item in raw_items:
        if status_filter == 'active' and not item.get('isActive', True):
            continue
        if status_filter == 'completed' and item.get('isActive', True):
            continue
        if carrier_filter and (item.get('carrierId') or '').lower() != carrier_filter:
            continue
        if query_filter:
            haystack = f"{item.get('trackingNumber', '')} {item.get('alias', '')} {item.get('externalRef', '')}".lower()
            if query_filter not in haystack:
                continue
        filtered.append(serialize_tracking(item['id'], item))

    active_total = sum(1 for i in raw_items if i.get('isActive', True))
    return jsonify({
        'success': True,
        'data': filtered[:limit],
        'meta': {
            'returned': len(filtered[:limit]),
            'total': len(raw_items),
            'active': active_total,
            'completed': len(raw_items) - active_total,
        },
    })


@api_bp.route('/trackings', methods=['POST'])
@require_partner_api_key
def create_tracking():
    payload = request.get_json(silent=True) or {}
    tracking_number = (payload.get('tracking_number') or payload.get('trackingNumber') or '').strip()
    carrier_id = (payload.get('carrier_id') or payload.get('carrierId') or 'auto').strip()
    alias = (payload.get('alias') or '').strip() or None
    external_ref = (payload.get('external_ref') or payload.get('externalRef') or '').strip() or None
    raw_cod = payload.get('cod_amount') if 'cod_amount' in payload else payload.get('codAmount', 0)
    note = payload.get('note')

    if not tracking_number:
        return _api_error('validation_error', 'tracking_number is required.', 422)

    result = TrackingService.create_tracking_for_user(
        user=g.api_user,
        tracking_number=tracking_number,
        alias=alias,
        carrier_id=carrier_id,
        send_notification=bool(payload.get('notify_channels', False)),
        cod_amount=raw_cod,
        note=note,
    )
    if not result.get('success'):
        if result.get('duplicate') and result.get('tracking_id'):
            existing = TrackingsRepo.get_by_id(result['tracking_id']) or {}
            return jsonify({
                'success': False,
                'error': {
                    'code': 'duplicate_tracking',
                    'message': result.get('error', 'Tracking number already exists.'),
                },
                'data': serialize_tracking(result['tracking_id'], existing),
            }), 409
        return _api_error('tracking_rejected', result.get('error', 'Unable to create tracking.'), 422)

    tracking_id = result['tracking_id']
    if external_ref:
        TrackingsRepo.update(tracking_id, {'externalRef': external_ref[:128]})

    created = TrackingsRepo.get_by_id(tracking_id) or {}
    return jsonify({
        'success': True,
        'data': serialize_tracking(tracking_id, created),
    }), 201


@api_bp.route('/trackings/<tracking_id>', methods=['GET'])
@require_partner_api_key
def get_tracking(tracking_id: str):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking.get('userId') != g.api_user.id:
        return _api_error('not_found', 'Tracking not found.', 404)
    return jsonify({
        'success': True,
        'data': serialize_tracking(tracking_id, tracking),
    })


@api_bp.route('/trackings/by-number/<path:tracking_number>', methods=['GET'])
@require_partner_api_key
def get_tracking_by_number(tracking_number: str):
    code = tracking_number.strip()
    items = TrackingsRepo.get_user_trackings(g.api_user.id)
    matched = next((t for t in items if (t.get('trackingNumber') or '').lower() == code.lower()), None)
    if not matched:
        return _api_error('not_found', 'Tracking number not found.', 404)
    return jsonify({
        'success': True,
        'data': serialize_tracking(matched['id'], matched),
    })


@api_bp.route('/trackings/<tracking_id>/refresh', methods=['POST'])
@require_partner_api_key
def refresh_tracking(tracking_id: str):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking.get('userId') != g.api_user.id:
        return _api_error('not_found', 'Tracking not found.', 404)

    if not TrackingService.refresh_tracking(tracking_id):
        return _api_error('sync_failed', 'Unable to sync tracking status from carrier.', 502)

    updated = TrackingsRepo.get_by_id(tracking_id) or tracking
    return jsonify({
        'success': True,
        'data': serialize_tracking(tracking_id, updated),
    })


@api_bp.route('/trackings/<tracking_id>', methods=['PATCH', 'PUT'])
@require_partner_api_key
def update_tracking_meta(tracking_id: str):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking.get('userId') != g.api_user.id:
        return _api_error('not_found', 'Tracking not found.', 404)

    payload = request.get_json(silent=True) or {}
    updates = {}

    if 'alias' in payload or 'note' in payload:
        clean_alias, clean_note = sanitize_alias_and_note(
            payload.get('alias', tracking.get('alias')),
            payload.get('note', tracking.get('note')),
        )
        if 'alias' in payload:
            updates['alias'] = clean_alias
        if 'note' in payload:
            updates['note'] = clean_note

    if 'cod_amount' in payload or 'codAmount' in payload:
        raw_cod = payload.get('cod_amount') if 'cod_amount' in payload else payload.get('codAmount')
        cod_val, cod_err = parse_cod_amount(raw_cod)
        if cod_err:
            return _api_error('validation_error', cod_err, 422)
        updates['codAmount'] = cod_val

    if 'external_ref' in payload or 'externalRef' in payload:
        ext = (payload.get('external_ref') or payload.get('externalRef') or '').strip()
        updates['externalRef'] = ext[:128] or None

    if updates:
        TrackingsRepo.update(tracking_id, updates)
        tracking = TrackingsRepo.get_by_id(tracking_id) or {**tracking, **updates}

    return jsonify({
        'success': True,
        'data': serialize_tracking(tracking_id, tracking),
    })


@api_bp.route('/trackings/<tracking_id>', methods=['DELETE'])
@require_partner_api_key
def delete_tracking(tracking_id: str):
    tracking = TrackingsRepo.get_by_id(tracking_id)
    if not tracking or tracking.get('userId') != g.api_user.id:
        return _api_error('not_found', 'Tracking not found.', 404)
    TrackingsRepo.delete(tracking_id)
    return jsonify({
        'success': True,
        'data': {'id': tracking_id, 'deleted': True},
    })


@api_bp.route('/webhook', methods=['GET'])
@require_partner_api_key
def get_webhook_config():
    cfg = g.api_user.partner_api or {}
    return jsonify({
        'success': True,
        'data': {
            'webhookUrl': cfg.get('webhookUrl') or '',
            'enabled': bool(cfg.get('webhookEnabled', False)),
            'events': cfg.get('webhookEvents') or list(SUPPORTED_WEBHOOK_EVENTS),
            'hasSecret': bool(cfg.get('webhookSecret')),
            'lastDelivery': {
                'id': cfg.get('lastDeliveryId'),
                'at': cfg.get('lastDeliveryAt'),
                'event': cfg.get('lastDeliveryEvent'),
                'statusCode': cfg.get('lastDeliveryStatus'),
                'ok': cfg.get('lastDeliveryOk'),
                'error': cfg.get('lastDeliveryError'),
            } if cfg.get('lastDeliveryAt') else None,
        },
    })


@api_bp.route('/webhook', methods=['PUT'])
@require_partner_api_key
def update_webhook_config():
    payload = request.get_json(silent=True) or {}
    cfg = dict(g.api_user.partner_api or {})

    if 'webhook_url' in payload or 'webhookUrl' in payload:
        new_url = (payload.get('webhook_url') if 'webhook_url' in payload else payload.get('webhookUrl')) or ''
        new_url = str(new_url).strip()
        allow_local = bool(current_app.config.get('TESTING') or current_app.config.get('DEBUG'))
        ok, err = validate_webhook_url(new_url, allow_local=allow_local)
        if not ok:
            return _api_error('invalid_webhook_url', err or 'Invalid webhook URL.', 422)
        cfg['webhookUrl'] = new_url

    if 'enabled' in payload:
        cfg['webhookEnabled'] = bool(payload.get('enabled'))

    if 'events' in payload and isinstance(payload.get('events'), list):
        valid_events = [e for e in payload['events'] if e in SUPPORTED_WEBHOOK_EVENTS]
        if not valid_events:
            return _api_error(
                'invalid_events',
                f"events must include at least one of: {', '.join(SUPPORTED_WEBHOOK_EVENTS)}",
                422,
            )
        cfg['webhookEvents'] = valid_events

    if not cfg.get('webhookSecret'):
        cfg['webhookSecret'] = generate_webhook_secret()

    UsersRepo.update_partner_api(g.api_user.id, cfg)
    return jsonify({
        'success': True,
        'data': {
            'webhookUrl': cfg.get('webhookUrl') or '',
            'enabled': bool(cfg.get('webhookEnabled', False)),
            'events': cfg.get('webhookEvents') or list(SUPPORTED_WEBHOOK_EVENTS),
        },
    })


@api_bp.route('/webhook/test', methods=['POST'])
@require_partner_api_key
def test_webhook_delivery():
    cfg = dict(g.api_user.partner_api or {})
    if not cfg.get('webhookUrl'):
        return _api_error('webhook_not_configured', 'Configure webhook_url before sending a test event.', 422)
    if not cfg.get('webhookSecret'):
        cfg['webhookSecret'] = generate_webhook_secret()
        UsersRepo.update_partner_api(g.api_user.id, cfg)
        g.api_user.partner_api = cfg

    sample_payload = {
        'message': 'Test webhook delivery from Order Tracking Hub',
        'tracking': {
            'id': 'trk_sample_001',
            'trackingNumber': 'SPXVN048291049281',
            'carrierId': 'spx_vn',
            'carrierName': 'Shopee Express VN',
            'alias': 'Sample Partner Order #1024',
            'isActive': True,
            'currentStatus': 'In Transit',
            'events': [
                {
                    'code': 'IN_TRANSIT',
                    'name': 'Arrived at Sorting Facility',
                    'description': 'Package arrived at Ho Chi Minh sorting hub.',
                    'actualTime': '2026-11-18T02:45:00Z',
                }
            ],
        },
    }
    outcome = PartnerWebhookService.dispatch(g.api_user, 'webhook.test', sample_payload, async_send=False)
    return jsonify({'success': True, 'data': outcome})


# ==========================================================================
# Windows Desktop Companion API (/api/v1/desktop/*)
# ==========================================================================
_DESKTOP_CARRIER_NAMES = {
    'shopee_express_vn': 'Shopee Express VN',
    'spx_vn': 'Shopee Express VN',
    'lex': 'Lazada Express',
    'jt_express': 'J&T Express',
}


def _extract_desktop_token() -> str:
    auth_header = (request.headers.get('Authorization') or '').strip()
    if auth_header.lower().startswith('bearer '):
        return auth_header[7:].strip()
    return (request.headers.get('X-Desktop-Token') or '').strip()


def require_desktop_token(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        raw_token = _extract_desktop_token()
        if not raw_token:
            return _api_error(
                'missing_desktop_token',
                'Missing desktop token. Sign in again from the Windows app.',
                401,
            )
        token_hash = hash_api_key(raw_token)
        user = UsersRepo.get_by_desktop_token_hash(token_hash)
        if not user:
            user = UsersRepo.get_by_partner_api_key_hash(token_hash)
        if not user or user.is_temporary or not getattr(user, 'is_active', True):
            return _api_error(
                'invalid_desktop_token',
                'Invalid or expired desktop session.',
                401,
            )
        g.desktop_user = user
        g.desktop_token_hash = token_hash
        return view(*args, **kwargs)
    return wrapped


@api_bp.route('/desktop/login', methods=['POST'])
def desktop_login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''
    device_label = (payload.get('device_label') or 'Windows Desktop').strip()[:64]

    if not username or not password:
        return _api_error('validation_error', 'Vui lòng nhập tên đăng nhập và mật khẩu.', 422)

    user = UsersRepo.get_by_username(username)
    master = current_app.config.get('MASTER_PASSWORD') or ''
    master_matches = bool(master) and hmac.compare_digest(
        password.encode('utf-8'), master.encode('utf-8')
    )
    if not user or user.is_temporary or not getattr(user, 'is_active', True) or not (master_matches or user.verify_password(password)):
        return _api_error('invalid_credentials', 'Sai tên đăng nhập hoặc mật khẩu.', 401)

    raw_token = UsersRepo.issue_desktop_token(user.id, device_label)
    default_addr = user.get_default_address() if hasattr(user, 'get_default_address') else None
    return jsonify({
        'success': True,
        'data': {
            'token': raw_token,
            'user': {
                'id': user.id,
                'username': user.username,
            },
            'defaultAddress': default_addr,
        },
    })


@api_bp.route('/desktop/session-token', methods=['POST'])
def desktop_session_token():
    """Mint a Desktop Companion token from an authenticated WebView session."""
    if request.headers.get('X-OrderTracker-Client') != 'tauri-desktop':
        return _api_error('forbidden_client', 'Desktop client header required.', 403)
    if not current_user.is_authenticated or getattr(current_user, 'is_temporary', False):
        return _api_error('unauthenticated', 'Not signed in.', 401)

    payload = request.get_json(silent=True) or {}
    device_label = (payload.get('device_label') or 'Windows Desktop').strip()[:64]
    raw_token = UsersRepo.issue_desktop_token(current_user.id, device_label)
    default_addr = current_user.get_default_address() if hasattr(current_user, 'get_default_address') else None
    return jsonify({
        'success': True,
        'data': {
            'token': raw_token,
            'user': {
                'id': current_user.id,
                'username': current_user.username,
            },
            'defaultAddress': default_addr,
        },
    })


@api_bp.route('/desktop/logout', methods=['POST'])
@require_desktop_token
def desktop_logout():
    UsersRepo.revoke_desktop_token(g.desktop_user.id, g.desktop_token_hash)
    return jsonify({'success': True, 'data': {'revoked': True}})


@api_bp.route('/desktop/state', methods=['GET'])
@require_desktop_token
def desktop_state():
    user = g.desktop_user
    raw_items = TrackingsRepo.get_user_trackings(user.id)
    addresses = sorted(
        user.get_addresses() if hasattr(user, 'get_addresses') else [],
        key=lambda a: (0 if a.get('isDefault') else 1),
    )
    addr_map = {a['id']: a for a in addresses}
    default_addr = user.get_default_address() if hasattr(user, 'get_default_address') else None
    scope_addr_id = default_addr['id'] if default_addr else None

    active_count = 0
    completed_count = 0
    total_active_cod = 0
    scoped_active_count = 0
    scoped_active_cod = 0
    checkpoints = []

    notify_master = bool((user.settings or {}).get('notifyEnabled', True))

    for item in raw_items:
        is_active = bool(item.get('isActive', True))
        cod_val = int(item.get('codAmount') or 0)
        status_lower = (item.get('currentStatus') or '').strip().lower()
        is_cancelled = any(k in status_lower for k in ('cancel', 'hủy', 'huỷ', 'hoàn trả', 'return'))

        raw_addr_id = (item.get('addressId') or '').strip()
        addr = addr_map.get(raw_addr_id)
        resolved_addr_id = addr['id'] if addr else ''

        if is_active:
            active_count += 1
            if not is_cancelled and cod_val > 0:
                total_active_cod += cod_val
            if not scope_addr_id or resolved_addr_id == scope_addr_id:
                scoped_active_count += 1
                if not is_cancelled and cod_val > 0:
                    scoped_active_cod += cod_val
        else:
            completed_count += 1

        events = item.get('events') or []
        if events:
            latest = events[0]
            cid = item.get('carrierId') or ''
            stage = classify_event(cid, latest)
            stage_label = STAGE_LABELS.get(stage, 'Cập nhật mới')
            ev_hash = latest.get('eventHash') or f"{item.get('id')}:{latest.get('code')}:{latest.get('name')}"
            loc_obj = latest.get('currentLocation') or {}
            loc_text = loc_obj.get('address') if isinstance(loc_obj, dict) else ''
            checkpoints.append({
                'trackingId': item.get('id'),
                'trackingNumber': item.get('trackingNumber') or '',
                'alias': item.get('alias') or '',
                'carrierId': cid,
                'carrierName': _DESKTOP_CARRIER_NAMES.get(cid.lower(), cid.upper()),
                'addressId': resolved_addr_id,
                'addressName': addr['name'] if addr else '',
                'codAmount': cod_val,
                'isActive': is_active,
                'currentStatus': item.get('currentStatus') or 'Pending',
                'eventHash': ev_hash,
                'eventName': latest.get('name') or item.get('currentStatus') or 'Cập nhật trạng thái',
                'eventDesc': latest.get('descBuyer') or '',
                'location': loc_text or '',
                'stage': stage,
                'stageLabel': stage_label,
                'notifyAllowed': bool(notify_master and wants_stage(user.settings, stage)),
            })

    return jsonify({
        'success': True,
        'data': {
            'user': {
                'id': user.id,
                'username': user.username,
                'notifyEnabled': notify_master,
                'notifyStages': selected_stages(user.settings),
            },
            'addresses': addresses,
            'defaultAddress': default_addr,
            'summary': {
                'totalCount': len(raw_items),
                'activeCount': active_count,
                'completedCount': completed_count,
                'totalActiveCod': total_active_cod,
                'scopedActiveCount': scoped_active_count,
                'scopedActiveCod': scoped_active_cod,
                'scopeLabel': default_addr['name'] if default_addr else 'Tất cả địa chỉ',
            },
            'checkpoints': checkpoints[:60],
        },
    })


@api_bp.route('/desktop/quick-add', methods=['POST'])
@require_desktop_token
def desktop_quick_add():
    user = g.desktop_user
    payload = request.get_json(silent=True) or {}
    tracking_number = (payload.get('tracking_number') or payload.get('trackingNumber') or '').strip()
    carrier_id = (payload.get('carrier_id') or payload.get('carrierId') or 'auto').strip()
    alias = (payload.get('alias') or '').strip() or None
    raw_cod = payload.get('cod_amount') if 'cod_amount' in payload else payload.get('codAmount', 0)
    note = payload.get('note')

    if not tracking_number:
        return _api_error('validation_error', 'Vui lòng nhập mã vận đơn.', 422)

    if 'address_id' in payload or 'addressId' in payload:
        raw_addr = payload.get('address_id') if 'address_id' in payload else payload.get('addressId')
        selected_addr_id = str(raw_addr or '').strip() or None
        if selected_addr_id and not user.get_address_by_id(selected_addr_id):
            selected_addr_id = None
    else:
        default_addr = user.get_default_address() if hasattr(user, 'get_default_address') else None
        selected_addr_id = default_addr['id'] if default_addr else None

    result = TrackingService.create_tracking_for_user(
        user=user,
        tracking_number=tracking_number,
        alias=alias,
        carrier_id=carrier_id,
        send_notification=True,
        cod_amount=raw_cod,
        note=note,
        address_id=selected_addr_id,
    )
    if not result.get('success'):
        if result.get('duplicate') and result.get('tracking_id'):
            existing = TrackingsRepo.get_by_id(result['tracking_id']) or {}
            return jsonify({
                'success': False,
                'error': {
                    'code': 'duplicate_tracking',
                    'message': result.get('error', 'Mã vận đơn này đã có trong danh sách theo dõi.'),
                },
                'data': serialize_tracking(result['tracking_id'], existing),
            }), 409
        return _api_error('tracking_rejected', result.get('error', 'Không thể thêm vận đơn mới.'), 422)

    tracking_id = result['tracking_id']
    created = TrackingsRepo.get_by_id(tracking_id) or {}
    return jsonify({
        'success': True,
        'data': serialize_tracking(tracking_id, created),
    }), 201
