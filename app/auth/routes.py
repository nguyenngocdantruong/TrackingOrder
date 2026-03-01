from flask import Blueprint, render_template, url_for, flash, redirect, request
from flask_login import login_user, current_user, logout_user, login_required
from app.auth.forms import RegistrationForm, LoginForm, LinkTelegramForm
from app.repos.users_repo import UsersRepo

auth_bp = Blueprint('auth', __name__)
link_bp = Blueprint('link', __name__)

@auth_bp.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('tracking.dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        UsersRepo.create(form.username.data, form.password.data)
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('tracking.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = UsersRepo.get_by_username(form.username.data)
        if user and user.verify_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('tracking.dashboard'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('auth/login.html', title='Login', form=form)

@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('index'))


@link_bp.route("/link", methods=['GET', 'POST'])
def link_account():
    chat_id = request.values.get('chat_id')
    token = request.values.get('token')

    if not chat_id or not token:
        flash('Thiếu thông tin liên kết. Vui lòng thao tác lại từ Telegram bot.', 'danger')
        return redirect(url_for('auth.login'))

    user = UsersRepo.get_by_telegram_chat_id(chat_id)
    if not user:
        user = UsersRepo.get_or_create_temp_by_telegram_chat_id(chat_id)

    if not user.is_temporary:
        flash('Telegram này đã được liên kết tài khoản website.', 'info')
        return redirect(url_for('auth.login'))

    if not user.link_token or user.link_token != token:
        flash('Liên kết không hợp lệ hoặc đã hết hạn.', 'danger')
        return redirect(url_for('auth.login'))

    form = LinkTelegramForm()
    if form.validate_on_submit():
        existed = UsersRepo.get_by_username(form.username.data)
        if existed and existed.id != user.id:
            form.username.errors.append('Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.')
        else:
            UsersRepo.link_temp_account(chat_id, form.username.data, form.password.data)
            flash('Liên kết thành công! Bạn có thể đăng nhập bằng tài khoản vừa tạo.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/link.html', title='Liên kết tài khoản', form=form, chat_id=chat_id, token=token)
