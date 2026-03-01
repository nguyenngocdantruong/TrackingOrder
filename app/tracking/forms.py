from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired
from app.providers.registry import registry

class AddTrackingForm(FlaskForm):
    tracking_number = StringField('Mã vận đơn', validators=[DataRequired()])
    carrier_id = SelectField('Đơn vị vận chuyển', choices=[('auto', 'Tự động nhận diện')] + registry.list_providers())
    alias = StringField('Tên gợi nhớ (Tuỳ chọn)')
    submit = SubmitField('Thêm vận đơn')
