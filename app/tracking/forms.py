from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length
from app.providers.registry import registry


class AddTrackingForm(FlaskForm):
    tracking_number = StringField('Mã vận đơn', validators=[DataRequired()])
    carrier_id = SelectField('Đơn vị vận chuyển', choices=[('auto', 'Tự động nhận diện')] + registry.list_providers())
    alias = StringField('Tên gợi nhớ (Tuỳ chọn)', validators=[Length(max=80)])
    address_id = SelectField('Địa chỉ nhận hàng', choices=[('', 'Không chọn địa chỉ')], default='')
    cod_amount = StringField('Tiền thu hộ COD (VND)', validators=[Length(max=24)])
    note = TextAreaField('Ghi chú nhận hàng', validators=[Length(max=240)])
    submit = SubmitField('Thêm vận đơn')


class EditTrackingForm(FlaskForm):
    alias = StringField('Tên gợi nhớ', validators=[Length(max=80)])
    address_id = SelectField('Địa chỉ nhận hàng', choices=[('', 'Không chọn địa chỉ')], default='')
    cod_amount = StringField('Tiền thu hộ COD (VND)', validators=[Length(max=24)])
    note = TextAreaField('Ghi chú nhận hàng', validators=[Length(max=240)])
    submit = SubmitField('Lưu thay đổi')
