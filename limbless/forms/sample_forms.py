from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FieldList, FormField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Length

from .. import logger
from ..core.DBHandler import DBHandler
from ..core.DBSession import DBSession


class SampleForm(FlaskForm):
    name = StringField("Sample Name", validators=[DataRequired(), Length(min=6, max=64)])
    organism = IntegerField("Organism", validators=[DataRequired()])

    def custom_validate(
        self,
        db_handler: DBHandler, user_id: int,
        project_id: int,
        sample_id: int | None = None,
    ) -> tuple[bool, "SampleForm"]:

        validated = self.validate()
        if not validated:
            return False, self

        with DBSession(db_handler) as session:
            if (user := session.get_user(user_id)) is None:
                logger.error(f"User with id {user_id} does not exist.")
                return False, self
            
            if (project := session.get_project(project_id)) is None:
                logger.error(f"Project with id {project_id} does not exist.")
                return False, self
            
            project_samples = project.samples

            # Creating new sample
            if sample_id is None:
                if self.name.data in [sample.name for sample in project_samples]:
                    self.name.errors = ("This project already has a sample with this name.",)
                    validated = False

        return validated, self


class SampleSelectForm(FlaskForm):
    query_field = StringField("Search", validators=[DataRequired()])


class SampleTableConfirmForm(FlaskForm):
    data = TextAreaField(validators=[DataRequired()])
    selected_samples = StringField()


class SampleColSelectForm(FlaskForm):
    _sample_fields = [
        ("", "-"),
        ("sample_name", "Sample Name"),
        ("organism", "Organism"),
    ]
    select_field = SelectField(
        choices=_sample_fields,
    )


class SampleTableForm(FlaskForm):
    fields = FieldList(FormField(SampleColSelectForm))
    data = TextAreaField(validators=[DataRequired()])
