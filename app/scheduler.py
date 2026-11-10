import atexit
from datetime import timezone

from apscheduler.schedulers.background import BackgroundScheduler
from app.repos.trackings_repo import TrackingsRepo
from app.tracking.services import TrackingService


def refresh_all_active_trackings(app):
    with app.app_context():
        if not app.config.get('TRACKING_ENABLED', True):
            return
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

    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())
    return scheduler
