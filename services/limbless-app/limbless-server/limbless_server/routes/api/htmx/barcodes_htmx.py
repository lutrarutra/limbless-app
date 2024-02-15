from typing import Optional, TYPE_CHECKING

from flask import Blueprint, render_template, request, abort
from flask_htmx import make_response
from flask_login import login_required

from limbless_db import models, DBSession, PAGE_LIMIT
from limbless_db.core.categories import HttpResponse
from .... import db

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user

barcodes_htmx = Blueprint("barcodes_htmx", __name__, url_prefix="/api/barcodes/")


@barcodes_htmx.route("get/<int:page>", methods=["GET"])
@login_required
def get(page: int):
    sort_by = request.args.get("sort_by", "id")
    order = request.args.get("order", "desc")
    descending = order == "desc"

    if sort_by not in models.Barcode.sortable_fields:
        return abort(HttpResponse.BAD_REQUEST.value.id)

    with DBSession(db) as session:
        barcodes, n_pages = session.get_seqbarcodes(offset=PAGE_LIMIT * page, sort_by=sort_by, descending=descending)

    return make_response(
        render_template(
            "components/tables/barcode.html", barcodes=barcodes,
            barcodes_n_pages=n_pages, barcodes_active_page=page,
            barcodes_current_sort=sort_by, barcodes_current_sort_order=order
        ), push_url=False
    )


@barcodes_htmx.route("query_index_kits", methods=["POST"])
@login_required
def query_index_kits():
    field_name = next(iter(request.form.keys()))
    
    if (word := request.form.get(field_name)) is None:
        return abort(HttpResponse.BAD_REQUEST.value.id)

    results = db.query_index_kit(word)

    return make_response(
        render_template(
            "components/search_select_results.html",
            results=results,
            field_name=field_name
        ), push_url=False
    )


@barcodes_htmx.route("query/<int:index_kit_id>", methods=["POST"], defaults={"exclude_library_id": None})
@barcodes_htmx.route("query_adapters/<int:index_kit_id>/<int:exclude_library_id>", methods=["POST"])
@login_required
def query_adapters(index_kit_id: int, exclude_library_id: Optional[int] = None):
    field_name = next(iter(request.form.keys()))
    
    if (word := request.form.get(field_name)) is None:
        return abort(HttpResponse.BAD_REQUEST.value.id)

    raise NotImplementedError("This function is not implemented yet.")
    # TODO: add exclude_library_id to query_adapters
    results = db.query_adapters(
        word, index_kit_id=index_kit_id
    )

    return make_response(
        render_template(
            "components/search_select_results.html",
            results=results,
            field_name=field_name
        ), push_url=False
    )