from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, HiddenField, SelectMultipleField
from wtforms import widgets
from wtforms.validators import DataRequired, Optional

class SettingsForm(FlaskForm):
    telegram_chat_id = StringField('Telegram Chat ID')
    zalo_chat_id = StringField('Zalo Chat ID')
    notify_enabled = BooleanField('Enable Notifications')
    telegram_enabled = BooleanField('Enable Telegram', default=True)
    zalo_enabled = BooleanField('Enable Zalo', default=True)
    submit = SubmitField('Save Settings')


class PowerOutageSubscriptionForm(FlaskForm):
    province_id = StringField('Province', validators=[DataRequired()])
    district_id = StringField('District', validators=[Optional()])
    submit = SubmitField('Theo dõi khu vực')


class DeletePowerOutageSubscriptionForm(FlaskForm):
    subscription_id = HiddenField(validators=[DataRequired()])
    submit = SubmitField('Xóa')


class OilSettingsForm(FlaskForm):
    oil_enabled = BooleanField('Nhận thông báo giá xăng dầu', default=True)
    suppliers = SelectMultipleField(
        'Đại lý',
        choices=[],
        coerce=str,
        validators=[Optional()],
        option_widget=widgets.CheckboxInput(),
        widget=widgets.ListWidget(prefix_label=False),
    )
    petrolimex_products = SelectMultipleField(
        'Sản phẩm Petrolimex',
        choices=[],
        coerce=str,
        validators=[Optional()],
        option_widget=widgets.CheckboxInput(),
        widget=widgets.ListWidget(prefix_label=False),
    )
    pvoil_products = SelectMultipleField(
        'Sản phẩm PVOIL',
        choices=[],
        coerce=str,
        validators=[Optional()],
        option_widget=widgets.CheckboxInput(),
        widget=widgets.ListWidget(prefix_label=False),
    )
    submit = SubmitField('Lưu cài đặt')
