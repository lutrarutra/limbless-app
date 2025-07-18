from typing import TYPE_CHECKING

from flask import Blueprint, render_template, abort, url_for, request
from flask_login import login_required

from opengsync_db import db_session
from opengsync_db.categories import PoolStatus
from opengsync_db.models import User
from opengsync_db.categories import HTTPResponse

from ... import db

if TYPE_CHECKING:
    current_user: User = None  # type: ignore
else:
    from flask_login import current_user

pools_page_bp = Blueprint("pools_page", __name__)


@pools_page_bp.route("/pools")
@login_required
def pools_page():
    return render_template("pools_page.html")


@pools_page_bp.route("/pools/<int:pool_id>")
@db_session(db)
@login_required
def pool_page(pool_id: int):
    if (pool := db.get_pool(pool_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and pool.owner_id != current_user.id:
        return abort(HTTPResponse.FORBIDDEN.id)

    path_list = [
        ("Pools", url_for("pools_page.pools_page")),
        (f"Pool {pool.id}", ""),
    ]
    if (_from := request.args.get("from", None)) is not None:
        page, id = _from.split("@")
        if page == "experiment":
            path_list = [
                ("Experiments", url_for("experiments_page.experiments_page")),
                (f"Experiment {id}", url_for("experiments_page.experiment_page", experiment_id=id)),
                (f"Pool {pool_id}", ""),
            ]
        elif page == "library":
            path_list = [
                ("Libraries", url_for("libraries_page.libraries_page")),
                (f"Library {id}", url_for("libraries_page.library_page", library_id=id)),
                (f"Pool {pool_id}", ""),
            ]
        elif page == "seq_request":
            path_list = [
                ("Requests", url_for("seq_requests_page.seq_requests_page")),
                (f"Request {id}", url_for("seq_requests_page.seq_request_page", seq_request_id=id)),
                (f"Pool {pool_id}", ""),
            ]
        elif page == "lab_prep":
            path_list = [
                ("Lab Preps", url_for("lab_preps_page.lab_preps_page")),
                (f"Lab Prep {id}", url_for("lab_preps_page.lab_prep_page", lab_prep_id=id)),
                (f"Pool {pool_id}", ""),
            ]

    is_editable = pool.status == PoolStatus.DRAFT or current_user.is_insider()
    is_indexed = True and len(pool.libraries) > 0
    for library in pool.libraries:
        if not library.is_indexed():
            is_indexed = False
            break

    return render_template(
        "pool_page.html", pool=pool, path_list=path_list, is_editable=is_editable,
        is_plated=False, is_indexed=is_indexed
    )
