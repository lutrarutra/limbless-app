from typing import Optional

import pandas as pd

from flask import Response, url_for

from limbless_db import models
from limbless_db.categories import LibraryType, FeatureType

from .... import logger, tools  # noqa
from ....tools import SpreadSheetColumn
from ...MultiStepForm import MultiStepForm
from ...SpreadsheetInput import SpreadsheetInput
from .KitMappingForm import KitMappingForm
from .FeatureAnnotationForm import FeatureAnnotationForm
from .VisiumAnnotationForm import VisiumAnnotationForm
from .FlexAnnotationForm import FlexAnnotationForm
from .SampleAttributeAnnotationForm import SampleAttributeAnnotationForm


class CMOAnnotationForm(MultiStepForm):
    _template_path = "workflows/library_annotation/sas-cmo_annotation.html"
    _workflow_name = "library_annotation"
    _step_name = "cmo_annotation"
    columns = [
        SpreadSheetColumn("demux_name", "Demultiplexed Name", "text", 170, str, clean_up_fnc=lambda x: tools.make_alpha_numeric(x)),
        SpreadSheetColumn("sample_name", "Sample Name", "text", 170, str, clean_up_fnc=lambda x: tools.make_alpha_numeric(x)),
        SpreadSheetColumn("kit", "Kit", "text", 170, str),
        SpreadSheetColumn("feature", "Feature", "text", 150, str, clean_up_fnc=lambda x: tools.make_alpha_numeric(x)),
        SpreadSheetColumn("sequence", "Sequence", "text", 150, str, clean_up_fnc=lambda x: tools.make_alpha_numeric(x, keep=[], replace_white_spaces_with="")),
        SpreadSheetColumn("pattern", "Pattern", "text", 200, str, clean_up_fnc=lambda x: x.strip() if pd.notna(x) else None),
        SpreadSheetColumn("read", "Read", "text", 100, str, clean_up_fnc=lambda x: tools.make_alpha_numeric(x, keep=[], replace_white_spaces_with="")),
    ]

    def __init__(self, seq_request: models.SeqRequest, uuid: str, previous_form: Optional[MultiStepForm] = None, formdata: dict = {}):
        MultiStepForm.__init__(
            self, workflow=CMOAnnotationForm._workflow_name, step_name=CMOAnnotationForm._step_name,
            uuid=uuid, formdata=formdata, previous_form=previous_form, step_args={}
        )
        self.seq_request = seq_request
        self._context["seq_request"] = seq_request

        if (csrf_token := formdata.get("csrf_token")) is None:
            csrf_token = self.csrf_token._value()  # type: ignore
        self.spreadsheet: SpreadsheetInput = SpreadsheetInput(
            columns=CMOAnnotationForm.columns, csrf_token=csrf_token,
            post_url=url_for('library_annotation_workflow.parse_cmo_reference', seq_request_id=seq_request.id, uuid=self.uuid),
            formdata=formdata, allow_new_rows=True
        )

    def validate(self) -> bool:
        if not super().validate():
            return False
        
        if not self.spreadsheet.validate():
            return False
        
        df = self.spreadsheet.df
        library_table: pd.DataFrame = self.tables["library_table"]

        kit_feature = pd.notna(df["kit"]) & pd.notna(df["feature"])
        custom_feature = pd.notna(df["sequence"]) & pd.notna(df["pattern"]) & pd.notna(df["read"])
        invalid_feature = (pd.notna(df["kit"]) | pd.notna(df["feature"])) & (pd.notna(df["sequence"]) | pd.notna(df["pattern"]) | pd.notna(df["read"]))

        for i, (idx, row) in enumerate(df.iterrows()):
            # sample name not defined
            if pd.isna(row["sample_name"]):
                self.spreadsheet.add_error(idx, "sample_name", "'Sample Name' must be specified.", "missing_value")

            # sample name not found in library table
            elif row["sample_name"] not in library_table["sample_name"].values:
                self.spreadsheet.add_error(idx, "sample_name", f"'Sample Name' must be one of: [{', '.join(set(library_table['sample_name'].values.tolist()))}]", "invalid_value")

            # Demux name not defined
            if pd.isna(row["demux_name"]):
                self.spreadsheet.add_error(idx, "demux_name", "'Demux Name' must be specified.", "missing_value")

            # Not defined custom nor kit feature
            if (not custom_feature.at[idx] and not kit_feature.at[idx]):
                self.spreadsheet.add_error(idx, "kit", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified.", "missing_value")
                self.spreadsheet.add_error(idx, "feature", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified.", "missing_value")
                self.spreadsheet.add_error(idx, "sequence", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified.", "missing_value")
                self.spreadsheet.add_error(idx, "pattern", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified.", "missing_value")
                self.spreadsheet.add_error(idx, "read", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified.", "missing_value")

            # Defined both custom and kit feature
            elif custom_feature.at[idx] and kit_feature.at[idx]:
                self.spreadsheet.add_error(idx, "kit", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified, not both.", "invalid_input")
                self.spreadsheet.add_error(idx, "feature", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified, not both.", "invalid_input")
                self.spreadsheet.add_error(idx, "sequence", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified, not both.", "invalid_input")
                self.spreadsheet.add_error(idx, "pattern", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified, not both.", "invalid_input")
                self.spreadsheet.add_error(idx, "read", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified, not both.", "invalid_input")

            elif invalid_feature.at[idx]:
                if pd.notna(row["kit"]):
                    self.spreadsheet.add_error(idx, "kit", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified, not both.", "invalid_input")
                if pd.notna(row["feature"]):
                    self.spreadsheet.add_error(idx, "feature", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified, not both.", "invalid_input")
                if pd.notna(row["sequence"]):
                    self.spreadsheet.add_error(idx, "sequence", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified, not both.", "invalid_input")
                if pd.notna(row["pattern"]):
                    self.spreadsheet.add_error(idx, "pattern", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified, not both.", "invalid_input")
                if pd.notna(row["read"]):
                    self.spreadsheet.add_error(idx, "read", "must have either 'Kit' (+ 'Feature', optional) or 'Feature + Sequence + Pattern + Read' specified, not both.", "invalid_input")

        if len(self.spreadsheet._errors) > 0:
            return False
        
        self.cmo_table = df
        self.cmo_table["custom_feature"] = custom_feature
        self.cmo_table["kit_feature"] = kit_feature

        return True
    
    def process_request(self) -> Response:
        if not self.validate():
            return self.make_response()

        library_table = self.tables["library_table"]

        kit_table = self.cmo_table[self.cmo_table["kit"].notna()][["kit"]].drop_duplicates().copy()
        kit_table["type_id"] = FeatureType.CMO.id
        kit_table["kit_id"] = None

        if kit_table.shape[0] > 0:
            if (existing_kit_table := self.tables.get("kit_table")) is None:  # type: ignore
                self.add_table("kit_table", kit_table)
            else:
                kit_table = pd.concat([kit_table[kit_table["type_id"] != FeatureType.CMO.id], existing_kit_table])
                self.update_table("kit_table", kit_table, update_data=False)
        
        self.add_table("cmo_table", self.cmo_table)
        self.update_data()

        if ((library_table["library_type_id"] == LibraryType.TENX_ANTIBODY_CAPTURE.id) | (library_table["library_type_id"] == LibraryType.TENX_SC_ABC_FLEX.id)).any():
            next_form = FeatureAnnotationForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)

        elif kit_table["kit_id"].isna().any():
            next_form = KitMappingForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
        
        elif (library_table["library_type_id"].isin([LibraryType.TENX_VISIUM.id, LibraryType.TENX_VISIUM_FFPE.id, LibraryType.TENX_VISIUM_HD.id])).any():
            next_form = VisiumAnnotationForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
        
        elif LibraryType.TENX_SC_GEX_FLEX.id in library_table["library_type_id"].values:
            next_form = FlexAnnotationForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
        else:
            next_form = SampleAttributeAnnotationForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
        
        return next_form.make_response()