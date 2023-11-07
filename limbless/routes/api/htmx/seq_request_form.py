from io import StringIO
from typing import Optional, Any, TYPE_CHECKING

from flask import Blueprint, redirect, url_for, render_template, flash, request, abort, Response
from flask_htmx import make_response
from flask_login import login_required
from werkzeug.utils import secure_filename

import pandas as pd

from .... import db, logger, forms, tools, models, PAGE_LIMIT
from ....core import DBSession
from ....categories import UserRole, HttpResponse

if TYPE_CHECKING:
    current_user: models.User = None
else:
    from flask_login import current_user


seq_request_form_htmx = Blueprint("seq_request_form_htmx", __name__, url_prefix="/api/samples/")


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
    
    raw_text, sep = table_input_form.get_data()
    df = pd.read_csv(
        StringIO(raw_text.rstrip()), sep=sep, index_col=False, header=0
    )

    table_col_form = forms.SampleColTableForm()
    required_fields = forms.SampleColSelectForm.required_fields
    
    table_col_form.data.data = df.to_csv(sep="\t", index=False, header=True)
    columns = df.columns.tolist()
    refs = [key for key, _ in required_fields if key]
    matches = tools.connect_similar_strings(required_fields, columns)

    for i, col in enumerate(columns):
        select_form = forms.SampleColSelectForm()
        select_form.select_field.label.text = col
        table_col_form.fields.append_entry(select_form)
        table_col_form.fields.entries[i].select_field.label.text = col
        if col in matches.keys():
            table_col_form.fields.entries[i].select_field.data = matches[col]

    # Form is submittable if all columns are selected
    submittable: bool = set(matches.values()) == set(refs)

    return make_response(
        render_template(
            "components/popups/seq_request/step-2.html",
            columns=columns, sample_table_form=table_col_form,
            matches=matches, data=df.values.tolist(),
            required_fields=refs,
            submittable=submittable,
            seq_request=seq_request
        ), push_url=False
    )


# 2. Map columns to sample features
@seq_request_form_htmx.route("<int:seq_request_id>/map_columns", methods=["POST"])
@login_required
def map_columns(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    required_fields = forms.SampleColSelectForm.required_fields

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

    df = pd.read_csv(StringIO(sample_table_form.data.data), sep="\t", index_col=False, header=0)
    for i, entry in enumerate(sample_table_form.fields.entries):
        val = entry.select_field.data.strip()
        if not val:
            continue
        df.rename(columns={df.columns[i]: val}, inplace=True)

    refs = [key for key, _ in required_fields if key]
    df = df[refs]

    project_select_form = forms.SampleProjectSelectForm()
    project_select_form.data.data = df.to_csv(sep="\t", index=False, header=True)

    return make_response(
        render_template(
            "components/popups/seq_request/step-3.html",
            project_select_form=project_select_form,
            seq_request=seq_request
        ), push_url=False
    )


# 3. Select project
@seq_request_form_htmx.route("<int:seq_request_id>/project_select", methods=["POST"])
@login_required
def select_project(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    project_select_form = forms.SampleProjectSelectForm()
    validated, project_select_form = project_select_form.custom_validate(db.db_handler, current_user.id)

    if not validated:
        return make_response(
            render_template(
                "components/popups/seq_request/step-3.html",
                project_select_form=project_select_form,
                seq_request=seq_request,
            ), push_url=False
        )
    
    df = pd.read_csv(StringIO(project_select_form.data.data), sep="\t", index_col=False, header=0)

    if project_select_form.existing_project.data:
        if (project := db.db_handler.get_project(project_select_form.existing_project.data)) is None:
            return abort(HttpResponse.NOT_FOUND.value.id)
        df["project_name"] = project.name
        df["project_id"] = project.id
        
    elif project_select_form.new_project.data:
        df["project_name"] = project_select_form.new_project.data
        df["project_id"] = None
    else:
        assert False    # This should never happen because its checked in custom_validate()

    category_mapping_form = forms.OrganismMappingForm()
    df = category_mapping_form.prepare(seq_request.id, df)

    if df["sample_id"].isna().any():
        # new sample -> map organism
        organisms = sorted(df["organism"].unique())
        selected: list[str] = []
        for i, organism in enumerate(organisms):
            selected.append("")
            category_mapping_form.fields.append_entry(forms.CategoricalMappingField())
            category_mapping_form.fields.entries[i].raw_category.data = organism
            # category_mapping_form.fields.entries[i].category.data = organism

        logger.debug(category_mapping_form)
        return make_response(
            render_template(
                "components/popups/seq_request/step-4.html",
                category_mapping_form=category_mapping_form,
                categories=organisms, selected=selected,
                seq_request=seq_request,
            ), push_url=False
        )

    sample_confirm_form = forms.SampleConfirmForm()
    samples = sample_confirm_form.parse_samples(seq_request.id, df)

    if not df["sample_id"].isna().any():
        return make_response(
            render_template(
                "components/popups/seq_request/step-5.html",
                seq_request=seq_request,
                sample_confirm_form=sample_confirm_form,
                samples=samples
            ), push_url=False
        )


# Map organisms if new samples
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
                category_mapping_form.fields.entries[i].raw_category.data = organism
                if category_mapping_form.fields.entries[i].category.data:
                    selected_organism = session.get_organism(category_mapping_form.fields.entries[i].category.data)
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
        organism_id_mapping[organism] = category_mapping_form.fields.entries[i].category.data
    
    df["tax_id"] = df["organism"].map(organism_id_mapping)

    sample_confirm_form = forms.SampleConfirmForm()
    samples = sample_confirm_form.parse_samples(seq_request.id, df)

    return make_response(
        render_template(
            "components/popups/seq_request/step-5.html",
            seq_request=seq_request,
            sample_confirm_form=sample_confirm_form,
            samples=samples
        ), push_url=False
    )


@seq_request_form_htmx.route("<int:seq_request_id>/confirm", methods=["POST"])
@login_required
def confirm(seq_request_id: int):
    if (seq_request := db.db_handler.get_seq_request(seq_request_id)) is None:
        return abort(HttpResponse.NOT_FOUND.value.id)
    
    sample_confirm_form = forms.SampleConfirmForm()
    df = pd.read_csv(StringIO(sample_confirm_form.data.data), sep="\t", index_col=False, header=0)
    samples = sample_confirm_form.parse_samples(seq_request.id, df)
    
    validated, sample_select_form = sample_confirm_form.custom_validate()

    if not validated:
        return make_response(
            render_template(
                "components/popups/seq_request/step-5.html",
                seq_request=seq_request,
                sample_confirm_form=sample_confirm_form,
                samples=samples
            ), push_url=False
        )

    if sample_select_form.selected_samples.data is None:
        assert False    # This should never happen because its checked in custom_validate()

    selected_samples_ids = sample_select_form.selected_samples.data.removeprefix(",").split(",")
    selected_samples_ids = [int(i) - 1 for i in selected_samples_ids if i != ""]

    logger.debug(selected_samples_ids)
    df = df.loc[selected_samples_ids, :]
    df["sample_id"] = df["sample_id"].astype("Int64")
    df["project_id"] = df["project_id"].astype("Int64")

    n_added = 0
    n_new_samples = 0
    n_new_projects = 0

    with DBSession(db.db_handler) as session:
        projects: dict[int | str, models.Project] = {}
        for project_id, project_name in df[["project_id", "project_name"]].drop_duplicates().values.tolist():
            if not pd.isnull(project_id):
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
            if i not in selected_samples_ids:
                continue

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
    elif n_added == len(selected_samples_ids):
        flash(f"Added all ({n_added}) samples to sequencing request.", "success")
    elif n_added < len(selected_samples_ids):
        flash(f"Some samples ({len(selected_samples_ids) - n_added}) could not be added.", "warning")

    return make_response(
        redirect=url_for(
            "seq_requests_page.seq_request_page",
            seq_request_id=seq_request.id
        ),
    )