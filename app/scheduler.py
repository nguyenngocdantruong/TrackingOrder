import atexit
from datetime import timezone

from apscheduler.schedulers.background import BackgroundScheduler
from app.operations import record
from app.repos.trackings_repo import TrackingsRepo
from app.tracking.services import TrackingService


def refresh_all_active_trackings(app):
    with app.app_context():
        if not app.config.get('TRACKING_ENABLED', True):
            return
        try:
            active_trackings = [tracking for tracking in TrackingsRepo.get_active_trackings()
                                if not tracking.get('adminPaused')]
        except Exception:
            record('scheduler', 'poll', 'error', processed=0, failed=1)
            raise
        failed = 0
        for tracking in active_trackings:
            try:
                if not TrackingService.refresh_tracking(tracking['id']):
                    failed += 1
            except Exception:
                failed += 1
                record('tracking', 'sync', 'error', trackingId=tracking['id'],
                       userId=tracking.get('userId'), carrierId=tracking.get('carrierId'))
                app.logger.warning("Could not refresh tracking %s", tracking['id'])
        record('scheduler', 'poll', 'error' if failed else 'ok',
               processed=len(active_trackings), failed=failed)


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
