from datetime import datetime, timezone
from flask import current_app
from app.repos.trackings_repo import TrackingsRepo
from app.providers.registry import registry
from app.notifications.telegram import TelegramNotifier

class TrackingService:
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
            if user and user.settings.get('notifyEnabled') and user.settings.get('telegramChatId'):
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

                TelegramNotifier.send_message(user.settings['telegramChatId'], msg)

        TrackingsRepo.update(tracking_id, update_data)
        return True
