import json
from typing import TYPE_CHECKING

from flask import Blueprint, render_template, request, abort
from flask_htmx import make_response
from flask_login import login_required

from limbless_db import models, DBSession, PAGE_LIMIT
from limbless_db.categories import HTTPResponse, LibraryType, LibraryStatus
from .... import db, forms, logger  # noqa

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user

libraries_htmx = Blueprint("libraries_htmx", __name__, url_prefix="/api/hmtx/libraries/")


@libraries_htmx.route("get", methods=["GET"], defaults={"page": 0})
@libraries_htmx.route("get/<int:page>", methods=["GET"])
@login_required
def get(page: int):
    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "desc")
    descending = sort_order == "desc"
    offset = PAGE_LIMIT * page

    if (status_in := request.args.get("status_id_in")) is not None:
        status_in = json.loads(status_in)
        try:
            status_in = [LibraryStatus.get(int(status)) for status in status_in]
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
    
        if len(status_in) == 0:
            status_in = None

    if (type_in := request.args.get("type_id_in")) is not None:
        type_in = json.loads(type_in)
        try:
            type_in = [LibraryType.get(int(type_)) for type_ in type_in]
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
    
        if len(type_in) == 0:
            type_in = None
    
    libraries, n_pages = db.get_libraries(
        offset=offset,
        user_id=current_user.id if not current_user.is_insider() else None,
        sort_by=sort_by, descending=descending,
        status_in=status_in, type_in=type_in
    )

    return make_response(
        render_template(
            "components/tables/library.html", libraries=libraries,
            n_pages=n_pages, active_page=page,
            sort_by=sort_by, sort_order=sort_order,
            status_in=status_in, type_in=type_in
        )
    )


@libraries_htmx.route("edit/<int:library_id>", methods=["POST"])
@login_required
def edit(library_id):
    with DBSession(db) as session:
        if (library := session.get_library(library_id)) is None:
            return abort(HTTPResponse.NOT_FOUND.id)
        if not library.is_editable() and not current_user.is_insider():
            return abort(HTTPResponse.FORBIDDEN.id)

    return forms.models.LibraryForm(request.form).process_request(
        library=library
    )


@libraries_htmx.route("query", methods=["POST"])
@login_required
def query():
    field_name = next(iter(request.args.keys()))
    if (word := request.form.get(field_name, default="")) is None:
        return abort(HTTPResponse.BAD_REQUEST.id)

    if not current_user.is_insider():
        results = db.query_libraries(word, current_user.id)
    else:
        results = db.query_libraries(word)

    return make_response(
        render_template(
            "components/search_select_results.html",
            results=results, field_name=field_name,
        )
    )


@libraries_htmx.route("<int:library_id>/get_feautres", methods=["GET"], defaults={"page": 0})
@libraries_htmx.route("<int:library_id>/get_feautres/<int:page>", methods=["GET"])
@login_required
def get_features(library_id: int, page: int):
    if (library := db.get_library(library_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and library.owner_id != current_user.id:
        return abort(HTTPResponse.FORBIDDEN.id)
    
    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "desc")
    descending = sort_order == "desc"
    offset = PAGE_LIMIT * page

    features, n_pages = db.get_features(offset=offset, library_id=library_id, sort_by=sort_by, descending=descending)
    
    return make_response(
        render_template(
            "components/tables/library-feature.html",
            features=features, n_pages=n_pages, active_page=page,
            sort_by=sort_by, sort_order=sort_order, library=library
        )
    )


@libraries_htmx.route("<int:library_id>/get_visium_annotation", methods=["GET"])
@login_required
def get_visium_annotation(library_id: int):
    with DBSession(db) as session:
        if (library := session.get_library(library_id)) is None:
            return abort(HTTPResponse.NOT_FOUND.id)
        
        if not current_user.is_insider() and library.owner_id != current_user.id:
            return abort(HTTPResponse.FORBIDDEN.id)
        
        if library.type != LibraryType.SPATIAL_TRANSCRIPTOMIC:
            return abort(HTTPResponse.BAD_REQUEST.id)
        
        visium_annotation = library.visium_annotation
    
    return make_response(
        render_template(
            "components/library-visium-annotation.html",
            visium_annotation=visium_annotation, library=library
        )
    )


@libraries_htmx.route("table_query", methods=["GET"])
@login_required
def table_query():
    if (word := request.args.get("name")) is not None:
        field_name = "name"
    elif (word := request.args.get("id")) is not None:
        field_name = "id"
    else:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    user_id = current_user.id if not current_user.is_insider() else None

    if (status_in := request.args.get("status_id_in")) is not None:
        status_in = json.loads(status_in)
        try:
            status_in = [LibraryStatus.get(int(status)) for status in status_in]
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
    
        if len(status_in) == 0:
            status_in = None

    if (type_in := request.args.get("type_id_in")) is not None:
        type_in = json.loads(type_in)
        try:
            type_in = [LibraryType.get(int(type_)) for type_ in type_in]
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
    
        if len(type_in) == 0:
            type_in = None

    libraries: list[models.Library] = []
    if field_name == "name":
        libraries = db.query_libraries(word, user_id=user_id, status_in=status_in, type_in=type_in)
    elif field_name == "id":
        try:
            _id = int(word)
            if (library := db.get_library(_id)) is not None:
                if user_id is not None:
                    if library.owner_id == user_id:
                        libraries = [library]
                if status_in is not None and library.status not in status_in:
                    libraries = []
                if type_in is not None and library.type not in type_in:
                    libraries = []
        except ValueError:
            pass

    return make_response(
        render_template(
            "components/tables/library.html",
            current_query=word, active_query_field=field_name,
            libraries=libraries, type_in=type_in, status_in=status_in
        )
    )