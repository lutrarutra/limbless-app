from typing import TYPE_CHECKING

from flask import Blueprint, render_template, abort, url_for, request
from flask_login import login_required

from opengsync_db import models, db_session
from opengsync_db.categories import HTTPResponse
from ... import forms, db, logger, page_route  # noqa

seq_requests_page_bp = Blueprint("seq_requests_page", __name__)

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user


@page_route(seq_requests_page_bp, db=db)
def seq_requests():
    return render_template("seq_requests_page.html")


@page_route(seq_requests_page_bp, db=db)
def seq_request(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)

    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)

    path_list = [
        ("Requests", url_for("seq_requests_page.seq_requests")),
        (f"Request {seq_request_id}", ""),
    ]
    if (_from := request.args.get("from")) is not None:
        page, id = _from.split("@")
        if page == "experiment":
            path_list = [
                ("Experiments", url_for("experiments_page.experiments")),
                (f"Experiment {id}", url_for("experiments_page.experiment", experiment_id=id)),
                (f"Request {seq_request_id}", ""),
            ]
        elif page == "user":
            path_list = [
                ("Users", url_for("users_page.users")),
                (f"User {id}", url_for("users_page.user", user_id=id)),
                (f"Request {seq_request_id}", ""),
            ]
        elif page == "library":
            path_list = [
                ("Libraries", url_for("libraries_page.libraries")),
                (f"Library {id}", url_for("libraries_page.library", library_id=id)),
                (f"Request {seq_request_id}", ""),
            ]
        elif page == "pool":
            path_list = [
                ("Pools", url_for("pools_page.pools")),
                (f"Pool {id}", url_for("pools_page.pool", pool_id=id)),
                (f"Request {seq_request_id}", ""),
            ]
        elif page == "group":
            path_list = [
                ("Groups", url_for("groups_page.groups")),
                (f"Group {id}", url_for("groups_page.group", group_id=id)),
                (f"Request {seq_request_id}", ""),
            ]
        elif page == "sample":
            path_list = [
                ("Samples", url_for("samples_page.samples")),
                (f"Sample {id}", url_for("samples_page.sample", sample_id=id)),
                (f"Request {seq_request_id}", ""),
            ]

    process_request_form = forms.ProcessRequestForm(seq_request=seq_request)
    seq_auth_form = forms.SeqAuthForm(seq_request=seq_request)
    seq_request_share_email_form = forms.SeqRequestShareEmailForm()

    return render_template(
        "seq_request_page.html",
        seq_request=seq_request,
        path_list=path_list,
        seq_request_share_email_form=seq_request_share_email_form,
        process_request_form=process_request_form,
        seq_auth_form=seq_auth_form,
    )
