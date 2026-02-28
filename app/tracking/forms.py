from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired
from app.providers.registry import registry

class AddTrackingForm(FlaskForm):
    tracking_number = StringField('Tracking Number', validators=[DataRequired()])
    carrier_id = SelectField('Carrier', choices=[('auto', 'Auto Detect')] + registry.list_providers())
    alias = StringField('Alias (Optional)')
    submit = SubmitField('Add Tracking')
