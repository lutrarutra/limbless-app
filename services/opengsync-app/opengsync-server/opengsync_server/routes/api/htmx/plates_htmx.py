from typing import TYPE_CHECKING

from flask import Blueprint, render_template, abort
from flask_htmx import make_response


from opengsync_db import models
from opengsync_db.categories import HTTPResponse
from .... import db, htmx_route

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user

plates_htmx = Blueprint("plates_htmx", __name__, url_prefix="/api/hmtx/plates/")


@htmx_route(plates_htmx, db=db)
def plate_tab(plate_id: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (plate := db.get_plate(plate_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    return make_response(render_template("components/plate.html", plate=plate))