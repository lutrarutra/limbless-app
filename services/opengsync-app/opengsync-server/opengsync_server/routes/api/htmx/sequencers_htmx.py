from typing import TYPE_CHECKING

from flask import Blueprint, url_for, render_template, flash, request, abort
from flask_htmx import make_response
from flask_login import login_required

from opengsync_db import PAGE_LIMIT, exceptions, models, db_session
from opengsync_db.categories import HTTPResponse, UserRole
from .... import db, forms, cache

sequencers_htmx = Blueprint("sequencers_htmx", __name__, url_prefix="/api/hmtx/sequencers/")

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user


@sequencers_htmx.route("get", methods=["GET"], defaults={"page": 0})
@sequencers_htmx.route("get/<int:page>", methods=["GET"])
@db_session(db)
@login_required
@cache.cached(timeout=60, query_string=True)
def get(page: int):
    if current_user.role != UserRole.ADMIN:
        return abort(HTTPResponse.FORBIDDEN.id)
    
    sequencers, n_pages = db.get_sequencers(offset=PAGE_LIMIT * page, count_pages=True)
    
    return make_response(
        render_template(
            "components/tables/sequencer.html",
            sequencers=sequencers,
            n_pages=n_pages,
            active_page=page
        )
    )


@sequencers_htmx.route("create", methods=["POST"])
@db_session(db)
@login_required
def create():
    if current_user.role != UserRole.ADMIN:
        return abort(HTTPResponse.FORBIDDEN.id)

    return forms.models.SequencerForm(request.form).process_request()


@sequencers_htmx.route("update/<int:sequencer_id>", methods=["POST"])
@db_session(db)
@login_required
def update(sequencer_id: int):
    if current_user.role != UserRole.ADMIN:
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (sequencer := db.get_sequencer(sequencer_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)

    return forms.models.SequencerForm(request.form).process_request(
        sequencer=sequencer
    )


@sequencers_htmx.route("delete/<int:sequencer_id>", methods=["GET"])
@db_session(db)
@login_required
def delete(sequencer_id: int):
    if current_user.role != UserRole.ADMIN:
        return abort(HTTPResponse.FORBIDDEN.id)

    if db.get_sequencer(sequencer_id) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    try:
        db.delete_sequencer(sequencer_id)
    except exceptions.ElementIsReferenced:
        flash("Sequencer is referenced by experiment(s) and cannot be deleted.", "error")
        return make_response(
            redirect=url_for("devices_page.sequencer_page", sequencer_id=sequencer_id)
        )

    flash("Sequencer deleted.", "success")
    return make_response(
        redirect=url_for("devices_page.devices_page")
    )


@sequencers_htmx.route("query", methods=["POST"])
@db_session(db)
@login_required
def query():
    field_name = next(iter(request.form.keys()))
    query = request.form.get(field_name)

    if query is None:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    results = db.query_sequencers(query)
    
    return make_response(
        render_template(
            "components/search_select_results.html",
            results=results,
            field_name=field_name
        )
    )
