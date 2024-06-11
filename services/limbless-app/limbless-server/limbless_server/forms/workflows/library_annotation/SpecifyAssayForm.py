from typing import Optional, Literal

import pandas as pd
import numpy as np

from flask import Response
from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, BooleanField, FormField, StringField
from wtforms.validators import Optional as OptionalValidator, Length, DataRequired

from limbless_db import models
from limbless_db.categories import AssayType, GenomeRef, LibraryType

from .... import logger

from ...HTMXFlaskForm import HTMXFlaskForm
from ....tools import SpreadSheetColumn
from .ProjectMappingForm import ProjectMappingForm

columns = {
    "sample_name": SpreadSheetColumn("A", "sample_name", "Sample Name", "text", 300, str),
    "genome": SpreadSheetColumn("B", "genome", "Genome", "dropdown", 300, str, GenomeRef.names()),
}


class OptionalAssaysForm(FlaskForm):
    antibody_capture = BooleanField("Cell Surface Protein Capture", description="Anitbody Capture", default=False)
    vdj_b = BooleanField("VDJ-B", description="BCR-sequencing", default=False)
    vdj_t = BooleanField("VDJ-T", description="TCR-sequencing", default=False)
    vdj_t_gd = BooleanField("VDJ-T-GD", description="TCR-GD-sequencing", default=False)
    crispr_screening = BooleanField("CRISPR Screening", default=False)


class AdditionalSerevicesForm(FlaskForm):
    multiplexing = BooleanField("Sample Multiplexing", description="Multiple samples per library with cell multiplexing oligo (CMO) tag", default=False)
    nuclei_isolation = BooleanField("Nuclei Isolation", default=False)


class SpecifyAssayForm(HTMXFlaskForm):
    _template_path = "workflows/library_annotation/sas-0.html"
    _form_label = "select_assay_form"

    assay_type = SelectField("Assay Type", choices=AssayType.as_selectable(), validators=[DataRequired()])
    additional_info = TextAreaField("Additional Information", validators=[OptionalValidator(), Length(max=models.Comment.text.type.length)])
    optional_assays = FormField(OptionalAssaysForm)
    additional_services = FormField(AdditionalSerevicesForm)
    spreadsheet_dummy = StringField(validators=[OptionalValidator()])

    def __init__(self, formdata: Optional[dict] = None):
        super().__init__(formdata=formdata)
        self.spreadsheet_style = {}
        self._context["columns"] = columns.values()
        self._context["colors"] = {
            "missing_value": "#FAD7A0",
            "invalid_value": "#F5B7B1",
            "duplicate_value": "#D7BDE2",
        }
        self._context["active_tab"] = "help"

    def validate(self) -> bool:
        if not super().validate():
            return False
        
        import json
        data = json.loads(self.formdata["spreadsheet"])  # type: ignore
        try:
            self.df = pd.DataFrame(data)
        except ValueError as e:
            self.spreadsheet_dummy.errors = (str(e),)
            return False
        
        if len(self.df.columns) != len(list(columns.keys())):
            self.spreadsheet_dummy.errors = (f"Invalid number of columns (expected {len(columns)}). Do not insert new columns or rearrange existing columns.",)
            return False
        
        self.df.columns = list(columns.keys())
        self.df = self.df.replace(r'^\s*$', None, regex=True)
        self.df = self.df.dropna(how="all")

        if len(self.df) == 0:
            self.spreadsheet_dummy.errors = ("Please, fill-out spreadsheet",)
            return False
        
        def add_error(row_num: int, column: str, message: str, color: Literal["missing_value", "invalid_value", "duplicate_value"]):
            self.spreadsheet_style[f"{columns[column].column}{row_num}"] = f"background-color: {self._context['colors'][color]};"
            self.spreadsheet_dummy.errors.append(f"Row {row_num}: {message}")  # type: ignore

        sample_name_counts = self.df["sample_name"].value_counts()

        for i, (_, row) in enumerate(self.df.iterrows()):
            if pd.isna(row["sample_name"]):
                add_error(i + 1, "sample_name", "missing 'Sample Name'", "missing_value")
            elif sample_name_counts[row["sample_name"]] > 1:
                add_error(i + 1, "sample_name", "duplicate 'Sample Name'", "duplicate_value")

            if pd.isna(row["genome"]):
                add_error(i + 1, "genome", "missing 'Genome'", "missing_value")

        if self.spreadsheet_dummy.errors:
            return False
        
        genome_map = {}
        for id, e in GenomeRef.as_tuples():
            genome_map[e.display_name] = id
        
        logger.debug(genome_map)
        self.df["genome_id"] = self.df["genome"].map(genome_map)

        try:
            self.assay_type_enum = AssayType.get(int(self.assay_type.data))
        except ValueError:
            self.assay_type.errors = ("Invalid assay type",)
            return False

        return True
    
    def process_request(self, user: models.User, seq_request: models.SeqRequest) -> Response:
        self._context["seq_request"] = seq_request
        if not self.validate():
            self._context["active_tab"] = "form"
            self._context["spreadsheet_style"] = self.spreadsheet_style
            self._context["spreadsheet_data"] = self.df.replace(np.nan, "").values.tolist()
            if self._context["spreadsheet_data"] == []:
                self._context["spreadsheet_data"] = [[None]]
            return self.make_response()
        
        library_table_data = {
            "sample_name": [],
            "library_name": [],
            "genome": [],
            "genome_id": [],
            "library_type": [],
            "library_type_id": [],
        }
        for library_type in self.assay_type_enum.library_types:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["library_name"].append(f"{row['sample_name']}_{library_type.assay_type}")
                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append(library_type.name)
                library_table_data["library_type_id"].append(library_type.id)

        if self.optional_assays.antibody_capture.data:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["library_name"].append(f"{row['sample_name']}_{LibraryType.ANTIBODY_CAPTURE.assay_type}")
                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append("Antibody Capture")
                library_table_data["library_type_id"].append(LibraryType.ANTIBODY_CAPTURE.id)

        if self.optional_assays.vdj_b.data:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["library_name"].append(f"{row['sample_name']}_{LibraryType.VDJ_B.assay_type}")
                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append("VDJ-B")
                library_table_data["library_type_id"].append(LibraryType.VDJ_B.id)

        if self.optional_assays.vdj_t.data:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["library_name"].append(f"{row['sample_name']}_{LibraryType.VDJ_T.assay_type}")
                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append("VDJ-T")
                library_table_data["library_type_id"].append(LibraryType.VDJ_T.id)

        if self.optional_assays.vdj_t_gd.data:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["library_name"].append(f"{row['sample_name']}_{LibraryType.VDJ_T_GD.assay_type}")
                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append("VDJ-T-GD")
                library_table_data["library_type_id"].append(LibraryType.VDJ_T_GD.id)

        if self.optional_assays.crispr_screening.data:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["library_name"].append(f"{row['sample_name']}_{LibraryType.CRISPR_SCREENING.assay_type}")
                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append("CRISPR Screening")
                library_table_data["library_type_id"].append(LibraryType.CRISPR_SCREENING.id)

        project_mapping_form = ProjectMappingForm()
        library_table = pd.DataFrame(library_table_data)
        library_table["project"] = "Project"
        library_table["seq_depth"] = None
        library_table["is_cmo_sample"] = False
        library_table["is_flex_sample"] = False
        library_table = library_table.sort_values(by=["sample_name", "library_type"]).reset_index(drop=True)
        project_mapping_form.add_table("library_table", library_table)
        
        if self.additional_info.data:
            comment_table = pd.DataFrame({
                "context": ["assay_tech_selection"],
                "text": [self.additional_info.data]
            })
            project_mapping_form.add_table("comment_table", comment_table)
        
        project_mapping_form.metadata = dict(workflow="library_annotation", type="tech")
        project_mapping_form.update_data()
        project_mapping_form.prepare(user)
        return project_mapping_form.make_response(seq_request=seq_request)

            
        
        
        