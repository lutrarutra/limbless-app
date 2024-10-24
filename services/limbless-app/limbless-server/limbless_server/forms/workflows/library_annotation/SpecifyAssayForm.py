import json
from typing import Optional, Literal

import pandas as pd
import numpy as np

from flask import Response
from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, BooleanField, FormField, StringField
from wtforms.validators import Optional as OptionalValidator, Length, DataRequired

from limbless_db import models
from limbless_db.categories import AssayType, GenomeRef, LibraryType

from .... import logger, db
from ....tools import SpreadSheetColumn
from ...HTMXFlaskForm import HTMXFlaskForm
from ...TableDataForm import TableDataForm
from .CMOReferenceInputForm import CMOReferenceInputForm
from .VisiumAnnotationForm import VisiumAnnotationForm
from .FRPAnnotationForm import FRPAnnotationForm
from .FeatureReferenceInputForm import FeatureReferenceInputForm
from .SampleAnnotationForm import SampleAnnotationForm

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
    multiplexing = BooleanField("Sample Multiplexing", description="Multiple samples per library with cell multiplexing hashtag-oligo (HTO)", default=False)
    nuclei_isolation = BooleanField("Nuclei Isolation", default=False)


class SpecifyAssayForm(HTMXFlaskForm, TableDataForm):
    _template_path = "workflows/library_annotation/sas-2.2.html"
    _form_label = "select_assay_form"

    assay_type = SelectField("Assay Type", choices=AssayType.as_selectable(), validators=[DataRequired()], coerce=int)
    additional_info = TextAreaField("Additional Information", validators=[OptionalValidator(), Length(max=models.Comment.text.type.length)])
    optional_assays = FormField(OptionalAssaysForm)
    additional_services = FormField(AdditionalSerevicesForm)
    spreadsheet_dummy = StringField(validators=[OptionalValidator()])

    def __init__(self, seq_request: models.SeqRequest, formdata: dict = {}, uuid: Optional[str] = None):
        super().__init__(formdata=formdata)
        if uuid is None:
            uuid = formdata.get("file_uuid")
        TableDataForm.__init__(self, uuid=uuid, dirname="library_annotation")
        self.seq_request = seq_request
        self.spreadsheet_style = {}
        self._context["columns"] = columns.values()
        self._context["colors"] = {
            "missing_value": "#FAD7A0",
            "invalid_value": "#F5B7B1",
            "duplicate_value": "#D7BDE2",
        }
        self._context["active_tab"] = "help"
        self._context["seq_request"] = seq_request

    def validate(self) -> bool:
        self.df = None
        if not (validated := super().validate()):
            return False

        if self.assay_type.data is None or AssayType.get(self.assay_type.data) == AssayType.CUSTOM:
            self.assay_type.errors = ("Please select an assay type.",)
            return False
        
        data = json.loads(self.formdata["spreadsheet"])  # type: ignore
        try:
            self.df = pd.DataFrame(data)
        except ValueError as e:
            self.spreadsheet_dummy.errors = (str(e),)
            return False

        if not validated:
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
        if (project_id := self.metadata.get("project_id")) is not None:
            if (project := db.get_project(project_id)) is None:
                logger.error(f"{self.uuid}: Project with ID {project_id} does not exist.")
                raise ValueError(f"Project with ID {project_id} does not exist.")
        else:
            project = None

        seq_request_samples = db.get_seq_request_samples_df(self.seq_request.id)

        selected_library_types = [t.abbreviation for t in AssayType.get(self.assay_type.data).library_types]
        if self.optional_assays.antibody_capture.data:
            selected_library_types.append(LibraryType.TENX_ANTIBODY_CAPTURE.abbreviation)
        if self.optional_assays.vdj_b.data:
            selected_library_types.append(LibraryType.TENX_VDJ_B.abbreviation)
        if self.optional_assays.vdj_t.data:
            selected_library_types.append(LibraryType.TENX_VDJ_T.abbreviation)
        if self.optional_assays.vdj_t_gd.data:
            selected_library_types.append(LibraryType.TENX_VDJ_T_GD.abbreviation)
        if self.optional_assays.crispr_screening.data:
            selected_library_types.append(LibraryType.TENX_CRISPR_SCREENING.abbreviation)
        if self.additional_services.multiplexing.data:
            selected_library_types.append(LibraryType.TENX_MULTIPLEXING_CAPTURE.abbreviation)

        for i, (_, row) in enumerate(self.df.iterrows()):
            if pd.isna(row["sample_name"]):
                add_error(i + 1, "sample_name", "missing 'Sample Name'", "missing_value")
            elif sample_name_counts[row["sample_name"]] > 1:
                add_error(i + 1, "sample_name", "duplicate 'Sample Name'", "duplicate_value")

            duplicate_library = (seq_request_samples["sample_name"] == row["sample_name"]) & (seq_request_samples["library_type"].apply(lambda x: x.abbreviation).isin(selected_library_types))
            if (duplicate_library).any():
                library_type = seq_request_samples.loc[duplicate_library, "library_type"].iloc[0]  # type: ignore
                add_error(i + 1, "sample_name", f"You already have '{library_type.abbreviation}'-library from sample {row['sample_name']} in the request", "duplicate_value")

            if pd.isna(row["genome"]):
                add_error(i + 1, "genome", "missing 'Genome'", "missing_value")
        
        genome_map = {}
        for id, e in GenomeRef.as_tuples():
            genome_map[e.display_name] = id
        
        self.df["genome_id"] = self.df["genome"].map(genome_map)

        self.df["sample_id"] = None
        if (project_id := self.metadata.get("project_id")) is not None:
            if (project := db.get_project(project_id)) is None:
                logger.error(f"{self.uuid}: Project with ID {self.metadata['project_id']} does not exist.")
                raise ValueError(f"Project with ID {self.metadata['project_id']} does not exist.")
            
            for sample in project.samples:
                self.df.loc[self.df["sample_name"] == sample.name, "sample_id"] = sample.id

        if self.spreadsheet_dummy.errors:
            return False

        try:
            self.assay_type_enum = AssayType.get(int(self.assay_type.data))
        except ValueError:
            self.assay_type.errors = ("Invalid assay type",)
            return False

        return True
    
    def process_request(self) -> Response:
        if not self.validate() or self.df is None:
            self._context["active_tab"] = "form"
            self._context["spreadsheet_style"] = self.spreadsheet_style
            if self.df is not None:
                self._context["spreadsheet_data"] = self.df.replace(np.nan, "").values[:, :len(columns)].tolist()
                if self._context["spreadsheet_data"] == []:
                    self._context["spreadsheet_data"] = [[None]]
            return self.make_response()

        library_table_data = {
            "sample_name": [],
            "sample_id": [],
            "library_name": [],
            "genome": [],
            "genome_id": [],
            "library_type": [],
            "library_type_id": [],
        }
        for library_type in self.assay_type_enum.library_types:
            for _, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["sample_id"].append(row["sample_id"])
                
                library_name = f"{row['sample_name']}_{library_type.identifier}"

                library_table_data["library_name"].append(library_name)
                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append(library_type.name)
                library_table_data["library_type_id"].append(library_type.id)

        if self.optional_assays.antibody_capture.data:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["sample_id"].append(row["sample_id"])

                library_table_data["library_name"].append(f"{row['sample_name']}_{LibraryType.TENX_ANTIBODY_CAPTURE.identifier}")
                
                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append("Antibody Capture")
                library_table_data["library_type_id"].append(LibraryType.TENX_ANTIBODY_CAPTURE.id)

        if self.optional_assays.vdj_b.data:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["sample_id"].append(row["sample_id"])

                library_table_data["library_name"].append(f"{row['sample_name']}_{LibraryType.TENX_VDJ_B.identifier}")

                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append("VDJ-B")
                library_table_data["library_type_id"].append(LibraryType.TENX_VDJ_B.id)

        if self.optional_assays.vdj_t.data:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["sample_id"].append(row["sample_id"])

                library_table_data["library_name"].append(f"{row['sample_name']}_{LibraryType.TENX_VDJ_T.identifier}")

                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append("VDJ-T")
                library_table_data["library_type_id"].append(LibraryType.TENX_VDJ_T.id)

        if self.optional_assays.vdj_t_gd.data:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["sample_id"].append(row["sample_id"])

                library_table_data["library_name"].append(f"{row['sample_name']}_{LibraryType.TENX_VDJ_T_GD.identifier}")

                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append("VDJ-T-GD")
                library_table_data["library_type_id"].append(LibraryType.TENX_VDJ_T_GD.id)

        if self.optional_assays.crispr_screening.data:
            for i, row in self.df.iterrows():
                library_table_data["sample_name"].append(row["sample_name"])
                library_table_data["sample_id"].append(row["sample_id"])

                library_table_data["library_name"].append(f"{row['sample_name']}_{LibraryType.TENX_CRISPR_SCREENING.identifier}")

                library_table_data["genome"].append(row["genome"])
                library_table_data["genome_id"].append(row["genome_id"])
                library_table_data["library_type"].append("CRISPR Screening")
                library_table_data["library_type_id"].append(LibraryType.TENX_CRISPR_SCREENING.id)

        library_table = pd.DataFrame(library_table_data)
        library_table["seq_depth"] = None
        library_table = library_table.reset_index(drop=True)
        self.add_table("library_table", library_table)
        self.update_data()

        if self.additional_info.data:
            comment_table = pd.DataFrame({
                "context": ["assay_tech_selection"],
                "text": [self.additional_info.data]
            })
            self.add_table("comment_table", comment_table)

        if library_table["library_type_id"].isin([LibraryType.TENX_MULTIPLEXING_CAPTURE.id]).any():
            cmo_reference_input_form = CMOReferenceInputForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
            return cmo_reference_input_form.make_response()
        
        if (library_table["library_type_id"] == LibraryType.TENX_ANTIBODY_CAPTURE.id).any():
            feature_reference_input_form = FeatureReferenceInputForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
            return feature_reference_input_form.make_response()
        
        if (library_table["library_type_id"].isin([LibraryType.TENX_VISIUM.id, LibraryType.TENX_VISIUM_FFPE.id, LibraryType.TENX_VISIUM_HD.id])).any():
            visium_annotation_form = VisiumAnnotationForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
            visium_annotation_form.prepare()
            return visium_annotation_form.make_response()
        
        if LibraryType.TENX_SC_GEX_FLEX.id in library_table["library_type_id"].values:
            frp_annotation_form = FRPAnnotationForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
            frp_annotation_form.prepare()
            return frp_annotation_form.make_response()
    
        sample_annotation_form = SampleAnnotationForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
        sample_annotation_form.prepare()
        return sample_annotation_form.make_response()
        
        
        
