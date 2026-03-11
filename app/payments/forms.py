from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, NumberRange


class SupportForm(FlaskForm):
    name = StringField('Tên', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=255)])
    amount = IntegerField('Số tiền (VND)', validators=[DataRequired(), NumberRange(min=1000, message='Vui lòng nhập tối thiểu 1,000 VND')])
    message = TextAreaField('Lời nhắn', validators=[Length(max=500)])
    submit = SubmitField('Ủng hộ')
