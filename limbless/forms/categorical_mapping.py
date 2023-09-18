from flask_wtf import FlaskForm
from wtforms import StringField, FieldList, FormField, TextAreaField, IntegerField
from wtforms.validators import DataRequired


class CategoricalMappingField(FlaskForm):
    raw_category = StringField("Category", validators=[DataRequired()])
    category = IntegerField("Category", validators=[DataRequired()])


class CategoricalMappingForm(FlaskForm):
    fields = FieldList(FormField(CategoricalMappingField))
    data = TextAreaField(validators=[DataRequired()])