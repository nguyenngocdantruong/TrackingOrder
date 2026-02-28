from flask import Blueprint, render_template, url_for, flash, redirect, request
from flask_login import login_user, current_user, logout_user, login_required
from app.auth.forms import RegistrationForm, LoginForm
from app.repos.users_repo import UsersRepo

auth_bp = Blueprint('auth', __name__)

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
