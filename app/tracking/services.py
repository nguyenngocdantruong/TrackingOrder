from datetime import datetime, timezone
from flask import current_app
from app.repos.trackings_repo import TrackingsRepo
from app.providers.registry import registry
from app.notifications.service import NotificationService

class TrackingService:
    @staticmethod
    def create_tracking_for_user(user, tracking_number, alias=None, carrier_id='auto', send_notification=True):
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
            'alias': alias,
            'isActive': True,
            'events': [],
            'lastEventHash': None,
            'currentStatus': 'Pending',
            'lastEventTime': None,
            'lastCheckedAt': None
        }

        tracking_id = TrackingsRepo.create(tracking_data)

        if send_notification and user.settings.get('notifyEnabled'):
            msg = f"➕ *Đã thêm vận đơn mới thành công!*\n" \
                  f"Mã: `{tracking_number}`\n" \
                  f"Tên: {alias or 'Không có'}\n" \
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

        return {
            'success': True,
            'tracking_id': tracking_id,
            'carrier_id': selected_carrier_id
        }

    @staticmethod
    def refresh_tracking(tracking_id):
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
            if user and user.settings.get('notifyEnabled'):
                status_emoji = "✅" if is_final and result.currentStatus != "Cancelled" else "📦"
                if "Cancel" in result.currentStatus or "Hủy" in result.currentStatus:
                    status_emoji = "❌"

                msg = f"{status_emoji} *Cập nhật đơn hàng: {tracking.get('alias') or tracking['trackingNumber']}*\n" \
                      f"Trạng thái: {result.currentStatus}\n" \
                      f"Thời gian: {provider.format_time(get_actual_time(final_events[0]))}\n" \
                      f"Tình trạng: {final_events[0]['name']}\n" \
                      f"Chi tiết: {final_events[0]['descBuyer']}"

                if is_final:
                    msg += "\n\n🏁 *Đơn hàng này đã hoàn tất. Ngừng theo dõi.*"

                NotificationService.send_to_user(user, msg)

        TrackingsRepo.update(tracking_id, update_data)
        return True
