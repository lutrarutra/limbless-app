from typing import Optional, TYPE_CHECKING

from flask import Blueprint, url_for, render_template, flash, request, abort, Response
from flask_htmx import make_response
from flask_login import login_required
from werkzeug.utils import secure_filename

import pandas as pd

from limbless_db import models, DBSession, PAGE_LIMIT, DBHandler
from limbless_db.categories import HTTPResponse, UserRole
from .... import db, logger, forms

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user

samples_htmx = Blueprint("samples_htmx", __name__, url_prefix="/api/hmtx/samples/")


@samples_htmx.route("get", methods=["GET"], defaults={"page": 0})
@samples_htmx.route("get/<int:page>", methods=["GET"])
@login_required
def get(page: int):
    if not (sort_by := request.args.get("sort_by", None)):
        sort_by = "id"
    
    if not (sort_order := request.args.get("sort_order", None)):
        sort_order = "desc"

    descending = sort_order == "desc"
    offset = PAGE_LIMIT * page

    if sort_by not in models.Sample.sortable_fields:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    samples: list[models.Sample] = []

    samples, n_pages = db.get_samples(
        offset=offset,
        user_id=current_user.id if not current_user.is_insider() else None,
        sort_by=sort_by, descending=descending
    )
    
    return make_response(
        render_template(
            "components/tables/sample.html", samples=samples,
            n_pages=n_pages, active_page=page,
            sort_by=sort_by, sort_order=sort_order,
        )
    )


@samples_htmx.route("<int:sample_id>/delete", methods=["DELETE"])
@login_required
def delete(sample_id: int):
    if (sample := db.get_sample(sample_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not sample.is_editable():
        return abort(HTTPResponse.FORBIDDEN.id)

    db.delete_sample(sample_id)

    logger.info(f"Deleted sample {sample.name} (id: {sample.id})")
    flash(f"Deleted sample {sample.name} (id: {sample.id})", "success")

    return make_response(
        redirect=url_for(
            "samples_page.samples_page"
        ),
    )


@samples_htmx.route("<int:sample_id>/edit", methods=["POST"])
@login_required
def edit(sample_id):
    with DBSession(db) as session:
        if (sample := session.get_sample(sample_id)) is None:
            return abort(HTTPResponse.NOT_FOUND.id)

        if not sample.is_editable() and not current_user.is_insider():
            return abort(HTTPResponse.FORBIDDEN.id)

    return forms.models.SampleForm(request.form).process_request(
        user_id=current_user.id, sample=sample
    )


@samples_htmx.route("query", methods=["POST"])
@login_required
def query():
    field_name = next(iter(request.form.keys()))
    if (word := request.form.get(field_name)) is None:
        return abort(HTTPResponse.BAD_REQUEST.id)

    if current_user.role == UserRole.CLIENT:
        _user_id = current_user.id
    else:
        _user_id = None

    results = db.query_samples(word, user_id=_user_id)

    return make_response(
        render_template(
            "components/search_select_results.html",
            results=results,
            field_name=field_name
        )
    )


@samples_htmx.route("table_query", methods=["POST"])
@login_required
def table_query():
    if (word := request.form.get("name", None)) is not None:
        field_name = "name"
    elif (word := request.form.get("id", None)) is not None:
        field_name = "id"
    else:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if word is None:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if not current_user.is_insider():
        _user_id = current_user.id
    else:
        _user_id = None
    
    def __get_samples(
        session: DBHandler, word: str | int, field_name: str,
        seq_request_id: Optional[int], project_id: Optional[int],
    ) -> list[models.Sample]:
        samples: list[models.Sample] = []
        if field_name == "name":
            samples = session.query_samples(
                str(word),
                project_id=project_id, user_id=_user_id,
                seq_request_id=seq_request_id
            )
        elif field_name == "id":
            try:
                _id = int(word)
            except ValueError:
                return []
            if (sample := session.get_sample(_id)) is not None:
                if _user_id is not None:
                    if sample.owner_id == _user_id:
                        samples = [sample]

                if project_id is not None:
                    if sample.project_id == project_id:
                        samples = [sample]
                    else:
                        samples = []
                
                if seq_request_id is not None:
                    if session.is_sample_in_seq_request(sample.id, seq_request_id):
                        samples = [sample]
                    else:
                        samples = []
        else:
            assert False    # This should never happen

        return samples

    context = {}
    with DBSession(db) as session:
        if (project_id := request.args.get("project_id", None)) is not None:
            template = "components/tables/project-sample.html"
            try:
                project_id = int(project_id)

            except (ValueError, TypeError):
                return abort(HTTPResponse.BAD_REQUEST.id)
            
            if (project := session.get_project(project_id)) is None:
                return abort(HTTPResponse.NOT_FOUND.id)
                
            samples = __get_samples(session, word, field_name, project_id=project_id, seq_request_id=None)
            context["project"] = project
        
        elif (seq_request_id := request.args.get("seq_request_id", None)) is not None:
            template = "components/tables/seq_request-sample.html"
            try:
                seq_request_id = int(seq_request_id)
            except (ValueError, TypeError):
                return abort(HTTPResponse.BAD_REQUEST.id)
            
            if (seq_request := session.get_seq_request(seq_request_id)) is None:
                return abort(HTTPResponse.NOT_FOUND.id)
            
            samples = __get_samples(session, word, field_name, project_id=None, seq_request_id=seq_request_id)
            context["seq_request"] = seq_request
        else:
            template = "components/tables/sample.html"
            samples = __get_samples(session, word, field_name, project_id=None, seq_request_id=None)

        return make_response(
            render_template(
                template,
                current_query=word,
                samples=samples,
                field_name=field_name,
                **context
            )
        )
    

@samples_htmx.route("<int:sample_id>/get_libraries", methods=["GET"])
@login_required
def get_libraries(sample_id: int):
    if (sample := db.get_sample(sample_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if sample.owner_id != current_user.id and not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    libraries, n_pages = db.get_libraries(
        sample_id=sample_id
    )
    
    return make_response(
        render_template(
            "components/tables/sample-library.html",
            sample=sample, libraries=libraries,
            n_pages=n_pages
        )
    )
