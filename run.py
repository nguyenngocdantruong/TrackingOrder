from app import create_app
from app.scheduler import init_scheduler
import os

app = create_app()

if __name__ == "__main__":
    # Giá trị mặc định
    port = 5000
    host = '127.0.0.1'
    debug_mode = True

    # Đọc cấu hình từ config.conf
    if os.path.exists('config.conf'):
        with open('config.conf', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    if key == 'PORT_APP':
                        try:
                            port = int(value)
                        except ValueError:
                            pass
                    elif key == 'LISTEN_PORT':
                        host = value
                    elif key == 'DEBUG':
                        debug_mode = (value == '1')
                    elif key == 'SCHEDULER_ENABLED':
                        app.config['SCHEDULER_ENABLED'] = (value == '1' or value.lower() == 'true')
                    elif key == 'POLL_INTERVAL_SECONDS':
                        try:
                            app.config['POLL_INTERVAL_SECONDS'] = int(value)
                        except ValueError:
                            pass

    # Initialize background scheduler AFTER reading config.conf
    init_scheduler(app)

    print(f" * Ứng dụng đang khởi chạy tại {host}:{port} (Debug: {debug_mode})")
    print(f" * Scheduler: {'Bật' if app.config.get('SCHEDULER_ENABLED') else 'Tắt'} (Interval: {app.config.get('POLL_INTERVAL_SECONDS')}s)")
    app.run(host=host, port=port, debug=debug_mode)
