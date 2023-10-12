from typing import Optional

from flask import Blueprint, render_template, request, abort
from flask_htmx import make_response
from flask_login import login_required, current_user

from .... import db, logger, forms
from ....core import DBSession
from ....categories import LibraryType

indices_htmx = Blueprint("indices_htmx", __name__, url_prefix="/api/indices/")


@indices_htmx.route("get/<int:page>", methods=["GET"])
@login_required
def get(page):
    with DBSession(db.db_handler) as session:
        n_pages = int(session.get_num_seqindices() / 20)
        page = min(page, n_pages)
        indices = session.get_seqindices(limit=20, offset=20 * page)

    return make_response(
        render_template(
            "components/tables/index.html", indices=indices,
            n_pages=n_pages, active_page=page
        ), push_url=False
    )


@indices_htmx.route("query_index_kits", methods=["POST"])
@login_required
def query_index_kits():
    library_type_id: Optional[int] = None
    
    if (raw_library_type_id := request.form.get("library_type")) is None:
        logger.debug("No library type id provided with POST request")
        return abort(400)

    try:
        library_type_id = int(raw_library_type_id)
    except ValueError:
        logger.debug(f"Invalid library type '{raw_library_type_id}' id provided with POST request")
        return abort(400)

    field_name = next(iter(request.form.keys()))
    word = request.form.get(field_name)

    if word is None:
        return abort(400)

    if library_type_id is not None:
        library_type = LibraryType.get(library_type_id)
    else:
        library_type = None

    results = db.db_handler.query_index_kit(word, library_type=library_type)

    return make_response(
        render_template(
            "components/search_select_results.html",
            results=results,
            field_name=field_name
        ), push_url=False
    )


@indices_htmx.route("query/<int:index_kit_id>", methods=["POST"], defaults={"exclude_library_id": None})
@indices_htmx.route("query_seq_adapters/<int:index_kit_id>/<int:exclude_library_id>", methods=["POST"])
@login_required
def query_seq_adapters(index_kit_id: int, exclude_library_id: Optional[int] = None):
    field_name = next(iter(request.form.keys()))
    
    if (word := request.form.get(field_name)) is None:
        return abort(400)

    # TODO: add exclude_library_id to query_adapters
    results = db.db_handler.query_adapters(
        word, index_kit_id=index_kit_id
    )

    return make_response(
        render_template(
            "components/search_select_results.html",
            results=results,
            field_name=field_name
        ), push_url=False
    )


@indices_htmx.route("select_indices/<int:library_id>", methods=["POST"])
@login_required
def select_indices(library_id: int):
    with DBSession(db.db_handler) as session:
        if (library := session.get_library(library_id)) is None:
            return abort(404)
        if (user := session.get_user(current_user.id)) is None:
            return abort(404)

        user.samples = user.samples

    index_form = forms.IndexForm()
    if (selected_adapter_id := index_form.adapter.data) is None:
        return abort(400)

    if (selected_sample_id := index_form.sample.data) is None:
        return abort(400)

    selected_adapter = db.db_handler.get_adapter(selected_adapter_id)
    selected_sample = db.db_handler.get_sample(selected_sample_id)

    for i, entry in enumerate(index_form.indices.entries):
        entry.index_seq_id.data = selected_adapter.indices[i].id
        entry.sequence.data = selected_adapter.indices[i].sequence

    return make_response(
        render_template(
            "forms/index.html",
            library=library,
            index_form=index_form,
            selected_adapter=selected_adapter,
            selected_sample=selected_sample
        )
    )
