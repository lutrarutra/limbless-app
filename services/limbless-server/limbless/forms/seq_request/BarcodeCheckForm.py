from typing import Optional
import pandas as pd

from wtforms import TextAreaField, BooleanField
from wtforms.validators import DataRequired, Optional as OptionalValidator

from ... import db, models, logger
from .TableDataForm import TableDataForm


# 7. Check barcodes
class BarcodeCheckForm(TableDataForm):
    reverse_complement_index_1 = BooleanField("Reverse complement index 1", default=False)
    reverse_complement_index_2 = BooleanField("Reverse complement index 2", default=False)
    reverse_complement_index_3 = BooleanField("Reverse complement index 3", default=False)
    reverse_complement_index_4 = BooleanField("Reverse complement index 4", default=False)
    
    def prepare(self, df: Optional[pd.DataFrame] = None) -> dict:
        if df is None:
            df = self.get_df()

        samples_data: list[dict[str, str | int | None]] = []
        
        reused_barcodes = (df[["index_1", "index_2", "index_3", "index_4"]].duplicated(keep=False)) & (~df[["index_1", "index_2", "index_3", "index_4"]].isna().all(axis=1))

        for i, row in df.iterrows():
            # Check if sample names are unique in project
            data = {
                "id": row["id"],
                "name": row["sample_name"] if "sample_name" in row else row["library_name"],
                "library_type": row["library_type"],
                "error": None,
                "warning": "",
                "info": "",
                "index_1": row["index_1"],
                "index_2": row["index_2"],
                "index_3": row["index_3"],
                "index_4": row["index_4"],
                "adapter": row["adapter"],
            }

            if data["index_1"] == data["index_2"]:
                data["warning"] += "Index 1 and index 2 are the same. "

            if data["index_1"] == data["index_3"]:
                data["warning"] += "Index 1 and index 3 are the same. "

            if data["index_1"] == data["index_4"]:
                data["warning"] += "Index 1 and index 4 are the same. "

            if data["index_2"] == data["index_3"]:
                data["warning"] += "Index 2 and index 3 are the same. "

            if data["index_2"] == data["index_4"]:
                data["warning"] += "Index 2 and index 4 are the same. "

            if data["index_3"] == data["index_4"]:
                data["warning"] += "Index 3 and index 4 are the same. "

            if reused_barcodes[i]:
                data["warning"] += "Index combination is reused in two or more libraries. "

            samples_data.append(data)

        self.set_df(df)

        return {
            "samples_data": samples_data,
            "show_index_1": df["index_1"].notnull().any(),
            "show_index_2": df["index_2"].notnull().any(),
            "show_index_3": df["index_3"].notnull().any(),
            "show_index_4": df["index_4"].notnull().any(),
        }
    
    def parse(self) -> pd.DataFrame:
        df = self.get_df()
            
        return df
        
    def custom_validate(self):
        validated = self.validate()
        if not validated:
            return False, self

        return validated, self