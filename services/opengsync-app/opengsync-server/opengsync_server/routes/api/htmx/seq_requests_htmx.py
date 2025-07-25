import os
import json
from io import BytesIO
from typing import TYPE_CHECKING, Literal

from flask import Blueprint, url_for, render_template, flash, abort, request, Response, current_app
from flask_htmx import make_response
from flask_login import login_required
from werkzeug.utils import secure_filename  # type: ignore
import pandas as pd

from opengsync_db import models, PAGE_LIMIT, db_session
from opengsync_db.categories import HTTPResponse, SeqRequestStatus, LibraryStatus, LibraryType, SampleStatus, SubmissionType, PoolStatus
from opengsync_db.core import exceptions
from .... import db, forms, logger, htmx_route

if TYPE_CHECKING:
    current_user: models.User = None    # type: ignore
else:
    from flask_login import current_user


seq_requests_htmx = Blueprint("seq_requests_htmx", __name__, url_prefix="/api/hmtx/seq_requests/")


@seq_requests_htmx.route("get", methods=["GET"], defaults={"page": 0})
@seq_requests_htmx.route("get/<int:page>", methods=["GET"])
@db_session(db)
@login_required
def get(page: int):
    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "desc")
    descending = sort_order == "desc"
    offset = PAGE_LIMIT * page

    if (status_in := request.args.get("status_id_in")) is not None:
        status_in = json.loads(status_in)
        try:
            status_in = [SeqRequestStatus.get(int(status)) for status in status_in]
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
        
        if len(status_in) == 0:
            status_in = None

    if (submission_type_in := request.args.get("submission_type_id_in")) is not None:
        submission_type_in = json.loads(submission_type_in)
        try:
            submission_type_in = [SubmissionType.get(int(submission_type)) for submission_type in submission_type_in]
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
        
        if len(submission_type_in) == 0:
            submission_type_in = None
    
    seq_requests: list[models.SeqRequest] = []

    user_id = current_user.id if not current_user.is_insider() else None

    seq_requests, n_pages = db.get_seq_requests(
        offset=offset, user_id=user_id, sort_by=sort_by, descending=descending,
        submission_type_in=submission_type_in,
        show_drafts=True, status_in=status_in, count_pages=True
    )

    return make_response(
        render_template(
            "components/tables/seq_request.html",
            seq_requests=seq_requests,
            n_pages=n_pages, active_page=page,
            sort_by=sort_by, sort_order=sort_order,
            SeqRequestStatus=SeqRequestStatus,
            status_in=status_in,
            submission_type_in=submission_type_in,
        )
    )


@htmx_route(seq_requests_htmx, db=db)
def get_form(form_type: Literal["create", "edit"]):
    if form_type not in ["create", "edit"]:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if (seq_request_id := request.args.get("seq_request_id")) is not None:
        try:
            seq_request_id = int(seq_request_id)
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
        
        if form_type != "edit":
            return abort(HTTPResponse.BAD_REQUEST.id)
        
        if (seq_request := db.get_seq_request(seq_request_id)) is None:
            return abort(HTTPResponse.NOT_FOUND.id)
        
        if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
            affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
            if affiliation is None:
                return abort(HTTPResponse.FORBIDDEN.id)
        
        return forms.models.SeqRequestForm(form_type=form_type, seq_request=seq_request).make_response()
    
    # seq_request_id must be provided if form_type is "edit"
    if form_type == "edit":
        return abort(HTTPResponse.BAD_REQUEST.id)

    return forms.models.SeqRequestForm(form_type=form_type, current_user=current_user).make_response()


@htmx_route(seq_requests_htmx, db=db)
def export(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)

    file_name = secure_filename(f"{seq_request.name}_request.xlsx")

    metadata = {
        "Name": [seq_request.name],
        "Description": [seq_request.description],
        "Requestor": [seq_request.requestor.name],
        "Requestor Email": [seq_request.requestor.email],
        "Submission Type": [seq_request.submission_type.name],
        "Organization": [seq_request.organization_contact.name],
        "Organization Address": [seq_request.organization_contact.address],
        "Contact Person": [seq_request.contact_person.name],
        "Contact Person Email": [seq_request.contact_person.email],
        "Contact Person Phone": [seq_request.contact_person.phone],
    }

    if seq_request.group is not None:
        metadata["Group"] = [seq_request.group.name]
        metadata["Group ID"] = [seq_request.group.id]
    
    if seq_request.billing_code is not None:
        metadata["Billing Code"] = [seq_request.billing_code]
        
    metadata_df = pd.DataFrame.from_records(metadata).T

    libraries_df = db.get_seq_request_libraries_df(seq_request_id, include_indices=True)
    features_df = db.get_seq_request_features_df(seq_request_id)

    bytes_io = BytesIO()
    # TODO: export features, CMOs, VISIUM metadata, etc...
    with pd.ExcelWriter(bytes_io, engine="openpyxl") as writer:  # type: ignore
        metadata_df.to_excel(writer, sheet_name="metadata", index=True)
        libraries_df.to_excel(writer, sheet_name="libraries", index=False)
        features_df.to_excel(writer, sheet_name="features", index=False)

    bytes_io.seek(0)
        
    return Response(
        bytes_io, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-disposition": f"attachment; filename={file_name}"}
    )


@htmx_route(seq_requests_htmx, db=db)
def export_libraries(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)

    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
        
    file_name = secure_filename(f"{seq_request.name}_libraries.tsv")

    libraries_df = db.get_seq_request_libraries_df(seq_request_id=seq_request_id, include_indices=True)

    return Response(
        libraries_df.to_csv(sep="\t", index=False), mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={file_name}"}
    )


@htmx_route(seq_requests_htmx, db=db, methods=["POST"])
def edit(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)

    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)

    return forms.models.SeqRequestForm(form_type="edit", formdata=request.form).process_request(
        seq_request=seq_request, user=current_user
    )


@htmx_route(seq_requests_htmx, db=db, methods=["DELETE"])
def delete(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)

    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)

    db.delete_seq_request(seq_request_id)

    flash(f"Deleted sequencing request '{seq_request.name}'", "success")
    return make_response(
        redirect=url_for("seq_requests_page.seq_requests"),
    )


@htmx_route(seq_requests_htmx, db=db, methods=["POST"])
def archive(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
    seq_request.status = SeqRequestStatus.ARCHIVED
    seq_request = db.update_seq_request(seq_request)
    flash(f"Archived sequencing request '{seq_request.name}'", "success")
    logger.debug(f"Archived sequencing request '{seq_request.name}'")
    return make_response(
        redirect=url_for("seq_requests_page.seq_request", seq_request_id=seq_request.id),
    )


@htmx_route(seq_requests_htmx, db=db, methods=["POST"])
def unarchive(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)
    
    seq_request.status = SeqRequestStatus.DRAFT
    seq_request.timestamp_submitted_utc = None
    seq_request = db.update_seq_request(seq_request)

    flash(f"Unarchived sequencing request '{seq_request.name}'", "success")
    logger.debug(f"Unarchived sequencing request '{seq_request.name}'")

    return make_response(
        redirect=url_for("seq_requests_page.seq_request", seq_request_id=seq_request.id),
    )


@htmx_route(seq_requests_htmx, db=db, methods=["GET", "POST"])
def submit_request(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
    if not seq_request.is_submittable():
        return abort(HTTPResponse.FORBIDDEN.id)

    if request.method == "GET":
        form = forms.SubmitSeqRequestForm(seq_request=seq_request)
        return form.make_response()
    else:
        form = forms.SubmitSeqRequestForm(seq_request=seq_request, formdata=request.form)
        return form.process_request(user=current_user)


@htmx_route(seq_requests_htmx, db=db, methods=["POST"])
def create():
    return forms.models.SeqRequestForm(form_type="create", formdata=request.form).process_request(user=current_user, seq_request=None)


@htmx_route(seq_requests_htmx, db=db, methods=["POST"])
def upload_auth_form(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
    return forms.SeqAuthForm(
        seq_request=seq_request, formdata=request.form | request.files
    ).process_request(
        user=current_user
    )


@htmx_route(seq_requests_htmx, db=db, methods=["GET", "POST"])
def comment_form(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)

    if request.method == "GET":
        form = forms.comment.SeqRequestCommentForm(seq_request=seq_request)
        return form.make_response()
    elif request.method == "POST":
        form = forms.comment.SeqRequestCommentForm(seq_request=seq_request, formdata=request.form)
        return form.process_request(current_user)
    else:
        return abort(HTTPResponse.METHOD_NOT_ALLOWED.id)


@seq_requests_htmx.route("<int:seq_request_id>/file_form", methods=["GET", "POST"])
def file_form(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
        
    if request.method == "GET":
        form = forms.file.SeqRequestAttachmentForm(seq_request=seq_request)
        return form.make_response()
    elif request.method == "POST":
        form = forms.file.SeqRequestAttachmentForm(seq_request=seq_request, formdata=request.form | request.files)
        return form.process_request(current_user)
    else:
        return abort(HTTPResponse.METHOD_NOT_ALLOWED.id)


@htmx_route(seq_requests_htmx, db=db, methods=["DELETE"])
def delete_file(seq_request_id: int, file_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
    if (file := db.get_file(file_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if file not in seq_request.files:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    file_path = os.path.join(current_app.config["MEDIA_FOLDER"], file.path)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.delete_file(file_id=file.id)

    logger.info(f"Deleted file '{file.name}' from request (id='{seq_request_id}')")
    flash(f"Deleted file '{file.name}' from request.", "success")
    return make_response(redirect=url_for("seq_requests_page.seq_request", seq_request_id=seq_request_id))


@htmx_route(seq_requests_htmx, db=db, methods=["DELETE"])
def remove_auth_form(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if seq_request.seq_auth_form_file is None:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
        
    if seq_request.status != SeqRequestStatus.DRAFT:
        if not current_user.is_insider():
            return abort(HTTPResponse.FORBIDDEN.id)
        
    file = seq_request.seq_auth_form_file

    filepath = os.path.join(current_app.config["MEDIA_FOLDER"], file.path)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.delete_file(file_id=file.id)

    flash("Authorization form removed!", "success")
    logger.debug(f"Removed sequencing authorization form for sequencing request '{seq_request.name}'")

    return make_response(
        redirect=url_for("seq_requests_page.seq_request", seq_request_id=seq_request.id),
    )


@htmx_route(seq_requests_htmx, db=db, methods=["DELETE"])
def remove_library(seq_request_id: int):
    if (library_id := request.args.get("library_id")) is None:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
    if not current_user.is_insider():
        if seq_request.status != SeqRequestStatus.DRAFT:
            return abort(HTTPResponse.FORBIDDEN.id)

    try:
        library_id = int(library_id)
    except ValueError:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if (library := db.get_library(library_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
        
    db.delete_library(library_id)

    flash(f"Removed library '{library.name}' from sequencing request '{seq_request.name}'", "success")
    logger.debug(f"Removed library '{library.name}' from sequencing request '{seq_request.name}'")

    return make_response(
        redirect=url_for(
            "seq_requests_page.seq_request",
            seq_request_id=seq_request_id,
            tab="request-libraries-tab"
        ),
    )


@htmx_route(seq_requests_htmx, db=db, methods=["DELETE"])
def remove_sample(seq_request_id: int):
    if (sample_id := request.args.get("sample_id")) is None:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
    if not current_user.is_insider():
        if seq_request.status != SeqRequestStatus.DRAFT:
            return abort(HTTPResponse.FORBIDDEN.id)
        
    try:
        sample_id = int(sample_id)
    except ValueError:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if (sample := db.get_sample(sample_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)

    for library_link in sample.library_links:
        if library_link.library.seq_request_id != seq_request_id:
            continue
        
        db.delete_library(library_link.library.id)

    flash(f"Removed sample '{sample.name}' from sequencing request '{seq_request.name}'", "success")
    logger.debug(f"Removed sample '{sample.name}' from sequencing request '{seq_request.name}'")
    return make_response(
        redirect=url_for("seq_requests_page.seq_request", seq_request_id=seq_request_id),
    )
        

@htmx_route(seq_requests_htmx, db=db, methods=["DELETE"])
def remove_all_libraries(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)

    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
        
    if seq_request.status != SeqRequestStatus.DRAFT and not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)

    for library in seq_request.libraries:
        db.delete_library(library.id)

    flash(f"Removed all libraries from sequencing request '{seq_request.name}'", "success")
    logger.debug(f"Removed all libraries from sequencing request '{seq_request.name}'")

    return make_response(
        redirect=url_for("seq_requests_page.seq_request", seq_request_id=seq_request_id),
    )


@htmx_route(seq_requests_htmx, db=db)
def table_query():
    if (word := request.args.get("name")) is not None:
        field_name = "name"
    elif (word := request.args.get("id")) is not None:
        field_name = "id"
    elif (word := request.args.get("requestor_id")) is not None:
        field_name = "requestor_id"
    elif (word := request.args.get("group_id")) is not None:
        field_name = "group_id"
    else:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    user_id = current_user.id if not current_user.is_insider() else None

    if (status_in := request.args.get("status_id_in")) is not None:
        status_in = json.loads(status_in)
        try:
            status_in = [SeqRequestStatus.get(int(status)) for status in status_in]
        except ValueError:
            return abort(HTTPResponse.BAD_REQUEST.id)
        
        if len(status_in) == 0:
            status_in = None

    seq_requests: list[models.SeqRequest] = []
    if field_name == "name":
        seq_requests = db.query_seq_requests(name=word, user_id=user_id, status_in=status_in)
    elif field_name == "id":
        try:
            _id = int(word)
            if (seq_request := db.get_seq_request(_id)) is not None:
                if user_id is None or seq_request.requestor_id == user_id:
                    seq_requests = [seq_request]
                if status_in is not None and seq_request.status not in status_in:
                    seq_requests = []
        except ValueError:
            pass
    elif field_name == "requestor_id":
        seq_requests = db.query_seq_requests(requestor=word, user_id=user_id, status_in=status_in)
    elif field_name == "group_id":
        seq_requests = db.query_seq_requests(group=word, user_id=user_id, status_in=status_in)

    return make_response(
        render_template(
            "components/tables/seq_request.html",
            current_query=word, active_query_field=field_name,
            seq_requests=seq_requests, status_in=status_in
        )
    )


@htmx_route(seq_requests_htmx, db=db, methods=["POST"])
def process_request(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
    return forms.ProcessRequestForm(formdata=request.form).process_request(
        seq_request=seq_request, user=current_user
    )


@htmx_route(seq_requests_htmx, db=db, methods=["POST"])
def add_share_email(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
    return forms.SeqRequestShareEmailForm(formdata=request.form).process_request(
        seq_request=seq_request
    )


@htmx_route(seq_requests_htmx, db=db, methods=["DELETE"])
def remove_share_email(seq_request_id: int, email: str):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if len(seq_request.delivery_email_links) == 1:
        return abort(HTTPResponse.FORBIDDEN.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
        
    try:
        db.remove_seq_request_share_email(seq_request_id, email)
    except exceptions.ElementDoesNotExist:
        return abort(HTTPResponse.NOT_FOUND.id)

    flash(f"Removed shared email '{email}' from sequencing request '{seq_request.name}'", "success")
    return make_response(
        redirect=url_for("seq_requests_page.seq_request", seq_request_id=seq_request.id),
    )


@htmx_route(seq_requests_htmx, db=db)
def overview(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)

    LINK_WIDTH_UNIT = 1

    samples, _ = db.get_samples(seq_request_id=seq_request_id, limit=None)
    
    nodes = []
    links = []
    contains_pooled = False

    seq_request_node = {
        "node": 0,
        "name": seq_request.name,
        "id": f"seq_request-{seq_request.id}"
    }
    nodes.append(seq_request_node)

    idx = 1

    project_nodes: dict[int, int] = {}
    sample_nodes: dict[int, int] = {}
    library_nodes: dict[int, int] = {}
    pool_nodes: dict[int, int] = {}
    pool_link_widths: dict[int, int] = {}

    for sample in samples:
        if sample.project_id not in project_nodes.keys():
            project_node = {
                "node": idx,
                "name": sample.project.name,
                "id": f"project-{sample.project_id}"
            }
            nodes.append(project_node)
            project_nodes[sample.project.id] = idx
            project_idx = idx
            idx += 1
        else:
            project_idx = project_nodes[sample.project.id]

        sample_node = {
            "node": idx,
            "name": sample.name,
            "id": f"sample-{sample.id}"
        }
        nodes.append(sample_node)
        sample_nodes[sample.id] = idx
        idx += 1
        n_sample_links = 0
        for link in sample.library_links:
            if link.library.seq_request_id == seq_request_id:
                n_sample_links += 1
                if link.library.id not in library_nodes.keys():
                    library_node = {
                        "node": idx,
                        "name": link.library.type.identifier,
                        "id": f"library-{link.library.id}"
                    }
                    nodes.append(library_node)
                    library_nodes[link.library.id] = idx
                    library_idx = idx
                    idx += 1

                    if not link.library.is_pooled():
                        links.append({
                            "source": library_idx,
                            "target": seq_request_node["node"],
                            "value": LINK_WIDTH_UNIT * link.library.num_samples
                        })
                    else:
                        contains_pooled = True
                        if link.library.pool_id not in pool_nodes.keys():
                            pool_node = {
                                "node": idx,
                                "name": link.library.pool.name,         # type: ignore
                                "id": f"pool-{link.library.pool.id}"    # type: ignore
                            }
                            nodes.append(pool_node)
                            pool_nodes[link.library.pool.id] = idx      # type: ignore
                            pool_link_widths[link.library.pool.id] = 0  # type: ignore
                            pool_idx = idx

                            idx += 1
                        else:
                            pool_idx = pool_nodes[link.library.pool.id]     # type: ignore

                        pool_link_widths[link.library.pool.id] += LINK_WIDTH_UNIT * link.library.num_samples    # type: ignore
                        
                        links.append({
                            "source": library_nodes[link.library_id],
                            "target": pool_idx,
                            "value": LINK_WIDTH_UNIT * link.library.num_samples
                        })
                else:
                    library_idx = library_nodes[link.library.id]
                links.append({
                    "source": sample_node["node"],
                    "target": library_idx,
                    "value": LINK_WIDTH_UNIT
                })

        links.append({
            "source": project_idx,
            "target": sample_nodes[sample.id],
            "value": LINK_WIDTH_UNIT * n_sample_links
        })

    for pool_id, pool_node in pool_nodes.items():
        links.append({
            "source": pool_node,
            "target": seq_request_node["node"],
            "value": pool_link_widths[pool_id]
        })

    return make_response(
        render_template(
            "components/plots/request_overview.html",
            nodes=nodes, links=links, contains_pooled=contains_pooled
        )
    )


@seq_requests_htmx.route("<int:seq_request_id>/get_libraries/<int:page>", methods=["GET"])
@seq_requests_htmx.route("<int:seq_request_id>/get_libraries", methods=["GET"], defaults={"page": 0})
@db_session(db)
@login_required
def get_libraries(seq_request_id: int, page: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
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
        offset=offset, seq_request_id=seq_request_id, sort_by=sort_by, descending=descending,
        status_in=status_in, type_in=type_in, count_pages=True
    )

    return make_response(
        render_template(
            "components/tables/seq_request-library.html",
            libraries=libraries, n_pages=n_pages, active_page=page,
            sort_by=sort_by, sort_order=sort_order, seq_request=seq_request,
            status_in=status_in, type_in=type_in
        )
    )



@htmx_route(seq_requests_htmx, db=db)
def query_libraries(seq_request_id: int):
    if (word := request.args.get("name")) is not None:
        field_name = "name"
    elif (word := request.args.get("id")) is not None:
        field_name = "id"
    else:
        return abort(HTTPResponse.BAD_REQUEST.id)
    
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if seq_request.requestor_id != current_user.id and not current_user.is_insider():
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
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
        libraries = db.query_libraries(name=word, seq_request_id=seq_request_id, status_in=status_in, type_in=type_in)
    elif field_name == "id":
        try:
            _id = int(word)
            if (library := db.get_library(_id)) is not None:
                if library.seq_request_id == seq_request_id:
                    libraries = [library]
                if status_in is not None and library.status not in status_in:
                    libraries = []
                if type_in is not None and library.type not in type_in:
                    libraries = []
        except ValueError:
            pass

    return make_response(
        render_template(
            "components/tables/seq_request-library.html",
            current_query=word, active_query_field=field_name,
            seq_request=seq_request,
            libraries=libraries, type_in=type_in, status_in=status_in
        )
    )


@seq_requests_htmx.route("<int:seq_request_id>/get_samples/<int:page>", methods=["GET"])
@seq_requests_htmx.route("<int:seq_request_id>/get_samples", methods=["GET"], defaults={"page": 0})
@db_session(db)
@login_required
def get_samples(seq_request_id: int, page: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "desc")
    descending = sort_order == "desc"
    offset = PAGE_LIMIT * page

    samples, n_pages = db.get_samples(offset=offset, seq_request_id=seq_request_id, sort_by=sort_by, descending=descending, count_pages=True)

    return make_response(
        render_template(
            "components/tables/seq_request-sample.html",
            samples=samples, n_pages=n_pages, active_page=page,
            sort_by=sort_by, sort_order=sort_order, seq_request=seq_request
        )
    )
    

@seq_requests_htmx.route("<int:seq_request_id>/get_pools/<int:page>", methods=["GET"])
@seq_requests_htmx.route("<int:seq_request_id>/get_pools", methods=["GET"], defaults={"page": 0})
@db_session(db)
@login_required
def get_pools(seq_request_id: int, page: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)
    
    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "desc")
    descending = sort_order == "desc"
    offset = PAGE_LIMIT * page

    pools, n_pages = db.get_pools(
        seq_request_id=seq_request_id, offset=offset, sort_by=sort_by, descending=descending, count_pages=True
    )

    return make_response(
        render_template(
            "components/tables/seq_request-pool.html",
            pools=pools, n_pages=n_pages, active_page=page,
            sort_by=sort_by, sort_order=sort_order, seq_request=seq_request
        )
    )


@htmx_route(seq_requests_htmx, db=db)
def get_comments(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)

    return make_response(
        render_template(
            "components/comment-list.html",
            comments=seq_request.comments
        )
    )


@htmx_route(seq_requests_htmx, db=db)
def get_files(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if not current_user.is_insider() and seq_request.requestor_id != current_user.id:
        affiliation = db.get_group_user_affiliation(user_id=current_user.id, group_id=seq_request.group_id) if seq_request.group_id else None
        if affiliation is None:
            return abort(HTTPResponse.FORBIDDEN.id)

    return make_response(
        render_template(
            "components/file-list.html",
            files=seq_request.files, seq_request=seq_request, delete="seq_requests_htmx.delete_file",
            delete_context={"seq_request_id": seq_request_id}
        )
    )


@htmx_route(seq_requests_htmx, db=db, methods=["POST"])
def clone(seq_request_id: int, method: Literal["pooled", "indexed", "raw"]):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)
    
    if method not in {"pooled", "indexed", "raw"}:
        return abort(HTTPResponse.BAD_REQUEST.id)

    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)

    cloned_request = db.clone_seq_request(seq_request_id=seq_request.id, method=method)

    flash("Request cloned", "success")
    return make_response(redirect=url_for("seq_requests_page.seq_request", seq_request_id=cloned_request.id))


@htmx_route(seq_requests_htmx, db=db)
def store_samples(seq_request_id: int):
    if (seq_request := db.get_seq_request(seq_request_id)) is None:
        return abort(HTTPResponse.NOT_FOUND.id)

    if not current_user.is_insider():
        return abort(HTTPResponse.FORBIDDEN.id)

    if seq_request.submission_type == SubmissionType.RAW_SAMPLES:
        form: forms.SelectSamplesForm = forms.SelectSamplesForm(
            workflow="store_samples",
            sample_status_filter=[SampleStatus.WAITING_DELIVERY],
            context=dict(seq_request=seq_request),
            select_samples=True, select_libraries=False, select_pools=False,
            selected_samples=[s for s in seq_request.samples if s.status == SampleStatus.WAITING_DELIVERY]
        )
    elif seq_request.submission_type == SubmissionType.POOLED_LIBRARIES:
        form: forms.SelectSamplesForm = forms.SelectSamplesForm(
            workflow="store_samples",
            pool_status_filter=[PoolStatus.ACCEPTED],
            context=dict(seq_request=seq_request),
            select_samples=False, select_libraries=False, select_pools=True,
            selected_pools=[pool for pool in seq_request.pools if pool.status == PoolStatus.ACCEPTED]
        )
    else:
        form: forms.SelectSamplesForm = forms.SelectSamplesForm(
            workflow="store_samples",
            library_status_filter=[LibraryStatus.ACCEPTED],
            context=dict(seq_request=seq_request),
            select_samples=False, select_libraries=True, select_pools=False,
            selected_libraries=[library for library in seq_request.libraries if library.status == LibraryStatus.ACCEPTED],
        )

    return form.make_response()


@htmx_route(seq_requests_htmx, db=db)
def get_recent_seq_requests():
    if (sort_by := request.args.get("sort_by")) is not None:
        if sort_by not in ["timestamp_submitted_utc", "id"]:
            return abort(HTTPResponse.BAD_REQUEST.id)
    else:
        sort_by = "timestamp_submitted_utc"

    seq_requests, _ = db.get_seq_requests(
        user_id=None if current_user.is_insider() else current_user.id,
        sort_by=sort_by, descending=True,
        show_drafts=False if current_user.is_insider() else True,
    )

    return make_response(
        render_template("components/dashboard/seq_requests-list.html", seq_requests=seq_requests, sort_by=sort_by)
    )
