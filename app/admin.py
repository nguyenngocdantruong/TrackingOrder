import hashlib
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from app.firebase import get_db

admin_bp = Blueprint('admin', __name__)
_lock = threading.RLock()
_links = {}
GROUPS = [
 ('tracking', 'Theo dõi đơn hàng', 'Điều chỉnh việc nhận và cập nhật vận đơn.', [
 ('TRACKING_ENABLED','Cho phép theo dõi','bool'), ('SCHEDULER_ENABLED','Tự động cập nhật','bool'),
 ('POLL_INTERVAL_SECONDS','Chu kỳ cập nhật (giây)','int'), ('MAX_EVENTS_PER_TRACKING','Số sự kiện tối đa mỗi đơn','int')]),
 ('payos', 'PayOS', 'Quản lý cổng thanh toán và thông tin kết nối.', [
 ('PAYOS_ENABLED','Bật PayOS','bool'), ('PAYOS_CLIENT_ID','Client ID','text'), ('PAYOS_API_KEY','API key','secret'),
 ('PAYOS_CHECKSUM_KEY','Checksum key','secret'), ('PAYOS_RETURN_URL','URL thanh toán thành công','url'),
 ('PAYOS_CANCEL_URL','URL hủy thanh toán','url'), ('PAYOS_DONATION_AMOUNT','Số tiền mặc định (VND)','int'), ('DONATE_NOTIFY_ALL','Thông báo ủng hộ cho mọi người','bool')]),
 ('telegram', 'Telegram', 'Kết nối bot nhận lệnh và gửi thông báo vận đơn.', [
 ('TELEGRAM_ENABLED','Bật Telegram bot','bool'), ('TELEGRAM_BOT_TOKEN','Bot token','secret'), ('TELEGRAM_BOT_USERNAME','Tên bot','text')]),
 ('zalo', 'Zalo', 'Kết nối bot Zalo qua polling.', [
 ('ZALO_ENABLED','Bật Zalo bot','bool'), ('ZALO_BOT_TOKEN','Bot token','secret'), ('ZALO_BOT_UID','Bot UID','text')]),
]
CONF_KEYS = {'TRACKING_ENABLED','SCHEDULER_ENABLED','POLL_INTERVAL_SECONDS','MAX_EVENTS_PER_TRACKING'}

def is_admin():
    expected = str(current_app.config.get('ADMIN_TELEGRAM_USER_ID') or '').strip()
    return bool(expected and current_user.is_authenticated and not current_user.is_temporary
                and str(current_user.telegram_verified_id or '') == expected
                and str(current_user.settings.get('telegramChatId') or '') == expected)

def create_admin_link(app, chat_id):
    if str(chat_id) != str(app.config.get('ADMIN_TELEGRAM_USER_ID') or ''):
        return None
    token = secrets.token_urlsafe(32)
    with _lock:
        _links.clear()
        _links[hashlib.sha256(token.encode()).hexdigest()] = (str(chat_id), time.time()+600)
    return app.config['WEBSITE_URL'] + '/admin/verify?' + urlencode({'token': token})

@admin_bp.route('/verify', methods=['GET','POST'])
@login_required
def verify():
    # URL-safe tokens never contain slashes; tolerate a copied URL's trailing slash.
    token = request.values.get('token','').strip().rstrip('/')
    digest = hashlib.sha256(token.encode()).hexdigest()
    form = FlaskForm()
    with _lock:
        entry = _links.get(digest)
        if not entry or entry[1] < time.time():
            abort(403, description='Liên kết xác nhận không hợp lệ hoặc đã hết hạn. Gửi /admin cho bot Telegram để lấy liên kết mới (có hiệu lực 10 phút). Liên kết cũ cũng mất hiệu lực khi ứng dụng khởi động lại hoặc bạn yêu cầu liên kết mới.')
        if str(current_user.settings.get('telegramChatId') or '') != entry[0] or current_user.is_temporary:
            abort(403, description='Tài khoản web phải là tài khoản chính thức và có Telegram Chat ID trùng với tài khoản Telegram đã yêu cầu liên kết. Kiểm tra tài khoản đăng nhập và Cài đặt → Thông báo.')
        if form.validate_on_submit():
            get_db().collection('users').document(current_user.id).update({'telegramVerifiedId': entry[0]})
            _links.pop(digest,None)
            return redirect(url_for('admin.index'))
    return render_template('admin/verify.html',form=form,token=token)

def read_files():
    return {name: Path(os.getenv(var, name)).read_text(encoding='utf-8') for name,var in [('.env','ENV_FILE'),('config.conf','CONF_FILE')]}

def revision(files):
    return hashlib.sha256((files['.env']+'\0'+files['config.conf']).encode()).hexdigest()

def update_text(text, changes):
    import re
    lines = text.splitlines()
    for key,value in changes.items():
        encoded = str(value).replace('\\','\\\\').replace("'", "\\'")
        new_line = key + "='" + encoded + "'"
        matches = [i for i,line in enumerate(lines) if re.match(r'^\s*(?:export\s+)?'+re.escape(key)+r'\s*=',line)]
        if matches:
            lines[matches[0]]=new_line
            for i in reversed(matches[1:]):
                lines.pop(i)
        else:
            lines.append(new_line)
    return '\n'.join(lines)+'\n'

def restart_process():
    time.sleep(2)
    os._exit(0)

@admin_bp.route('/', methods=['GET','POST'])
@login_required
def index():
    if not is_admin():
        abort(403)
    form = FlaskForm()
    error = None
    with _lock:
        files=read_files()
        if form.validate_on_submit():
            try:
                if request.form.get('revision') != revision(files):
                    raise ValueError('Cấu hình đã thay đổi. Tải lại trang rồi thử lại.')
                updates={}
                for _,_,_,fields in GROUPS:
                    for key,label,kind in fields:
                        value=request.form.get(key,'').strip()
                        if kind == 'bool':
                            value='true' if value == 'on' else 'false'
                        elif kind == 'secret' and not value:
                            continue
                        elif kind == 'int':
                            value=int(value)
                            minimum=30 if key=='POLL_INTERVAL_SECONDS' else 1
                            if not minimum <= value <= 100000000:
                                raise ValueError(label+': giá trị ngoài phạm vi cho phép.')
                        elif kind == 'url' and value and (urlsplit(value).scheme not in ('http','https') or not urlsplit(value).netloc):
                            raise ValueError(label+': cần URL http hoặc https hợp lệ.')
                        if '\n' in str(value) or '\r' in str(value) or '\x00' in str(value):
                            raise ValueError(label+': giá trị không hợp lệ.')
                        updates[key]=value
                # In-place writes support individual Docker bind mounts. Roll back both files on error.
                paths={'.env':Path(os.getenv('ENV_FILE','.env')), 'config.conf':Path(os.getenv('CONF_FILE','config.conf'))}
                try:
                    for name,path in paths.items():
                        selected={k:v for k,v in updates.items() if (k in CONF_KEYS)==(name=='config.conf')}
                        # Remove duplicate managed keys from the other source to avoid precedence surprises.
                        import re
                        base='\n'.join(line for line in files[name].splitlines() if not any(re.match(r'^\s*(?:export\s+)?'+k+r'\s*=',line) for k in updates if k not in selected))+'\n'
                        with path.open('w',encoding='utf-8') as out:
                            out.write(update_text(base,selected)); out.flush(); os.fsync(out.fileno())
                except OSError:
                    for name,path in paths.items():
                        path.write_text(files[name],encoding='utf-8')
                    raise
                if os.getenv('MANAGED_RESTART') == '1':
                    threading.Thread(target=restart_process,daemon=True).start()
                return render_template('admin/saved.html', automatic=os.getenv('MANAGED_RESTART')=='1')
            except (ValueError,OSError):
                error='Không lưu được. Kiểm tra giá trị (chu kỳ tối thiểu 30 giây), quyền ghi file hoặc tải lại nếu cấu hình vừa thay đổi.'
        elif request.method=='POST':
            error='Phiên làm việc đã hết hạn. Tải lại trang rồi lưu lại.'
    return render_template('admin/index.html',groups=GROUPS,values=current_app.config,form=form,revision=revision(files),error=error)
