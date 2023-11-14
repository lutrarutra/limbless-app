import os
from io import StringIO
from typing import Optional, Any, TYPE_CHECKING

from flask import Blueprint, redirect, url_for, render_template, flash, request, abort, Response, send_file, current_app
from flask_htmx import make_response
from flask_login import login_required
from werkzeug.utils import secure_filename

import pandas as pd

from .... import db, logger, forms, models, PAGE_LIMIT
from ....core import DBSession
from ....categories import UserRole, HttpResponse, LibraryType

if TYPE_CHECKING:
    current_user: models.User = None
else:
    from flask_login import current_user


seq_request_form_htmx = Blueprint("seq_request_form_htmx", __name__, url_prefix="/api/samples/")


# Template sample annotation sheet
@seq_request_form_htmx.route("download_template", methods=["GET"])
@login_required
def download_template():
    path = os.path.join(
        current_app.root_path,
        "static", "resources", "sample_annotation_sheet.tsv"
    )
    return send_file(path, mimetype="text/csv", as_attachment=True, download_name="sample_annotation_sheet.tsv")


# 0. Restart form
@seq_request_form_htmx.route("<int:seq_request_id>/restart_form", methods=["GET"])
@login_required
def restart_form(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    return make_response(
        render_template(
            "components/popups/seq_request/step-1.html",
            table_form=forms.TableForm(),
            seq_request=seq_request
        ), push_url=False
    )


# 1. Input sample annotation sheet
@seq_request_form_htmx.route("<int:seq_request_id>/parse_table", methods=["POST"])
@login_required
def parse_table(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    table_input_form = forms.TableForm()
    validated, table_input_form = table_input_form.custom_validate()

    if not validated:
        return make_response(
            render_template(
                "components/popups/seq_request/step-1.html",
                table_form=table_input_form, seq_request=seq_request
            ), push_url=False
        )
    
    df = table_input_form.parse()
    table_col_form = forms.SampleColTableForm()
    context = table_col_form.prepare(df)

    return make_response(
        render_template(
            "components/popups/seq_request/step-2.html",
            sample_table_form=table_col_form,
            data=df.values.tolist(),
            seq_request=seq_request,
            **context
        ), push_url=False
    )


# 2. Map columns to sample features
@seq_request_form_htmx.route("<int:seq_request_id>/map_columns", methods=["POST"])
@login_required
def map_columns(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)

    sample_table_form = forms.SampleColTableForm()
    if not sample_table_form.validate_on_submit():
        return make_response(
            render_template(
                "components/popups/sample/step-2.html",
                sample_table_form=sample_table_form,
                seq_request=seq_request
            ),
            push_url=False
        )

    df = sample_table_form.parse()
    
    project_mapping_form = forms.ProjectMappingForm()
    context = project_mapping_form.prepare(df)

    return make_response(
        render_template(
            "components/popups/seq_request/step-3.html",
            project_mapping_form=project_mapping_form,
            seq_request=seq_request, **context
        ), push_url=False
    )


# 3. Select project
@seq_request_form_htmx.route("<int:seq_request_id>/project_select", methods=["POST"])
@login_required
def select_project(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    project_mapping_form = forms.ProjectMappingForm()
    validated, project_mapping_form = project_mapping_form.custom_validate(db.db_handler, current_user.id)
    context = project_mapping_form.prepare()

    if not validated:
        return make_response(
            render_template(
                "components/popups/seq_request/step-3.html",
                project_mapping_form=project_mapping_form,
                seq_request=seq_request, **context
            ), push_url=False
        )
    
    df = project_mapping_form.parse()

    category_mapping_form = forms.OrganismMappingForm(formdata=None)
    context = category_mapping_form.prepare(seq_request.id, df)

    if df["sample_id"].isna().any():
        # new sample -> map organisms
        return make_response(
            render_template(
                "components/popups/seq_request/step-4.html",
                category_mapping_form=category_mapping_form,
                seq_request=seq_request, **context
            ), push_url=False
        )

    sample_confirm_form = forms.SampleConfirmForm()
    context = sample_confirm_form.prepare(seq_request.id, df)

    return make_response(
        render_template(
            "components/popups/seq_request/step-5.html",
            seq_request=seq_request,
            sample_confirm_form=sample_confirm_form,
            **context
        ), push_url=False
    )


# 4. Map organisms if new samples
@seq_request_form_htmx.route("<int:seq_request_id>/map_organisms", methods=["POST"])
@login_required
def map_organisms(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    category_mapping_form = forms.OrganismMappingForm()
    validated, category_mapping_form = category_mapping_form.custom_validate(db.db_handler)
    df = pd.read_csv(StringIO(category_mapping_form.data.data), sep="\t", index_col=False, header=0)
    organisms = sorted(df["organism"].unique())

    if not validated:
        selected = []
        with DBSession(db.db_handler) as session:
            for i, organism in enumerate(organisms):
                category_mapping_form.input_fields.entries[i].raw_category.data = organism
                if category_mapping_form.input_fields.entries[i].category.data:
                    selected_organism = session.get_organism(category_mapping_form.input_fields.entries[i].category.data)
                    selected.append(str(selected_organism))
                else:
                    selected.append("")

        return make_response(
            render_template(
                "components/popups/seq_request/step-4.html",
                category_mapping_form=category_mapping_form,
                categories=organisms, selected=selected,
                seq_request=seq_request
            ), push_url=False
        )

    organism_id_mapping = {}
    
    for i, organism in enumerate(organisms):
        organism_id_mapping[organism] = category_mapping_form.input_fields.entries[i].category.data
    
    df["tax_id"] = df["organism"].map(organism_id_mapping)

    sample_confirm_form = forms.SampleConfirmForm()
    context = sample_confirm_form.prepare(seq_request.id, df)

    return make_response(
        render_template(
            "components/popups/seq_request/step-5.html",
            seq_request=seq_request,
            sample_confirm_form=sample_confirm_form,
            **context
        ), push_url=False
    )


# 5. Confirm samples
@seq_request_form_htmx.route("<int:seq_request_id>/confirm_samples", methods=["POST"])
@login_required
def confirm_samples(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    sample_confirm_form = forms.SampleConfirmForm()
    context = sample_confirm_form.prepare(seq_request.id)
    
    validated, sample_select_form = sample_confirm_form.custom_validate()

    if not validated:
        return make_response(
            render_template(
                "components/popups/seq_request/step-5.html",
                seq_request=seq_request,
                sample_confirm_form=sample_confirm_form,
                **context
            ), push_url=False
        )
    
    df = sample_confirm_form.parse()

    library_mapping_form = forms.LibraryMappingForm()
    context = library_mapping_form.prepare(df)

    return make_response(
        render_template(
            "components/popups/seq_request/step-6.html",
            seq_request=seq_request,
            library_mapping_form=library_mapping_form,
            **context
        )
    )


@seq_request_form_htmx.route("<int:seq_request_id>/map_libraries", methods=["POST"])
@login_required
def map_libraries(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    library_mapping_form = forms.LibraryMappingForm()
    context = library_mapping_form.prepare()

    validated, library_mapping_form = library_mapping_form.custom_validate(db.db_handler)
    logger.debug(library_mapping_form.errors)

    if not validated:
        return make_response(
            render_template(
                "components/popups/seq_request/step-6.html",
                seq_request=seq_request,
                library_mapping_form=library_mapping_form,
                **context
            )
        )

    df = library_mapping_form.parse()

    barcode_check_form = forms.BarcodeCheckForm()
    context = barcode_check_form.prepare(df)

    return make_response(
        render_template(
            "components/popups/seq_request/step-7.html",
            seq_request=seq_request,
            barcode_check_form=barcode_check_form,
            **context
        )
    )


# 7. Check barcodes
@seq_request_form_htmx.route("<int:seq_request_id>/check_barcodes", methods=["POST"])
@login_required
def check_barcodes(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    index_check_form = forms.CheckIndexForm()
    logger.debug(index_check_form.data.data)
    df = pd.read_csv(StringIO(index_check_form.data.data), sep="\t", index_col=False, header=0)

    df["sample_id"] = df["sample_id"].astype("Int64")
    df["project_id"] = df["project_id"].astype("Int64")

    n_added = 0
    n_new_samples = 0
    n_new_projects = 0

    with DBSession(db.db_handler) as session:
        projects: dict[int | str, models.Project] = {}
        for project_id, project_name in df[["project_id", "project_name"]].drop_duplicates().values.tolist():
            if not pd.isnull(project_id):
                project_id = int(project_id)
                if (project := session.get_project(project_id)) is None:
                    raise Exception(f"Project with id {project_id} does not exist.")
                
                projects[project_id] = project
            else:
                project = session.create_project(
                    name=project_name,
                    description="",
                    owner_id=current_user.id
                )
                projects[project_name] = project

        for i, row in df.iterrows():
            if pd.isnull(row["sample_id"]):
                if pd.isnull(row["project_id"]):
                    project = projects[row["project_name"]]
                else:
                    project = projects[row["project_id"]]
                sample = session.create_sample(
                    name=row["sample_name"],
                    organism_tax_id=row["tax_id"],
                    project_id=project.id,
                    owner_id=current_user.id
                )
                n_new_samples += 1
            else:
                sample = session.get_sample(row["sample_id"])
            
            session.link_sample_seq_request(
                sample.id, seq_request.id
            )

            n_added += 1

    logger.info(f"Created '{n_new_samples}'-samples and '{n_new_projects}'-projects.")
    if n_added == 0:
        flash("No samples added.", "warning")
    elif n_added == len(df):
        flash(f"Added all ({n_added}) samples to sequencing request.", "success")
    elif n_added < len(df):
        flash(f"Some samples ({len(df) - n_added}) could not be added.", "warning")

    return make_response(
        redirect=url_for(
            "seq_requests_page.seq_request_page",
            seq_request_id=seq_request.id
        ),
    )