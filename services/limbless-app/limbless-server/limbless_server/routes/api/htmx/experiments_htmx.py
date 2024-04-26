import os
from typing import TYPE_CHECKING, Literal

import pandas as pd

from flask import Blueprint, url_for, render_template, flash, abort, request, current_app
from flask_htmx import make_response
from flask_login import login_required

from limbless_db import models, DBSession, PAGE_LIMIT
from limbless_db.categories import HTTPResponse, ExperimentStatus

from .... import db, forms, logger
from ....tools import io as iot

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user

experiments_htmx = Blueprint("experiments_htmx", __name__, url_prefix="/api/hmtx/experiments/")


@experiments_htmx.route("get/<int:page>")
@login_required
def get(page: int):
    sort_by = request.args.get("sort_by", "id")
    order = request.args.get("order", "desc")
    descending = order == "desc"
    offset = PAGE_LIMIT * page

    if sort_by not in models.Experiment.sortable_fields:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    with DBSession(db) as session:
        experiments, n_pages = session.get_experiments(
            offset=offset, sort_by=sort_by, descending=descending
        )

    return make_response(
        render_template(
            "components/tables/experiment.html",
            experiments=experiments,
            experiments_n_pages=n_pages, experiments_active_page=page,
            experiments_current_sort=sort_by, experiments_current_sort_order=order
        ), push_url=False
    )


@experiments_htmx.route("get_form/<string:form_type>", methods=["GET"])
@login_required
def get_form(form_type: Literal["create", "edit"]):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if form_type not in ["create", "edit"]:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if (experiment_id := request.args.get("experiment_id")) is not None:
        try:
            experiment_id = int(experiment_id)
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
        
        if form_type != "edit":
            return abort(HTTPResponse.BAD_REQUEST.id)
        
        with DBSession(db) as session:
            if (experiment := session.get_experiment(experiment_id)) is None:
                return abort(HTTPResponse.NOT_FOUND.id)
            
            return forms.models.ExperimentForm(form_type=form_type, experiment=experiment).make_response()
    
    # seq_request_id must be provided if form_type is "edit"
    if form_type == "edit":
        return abort(HTTPResponse.BAD_REQUEST.id)

    return forms.models.ExperimentForm(form_type=form_type, current_user=current_user).make_response()


@experiments_htmx.route("create", methods=["POST"])
@login_required
def create():
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)

    return forms.models.ExperimentForm(formdata=request.form, form_type="create").process_request()


@experiments_htmx.route("<int:experiment_id>/edit", methods=["POST"])
@login_required
def edit(experiment_id: int):
    with DBSession(db) as session:
        if not current_user.is_insider():
            return abort(HTTPResponse.FORBIDDEN.id)
        
        if (experiment := session.get_experiment(experiment_id)) is None:
            return abort(HTTPResponse.NOT_FOUND.id)

        return forms.models.ExperimentForm(formdata=request.form, form_type="edit").process_request(
            experiment=experiment
        )


@experiments_htmx.route("delete/<int:experiment_id>", methods=["DELETE"])
@login_required
def delete(experiment_id: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (experiment := db.get_experiment(experiment_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not experiment.is_deleteable():
        return abort(HTTPResponse.FORBIDDEN.id)

    db.delete_experiment(experiment_id)

    logger.debug(f"Deleted experiment on flowcell '{experiment.name}'")
    flash(f"Deleted experiment on flowcell '{experiment.name}'.", "success")
    
    return make_response(
        redirect=url_for("experiments_page.experiments_page"),
    )


@experiments_htmx.route("query", methods=["POST"])
@login_required
def query():
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    field_name = next(iter(request.form.keys()))
    if (word := request.form.get(field_name)) is None:
        return abort(HTTPResponse.BAD_REQUEST.id)

    results = db.query_experiments(word)

    return make_response(
        render_template(
            "components/search_select_results.html",
            results=results, field_name=field_name,
        ), push_url=False
    )


@experiments_htmx.route("<int:experiment_id>/render_lane_pooling_tables/<int:file_id>", methods=["GET"])
@login_required
def render_lane_pooling_tables(experiment_id: int, file_id: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
        
    if (experiment := db.get_experiment(experiment_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
        
    if (file := db.get_file(file_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    filepath = os.path.join(current_app.config["MEDIA_FOLDER"], file.path)
    df = pd.read_csv(filepath, sep="\t")

    df["molarity_color"] = "cemm-green"
    df.loc[df["molarity"] < models.Pool.warning_min_molarity, "molarity_color"] = "cemm-yellow"
    df.loc[df["molarity"] > models.Pool.warning_max_molarity, "molarity_color"] = "cemm-yellow"
    df.loc[df["molarity"] < models.Pool.error_min_molarity, "molarity_color"] = "cemm-red"
    df.loc[df["molarity"] > models.Pool.error_max_molarity, "molarity_color"] = "cemm-red"

    if "lane" not in df.columns:
        target_molarity = df["target_molarity"].values[0]
        target_total_volume = df["target_total_volume"].values[0]
        pipet = df["pipet"].sum()
        eb_volume = target_total_volume - pipet
        return make_response(
            render_template(
                "components/experiment-pooling-ratios.html", experiment=experiment, df=df,
                target_molarity=target_molarity, target_total_volume=target_total_volume,
                pipet=pipet, eb_volume=eb_volume
            )
        )
    
    return make_response(
        render_template(
            "components/lane-pooling-ratios.html", experiment=experiment, df=df
        )
    )


@experiments_htmx.route("table_query", methods=["POST"])
@login_required
def table_query():
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (word := request.form.get("name", None)) is not None:
        field_name = "name"
    elif (word := request.form.get("id", None)) is not None:
        field_name = "id"
    else:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if word is None:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if field_name == "name":
        experiments = db.query_experiments(word)
    elif field_name == "id":
        try:
            experiments = [db.get_experiment(int(word))]
        except ValueError:
            experiments = []

    return make_response(
        render_template(
            "components/tables/experiment.html",
            experiments=experiments, experiments_current_query=word, field_name=field_name
        ), push_url=False
    )
                     

@experiments_htmx.route("<int:experiment_id>/lane_pool/<int:pool_id>/<int:lane_num>", methods=["POST"])
@login_required
def lane_pool(experiment_id: int, pool_id: int, lane_num: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (experiment := db.get_experiment(experiment_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if (pool := db.get_pool(pool_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if lane_num > experiment.num_lanes or lane_num < 1:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if (_ := db.get_experiment_lane(experiment_id=experiment_id, lane_num=lane_num)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    db.add_pool_to_lane(
        experiment_id=experiment_id,
        pool_id=pool_id,
        lane_num=lane_num
    )

    logger.debug(f"Added pool '{pool.name}' to experiment (id='{experiment_id}') on lane '{lane_num}'")
    flash(f"Added pool '{pool.name}' to lane '{lane_num}'.", "success")

    return make_response(
        redirect=url_for("experiments_page.experiment_page", experiment_id=experiment.id),
        push_url=False
    )


@experiments_htmx.route("<int:experiment_id>/unlane_pool/<int:pool_id>/<int:lane_num>", methods=["DELETE"])
@login_required
def unlane_pool(experiment_id: int, pool_id: int, lane_num: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (experiment := db.get_experiment(experiment_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if (pool := db.get_pool(pool_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if lane_num > experiment.num_lanes or lane_num < 1:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if (_ := db.get_experiment_lane(experiment_id=experiment_id, lane_num=lane_num)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    db.remove_pool_from_lane(
        experiment_id=experiment_id,
        pool_id=pool_id,
        lane_num=lane_num,
    )

    logger.debug(f"Removed pool '{pool.name}' from lane '{lane_num}' (experiment_id='{experiment_id}')")
    flash(f"Removed pool '{pool.name}' from lane '{lane_num}'.", "success")

    return make_response(
        redirect=url_for("experiments_page.experiment_page", experiment_id=experiment.id),
        push_url=False
    )


@experiments_htmx.route("<int:experiment_id>/upload_file", methods=["POST"])
@login_required
def upload_file(experiment_id: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (experiment := db.get_experiment(experiment_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    return forms.file.ExperimentAttachmentForm(experiment_id=experiment_id, formdata=request.form | request.files).process_request(
        experiment=experiment, user=current_user
    )


@experiments_htmx.route("<int:experiment_id>/delete_file/<int:file_id>", methods=["DELETE"])
@login_required
def delete_file(experiment_id: int, file_id: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (experiment := db.get_experiment(experiment_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if (file := db.get_file(file_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    db.remove_file_from_experiment(experiment_id=experiment.id, file_id=file_id)
    filepath = os.path.join(current_app.config["MEDIA_FOLDER"], file.path)
    if os.path.exists(filepath):
        os.remove(filepath)

    logger.info(f"Deleted file '{file.name}' from experiment (id='{experiment_id}')")
    flash(f"Deleted file '{file.name}' from experiment.", "success")
    return make_response(redirect=url_for("experiments_page.experiment_page", experiment_id=experiment.id))


@experiments_htmx.route("<int:experiment_id>/add_comment", methods=["POST"])
@login_required
def add_comment(experiment_id: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (experiment := db.get_experiment(experiment_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    return forms.comment.ExperimentCommentForm(experiment_id=experiment_id, formdata=request.form).process_request(user=current_user, experiment=experiment)


@experiments_htmx.route("<int:experiment_id>/remove_pool", methods=["DELETE"])
@login_required
def remove_pool(experiment_id: int):
    with DBSession(db) as session:
        if not current_user.is_insider():
            return abort(HTTPResponse.FORBIDDEN.id)
        
        if (experiment := session.get_experiment(experiment_id)) is None:
            return abort(HTTPResponse.NOT_FOUND.id)
        
        if (pool_id := request.args.get("pool_id")) is None:
            return abort(HTTPResponse.BAD_REQUEST.id)
        
        try:
            pool_id = int(pool_id)
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
        
        if (_ := session.get_pool(pool_id)) is None:
            return abort(HTTPResponse.NOT_FOUND.id)

        session.unlink_pool_experiment(experiment_id=experiment_id, pool_id=pool_id)

        logger.info(f"Removed pool (id='{pool_id}') from experiment (id='{experiment_id}')")
        flash("Removed pool from experiment.", "success")

    return make_response(
        redirect=url_for("experiments_page.experiment_page", experiment_id=experiment.id),
    )
    

@experiments_htmx.route("<int:experiment_id>/overview", methods=["GET"])
@login_required
def overview(experiment_id: int):
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if (experiment := db.get_experiment(experiment_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    LINK_WIDTH_UNIT = 1
    
    df = db.get_experiment_libraries_df(experiment_id=experiment_id, include_seq_request=True, collapse_lanes=False)

    if df.empty:
        return make_response(
            render_template(
                "components/plots/experiment_overview.html",
                links=[], nodes=[]
            )
        )
    nodes = []
    links = []

    experiment_node = {
        "node": 0,
        "name": experiment.name
    }
    nodes.append(experiment_node)
    node_idx = 1

    libraries = {}
    pools = {}
    for (request_id, request_name), _df in df.groupby(["request_id", "request_name"]):
        request_node = {
            "node": node_idx,
            "name": request_name
        }
        nodes.append(request_node)
        node_idx += 1
        for lane, __df in _df.groupby("lane"):
            lane_node = {
                "node": node_idx,
                "name": f"Lane {lane}"
            }
            node_idx += 1
            nodes.append(lane_node)
            lane_width = 0
            for (pool_id, pool_name), ___df in __df.groupby(["pool_id", "pool_name"]):
                if pool_id not in pools.keys():
                    pool_node = {
                        "node": node_idx,
                        "name": pool_name
                    }
                    node_idx += 1
                    nodes.append(pool_node)
                    pools[pool_id] = pool_node
                else:
                    pool_node = pools[pool_id]

                width = ___df.shape[0] / len(_df[_df["pool_id"] == pool_id]["lane"].unique())
                links.append({
                    "source": pool_node["node"],
                    "target": lane_node["node"],
                    "value": LINK_WIDTH_UNIT * width
                })
                lane_width += width

                for i, row in ___df.iterrows():
                    if row["library_id"] not in libraries.keys():
                        library_node = {
                            "node": node_idx,
                            "name": row["library_type"].name
                        }
                        node_idx += 1
                        nodes.append(library_node)
                        libraries[row["library_id"]] = library_node
                        links.append({
                            "source": library_node["node"],
                            "target": pool_node["node"],
                            "value": LINK_WIDTH_UNIT
                        })
                        links.append({
                            "source": request_node["node"],
                            "target": library_node["node"],
                            "value": LINK_WIDTH_UNIT
                        })
                    else:
                        library_node = libraries[row["library_id"]]

            links.append({
                "source": lane_node["node"],
                "target": experiment_node["node"],
                "value": LINK_WIDTH_UNIT * lane_width
            })

    return make_response(
        render_template(
            "components/plots/experiment_overview.html",
            links=links, nodes=nodes
        )
    )