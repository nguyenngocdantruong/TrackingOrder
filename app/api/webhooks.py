from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit

import requests
from flask import current_app

from app.operations import record

from app.providers.registry import registry as provider_registry
from app.repos.trackings_repo import TrackingsRepo
from app.repos.users_repo import UsersRepo

SUPPORTED_WEBHOOK_EVENTS = (
    'tracking.created',
    'tracking.updated',
    'tracking.completed',
)

_CARRIER_NAMES = {
    'spx_vn': 'Shopee Express VN',
    'lex': 'Lazada Express',
    'jt_express': 'J&T Express',
}


def generate_api_key() -> tuple[str, str, str]:
    token = secrets.token_urlsafe(24)
    raw_key = f'oth_live_{token}'
    key_hash = hash_api_key(raw_key)
    key_prefix = f'{raw_key[:15]}…{raw_key[-4:]}'
    return raw_key, key_hash, key_prefix


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256((raw_key or '').strip().encode('utf-8')).hexdigest()


def generate_webhook_secret() -> str:
    return f'whsec_{secrets.token_urlsafe(24)}'


def sign_webhook_payload(secret: str, timestamp: int, raw_body: bytes) -> str:
    signed_input = f'{timestamp}.'.encode('utf-8') + raw_body
    digest = hmac.new((secret or '').encode('utf-8'), signed_input, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


def _iso_utc(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        dt = val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    if isinstance(val, str):
        return val
    return str(val)


def serialize_tracking(tracking_id: str, tracking: dict) -> dict:
    cid = tracking.get('carrierId', '')
    provider = provider_registry.get_provider(cid)
    carrier_name = _CARRIER_NAMES.get(
        cid,
        provider.displayName if (provider and provider.displayName != provider.displayName.upper()) else cid.upper(),
    )

    events_out = []
    for ev in tracking.get('events') or []:
        loc = ev.get('currentLocation') or {}
        events_out.append({
            'eventHash': ev.get('eventHash'),
            'code': ev.get('code'),
            'name': ev.get('name'),
            'description': ev.get('descBuyer') or ev.get('descSeller') or '',
            'milestoneCode': ev.get('milestoneCode'),
            'milestoneName': ev.get('milestoneName'),
            'actualTime': _iso_utc(ev.get('actualTime')),
            'location': {
                'name': loc.get('name'),
                'address': loc.get('address'),
            } if (loc.get('name') or loc.get('address')) else None,
        })

    return {
        'id': tracking_id,
        'trackingNumber': tracking.get('trackingNumber'),
        'carrierId': cid,
        'carrierName': carrier_name,
        'alias': tracking.get('alias'),
        'codAmount': int(tracking.get('codAmount') or 0),
        'note': tracking.get('note'),
        'externalRef': tracking.get('externalRef'),
        'isActive': bool(tracking.get('isActive', True)),
        'currentStatus': tracking.get('currentStatus') or 'Pending',
        'lastEventTime': _iso_utc(tracking.get('lastEventTime')),
        'lastCheckedAt': _iso_utc(tracking.get('lastCheckedAt')),
        'events': events_out,
    }


def validate_webhook_url(url: str, allow_local: bool = False) -> tuple[bool, str | None]:
    cleaned = (url or '').strip()
    if not cleaned:
        return True, None

    parsed = urlsplit(cleaned)
    hostname = (parsed.hostname or '').lower()
    if not hostname:
        return False, 'URL webhook không hợp lệ.'

    is_local_host = hostname in ('localhost', '127.0.0.1', '::1')
    if allow_local and is_local_host and parsed.scheme in ('http', 'https'):
        return True, None

    if parsed.scheme != 'https':
        return False, 'Webhook URL bắt buộc sử dụng giao thức HTTPS.'

    if is_local_host:
        return False, 'Không cho phép trỏ webhook tới địa chỉ nội bộ (localhost).'

    try:
        ip_obj = ipaddress.ip_address(hostname)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
            return False, 'Không cho phép trỏ webhook tới dải IP nội bộ.'
    except ValueError:
        # Hostname is a domain name; check resolved IPs if resolvable
        try:
            infos = socket.getaddrinfo(hostname, None)
            for info in infos:
                addr = info[4][0]
                ip_obj = ipaddress.ip_address(addr)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
                    return False, 'Tên miền webhook phân giải về địa chỉ IP nội bộ không được phép.'
        except socket.gaierror:
            pass

    return True, None


class PartnerWebhookService:
    @staticmethod
    def _deliver_sync(app, user_id: str, partner_cfg: dict, event_type: str, payload_data: dict) -> dict:
        webhook_url = (partner_cfg.get('webhookUrl') or '').strip()
        secret = partner_cfg.get('webhookSecret') or ''
        delivery_id = f'evt_{secrets.token_hex(12)}'
        now_ts = int(time.time())
        now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        envelope = {
            'id': delivery_id,
            'event': event_type,
            'createdAt': now_iso,
            'data': payload_data,
        }
        raw_body = json.dumps(envelope, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        signature = sign_webhook_payload(secret, now_ts, raw_body)

        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'User-Agent': 'OrderTrackingHub-Webhook/1.0',
            'X-OrderTracker-Event': event_type,
            'X-OrderTracker-Delivery': delivery_id,
            'X-OrderTracker-Timestamp': str(now_ts),
            'X-OrderTracker-Signature': signature,
        }

        status_code = 0
        delivered = False
        err_msg = None
        try:
            resp = requests.post(webhook_url, data=raw_body, headers=headers, timeout=8)
            status_code = resp.status_code
            delivered = 200 <= status_code < 300
            if not delivered:
                err_msg = f'HTTP {status_code}'
        except Exception as exc:
            err_msg = str(exc)

        try:
            with app.app_context():
                record('webhook', event_type, 'ok' if delivered else 'error',
                       userId=user_id, deliveryId=delivery_id, statusCode=status_code,
                       trackingId=(payload_data.get('tracking') or {}).get('id'))
                fresh_user = UsersRepo.get_by_id(user_id)
                merged = dict((fresh_user.partner_api if fresh_user else partner_cfg) or {})
                merged.update({
                    'lastDeliveryId': delivery_id,
                    'lastDeliveryAt': now_iso,
                    'lastDeliveryEvent': event_type,
                    'lastDeliveryStatus': status_code,
                    'lastDeliveryOk': delivered,
                    'lastDeliveryError': err_msg,
                })
                UsersRepo.update_partner_api(user_id, merged)
        except Exception:
            pass

        return {
            'delivered': delivered,
            'deliveryId': delivery_id,
            'statusCode': status_code,
            'error': err_msg,
            'timestamp': now_iso,
        }

    @staticmethod
    def dispatch(user, event_type: str, payload_data: dict, async_send: bool = True) -> dict | None:
        if not user or getattr(user, 'suspended', False):
            return None
        partner_cfg = dict(getattr(user, 'partner_api', None) or {})
        webhook_url = (partner_cfg.get('webhookUrl') or '').strip()
        if not webhook_url:
            return None

        if event_type != 'webhook.test':
            if not partner_cfg.get('webhookEnabled', False):
                return None
            subscribed = partner_cfg.get('webhookEvents') or list(SUPPORTED_WEBHOOK_EVENTS)
            if event_type not in subscribed:
                return None

        allow_local = bool(current_app.config.get('TESTING') or current_app.config.get('DEBUG'))
        ok, reason = validate_webhook_url(webhook_url, allow_local=allow_local)
        if not ok:
            return {'delivered': False, 'statusCode': 0, 'error': reason}

        app_obj = current_app._get_current_object()
        if async_send:
            threading.Thread(
                target=PartnerWebhookService._deliver_sync,
                args=(app_obj, user.id, partner_cfg, event_type, payload_data),
                daemon=True,
            ).start()
            return {'queued': True}

        return PartnerWebhookService._deliver_sync(app_obj, user.id, partner_cfg, event_type, payload_data)

    @staticmethod
    def notify_tracking_created(user, tracking_id: str):
        partner_cfg = getattr(user, 'partner_api', None) or {}
        if not partner_cfg.get('webhookEnabled') or not partner_cfg.get('webhookUrl'):
            return
        tracking = TrackingsRepo.get_by_id(tracking_id)
        if not tracking:
            return
        serialized = serialize_tracking(tracking_id, tracking)
        PartnerWebhookService.dispatch(user, 'tracking.created', {'tracking': serialized}, async_send=True)

    @staticmethod
    def notify_tracking_updated(user, tracking_id: str, is_final: bool = False, new_events: list | None = None):
        if not user:
            return
        partner_cfg = getattr(user, 'partner_api', None) or {}
        if not partner_cfg.get('webhookEnabled') or not partner_cfg.get('webhookUrl'):
            return
        tracking = TrackingsRepo.get_by_id(tracking_id)
        if not tracking:
            return
        serialized = serialize_tracking(tracking_id, tracking)
        latest_checkpoint = serialized['events'][0] if serialized.get('events') else None
        payload = {
            'tracking': serialized,
            'latestCheckpoint': latest_checkpoint,
            'newEventsCount': len(new_events or []),
        }
        PartnerWebhookService.dispatch(user, 'tracking.updated', payload, async_send=True)
        if is_final:
            PartnerWebhookService.dispatch(user, 'tracking.completed', payload, async_send=True)
