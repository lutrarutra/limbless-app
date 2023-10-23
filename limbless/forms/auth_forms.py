from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, StringField
from wtforms.validators import DataRequired, Length, ValidationError, Email, EqualTo

from ..db import db_handler
from ..core.DBSession import DBSession
from ..core.DBHandler import DBHandler


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])


class RegisterForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=128)])

    def validate_email(self, email):
        if db_handler.get_user_by_email(email.data):
            raise ValidationError("Email already registered.")


class CompleteRegistrationForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=64)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=64)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password", "Passwords must match.")])

    def custom_validate(
        self, db_handler: DBHandler, user_id: int,
        library_id: int | None = None,
    ) -> tuple[bool, "CompleteRegistrationForm"]:
        
        validated = self.validate()
        if not validated:
            return False, self

        with DBSession(db_handler) as session:
            if session.get_user_by_email(self.email.data):
                self.email.errors = ("Email already registered.",)
                validated = False

        return validated, self