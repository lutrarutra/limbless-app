from typing import Optional

import pandas as pd

from flask import Response, url_for

from limbless_db import models
from limbless_db.categories import LibraryType

from .... import logger, tools, db  # noqa F401
from ...MultiStepForm import MultiStepForm

from ....tools import SpreadSheetColumn
from ...HTMXFlaskForm import HTMXFlaskForm
from ...SpreadsheetInput import SpreadsheetInput
from .IndexKitMappingForm import IndexKitMappingForm
from .CMOReferenceInputForm import CMOReferenceInputForm
from .VisiumAnnotationForm import VisiumAnnotationForm
from .FeatureReferenceInputForm import FeatureReferenceInputForm
from .FRPAnnotationForm import FRPAnnotationForm
from .SampleAnnotationForm import SampleAnnotationForm


class BarcodeInputForm(HTMXFlaskForm, MultiStepForm):
    _template_path = "workflows/library_annotation/sas-barcode-input.html"
    
    columns = {
        "library_name": SpreadSheetColumn("A", "library_name", "Library Name", "text", 250, str),
        "index_well": SpreadSheetColumn("B", "index_well", "Index Well", "text", 100, str),
        "kit_i7": SpreadSheetColumn("C", "kit_i7", "i7 Kit", "text", 200, str),
        "name_i7": SpreadSheetColumn("D", "name_i7", "i7 Name", "text", 150, str),
        "sequence_i7": SpreadSheetColumn("E", "sequence_i7", "i7 Sequence", "text", 180, str, clean_up_fnc=lambda x: tools.make_alpha_numeric(x, keep=[";"], replace_white_spaces_with="")),
        "kit_i5": SpreadSheetColumn("F", "kit_i5", "i5 Kit", "text", 200, str),
        "name_i5": SpreadSheetColumn("G", "name_i5", "i5 Name", "text", 150, str),
        "sequence_i5": SpreadSheetColumn("H", "sequence_i5", "i5 Sequence", "text", 180, str, clean_up_fnc=lambda x: tools.make_alpha_numeric(x, keep=[";"], replace_white_spaces_with="")),
    }
    
    _mapping: dict[str, str] = dict([(col.name, col.label) for col in columns.values()])
    _required_columns: list[str] = [col.name for col in columns.values()]

    def __init__(self, seq_request: models.SeqRequest, uuid: str, formdata: dict = {}, previous_form: Optional[MultiStepForm] = None):
        HTMXFlaskForm.__init__(self, formdata=formdata)
        MultiStepForm.__init__(self, uuid=uuid, dirname="library_annotation", previous_form=previous_form)
        self.seq_request = seq_request
        self._context["seq_request"] = seq_request

        self.library_table = self.tables["library_table"]
        if (csrf_token := formdata.get("csrf_token")) is None:
            csrf_token = self.csrf_token._value()  # type: ignore
        self.spreadsheet: SpreadsheetInput = SpreadsheetInput(
            columns=BarcodeInputForm.columns, csrf_token=csrf_token,
            post_url=url_for("library_annotation_workflow.parse_barcode_table", seq_request_id=seq_request.id, uuid=self.uuid),
            formdata=formdata, df=self.get_template(),
        )

    def get_template(self) -> pd.DataFrame:
        barcode_table_data = {
            "library_name": [],
            "index_well": [],
            "kit_i7": [],
            "name_i7": [],
            "sequence_i7": [],
            "kit_i5": [],
            "name_i5": [],
            "sequence_i5": [],
        }

        for _, row in self.library_table.iterrows():
            barcode_table_data["library_name"].append(row["library_name"])
            barcode_table_data["index_well"].append(None)
            barcode_table_data["kit_i7"].append(None)
            barcode_table_data["name_i7"].append(None)
            barcode_table_data["sequence_i7"].append(None)
            barcode_table_data["kit_i5"].append(None)
            barcode_table_data["name_i5"].append(None)
            barcode_table_data["sequence_i5"].append(None)
        
        return pd.DataFrame(barcode_table_data)
    
    def validate(self) -> bool:
        validated = super().validate()
            
        if not validated:
            return False
        
        if not self.spreadsheet.validate():
            return False
        
        df = self.spreadsheet.df

        df.loc[df["kit_i7"].notna(), "kit_i7"] = df.loc[df["kit_i7"].notna(), "kit_i7"].astype(str)
        df.loc[df["kit_i5"].notna(), "kit_i5"] = df.loc[df["kit_i5"].notna(), "kit_i5"].astype(str)
            
        df["sequence_i7"] = df["sequence_i7"].apply(lambda x: tools.make_alpha_numeric(x, keep=[";"], replace_white_spaces_with=""))
        df["sequence_i5"] = df["sequence_i5"].apply(lambda x: tools.make_alpha_numeric(x, keep=[";"], replace_white_spaces_with=""))

        df.loc[df["index_well"].notna(), "index_well"] = df.loc[df["index_well"].notna(), "index_well"].str.replace(r'(?<=[A-Z])0+(?=\d)', '', regex=True)

        kit_defined = df["kit_i7"].notna() & (df["index_well"].notna() | df["name_i7"].notna())
        manual_defined = df["sequence_i7"].notna()

        df.loc[df["kit_i5"].isna(), "kit_i5"] = df.loc[df["kit_i5"].isna(), "kit_i7"]
        df.loc[df["name_i5"].isna(), "name_i5"] = df.loc[df["name_i5"].isna(), "name_i7"]

        for name in self.library_table["library_name"].values:
            if name not in df["library_name"].values:
                self.spreadsheet.add_general_error(f"Missing '{name}'")

        for i, (idx, row) in enumerate(df.iterrows()):
            if pd.isna(row["library_name"]):
                self.spreadsheet.add_error(i + 1, "library_name", "missing 'library_name'", "missing_value")
            elif row["library_name"] not in self.library_table["library_name"].values:
                self.spreadsheet.add_error(i + 1, "library_name", "invalid 'library_name'", "invalid_value")

            if not kit_defined.at[idx] and not manual_defined.at[idx]:
                self.spreadsheet.add_error(i + 1, "sequence_i7", "missing 'sequence_i7' or 'kit_i7' + 'name_i7' or 'kit_i7' + 'index_well'", "missing_value")

        validated = validated and (len(self.spreadsheet._errors) == 0)

        self.df = df

        return validated

    def process_request(self) -> Response:
        if not self.validate():

            return self.make_response()
        
        barcode_table_data = {
            "library_name": [],
            "index_well": [],
            "kit_i7": [],
            "name_i7": [],
            "sequence_i7": [],
            "kit_i5": [],
            "name_i5": [],
            "sequence_i5": [],
        }
        
        for idx, row in self.df.iterrows():
            index_i7_seqs = row["sequence_i7"].split(";") if pd.notna(row["sequence_i7"]) else [None]
            index_i5_seqs = row["sequence_i5"].split(";") if pd.notna(row["sequence_i5"]) else [None]

            for i in range(max(len(index_i7_seqs), len(index_i5_seqs))):
                barcode_table_data["library_name"].append(row["library_name"])
                barcode_table_data["index_well"].append(row["index_well"])
                barcode_table_data["kit_i7"].append(row["kit_i7"])
                barcode_table_data["name_i7"].append(row["name_i7"])
                barcode_table_data["sequence_i7"].append(index_i7_seqs[i] if len(index_i7_seqs) > i else None)
                barcode_table_data["kit_i5"].append(row["kit_i5"])
                barcode_table_data["name_i5"].append(row["name_i5"])
                barcode_table_data["sequence_i5"].append(index_i5_seqs[i] if len(index_i5_seqs) > i else None)

        barcode_table = pd.DataFrame(barcode_table_data)
        barcode_table["kit_i7_id"] = None
        barcode_table["kit_i7_name"] = None
        barcode_table["kit_i5_id"] = None
        barcode_table["kit_i5_name"] = None
        self.add_table("barcode_table", barcode_table)
        self.update_data()

        if barcode_table["kit_i7"].notna().any():
            index_kit_mapping_form = IndexKitMappingForm(seq_request=self.seq_request, uuid=self.uuid, previous_form=self)
            index_kit_mapping_form.prepare()
            return index_kit_mapping_form.make_response()

        if self.library_table["library_type_id"].isin([
            LibraryType.TENX_MULTIPLEXING_CAPTURE.id,
        ]).any():
            cmo_reference_input_form = CMOReferenceInputForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
            return cmo_reference_input_form.make_response()
        
        if (self.library_table["library_type_id"].isin([LibraryType.TENX_VISIUM.id, LibraryType.TENX_VISIUM_FFPE.id, LibraryType.TENX_VISIUM_HD.id])).any():
            visium_annotation_form = VisiumAnnotationForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
            visium_annotation_form.prepare()
            return visium_annotation_form.make_response()
        
        if (self.library_table["library_type_id"] == LibraryType.TENX_ANTIBODY_CAPTURE.id).any():
            feature_reference_input_form = FeatureReferenceInputForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
            return feature_reference_input_form.make_response()
        
        if LibraryType.TENX_SC_GEX_FLEX.id in self.library_table["library_type_id"].values:
            frp_annotation_form = FRPAnnotationForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
            return frp_annotation_form.make_response()
    
        sample_annotation_form = SampleAnnotationForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
        return sample_annotation_form.make_response()