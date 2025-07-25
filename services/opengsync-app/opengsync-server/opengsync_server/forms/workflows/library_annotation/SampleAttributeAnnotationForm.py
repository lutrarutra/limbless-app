import os
from typing import Optional

import pandas as pd

from flask import Response, url_for

from opengsync_db import models
from opengsync_db.categories import LibraryType, AttributeType
from opengsync_server.forms.MultiStepForm import StepFile

from .... import logger, db  # noqa F401
from ....tools.spread_sheet_components import TextColumn, DropdownColumn, MissingCellValue, SpreadSheetColumn
from ...MultiStepForm import MultiStepForm
from .CompleteSASForm import CompleteSASForm
from ...SpreadsheetInput import SpreadsheetInput


class SampleAttributeAnnotationForm(MultiStepForm):
    _template_path = "workflows/library_annotation/sas-sample_attribute_annotation.html"
    _workflow_name = "library_annotation"
    _step_name = "sample_attribute_annotation"

    predefined_columns = [
        DropdownColumn("sample_name", "Sample Name", 170, required=True, choices=[])
    ] + [TextColumn(t.label, t.name, 100, max_length=models.SampleAttribute.MAX_NAME_LENGTH) for t in AttributeType.as_list()[1:]]

    def __init__(self, seq_request: models.SeqRequest, uuid: str, formdata: dict = {}):
        MultiStepForm.__init__(
            self, uuid=uuid, formdata=formdata, workflow=SampleAttributeAnnotationForm._workflow_name,
            step_name=SampleAttributeAnnotationForm._step_name, step_args={}
        )

        self.seq_request = seq_request
        self._context["seq_request"] = seq_request
        self.upload_path = os.path.join("uploads", "seq_request")
        self.columns: list[SpreadSheetColumn] = SampleAttributeAnnotationForm.predefined_columns.copy()  # type: ignore

        if (csrf_token := formdata.get("csrf_token")) is None:
            csrf_token = self.csrf_token._value()  # type: ignore

        library_table = self.tables["library_table"]
        sample_table = self.tables["sample_table"]

        library_table["is_mux_sample"] = False
        library_table["is_flex_sample"] = False
        for sample_name, _df in library_table.groupby("sample_name"):
            if LibraryType.TENX_MUX_OLIGO.id in _df["library_type_id"].unique():
                library_table.loc[library_table["sample_name"] == sample_name, "is_mux_sample"] = True
            if LibraryType.TENX_SC_GEX_FLEX.id in _df["library_type_id"].unique():
                library_table.loc[library_table["sample_name"] == sample_name, "is_flex_sample"] = True

        self.update_table("library_table", library_table, False)

        df = sample_table[["sample_name"]].copy()
    
        for col in SampleAttributeAnnotationForm.predefined_columns:
            if col.label in df.columns:
                continue
            
            df[col.label] = ""

        for _, row in sample_table[sample_table["sample_id"].notna()].iterrows():
            if (sample := db.get_sample(sample_id=int(row["sample_id"]))) is None:
                logger.warning(f"Sample with ID {row['sample_id']} not found in the database.")
                raise ValueError(f"Sample with ID {row['sample_id']} not found in the database.")
            
            for attr in sample.attributes:
                df.loc[df["sample_name"] == row["sample_name"], attr.name] = attr.value

        for col in df.columns:
            if col not in [c.label for c in self.columns]:
                self.columns.append(TextColumn(col, col.replace("_", " ").title(), 100, max_length=models.SampleAttribute.MAX_NAME_LENGTH))

        self.spreadsheet: SpreadsheetInput = SpreadsheetInput(
            columns=self.columns, csrf_token=csrf_token,
            post_url=url_for('library_annotation_workflow.parse_sas_form', seq_request_id=seq_request.id, uuid=self.uuid),
            formdata=formdata, allow_new_cols=True, allow_col_rename=True, df=df
        )
        self.spreadsheet.columns["sample_name"].source = sample_table["sample_name"].unique().tolist()

    def fill_previous_form(self, previous_form: StepFile):
        df = previous_form.tables["sample_table"]
        for col in df.columns:
            if col.startswith("_attr_"):
                col = col.removeprefix("_attr_")
                if col not in self.spreadsheet.columns.keys():
                    self.spreadsheet.add_column(
                        label=col, column=TextColumn(
                            label=col, name=col.replace("_", " ").title(),
                            width=100, max_length=models.SampleAttribute.MAX_NAME_LENGTH
                        )
                    )
        df.columns = df.columns.str.removeprefix("_attr_")
        self.spreadsheet.set_data(df)

    def validate(self) -> bool:
        validated = super().validate()
                
        if not validated:
            return False
        
        if not self.spreadsheet.validate():
            return False
        
        self.sample_table = self.tables["sample_table"]
        df = self.spreadsheet.df

        if df.columns.str.len().min() < 3:
            shortest_col = df.columns[df.columns.str.len() == df.columns.str.len().min()].values[0]
            self.spreadsheet.add_general_error(f"Column: '{shortest_col}', specify more descriptive column name by right-clicking column and 'Rename this column'",)
            return False

        missing_samples = self.sample_table.loc[~self.sample_table["sample_name"].isin(df["sample_name"]), "sample_name"].values.tolist()
        if len(missing_samples) > 0:
            self.spreadsheet.add_general_error(f"Sample(s) not found in the sample table: {', '.join(missing_samples)}")
            validated = False

        for col in df.columns:
            if col not in self.spreadsheet.columns.keys():
                self.spreadsheet.add_column(label=col, column=TextColumn(label=col, name=col.replace("_", " ").title(), width=100, max_length=models.SampleAttribute.MAX_NAME_LENGTH))

        for idx, row in df.iterrows():
            for col in df.keys():
                if col == "sample_name":
                    continue
                
                if pd.isna(df[col]).all():
                    continue
                
                if pd.isna(row[col]):
                    self.spreadsheet.add_error(idx, col, MissingCellValue("Missing value"))
                    validated = False

        if len(self.spreadsheet._errors) > 0 or not validated:
            return False

        self.df = df.dropna(how="all")

        return True

    def process_request(self) -> Response:
        if not self.validate():
            return self.make_response()
        
        for idx, row in self.df.iterrows():
            sample_name = row["sample_name"]
            for col in self.df.columns:
                if col == "sample_name" or self.df[col].isna().all():
                    continue
                self.sample_table.loc[self.sample_table["sample_name"] == sample_name, f"_attr_{col}"] = row[col]

        self.update_table("sample_table", self.sample_table)
        
        next_form = CompleteSASForm(seq_request=self.seq_request, uuid=self.uuid)
        return next_form.make_response()