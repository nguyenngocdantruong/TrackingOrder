from datetime import datetime, timezone
import re
from flask import current_app
from app.repos.trackings_repo import TrackingsRepo
from app.providers.registry import registry
from app.notifications.service import NotificationService
from app.tracking.stages import STAGE_LABELS, classify_event, wants_stage

_ZERO_WIDTH_RE = re.compile(r'[\u200b-\u200d\ufeff]')
MAX_COD_VND = 1_000_000_000


def normalize_tracking_number(raw: str) -> str:
    cleaned = _ZERO_WIDTH_RE.sub('', (raw or '')).strip()
    # Collapse accidental spaces around hyphen for J&T phone suffix (e.g. "842594- 9880")
    cleaned = re.sub(r'\s*-\s*', '-', cleaned)
    return cleaned.upper()


def parse_cod_amount(raw) -> tuple[int, str | None]:
    if raw is None:
        return 0, None
    if isinstance(raw, bool):
        return 0, 'Số tiền COD không hợp lệ.'
    if isinstance(raw, (int, float)):
        val = int(raw)
        if val < 0:
            return 0, 'Số tiền COD không được âm.'
        if val > MAX_COD_VND:
            return 0, 'Số tiền COD vượt quá giới hạn cho phép (tối đa 1.000.000.000 VND).'
        return val, None

    text = str(raw).strip()
    if not text:
        return 0, None
    # Strip currency symbols and thousand separators (".", ",", spaces)
    cleaned = re.sub(r'(?i)(vnd|vnđ|đ|\s|\.|,|_)', '', text)
    if cleaned.startswith('-'):
        return 0, 'Số tiền COD không được âm.'
    if not cleaned.isdigit():
        return 0, 'Vui lòng nhập số tiền COD hợp lệ (ví dụ: 250000 hoặc 250.000).'
    val = int(cleaned)
    if val > MAX_COD_VND:
        return 0, 'Số tiền COD vượt quá giới hạn cho phép (tối đa 1.000.000.000 VND).'
    return val, None


def sanitize_alias_and_note(alias, note) -> tuple[str | None, str | None]:
    clean_alias = _ZERO_WIDTH_RE.sub('', (alias or '')).strip()[:80] or None
    clean_note = _ZERO_WIDTH_RE.sub('', (note or '')).strip()[:240] or None
    return clean_alias, clean_note


class TrackingService:
    @staticmethod
    def create_tracking_for_user(
        user,
        tracking_number,
        alias=None,
        carrier_id='auto',
        send_notification=True,
        cod_amount=0,
        note=None,
    ):
        if not current_app.config.get('TRACKING_ENABLED', True):
            return {'success': False, 'error': 'Theo dõi đơn hàng đang tạm dừng.'}

        tracking_number = normalize_tracking_number(tracking_number)
        if not tracking_number:
            return {'success': False, 'error': 'Vui lòng nhập mã vận đơn.'}

        cod_val, cod_err = parse_cod_amount(cod_amount)
        if cod_err:
            return {'success': False, 'error': cod_err}

        clean_alias, clean_note = sanitize_alias_and_note(alias, note)

        # Prevent duplicate tracking for the same user before hitting external carrier APIs
        existing = TrackingsRepo.find_by_user_and_number(user.id, tracking_number)
        if existing:
            return {
                'success': False,
                'duplicate': True,
                'tracking_id': existing['id'],
                'carrier_id': existing.get('carrierId'),
                'error': 'Mã vận đơn này đã có trong danh sách theo dõi của bạn.',
            }

        selected_carrier_id = carrier_id

        if selected_carrier_id == 'auto':
            provider = registry.find_provider_for(tracking_number)
            if not provider:
                return {
                    'success': False,
                    'error': 'Không thể tự động nhận diện đơn vị vận chuyển cho mã vận đơn này.'
                }
            selected_carrier_id = provider.id
        else:
            provider = registry.get_provider(selected_carrier_id)
            if provider and not provider.supports(tracking_number):
                return {
                    'success': False,
                    'error': f'Mã vận đơn không hợp lệ cho đơn vị vận chuyển {provider.displayName}.'
                }

        # Check tracking first to ensure validity before creating record
        try:
            initial_result = provider.track(tracking_number)
        except Exception as e:
            return {
                'success': False,
                'error': f'Lỗi khi kiểm tra mã vận đơn: {str(e)}'
            }

        tracking_data = {
            'userId': user.id,
            'trackingNumber': tracking_number,
            'carrierId': selected_carrier_id,
            'alias': clean_alias,
            'codAmount': cod_val,
            'note': clean_note,
            'isActive': True,
            'events': [],
            'lastEventHash': None,
            'currentStatus': 'Pending',
            'lastEventTime': None,
            'lastCheckedAt': None
        }

        tracking_id = TrackingsRepo.create(tracking_data)

        if send_notification and user.settings.get('notifyEnabled'):
            cod_line = f"COD: {cod_val:,} ₫\n".replace(',', '.') if cod_val > 0 else ""
            msg = f"➕ *Đã thêm vận đơn mới thành công!*\n" \
                  f"Mã: `{tracking_number}`\n" \
                  f"Tên: {clean_alias or 'Không có'}\n" \
                  f"{cod_line}" \
                  f"Hãng: {selected_carrier_id.upper()}\n\n" \
                  f"Hệ thống sẽ bắt đầu đồng bộ dữ liệu ngay bây giờ."
            NotificationService.send_to_user(user, msg)

        # We already have the initial result, so update the record immediately without re-fetching
        # But for simplicity and to reuse the logic in refresh_tracking (merging, sorting, saving),
        # we can just call refresh_tracking. Since we just verified it works, it should work again.
        # To avoid double request, we could pass initial_result to refresh_tracking if we refactor it,
        # but one extra request is acceptable for now to keep code simple.
        # Or better: catch exception here just in case it fails transiently
        try:
             TrackingService.refresh_tracking(tracking_id)
        except Exception:
             pass # Already warned user if initial check failed, this is background sync

        try:
            from app.api.webhooks import PartnerWebhookService
            PartnerWebhookService.notify_tracking_created(user, tracking_id)
        except Exception:
            pass

        return {
            'success': True,
            'tracking_id': tracking_id,
            'carrier_id': selected_carrier_id
        }

    @staticmethod
    def refresh_tracking(tracking_id):
        if not current_app.config.get("TRACKING_ENABLED", True):
            return False
        tracking = TrackingsRepo.get_by_id(tracking_id)
        if not tracking:
            return False

        provider = registry.get_provider(tracking['carrierId'])
        if not provider:
            return False

        result = provider.track(tracking['trackingNumber'])

        # Merge events
        existing_events = tracking.get('events', [])
        existing_hashes = {e['eventHash'] for e in existing_events}

        new_events = []
        for event in result.events:
            if event.eventHash not in existing_hashes:
                new_events.append(event.to_dict())
                existing_hashes.add(event.eventHash)

        has_changes = len(new_events) > 0

        # Combine and sort, keep MAX
        all_events = new_events + existing_events

        # Ensure actualTime is comparable
        def get_actual_time(e):
            t = e.get('actualTime')
            if isinstance(t, str):
                try:
                    return datetime.fromisoformat(t.replace('Z', '+00:00'))
                except ValueError:
                    return datetime.min.replace(tzinfo=timezone.utc)
            return t or datetime.min.replace(tzinfo=timezone.utc)

        all_events.sort(key=get_actual_time, reverse=True)
        max_events = current_app.config.get('MAX_EVENTS_PER_TRACKING', 50)
        final_events = all_events[:max_events]

        update_data = {
            'lastCheckedAt': datetime.now(timezone.utc),
            'events': final_events,
            'currentStatus': result.currentStatus,
            'lastEventTime': result.lastEventTime
        }

        # Check if tracking reached final status
        is_final = provider.is_final_status(result.events)
        if is_final:
            update_data['isActive'] = False

        if has_changes and final_events:
            update_data['lastEventHash'] = final_events[0]['eventHash']
            # Trigger notification
            from app.repos.users_repo import UsersRepo
            user = UsersRepo.get_by_id(tracking['userId'])
            if user and user.settings.get('notifyEnabled', True):
                # Initial sync is a snapshot, not a replay of the entire history.
                # Later polls can contain multiple events, including the same stage.
                notification_events = (
                    sorted(new_events, key=get_actual_time) if existing_events
                    else final_events[:1]
                )
                for event in notification_events:
                    stage = classify_event(tracking['carrierId'], event)
                    if stage is None:
                        current_app.logger.info(
                            "Unmapped shipment event: carrier=%s code=%s milestone=%s",
                            tracking['carrierId'], event.get('code'), event.get('milestoneCode'),
                        )
                    if not wants_stage(user.settings, stage):
                        continue

                    status_emoji = "✅" if stage == 'delivered' else "📦"
                    stage_label = STAGE_LABELS.get(stage) or event.get('milestoneName') or event.get('name', '')
                    # Describe this event, not the latest status of the shipment:
                    # a poll can include both warehouse and delivery events.
                    msg = f"{status_emoji} *Cập nhật đơn hàng: {tracking.get('alias') or tracking['trackingNumber']}*\n" \
                          f"Trạng thái: {stage_label}\n" \
                          f"Thời gian: {provider.format_time(get_actual_time(event))}\n" \
                          f"Tình trạng: {event.get('name', '')}\n" \
                          f"Chi tiết: {event.get('descBuyer', '')}"

                    if is_final and event['eventHash'] == final_events[0]['eventHash']:
                        msg += "\n\n🏁 *Đơn hàng này đã hoàn tất. Ngừng theo dõi.*"

                    NotificationService.send_to_user(user, msg)

        TrackingsRepo.update(tracking_id, update_data)

        if has_changes and final_events:
            try:
                from app.repos.users_repo import UsersRepo
                from app.api.webhooks import PartnerWebhookService
                webhook_user = UsersRepo.get_by_id(tracking['userId'])
                PartnerWebhookService.notify_tracking_updated(
                    webhook_user,
                    tracking_id,
                    is_final=is_final,
                    new_events=new_events,
                )
            except Exception:
                pass

        return True
