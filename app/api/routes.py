from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request

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
        if not user or user.is_temporary:
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
