from typing import TYPE_CHECKING

from flask import Blueprint, request, abort
from flask_login import login_required

from opengsync_db import models, db_session
from opengsync_db.categories import HTTPResponse

from .... import db, logger  # noqa
from ....forms.workflows import load_flow_cell as wff

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user

load_flow_cell_workflow = Blueprint("load_flow_cell_workflow", __name__, url_prefix="/api/workflows/load_flow_cell/")


@load_flow_cell_workflow.route("<int:experiment_id>/begin", methods=["GET"])
@db_session(db)
@login_required
def begin(experiment_id: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (experiment := db.get_experiment(experiment_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)

    if experiment.workflow.combined_lanes:
        form = wff.UnifiedLoadFlowCellForm(experiment=experiment)
    else:
        form = wff.LoadFlowCellForm(experiment=experiment)
        
    form.prepare()
    return form.make_response()


@load_flow_cell_workflow.route("<int:experiment_id>/load", methods=["POST"])
@db_session(db)
@login_required
def load(experiment_id: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (experiment := db.get_experiment(experiment_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    experiment.files

    if experiment.workflow.combined_lanes:
        form = wff.UnifiedLoadFlowCellForm(experiment=experiment, formdata=request.form)
    else:
        form = wff.LoadFlowCellForm(experiment=experiment, formdata=request.form)

    return form.process_request()