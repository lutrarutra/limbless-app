import os
from uuid import uuid4
from pathlib import Path
from typing import Optional

import pandas as pd

from flask_wtf.file import FileField, FileAllowed
from wtforms import SelectField
from flask import Response
from werkzeug.utils import secure_filename

from ..HTMXFlaskForm import HTMXFlaskForm
from .ProjectMappingForm import ProjectMappingForm


class SASInputForm(HTMXFlaskForm):
    _template_path = "components/popups/seq_request/sas-1.html"
    _form_label = "sas_input_form"

    _allowed_extensions: list[tuple[str, str]] = [
        ("tsv", "Tab-separated"),
        ("csv", "Comma-separated")
    ]
    separator = SelectField(choices=_allowed_extensions, default="tsv")
    file = FileField(validators=[FileAllowed([ext for ext, _ in _allowed_extensions])])

    def __init__(self, formdata: Optional[dict] = None):
        super().__init__(formdata=formdata)
        self.upload_path = os.path.join("uploads", "seq_request")
        if not os.path.exists(self.upload_path):
            os.makedirs(self.upload_path)

    def validate(self) -> bool:
        if not super().validate():
            return False
        
        if self.file.data is None:
            self.file.errors = ("Please upload a file.",)
            return False
        
        try:
            self.df = self.__parse()

            feature_mapping = {
                "Sample Name": "sample_name",
                "Library Name": "library_name",
                "Organism": "organism",
                "Project": "project",
                "Library Type": "library_type",
                "Pool": "pool",
                "Index Kit": "index_kit",
                "Adapter": "adapter",
                "Index 1 (i7)": "index_1",
                "Index 2 (i5)": "index_2",
                "Index 3": "index_3",
                "Index 4": "index_4",
                "Library Volume [uL]": "library_volume",
                "Library DNA Concentration [nM]": "library_concentration",
                "Library Total Size [bp]": "library_total_size",
            }
            missing_cols = [col for col in feature_mapping.keys() if col not in self.df.columns]
            if len(missing_cols) > 0:
                self.file.errors = (str(f"Uploaded table is missing column(s): [{', '.join(missing_cols)}]"),)
                return False

            self.df = self.df.rename(columns=feature_mapping)
            self.df = self.df[feature_mapping.values()]

        except pd.errors.ParserError as e:
            self.file.errors = (str(e),)
            return False

        return True
    
    def __parse(self) -> pd.DataFrame:
        if self.separator.data == "tsv":
            sep = "\t"
        else:
            sep = ","

        filename = f"{Path(self.file.data.filename).stem}_{uuid4()}.{self.file.data.filename.split('.')[-1]}"
        filename = secure_filename(filename)
        self.file.data.save(os.path.join(self.upload_path, filename))

        df = pd.read_csv(os.path.join(self.upload_path, filename), sep=sep, index_col=False, header=0)
        
        return df
    
    def process_request(self, **context) -> Response:
        if not self.validate():
            return self.make_response(**context)
        
        user_id: int = context["user_id"]
        
        data = {"library_table": self.df}

        project_mapping_form = ProjectMappingForm()
        context = project_mapping_form.prepare(user_id, data) | context
                
        return project_mapping_form.make_response(**context)
        