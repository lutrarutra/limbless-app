import os
import string
from typing import Optional, Literal

import pandas as pd
import numpy as np

from flask import Response
from wtforms import StringField
from wtforms.validators import Optional as OptionalValidator

from limbless_db import models
from limbless_db.categories import LibraryType, AttributeType

from .... import logger, db  # noqa F401
from ....tools import SpreadSheetColumn
from ...HTMXFlaskForm import HTMXFlaskForm
from ...TableDataForm import TableDataForm
from .CompleteSASForm import CompleteSASForm


class SampleAnnotationForm(HTMXFlaskForm, TableDataForm):
    _template_path = "workflows/library_annotation/sas-11.html"
    _form_label = "sample_annotation_form"

    _allowed_extensions: list[tuple[str, str]] = [
        ("tsv", "Tab-separated"),
        ("csv", "Comma-separated")
    ]
    colors = {
        "missing_value": "#FAD7A0",
        "invalid_value": "#F5B7B1",
        "duplicate_value": "#D7BDE2",
    }

    predefined_columns = {"sample_name": SpreadSheetColumn("A", "sample_name", "Sample Name", "text", 170, str)} | dict([(t.label, SpreadSheetColumn(string.ascii_uppercase[i + 1], t.label, t.name, "text", 100, str)) for i, t in enumerate(AttributeType.as_list()) if t.label != "custom"])

    spreadsheet_dummy = StringField(validators=[OptionalValidator()])

    def __init__(self, seq_request: models.SeqRequest, formdata: dict = {}, previous_form: Optional[TableDataForm] = None, uuid: Optional[str] = None):
        if uuid is None:
            uuid = formdata.get("file_uuid")
        HTMXFlaskForm.__init__(self, formdata=formdata)
        TableDataForm.__init__(self, dirname="library_annotation", uuid=uuid, previous_form=previous_form)

        self.seq_request = seq_request
        self._context["seq_request"] = seq_request

        self.spreadsheet_style = dict()
        self._context["colors"] = SampleAnnotationForm.colors
        self._context["active_tab"] = "help"
        self._context["columns"] = SampleAnnotationForm.predefined_columns.values()
        self.upload_path = os.path.join("uploads", "seq_request")

    def prepare(self):
        library_table = self.tables["library_table"]
        flex_table = self.tables.get("flex_table")
        cmo_table = self.tables.get("cmo_table")

        library_table["is_cmo_sample"] = False
        library_table["is_flex_sample"] = False
        for sample_name, _df in library_table.groupby("sample_name"):
            if LibraryType.TENX_MULTIPLEXING_CAPTURE.id in _df["library_type_id"].unique():
                library_table.loc[library_table["sample_name"] == sample_name, "is_cmo_sample"] = True
            if LibraryType.TENX_SC_GEX_FLEX.id in _df["library_type_id"].unique():
                library_table.loc[library_table["sample_name"] == sample_name, "is_flex_sample"] = True

        self.update_table("library_table", library_table, False)

        sample_data = {
            "sample_name": [],
            "sample_id": [],
            "sample_pool": [],
            "library_types": [],
            "is_cmo_sample": [],
            "is_flex_sample": [],
            "cmo_sequence": [],
            "cmo_pattern": [],
            "cmo_read": [],
            "flex_barcode": [],
        }

        def add_sample(
            sample_name: str,
            sample_id: Optional[int],
            sample_pool: str,
            is_cmo_sample: bool,
            is_flex_sample: bool,
            library_types: str,
            cmo_sequence: Optional[str] = None,
            cmo_pattern: Optional[str] = None,
            cmo_read: Optional[str] = None,
            flex_barcode: Optional[str] = None
        ):
            sample_data["sample_name"].append(sample_name)
            sample_data["sample_id"].append(sample_id)
            sample_data["sample_pool"].append(sample_pool)
            sample_data["library_types"].append(library_types)
            sample_data["is_cmo_sample"].append(is_cmo_sample)
            sample_data["is_flex_sample"].append(is_flex_sample)
            sample_data["cmo_sequence"].append(cmo_sequence)
            sample_data["cmo_pattern"].append(cmo_pattern)
            sample_data["cmo_read"].append(cmo_read)
            sample_data["flex_barcode"].append(flex_barcode)

        for (sample_name, sample_id, is_cmo_sample, is_flex_sample), _df in library_table.groupby(["sample_name", "sample_id", "is_cmo_sample", "is_flex_sample"], dropna=False, sort=False):
            library_types = ";".join([LibraryType.get(library_type_id).abbreviation for library_type_id in _df["library_type_id"].unique()])
            if is_cmo_sample:
                if cmo_table is None:
                    logger.error(f"{self.uuid}: CMO reference table not found.")
                    raise Exception("CMO reference should not be None.")
                
                for _, cmo_row in cmo_table[cmo_table["sample_name"] == sample_name].iterrows():
                    add_sample(
                        sample_name=cmo_row["demux_name"],
                        sample_pool=sample_name,
                        library_types=library_types,
                        is_cmo_sample=True,
                        is_flex_sample=False,
                        sample_id=sample_id if pd.notna(sample_id) else None,
                        cmo_sequence=cmo_row["sequence"],
                        cmo_pattern=cmo_row["pattern"],
                        cmo_read=cmo_row["read"],
                    )
            elif is_flex_sample:
                if flex_table is None:
                    logger.error(f"{self.uuid}: flex reference table not found.")
                    raise Exception("flex reference should not be None.")
                
                for (flex_sample_name, flex_demux_name, flex_barcode_id), _ in flex_table[flex_table["sample_name"] == sample_name].groupby(["sample_name", "demux_name", "barcode_id"], dropna=False):
                    add_sample(
                        sample_name=flex_demux_name,
                        sample_pool=flex_sample_name,
                        is_flex_sample=True,
                        is_cmo_sample=False,
                        library_types=library_types,
                        flex_barcode=flex_barcode_id,
                        sample_id=sample_id if pd.notna(sample_id) else None,
                    )
            else:
                add_sample(
                    sample_name=sample_name,
                    sample_pool=sample_name,
                    library_types=library_types,
                    is_cmo_sample=False,
                    is_flex_sample=False,
                    sample_id=sample_id if pd.notna(sample_id) else None,
                )

        self.sample_table = pd.DataFrame(sample_data).fillna(np.nan)
        self._context["sample_table"] = self.sample_table
        self.add_table("sample_table", self.sample_table)
        self.update_data()
        template = self.sample_table[["sample_name"]].copy()
        for col in SampleAnnotationForm.predefined_columns.values():
            if col.label in template.columns:
                continue
            
            template[col.label] = ""

        for _, row in self.sample_table.iterrows():
            attributes = db.get_sample_attributes(sample_id=row["sample_id"])
            for attr in attributes:
                template.loc[template["sample_name"] == row["sample_name"], attr.name] = attr.value

        columns = self.set_columns(template)
        self._context["spreadsheet_data"] = template[list(columns.keys())].replace(np.nan, "").values.tolist()

    def set_columns(self, df: pd.DataFrame) -> dict[str, SpreadSheetColumn]:
        columns = {}
        for col in df.columns:
            if col in SampleAnnotationForm.predefined_columns.keys():
                columns[col] = SampleAnnotationForm.predefined_columns[col]
            else:
                columns[col] = SpreadSheetColumn(string.ascii_uppercase[len(columns) + 1], col, col.replace("_", " ").title(), "text", 100, str)
        
        self._context["columns"] = columns.values()
        return columns

    def columns_mapping(self):
        return dict([(col.name, col.label) for col in SampleAnnotationForm.predefined_columns.values()])

    def validate(self) -> bool:
        self.df = None
        validated = super().validate()
                
        if not validated:
            return False
        
        self.sample_table = self.tables["sample_table"]
        
        import json
        data = json.loads(self.formdata["spreadsheet"])  # type: ignore
        try:
            self.df = pd.DataFrame(data)
        except ValueError as e:
            self.spreadsheet_dummy.errors = (str(e),)
            return False
        
        if not self.spreadsheet_dummy.data:
            logger.error("Spreadsheet dummy data not found.")
            raise Exception("Spreadsheet dummy data not found.")
        
        attribute_columns = json.loads(self.spreadsheet_dummy.data).split(",")
        if len(duplicate_columns := set(self.sample_table.columns.tolist()) & set(attribute_columns)) > 0:
            self.spreadsheet_dummy.errors = (f"Column(s) '{','.join(duplicate_columns)}' are duplicated/reserved.",)
            return False
        
        self.df.columns = attribute_columns
        self.df = self.df.replace(r'^\s*$', None, regex=True)
        self.df = self.df.dropna(how="all")

        if len(self.df) == 0:
            self.spreadsheet_dummy.errors = ("Please fill-out spreadsheet or upload a file.",)
            return False

        self.df = self.df.rename(columns=self.columns_mapping())
        column_order = self.df.columns.tolist()
        if self.df.columns.str.len().min() < 3:
            shortest_col = self.df.columns[self.df.columns.str.len() == self.df.columns.str.len().min()].values[0]
            self.spreadsheet_dummy.errors = (f"Column: '{shortest_col}', specify more descriptive column name by right-clicking column and 'Rename this column'",)
            return False

        self.spreadsheet_dummy.errors = []

        def add_error(row_num: int, column: str, message: str, color: Literal["missing_value", "invalid_value", "duplicate_value"]):
            self.spreadsheet_style[f"{string.ascii_uppercase[column_order.index(column)]}{row_num}"] = f"background-color: {SampleAnnotationForm.colors[color]};"
            self.spreadsheet_dummy.errors.append(f"Row {row_num}: {message}")  # type: ignore

        missing_samples = self.sample_table.loc[~self.sample_table["sample_name"].isin(self.df["sample_name"]), "sample_name"].values.tolist()
        if len(missing_samples) > 0:
            self.spreadsheet_dummy.errors.append(f"Sample(s) not found in the sample table: {', '.join(missing_samples)}")
            validated = False

        for i, (idx, row) in enumerate(self.df.iterrows()):
            if pd.isna(row["sample_name"]) or row["sample_name"] == "":
                add_error(i + 1, "sample_name", "Missing value", "missing_value")
                validated = False
                continue
            
            if row["sample_name"] not in self.tables["sample_table"]["sample_name"].values:
                add_error(i + 1, "sample_name", f"Unknown sample name '{row['sample_name']}'", "invalid_value")
                validated = False
                continue
            
            for col in self.df.keys():
                if col == "sample_name":
                    continue
                
                if pd.isna(self.df[col]).all():
                    continue
                
                if pd.isna(row[col]):
                    add_error(i + 1, col, "Missing value", "missing_value")
                    validated = False

        self.df = self.df.dropna(how="all")

        return validated

    def process_request(self) -> Response:
        if not self.validate() or self.df is None:
            self._context["active_tab"] = "spreadsheet"
            self._context["spreadsheet_style"] = self.spreadsheet_style
            if self.df is not None:
                self.set_columns(self.df)
                self._context["spreadsheet_data"] = self.df.replace(np.nan, "").values.tolist()
            if self._context["spreadsheet_data"] == []:
                self._context["spreadsheet_data"] = [[None]]
            return self.make_response()
        
        for idx, row in self.df.iterrows():
            sample_name = row["sample_name"]
            for col in self.df.columns:
                if col == "sample_name" or self.df[col].isna().all():
                    continue
                self.sample_table.loc[self.sample_table["sample_name"] == sample_name, f"_attr_{col}"] = row[col]

        self.update_table("sample_table", self.sample_table)
        
        complete_sas_form = CompleteSASForm(seq_request=self.seq_request, previous_form=self, uuid=self.uuid)
        complete_sas_form.prepare()
        return complete_sas_form.make_response()