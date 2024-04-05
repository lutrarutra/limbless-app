from typing import TYPE_CHECKING

from flask import Blueprint, request, abort
from flask_login import login_required

from limbless_db import models, DBSession
from limbless_db.categories import HTTPResponse

from .... import db, logger
from ....forms.workflows import load_flow_cell as wff

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user

load_flow_cell_workflow = Blueprint("load_flow_cell_workflow", __name__, url_prefix="/api/workflows/load_flow_cell/")


@load_flow_cell_workflow.route("<int:experiment_id>/begin", methods=["GET"])
@login_required
def begin(experiment_id: int):
    with DBSession(db) as session:
        if not current_user.is_insider():
            return abort(HTTPResponse.FORBIDDEN.id)
        
        if (experiment := session.get_experiment(experiment_id)) is None:
            return abort(HTTPResponse.NOT_FOUND.id)

    if experiment.workflow.combined_lanes:
        form = wff.UnifiedLoadFlowCellForm()
    else:
        form = wff.LoadFlowCellForm()
        
    context = form.prepare(experiment)
    return form.make_response(experiment=experiment, **context)


@load_flow_cell_workflow.route("<int:experiment_id>/dilute", methods=["POST"])
@login_required
def dilute(experiment_id: int):
    with DBSession(db) as session:
        if not current_user.is_insider():
            return abort(HTTPResponse.FORBIDDEN.id)
        
        if (experiment := session.get_experiment(experiment_id)) is None:
            return abort(HTTPResponse.NOT_FOUND.id)
        
        experiment.files

    if experiment.workflow.combined_lanes:
        form = wff.UnifiedLoadFlowCellForm(request.form)
    else:
        form = wff.LoadFlowCellForm(request.form)

    return form.process_request(experiment=experiment)