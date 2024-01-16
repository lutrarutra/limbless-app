from typing import Optional, TYPE_CHECKING

from flask import Blueprint, render_template, request, abort, url_for
from flask_htmx import make_response
from flask_login import login_required

from .... import db, logger, forms, models, PAGE_LIMIT
from ....core import DBSession
from ....categories import HttpResponse

if TYPE_CHECKING:
    current_user: models.User = None
else:
    from flask_login import current_user

adapters_htmx = Blueprint("adapters_htmx", __name__, url_prefix="/api/adapters/")


@adapters_htmx.route("<index_kit_id>/get/<int:page>", methods=["GET"], defaults={"index_kit_id": None})
@adapters_htmx.route("<int:index_kit_id>/get/<int:page>", methods=["GET"])
@login_required
def get(page: int, index_kit_id: Optional[int]):
    sort_by = request.args.get("sort_by", "id")
    order = request.args.get("order", "desc")
    descending = order == "desc"
    offset = PAGE_LIMIT * page

    if sort_by not in models.Adapter.sortable_fields:
        return abort(HttpResponse.BAD_REQUEST.value.id)

    with DBSession(db.db_handler) as session:
        if index_kit_id is not None:
            index_kit = session.get_index_kit(index_kit_id)
            if index_kit is None:
                return abort(HttpResponse.NOT_FOUND.value.id)

        adapters, n_pages = session.get_adapters(index_kit_id=index_kit_id, offset=offset, sort_by=sort_by, descending=descending)

    return make_response(
        render_template(
            "components/tables/adapter.html", adapters=adapters,
            adapters_n_pages=n_pages, adapters_active_page=page, index_kit_id=index_kit_id,
            adapters_current_sort=sort_by, adapters_current_sort_order=order
        ), push_url=False
    )