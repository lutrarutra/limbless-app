from flask import Response, flash, url_for
from flask_htmx import make_response
from wtforms import StringField
from wtforms.validators import DataRequired, Length

from ... import logger
from ... import db
from ...core.DBSession import DBSession
from ..HTMXFlaskForm import HTMXFlaskForm


class PoolForm(HTMXFlaskForm):
    _template_path = "forms/pool.html"
    name = StringField("Pool Name", validators=[DataRequired(), Length(min=6, max=64)])

    def validate(self, user_id: int, pool_id: int) -> bool:
        if not super().validate():
            return False
        
        with DBSession(db.db_handler) as session:
            if (user := session.get_user(user_id)) is None:
                logger.error(f"User with id {user_id} does not exist.")
                return False

            # Creating new pool
            if pool_id is None:
                if self.name.data in [pool.name for pool in user.pools]:
                    self.name.errors = ("Pool with this name already exists",)
                    return False

        return True
    
    def process_request(self, **context) -> Response:
        raise NotImplementedError()
        if not self.validate(**context):
            return self.make_response(**context)
        
