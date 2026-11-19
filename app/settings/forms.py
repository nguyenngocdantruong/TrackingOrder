from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, HiddenField, SelectMultipleField
from wtforms import widgets
from wtforms.validators import DataRequired, Optional
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
