from flask import Blueprint, url_for, render_template, flash, abort, request
from flask_htmx import make_response
from flask_login import login_required, current_user

from .... import db, forms, logger, models, PAGE_LIMIT
from ....categories import UserRole, HttpResponse
from ....core.DBSession import DBSession

experiments_htmx = Blueprint("experiments_htmx", __name__, url_prefix="/api/experiments/")


@experiments_htmx.route("get/<int:page>")
@login_required
def get(page: int):
    sort_by = request.args.get("sort_by", "id")
    order = request.args.get("order", "desc")
    descending = order == "desc"
    offset = PAGE_LIMIT * page

    if sort_by not in models.Experiment.sortable_fields:
        return abort(HttpResponse.BAD_REQUEST.value.id)
    
    with DBSession(db.db_handler) as session:
        experiments, n_pages = session.get_experiments(
            limit=PAGE_LIMIT, offset=offset, sort_by=sort_by, descending=descending
        )

    return make_response(
        render_template(
            "components/tables/experiment.html",
            experiments=experiments,
            n_pages=n_pages, active_page=page,
            current_sort=sort_by, current_sort_order=order
        ), push_url=False
    )


@experiments_htmx.route("create", methods=["POST"])
@login_required
def create():
    if not current_user.is_insider():
        return abort(HttpResponse.FORBIDDEN.value.id)

    experiment_form = forms.ExperimentForm()

    validated, experiment_form = experiment_form.custom_validate(
        db_handler=db.db_handler, user_id=current_user.id,
    )

    if not validated:
        return make_response(
            render_template(
                "forms/experiment.html",
                experiment_form=experiment_form
            ), push_url=False
        )

    experiment = db.db_handler.create_experiment(
        flowcell=experiment_form.flowcell.data,
        sequencer_id=experiment_form.sequencer.data,
        r1_cycles=experiment_form.r1_cycles.data,
        r2_cycles=experiment_form.r2_cycles.data,
        i1_cycles=experiment_form.i1_cycles.data,
        i2_cycles=experiment_form.i2_cycles.data,
        num_lanes=experiment_form.num_lanes.data,
    )

    logger.debug(f"Created experiment on flowcell '{experiment.flowcell}'")
    flash(f"Created experiment on flowcell '{experiment.flowcell}'.", "success")

    return make_response(
        redirect=url_for("experiments_page.experiment_page", experiment_id=experiment.id),
    )


@experiments_htmx.route("<int:experiment_id>/edit", methods=["POST"])
@login_required
def edit(experiment_id: int):
    if not current_user.is_insider():
        return abort(HttpResponse.FORBIDDEN.value.id)
    
    if (experiment := db.db_handler.get_experiment(experiment_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)

    experiment_form = forms.ExperimentForm()
    validated, experiment_form = experiment_form.custom_validate(
        db_handler=db.db_handler,
        user_id=current_user.id,
    )

    if not validated:
        return make_response(
            render_template(
                "forms/experiment.html",
                experiment_form=experiment_form
            ), push_url=False
        )
    
    db.db_handler.update_experiment(
        experiment_id=experiment_id,
        flowcell=experiment_form.flowcell.data,
        r1_cycles=experiment_form.r1_cycles.data,
        r2_cycles=experiment_form.r2_cycles.data,
        i1_cycles=experiment_form.i1_cycles.data,
        i2_cycles=experiment_form.i2_cycles.data,
        num_lanes=experiment_form.num_lanes.data,
        sequencer_id=experiment_form.sequencer.data,
    )

    logger.debug(f"Edited experiment on flowcell '{experiment.flowcell}'")
    flash(f"Edited experiment on flowcell '{experiment.flowcell}'.", "success")

    return make_response(
        redirect=url_for("experiments_page.experiment_page", experiment_id=experiment.id),
    )


@experiments_htmx.route("delete/<int:experiment_id>", methods=["POST"])
@login_required
def delete(experiment_id: int):
    if not current_user.is_insider():
        return abort(HttpResponse.FORBIDDEN.value.id)
    
    if (experiment := db.db_handler.get_experiment(experiment_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    if not experiment.is_deleteable():
        return abort(HttpResponse.FORBIDDEN.value.id)

    db.db_handler.delete_experiment(experiment_id)

    logger.debug(f"Deleted experiment on flowcell '{experiment.flowcell}'")
    flash(f"Deleted experiment on flowcell '{experiment.flowcell}'.", "success")
    
    return make_response(
        redirect=url_for("experiments_page.experiments_page"),
    )


@experiments_htmx.route("<int:experiment_id>/add_library/<int:library_id>/<int:lane>", methods=["POST"])
@login_required
def add_library(experiment_id: int, library_id: int, lane: int):
    if not current_user.is_insider():
        return abort(HttpResponse.FORBIDDEN.value.id)
    
    if (experiment := db.db_handler.get_experiment(experiment_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    if (library := db.db_handler.get_library(library_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    if not experiment.is_editable():
        return abort(HttpResponse.FORBIDDEN.value.id)
    
    if library.is_raw_library():
        raise NotImplementedError("Raw libraries are not supported yet.")
    
    db.db_handler.link_experiment_library(
        experiment_id=experiment_id,
        library_id=library_id,
        lane=lane,
    )

    logger.debug(f"Added library '{library.name}' to experiment (id='{experiment_id}') on lane '{lane}'")
    flash(f"Added library '{library.name}' to experiment on lane '{lane}'.", "success")

    return make_response(
        redirect=url_for("experiments_page.experiment_page", experiment_id=experiment_id),
        push_url=False
    )


@experiments_htmx.route("<int:experiment_id>/remove_library/<int:library_id>/<int:lane>", methods=["DELETE"])
@login_required
def remove_library(experiment_id: int, library_id: int, lane: int):
    if not current_user.is_insider():
        return abort(HttpResponse.FORBIDDEN.value.id)
    
    if (experiment := db.db_handler.get_experiment(experiment_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    if (library := db.db_handler.get_library(library_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    if lane > experiment.num_lanes or lane < 1:
        return abort(HttpResponse.BAD_REQUEST.value.id)
    
    if not experiment.is_editable():
        return abort(HttpResponse.FORBIDDEN.value.id)
    
    db.db_handler.unlink_experiment_library(
        experiment_id=experiment_id,
        library_id=library_id,
        lane=lane,
    )

    logger.debug(f"Removed library '{library.name}' from experiment  (id='{experiment_id}') on lane '{lane}'")
    flash(f"Removed library '{library.name}' from experiment on lane '{lane}'.", "success")

    return make_response(
        redirect=url_for("experiments_page.experiment_page", experiment_id=experiment.id),
        push_url=False
    )
    
