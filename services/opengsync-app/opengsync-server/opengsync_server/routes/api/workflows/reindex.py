from typing import TYPE_CHECKING

from flask import Blueprint, request, abort, Response
from flask_login import login_required

from opengsync_db import models, db_session
from opengsync_db.categories import HTTPResponse

from .... import db, logger, htmx_route  # noqa
from ....forms.workflows import reindex as forms
from ....forms import SelectSamplesForm
from ....tools import exceptions, utils

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user  # noqa

reindex_workflow = Blueprint("reindex_workflow", __name__, url_prefix="/api/workflows/reindex/")


def get_context(args: dict) -> dict:
    context = {}
    if (seq_request_id := args.get("seq_request_id")) is not None:
        seq_request_id = int(seq_request_id)
        if (seq_request := db.get_seq_request(seq_request_id)) is None:
            raise exceptions.NotFoundException()
        if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
            affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
            if affiliation is None:
                raise exceptions.NoPermissionsException()
        context["seq_request"] = seq_request
        
    elif (lab_prep_id := args.get("lab_prep_id")) is not None:
        lab_prep_id = int(lab_prep_id)
        if (lab_prep := db.get_lab_prep(lab_prep_id)) is None:
            raise exceptions.NotFoundException()
        context["lab_prep"] = lab_prep

    elif (pool_id := args.get("pool_id")) is not None:
        pool_id = int(pool_id)
        if (pool := db.get_pool(pool_id)) is None:
            raise exceptions.NotFoundException()
        context["pool"] = pool

    if not current_user.is_insider():
        if "seq_request" not in context:
            return abort(HTTPResponse.FORBIDDEN.id)
        
    return context


@htmx_route(reindex_workflow, db=db)
def begin() -> Response:
    try:
        context = get_context(request.args)
    except ValueError:
        return abort(HTTPResponse.BAD_REQUEST.id)
    except exceptions.OpeNGSyncServerException as e:
        return abort(e.response.id)
        
    form = SelectSamplesForm(
        "reindex", context=context,
        select_libraries=True
    )
    return form.make_response()


@htmx_route(reindex_workflow, db=db, methods=["POST"])
def select():
    try:
        context = get_context(request.args)
    except ValueError:
        return abort(HTTPResponse.BAD_REQUEST.id)
    except exceptions.OpeNGSyncServerException as e:
        return abort(e.response.id)
    
    form: SelectSamplesForm = SelectSamplesForm(
        "reindex", formdata=request.form, context=context,
        select_libraries=True
    )

    if not form.validate():
        return form.make_response()

    libraries = form.get_libraries()
    library_table = utils.get_barcode_table(db, libraries)
    form.add_table("library_table", library_table)
    form.update_data()

    next_form = forms.BarcodeInputForm(
        seq_request=context.get("seq_request"),
        lab_prep=context.get("lab_prep"),
        pool=context.get("pool"),
        uuid=form.uuid,
        formdata=None
    )
    return next_form.make_response()


@htmx_route(reindex_workflow, db=db, methods=["POST"])
def upload_barcode_form(uuid: str):
    try:
        context = get_context(request.args)
    except ValueError:
        return abort(HTTPResponse.BAD_REQUEST.id)
    except exceptions.OpeNGSyncServerException as e:
        return abort(e.response.id)
    
    form = forms.BarcodeInputForm(
        uuid=uuid, formdata=request.form,
        seq_request=context.get("seq_request"),
        lab_prep=context.get("lab_prep"),
        pool=context.get("pool")
    )
    return form.process_request()


@htmx_route(reindex_workflow, db=db, methods=["POST"])
def map_index_kits(uuid: str):
    try:
        context = get_context(request.args)
    except ValueError:
        return abort(HTTPResponse.BAD_REQUEST.id)
    except exceptions.OpeNGSyncServerException as e:
        return abort(e.response.id)
    
    form = forms.IndexKitMappingForm(
        uuid=uuid, formdata=request.form,
        seq_request=context.get("seq_request"),
        lab_prep=context.get("lab_prep"),
        pool=context.get("pool"),
    )
    return form.process_request()
    

    
    