import os
from typing import Optional, TYPE_CHECKING

from flask import Blueprint, url_for, render_template, flash, request, abort, send_file, current_app
from flask_htmx import make_response
from flask_login import login_required

from .... import db, logger, forms, models
from ....categories import HttpResponse

if TYPE_CHECKING:
    current_user: models.User = None
else:
    from flask_login import current_user


seq_request_form_htmx = Blueprint("seq_request_form_htmx", __name__, url_prefix="/api/seq_request_form/")


# Template sample annotation sheet
@seq_request_form_htmx.route("download_template/<string:type>", methods=["GET"])
@login_required
def download_template(type: str):
    if type == "raw":
        name = "sas_raw_libraries.tsv"
    elif type == "premade":
        name = "sas_premade_libraries.tsv"
    elif type == "cmo":
        name = "cmo.tsv"
    else:
        return abort(HttpResponse.NOT_FOUND.value.id)

    path = os.path.join(
        current_app.root_path, "..",
        "static", "resources", "templates", name
    )

    return send_file(path, mimetype="text/csv", as_attachment=True, download_name=name)


# Template sequencing authorization form
@seq_request_form_htmx.route("seq_auth_form/download", methods=["GET"])
@login_required
def download_seq_auth_form():
    name = "seq_auth_form_v2.pdf"

    path = os.path.join(
        current_app.root_path,
        "static", "resources", "templates", name
    )

    return send_file(path, mimetype="pdf", as_attachment=True, download_name=name)


# 0. Restart form
@seq_request_form_htmx.route("<int:seq_request_id>/restart_form", methods=["GET"])
@login_required
def restart_form(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    return make_response(
        render_template(
            "components/popups/seq_request/sas-1.html",
            form=forms.TableInputForm("seq_request"),
            seq_request=seq_request
        ), push_url=False
    )


# 1. Input sample annotation sheet
@seq_request_form_htmx.route("<int:seq_request_id>/parse_table", methods=["POST"])
@login_required
def parse_table(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    return forms.TableInputForm(
        upload_dir="seq_request", formdata=request.form | request.files
    ).process_request(
        seq_request=seq_request, user_id=current_user.id
    )


# 2. Select project
@seq_request_form_htmx.route("<int:seq_request_id>/project_select", methods=["POST"])
@login_required
def select_project(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    return forms.ProjectMappingForm(formdata=request.form).process_request(
        seq_request=seq_request, user_id=current_user.id,
        seq_request_id=seq_request_id
    )


# 3. Map organisms if new samples
@seq_request_form_htmx.route("<int:seq_request_id>/map_organisms", methods=["POST"])
@login_required
def map_organisms(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    return forms.OrganismMappingForm(formdata=request.form).process_request(
        seq_request=seq_request
    )


# 4. Map libraries
@seq_request_form_htmx.route("<int:seq_request_id>/map_libraries", methods=["POST"])
@login_required
def map_libraries(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    return forms.LibraryMappingForm(formdata=request.form).process_request(
        seq_request=seq_request
    )


# 5. Map index_kits
@seq_request_form_htmx.route("<int:seq_request_id>/map_index_kits", methods=["POST"])
@login_required
def map_index_kits(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)

    return forms.IndexKitMappingForm(formdata=request.form).process_request(
        seq_request=seq_request
    )


# 6. Specify Features
@seq_request_form_htmx.route("<int:seq_request_id>/parse_cmo_reference", methods=["POST"])
@login_required
def parse_cmo_reference(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)

    return forms.CMOReferenceInputForm(formdata=request.form).process_request(
        seq_request=seq_request
    )


# 7. Map Feature Kits
@seq_request_form_htmx.route("<int:seq_request_id>/map_feature_kits", methods=["POST"])
@login_required
def map_feature_kits(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)

    return forms.FeatureKitMappingForm(formdata=request.form).process_request(
        seq_request=seq_request
    )

    
# 8. Map pools
@seq_request_form_htmx.route("<int:seq_request_id>/map_pools", methods=["POST"])
@login_required
def map_pools(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    return forms.PoolMappingForm(formdata=request.form).process_request(
        seq_request=seq_request
    )


# 9. Check barcodes
@seq_request_form_htmx.route("<int:seq_request_id>/check_barcodes", methods=["POST"])
@login_required
def check_barcodes(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    return forms.BarcodeCheckForm(formdata=request.form).process_request(
        seq_request=seq_request, user_id=current_user.id
    )
