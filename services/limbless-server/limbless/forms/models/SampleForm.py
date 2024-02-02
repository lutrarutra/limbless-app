from typing import Optional

from flask import Response, flash, url_for
from flask_htmx import make_response
from wtforms import StringField, IntegerField
from wtforms.validators import DataRequired, Length


from ... import logger, db, models
from ...core.DBSession import DBSession
from ..HTMXFlaskForm import HTMXFlaskForm


class SampleForm(HTMXFlaskForm):
    _template_path = "forms/sample.html"
    name = StringField("Sample Name", validators=[DataRequired(), Length(min=6, max=64)])
    organism = IntegerField("Organism", validators=[DataRequired()])

    def validate(self, user_id: int, sample: models.Sample) -> bool:
        if not super().validate():
            return False
        
        with DBSession(db.db_handler) as session:
            if (user := session.get_user(user_id)) is None:
                logger.error(f"User with id {user_id} does not exist.")
                return False
            
            user_samples = user.samples
            
            for user_sample in user_samples:
                if self.name.data == user_sample.name:
                    if sample.id != user_sample.id:
                        self.name.errors = ("You already have a sample with this name.",)
                        return False
        
        return True
    
    def process_request(self, **context) -> Response:
        user_id = context["user_id"]
        sample: models.Sample = context["sample"]

        if not self.validate(user_id=user_id, sample=sample):
            return self.make_response(**context)
       
        sample = db.db_handler.update_sample(
            sample_id=sample.id,
            name=self.name.data,
            organism_tax_id=self.organism.data
        )

        logger.debug(f"Edited {sample}")
        flash("Changes saved succesfully!", "success")
        return make_response(
            redirect=url_for("samples_page.sample_page", sample_id=sample.id),
        )