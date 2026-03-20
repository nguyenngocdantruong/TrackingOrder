import atexit
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
        
    scheduler = BackgroundScheduler()
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
