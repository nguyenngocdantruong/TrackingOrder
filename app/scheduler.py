import atexit
from datetime import timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from app.repos.trackings_repo import TrackingsRepo
from app.tracking.services import TrackingService
from app.power_outage.service import PowerOutageService


def refresh_all_active_trackings(app):
    with app.app_context():
        active_trackings = TrackingsRepo.get_active_trackings()
        print(f"[POLLING ORDERS: {len(active_trackings)} Orders in transit]")
        for t in active_trackings:
            try:
                # app.logger.info(f"Background refreshing {t['id']} ({t['trackingNumber']})")
                TrackingService.refresh_tracking(t['id'])
            except Exception as e:
                app.logger.error(f"Error refreshing {t['id']}: {e}")

def init_scheduler(app):
    if not app.config.get('SCHEDULER_ENABLED'):
        return None
    
    scheduler = BackgroundScheduler(timezone=timezone.utc)
    interval = app.config.get('POLL_INTERVAL_SECONDS', 300)

    scheduler.add_job(
        func=refresh_all_active_trackings,
        trigger="interval",
        seconds=interval,
        args=[app]
    )

    power_enabled = app.config.get('POWER_OUTAGE_ENABLED', True)
    power_interval = app.config.get('POWER_OUTAGE_INTERVAL_SECONDS', 21600)
    if power_enabled:
        scheduler.add_job(
            func=_refresh_power_outage,
            trigger="interval",
            seconds=power_interval,
            args=[app]
        )

    oil_enabled = app.config.get('OIL_NOTIFY_ENABLED', True)
    oil_time_str = app.config.get('TIME_NOTIFY_OIL', '07:30')
    if oil_enabled:
        hour_min = _parse_time(oil_time_str)
        if hour_min:
            scheduler.add_job(
                func=_notify_oil_price,
                trigger="cron",
                hour=hour_min[0],
                minute=hour_min[1],
                timezone=timezone(timedelta(hours=7)),
                args=[app]
            )
        else:
            app.logger.warning("Invalid TIME_NOTIFY_OIL format: %s", oil_time_str)

    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())
    return scheduler


def _refresh_power_outage(app):
    with app.app_context():
        processed = PowerOutageService.check_and_notify_all()
        if current_app:
            current_app.logger.info(
                "[POLLING POWER] Sent %s notifications", processed
            )


def _notify_oil_price(app):
    with app.app_context():
        from app.notifications.oil_price_service import OilPriceService

        processed = OilPriceService.notify_all(app)
        if current_app:
            current_app.logger.info(
                "[POLLING OIL] Sent %s notifications", processed
            )


def _parse_time(time_str):
    """Parse HH:MM to (hour, minute)."""
    if not time_str or not isinstance(time_str, str):
        return None
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except ValueError:
        return None
    return None
