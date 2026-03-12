from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, RadioField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from app.repos.users_repo import UsersRepo

class RegistrationForm(FlaskForm):
    username = StringField('Tên đăng nhập', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Mật khẩu', validators=[DataRequired()])
    confirm_password = PasswordField('Xác nhận mật khẩu', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Đăng ký')

    def validate_username(self, username):
        user = UsersRepo.get_by_username(username.data)
        if user:
            raise ValidationError('Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.')

class LoginForm(FlaskForm):
    username = StringField('Tên đăng nhập', validators=[DataRequired()])
    password = PasswordField('Mật khẩu', validators=[DataRequired()])
    submit = SubmitField('Đăng nhập')


class LinkTelegramForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Liên kết tài khoản')


class LinkZaloForm(FlaskForm):
    mode = RadioField(
        'Cách liên kết',
        choices=[('existing', 'Đăng nhập tài khoản có sẵn'), ('new', 'Tạo tài khoản mới')],
        default='existing'
    )
    existing_username = StringField('Tên đăng nhập')
    existing_password = PasswordField('Mật khẩu')
    new_username = StringField('Tên đăng nhập mới')
    new_password = PasswordField('Mật khẩu mới')
    confirm_new_password = PasswordField('Xác nhận mật khẩu mới', validators=[EqualTo('new_password')])
    submit = SubmitField('Liên kết Zalo')

    def validate(self, extra_validators=None):
        # Run base validators first
        if not super().validate(extra_validators):
            return False

        is_valid = True
        if self.mode.data == 'existing':
            if not self.existing_username.data:
                self.existing_username.errors.append('Vui lòng nhập tên đăng nhập hiện có.')
                is_valid = False
            if not self.existing_password.data:
                self.existing_password.errors.append('Vui lòng nhập mật khẩu hiện có.')
                is_valid = False
        else:
            if not self.new_username.data or len(self.new_username.data) < 2:
                self.new_username.errors.append('Tên đăng nhập phải có ít nhất 2 ký tự.')
                is_valid = False
            if not self.new_password.data or len(self.new_password.data) < 6:
                self.new_password.errors.append('Mật khẩu phải có ít nhất 6 ký tự.')
                is_valid = False

        return is_valid
