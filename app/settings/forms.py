from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField

class SettingsForm(FlaskForm):
    telegram_chat_id = StringField('Telegram Chat ID')
    zalo_chat_id = StringField('Zalo Chat ID')
    notify_enabled = BooleanField('Enable Notifications')
    submit = SubmitField('Save Settings')
