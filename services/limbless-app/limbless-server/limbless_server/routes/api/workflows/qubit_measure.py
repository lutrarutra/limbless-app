import json
from typing import TYPE_CHECKING, Any

from flask import Blueprint, request, abort, render_template, Request
from flask_htmx import make_response
from flask_login import login_required

from limbless_db import models, PAGE_LIMIT, DBSession
from limbless_db.categories import HTTPResponse, PoolStatus, LibraryStatus, SampleStatus

from .... import db, logger  # noqa
from ....forms.workflows import qubit_measure as wff
from ....forms import SelectSamplesForm

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user

qubit_measure_workflow = Blueprint("qubit_measure_workflow", __name__, url_prefix="/api/workflows/qubit_measure/")


def get_context(request: Request) -> dict:
    if request.method == "GET":
        args = request.args
    elif request.method == "POST":
        args = request.form
    else:
        raise NotImplementedError()
    context = {}
    if (seq_request_id := args.get("seq_request_id")) is not None:
        try:
            seq_request_id = int(seq_request_id)
            if (seq_request := db.get_seq_request(seq_request_id)) is None:
                return abort(HTTPResponse.NOT_FOUND.id)
            context["seq_request"] = seq_request
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
    if (experiment_id := args.get("experiment_id")) is not None:
        try:
            experiment_id = int(experiment_id)
            if (experiment := db.get_experiment(experiment_id)) is None:
                return abort(HTTPResponse.NOT_FOUND.id)
            context["experiment"] = experiment
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
    if (pool_id := args.get("pool_id")) is not None:
        try:
            pool_id = int(pool_id)
            if (pool := db.get_pool(pool_id)) is None:
                return abort(HTTPResponse.NOT_FOUND.id)
            context["pool"] = pool
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
        
    return context


@qubit_measure_workflow.route("begin", methods=["GET"])
@login_required
def begin():
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    context = get_context(request)
    form = SelectSamplesForm(
        workflow="qubit_measure", context=context,
        sample_status_filter=[SampleStatus.STORED],
        library_status_filter=[LibraryStatus.PREPARING],
        pool_status_filter=[PoolStatus.STORED],
        select_lanes=True
    )
    return form.make_response()


@qubit_measure_workflow.route("select", methods=["POST"])
@login_required
def select():
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)

    context = get_context(request)
    form = SelectSamplesForm(workflow="qubit_measure", formdata=request.form, context=context)
    if not form.validate():
        return form.make_response()
    sample_table, library_table, pool_table, lane_table = form.get_tables()
    
    complete_qubit_measure_form = wff.CompleteQubitMeasureForm()
    metadata: dict[str, Any] = {"workflow": "qubit_measure"}

    if (experiment := context.get("experiment")) is not None:
        metadata["experiment_id"] = experiment.id
    if (seq_request := context.get("seq_request")) is not None:
        metadata["seq_request_id"] = seq_request.id
    if (pool := context.get("pool")) is not None:
        metadata["pool_id"] = pool.id

    complete_qubit_measure_form.metadata = metadata
    complete_qubit_measure_form.add_table("sample_table", sample_table)
    complete_qubit_measure_form.add_table("library_table", library_table)
    complete_qubit_measure_form.add_table("pool_table", pool_table)
    complete_qubit_measure_form.add_table("lane_table", lane_table)
    complete_qubit_measure_form.update_data()

    complete_qubit_measure_form.prepare()
    return complete_qubit_measure_form.make_response()


@qubit_measure_workflow.route("complete", methods=["POST"])
@login_required
def complete():
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
        
    return wff.CompleteQubitMeasureForm(formdata=request.form).process_request()