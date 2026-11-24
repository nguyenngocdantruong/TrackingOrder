from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, HiddenField, SelectMultipleField, TextAreaField
from wtforms import widgets
from wtforms.validators import DataRequired, Length, Optional
from app.tracking.stages import STAGE_CHOICES

class SettingsForm(FlaskForm):
    telegram_chat_id = StringField('Telegram Chat ID')
    zalo_chat_id = StringField('Zalo Chat ID')
    notify_enabled = BooleanField('Enable Notifications')
    notify_stages = SelectMultipleField(
        'Thông báo theo giai đoạn', choices=STAGE_CHOICES,
        widget=widgets.ListWidget(prefix_label=False),
        option_widget=widgets.CheckboxInput(),
    )
    telegram_enabled = BooleanField('Enable Telegram', default=True)
    zalo_enabled = BooleanField('Enable Zalo', default=True)
    submit = SubmitField('Save Settings')


class AddressForm(FlaskForm):
    name = StringField('Tên địa chỉ', validators=[DataRequired(), Length(max=60)])
    detail = TextAreaField('Địa chỉ cụ thể', validators=[Optional(), Length(max=240)])
    note = TextAreaField('Ghi chú', validators=[Optional(), Length(max=240)])
    is_default = BooleanField('Đặt làm địa chỉ mặc định', default=False)
    submit = SubmitField('Lưu địa chỉ')
