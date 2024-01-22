from typing import Optional
import pandas as pd

from flask_wtf import FlaskForm
from wtforms import StringField, FieldList, FormField, IntegerField
from wtforms.validators import DataRequired, Optional as OptionalValidator

from ... import db, models, logger, tools
from .TableDataForm import TableDataForm


class IndexKitSubForm(FlaskForm):
    raw_category = StringField("Raw Label", validators=[OptionalValidator()])
    category = IntegerField("Index Kit", validators=[DataRequired()])


class IndexKitMappingForm(TableDataForm):
    input_fields = FieldList(FormField(IndexKitSubForm), min_entries=1)

    def custom_validate(self) -> tuple[bool, "IndexKitMappingForm"]:
        validated = self.validate()
        if not validated:
            return False, self
        
        df = self.get_data()
        index_kits = df["index_kit"].unique().tolist()
        index_kits = [index_kit if index_kit and not pd.isna(index_kit) else "Index Kit" for index_kit in index_kits]
        
        for i, entry in enumerate(self.input_fields):
            raw_index_kit_label = index_kits[i]

            if (index_kit_id := entry.category.data) is None:
                entry.category.errors = ("Not valid index kit selected")
                return False, self
            
            if (selected_kit := db.db_handler.get_index_kit(index_kit_id)) is None:
                entry.category.errors = ("Not valid index kit selected")
                return False, self
            
            _df = df[df["index_kit"] == raw_index_kit_label]
            for _, row in _df.iterrows():
                adapter_name = str(row["adapter"])
                if (_ := db.db_handler.get_adapter_from_index_kit(adapter_name, selected_kit.id)) is None:
                    entry.category.errors = (f"Unknown adapter '{adapter_name}' does not belong to this index kit.",)
                    return False, self

        return validated, self
    
    def prepare(self, data: Optional[dict[str, pd.DataFrame]] = None) -> dict:
        if data is None:
            data = self.data

        index_kits = data["sample_table"]["index_kit"].unique().tolist()
        index_kits = [index_kit if index_kit and not pd.isna(index_kit) else "Index Kit" for index_kit in index_kits]

        selected: list[Optional[models.IndexKit]] = []

        for i, index_kit in enumerate(index_kits):
            if i > len(self.input_fields) - 1:
                self.input_fields.append_entry()

            entry = self.input_fields[i]
            entry.raw_category.data = index_kit

            if entry.category.data is None:
                selected_kit = next(iter(db.db_handler.query_index_kit(index_kit, 1)), None)
                entry.category.data = selected_kit.id if selected_kit else None
            else:
                selected_kit = db.db_handler.get_index_kit(entry.category.data)

            selected.append(selected_kit)

        self.update_data(data)

        return {
            "categories": index_kits,
            "selected": selected
        }
    
    def parse(self) -> dict[str, pd.DataFrame]:
        data = self.data

        df = data["sample_table"]

        df["index_kit_name"] = None
        df["index_kit_id"] = None

        index_kits = df["index_kit"].unique().tolist()
        index_kits = [index_kit if index_kit and not pd.isna(index_kit) else "Index Kit" for index_kit in index_kits]

        for i, index_kit in enumerate(index_kits):
            entry = self.input_fields[i]
            if (selected_id := entry.category.data) is not None:
                if (selected_kit := db.db_handler.get_index_kit(selected_id)) is None:
                    raise Exception(f"Index kit with id '{selected_id}' does not exist.")
                
                df.loc[df["index_kit"] == index_kit, "index_kit_id"] = selected_id
                df.loc[df["index_kit"] == index_kit, "index_kit_name"] = selected_kit.name

            else:
                raise Exception("Index Kit not selected.")
            
        df["index_1"] = None
        df["index_2"] = None
        df["index_3"] = None
        df["index_4"] = None

        for i, row in df.iterrows():
            index_kit_id = int(row["index_kit_id"])
            adapter_name = str(row["adapter"])
            adapter = db.db_handler.get_adapter_from_index_kit(adapter_name, index_kit_id)
            df.at[i, "index_1"] = adapter.barcode_1.sequence if adapter.barcode_1 else None
            df.at[i, "index_2"] = adapter.barcode_2.sequence if adapter.barcode_2 else None
            df.at[i, "index_3"] = adapter.barcode_3.sequence if adapter.barcode_3 else None
            df.at[i, "index_4"] = adapter.barcode_4.sequence if adapter.barcode_4 else None
            
        data["sample_table"] = df
        self.update_data(data)

        return data
            