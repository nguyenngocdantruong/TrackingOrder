from app import create_app
from app.scheduler import init_scheduler
from app.notifications.telegram_bot import start_telegram_chat_bot
from app.notifications.zalo_bot import start_zalo_bot
app = create_app()
init_scheduler(app)
start_telegram_chat_bot(app)
start_zalo_bot(app)
