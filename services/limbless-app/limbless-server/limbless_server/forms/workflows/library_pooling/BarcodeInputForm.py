import os
from pathlib import Path
from uuid import uuid4
from typing import Optional, Literal

import pandas as pd
import numpy as np

from flask import Response
from wtforms import SelectField, FileField, StringField
from wtforms.validators import Optional as OptionalValidator
from flask_wtf.file import FileAllowed
from werkzeug.utils import secure_filename

from .... import logger, tools
from ....tools import SpreadSheetColumn
from ...TableDataForm import TableDataForm
from ...HTMXFlaskForm import HTMXFlaskForm
from .IndexKitMappingForm import IndexKitMappingForm
from .CompleteLibraryPoolingForm import CompleteLibraryPoolingForm


class BarcodeInputForm(HTMXFlaskForm, TableDataForm):
    _template_path = "workflows/library_pooling/pooling-3.html"
    _form_label = "library_pooling_form"
    
    columns = {
        "library_id": SpreadSheetColumn("A", "library_id", "ID", "numeric", 50, int),
        "library_name": SpreadSheetColumn("B", "library_name", "Library Name", "text", 170, str),
        "kit": SpreadSheetColumn("C", "kit", "Kit", "text", 170, str),
        "adapter": SpreadSheetColumn("D", "adapter", "Adapter", "text", 170, str),
        "index_1": SpreadSheetColumn("E", "index_1", "Index 1 (i7)", "text", 150, str),
        "index_2": SpreadSheetColumn("F", "index_2", "Index 2 (i5)", "text", 150, str),
        "index_3": SpreadSheetColumn("G", "index_3", "Index 3", "text", 150, str),
        "index_4": SpreadSheetColumn("H", "index_4", "Index 4", "text", 150, str),
    }
    
    _allowed_extensions: list[tuple[str, str]] = [
        ("tsv", "Tab-separated"),
        ("csv", "Comma-separated")
    ]
    _mapping: dict[str, str] = dict([(col.name, col.label) for col in columns.values()])
    _required_columns: list[str] = [col.name for col in columns.values()]

    colors = {
        "missing_value": "#FAD7A0",
        "invalid_value": "#F5B7B1",
        "duplicate_value": "#D7BDE2",
        "invalid_input": "#AED6F1"
    }

    separator = SelectField(choices=_allowed_extensions, default="tsv")
    file = FileField(validators=[FileAllowed([ext for ext, _ in _allowed_extensions])])
    spreadsheet_dummy = StringField(validators=[OptionalValidator()])

    def __init__(self, formdata: dict = {}, uuid: Optional[str] = None, input_type: Optional[Literal["spreadsheet", "file"]] = None, previous_form: Optional[TableDataForm] = None):
        if uuid is None:
            uuid = formdata.get("file_uuid")
        HTMXFlaskForm.__init__(self, formdata=formdata)
        TableDataForm.__init__(self, dirname="library_pooling", uuid=uuid, previous_form=previous_form)
        self.input_type = input_type
        self._context["columns"] = BarcodeInputForm.columns.values()
        self._context["colors"] = BarcodeInputForm.colors
        self._context["active_tab"] = "help"
        self.spreadsheet_style = dict()

    def get_template(self) -> pd.DataFrame:
        barcode_table = self.tables["barcode_table"][BarcodeInputForm.columns.keys()]
        barcode_table = barcode_table.rename(columns=dict([(col.label, col.name) for col in BarcodeInputForm.columns.values()]))
        return barcode_table

    def prepare(self):
        barcode_table = self.tables["barcode_table"][BarcodeInputForm.columns.keys()]
        self._context["spreadsheet_data"] = barcode_table.replace(np.nan, "").values.tolist()

    def validate(self) -> bool:
        validated = super().validate()

        if self.input_type is None or self.input_type not in ["spreadsheet", "file"]:
            logger.error("Input type not set")
            raise ValueError("Input type not set")
        
        self._context["active_tab"] = self.input_type
        
        if self.input_type == "file":
            if self.file.data is None:
                self.file.errors = ("Upload a file.",)
                return False
            
        if not validated:
            return False
        
        if self.input_type == "file":
            filename = f"{Path(self.file.data.filename).stem}_{uuid4()}.{self.file.data.filename.split('.')[-1]}"
            filename = secure_filename(filename)
            filepath = os.path.join("uploads", "seq_request", filename)
            self.file.data.save(filepath)

            sep = "\t" if self.separator.data == "tsv" else ","

            try:
                self.df = pd.read_csv(filepath, sep=sep, index_col=False, header=0)
                validated = True
            except pd.errors.ParserError as e:
                self.file.errors = (str(e),)
                validated = False
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
                if not validated:
                    return False
            
            missing = []
            for col in BarcodeInputForm._required_columns:
                if col not in self.df.columns:
                    missing.append(col)
            
                if len(missing) > 0:
                    self.file.errors = (f"Missing column(s): [{', '.join(missing)}]",)
                    return False
            
            self.df = self.df.rename(columns=BarcodeInputForm._mapping)
            self.df = self.df.replace(r'^\s*$', None, regex=True)
            self.df = self.df.dropna(how="all")

            if len(self.df) == 0:
                self.file.errors = ("File is empty.",)
                return False
                
        elif self.input_type == "spreadsheet":
            import json
            data = json.loads(self.formdata["spreadsheet"])  # type: ignore
            try:
                self.df = pd.DataFrame(data)
            except ValueError as e:
                self.spreadsheet_dummy.errors = (str(e),)
                return False
            
            if len(self.df.columns) != len(list(BarcodeInputForm.columns.keys())):
                self.spreadsheet_dummy.errors = (f"Invalid number of columns (expected {len(BarcodeInputForm.columns)}). Do not insert new columns or rearrange existing columns.",)
                return False
            
            self.df.columns = list(BarcodeInputForm.columns.keys())
            self.df = self.df.replace(r'^\s*$', None, regex=True)
            self.df = self.df.dropna(how="all")

            if len(self.df) == 0:
                self.spreadsheet_dummy.errors = ("Please fill-out spreadsheet or upload a file.",)
                return False
            
        self.df["adapter"] = self.df["adapter"].apply(tools.make_alpha_numeric)
        self.df["index_1"] = self.df["index_1"].apply(lambda x: tools.make_alpha_numeric(x, keep=[], replace_white_spaces_with=""))
        self.df["index_2"] = self.df["index_2"].apply(lambda x: tools.make_alpha_numeric(x, keep=[], replace_white_spaces_with=""))
        self.df["index_3"] = self.df["index_3"].apply(lambda x: tools.make_alpha_numeric(x, keep=[], replace_white_spaces_with=""))
        self.df["index_4"] = self.df["index_4"].apply(lambda x: tools.make_alpha_numeric(x, keep=[], replace_white_spaces_with=""))

        self.file.errors = []
        self.spreadsheet_dummy.errors = []

        barcode_table = self.tables["barcode_table"]

        def add_error(row_num: int, column: str, message: str, color: Literal["missing_value", "invalid_value", "duplicate_value", "invalid_input"]):
            if self.input_type == "spreadsheet":
                self.spreadsheet_style[f"{BarcodeInputForm.columns[column].column}{row_num}"] = f"background-color: {BarcodeInputForm.colors[color]};"
                self.spreadsheet_dummy.errors.append(f"Row {row_num}: {message}")  # type: ignore
            else:
                self.file.errors.append(f"Row {row_num}: {message}")  # type: ignore

        kit_barcode = self.df["kit"].notna() & self.df["adapter"].notna()
        custom_barcode = self.df["index_1"].notna()

        for i, (idx, row) in enumerate(self.df.iterrows()):
            if pd.isna(row["library_id"]):
                add_error(i + 1, "library_id", "missing 'library_id'", "missing_value")
            elif row["library_id"] not in barcode_table["library_id"].values:
                add_error(i + 1, "library_id", "invalid 'library_id'", "invalid_value")

            if pd.isna(row["library_name"]):
                add_error(i + 1, "library_name", "missing 'library_name'", "missing_value")
            elif row["library_name"] not in barcode_table["library_name"].values:
                add_error(i + 1, "library_name", "invalid 'library_name'", "invalid_value")

            if not kit_barcode.at[idx] and not custom_barcode.at[idx]:
                add_error(i + 1, "kit", "specify 'kit' + 'adapter' or 'index_1/2/3/4'", "missing_value")
                add_error(i + 1, "adapter", "specify 'kit' + 'adapter' or 'index_1/2/3/4'", "missing_value")
                add_error(i + 1, "index_1", "specify 'kit' + 'adapter' or 'index_1/2/3/4'", "missing_value")

            if kit_barcode.at[idx] and custom_barcode.at[idx]:
                add_error(i + 1, "kit", "specify 'kit' + 'adapter or 'index_1/2/3/4', not both'", "invalid_input")
                add_error(i + 1, "adapter", "specify 'kit' + 'adapter' or 'index_1/2/3/4', not both'", "invalid_input")
                add_error(i + 1, "index_1", "specify 'kit' + 'adapter' or 'index_1/2/3/4', not both'", "invalid_input")

            if pd.isna(row["index_1"]) and pd.notna(row["index_2"]):
                add_error(i + 1, "index_1", "index_1 not specified but index_2 is", "missing_value")
                add_error(i + 1, "index_2", "index_1 not specified but index_2 is", "invalid_input")

            if pd.isna(row["index_1"]) and pd.notna(row["index_3"]):
                add_error(i + 1, "index_1", "index_1 not specified but index_3 is", "missing_value")
                add_error(i + 1, "index_3", "index_1 not specified but index_3 is", "invalid_input")

            if pd.isna(row["index_1"]) and pd.notna(row["index_4"]):
                add_error(i + 1, "index_1", "index_1 not specified but index_4 is", "missing_value")
                add_error(i + 1, "index_4", "index_1 not specified but index_4 is", "invalid_input")

        if self.input_type == "file":
            validated = validated and len(self.file.errors) == 0
        elif self.input_type == "spreadsheet":
            validated = validated and (len(self.spreadsheet_dummy.errors) == 0 and len(self.spreadsheet_style) == 0)

        for idx, row in self.df.iterrows():
            barcode_table.loc[barcode_table["library_id"] == row["library_id"], "kit"] = row["kit"]
            barcode_table.loc[barcode_table["library_id"] == row["library_id"], "adapter"] = row["adapter"]
            barcode_table.loc[barcode_table["library_id"] == row["library_id"], "index_1"] = row["index_1"]
            barcode_table.loc[barcode_table["library_id"] == row["library_id"], "index_2"] = row["index_2"]
            barcode_table.loc[barcode_table["library_id"] == row["library_id"], "index_3"] = row["index_3"]
            barcode_table.loc[barcode_table["library_id"] == row["library_id"], "index_4"] = row["index_4"]

        self.barcode_table = barcode_table

        return validated

    def process_request(self, **context) -> Response:
        if not self.validate():
            if self.input_type == "spreadsheet":
                self._context["spreadsheet_style"] = self.spreadsheet_style
                context["spreadsheet_data"] = self.df[BarcodeInputForm.columns.keys()].replace(np.nan, "").values.tolist()
                if context["spreadsheet_data"] == []:
                    context["spreadsheet_data"] = [[None]]
            else:
                barcode_table = self.tables["barcode_table"]
                self._context["spreadsheet_data"] = barcode_table[BarcodeInputForm.columns.keys()].replace(np.nan, "").values.tolist()

            return self.make_response(**context)
        
        self.update_table("barcode_table", self.barcode_table)

        if self.barcode_table["kit"].notna().any():
            index_kit_mapping_form = IndexKitMappingForm(previous_form=self, uuid=self.uuid)
            index_kit_mapping_form.prepare()
            return index_kit_mapping_form.make_response(**context)
        
        complete_library_pooling_form = CompleteLibraryPoolingForm(previous_form=self, uuid=self.uuid)
        complete_library_pooling_form.prepare()
        return complete_library_pooling_form.make_response(**context)