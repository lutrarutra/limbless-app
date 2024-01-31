from typing import Optional
import pandas as pd

from flask_wtf import FlaskForm
from wtforms import StringField, FieldList, FormField, IntegerField
from wtforms.validators import DataRequired, Optional as OptionalValidator

from ... import db, models, logger, tools
from .TableDataForm import TableDataForm


class FeatureKitSubForm(FlaskForm):
    raw_category = StringField("Raw Label", validators=[OptionalValidator()])
    category = IntegerField("Index Kit", validators=[DataRequired()])


class FeatureKitMappingForm(TableDataForm):
    input_fields = FieldList(FormField(FeatureKitSubForm), min_entries=1)

    def custom_validate(self) -> tuple[bool, "FeatureKitMappingForm"]:
        validated = self.validate()
        if not validated:
            return False, self
        
        data = self.data
        for table_name in ["feature_table", "cmo_table"]:
            if table_name not in data.keys():
                continue
            df = data[table_name]
        
            kits = df["kit"].unique().tolist()
            kits = [feature_kit if feature_kit and not pd.isna(feature_kit) else None for feature_kit in kits]
            
            for i, entry in enumerate(self.input_fields):
                raw_feature_kit_label = kits[i]

                if (feature_kit_id := entry.category.data) is None:
                    entry.category.errors = ("Not valid feature kit selected")
                    return False, self
                
                if (selected_kit := db.db_handler.get_feature_kit(feature_kit_id)) is None:
                    entry.category.errors = ("Not valid feature kit selected")
                    return False, self
                
                _df = df[df["kit"] == raw_feature_kit_label]
                for _, row in _df.iterrows():
                    feature_name = str(row["feature_name"])
                    if (_ := db.db_handler.get_feature_from_kit_by_feature_name(feature_name, selected_kit.id)) is None:
                        entry.category.errors = (f"Unknown feature '{feature_name}' does not belong to this feature kit.",)
                        return False, self

        return validated, self
    
    def prepare(self, data: Optional[dict[str, pd.DataFrame]] = None) -> dict:
        if data is None:
            data = self.data

        kits = []
        selected: list[Optional[models.FeatureKit]] = []

        for table_name in ["feature_table", "cmo_table"]:
            if table_name not in data.keys():
                continue
            df = data[table_name]

            kits.extend([feature_kit if feature_kit and not pd.isna(feature_kit) else None for feature_kit in df["kit"].unique().tolist()])

            for i, feature_kit in enumerate(kits):
                if i > len(self.input_fields) - 1:
                    self.input_fields.append_entry()

                entry = self.input_fields[i]
                entry.raw_category.data = feature_kit

                if feature_kit is None:
                    selected_kit = None
                elif entry.category.data is None:
                    selected_kit = next(iter(db.db_handler.query_feature_kits(feature_kit, 1)), None)
                    entry.category.data = selected_kit.id if selected_kit else None
                else:
                    selected_kit = db.db_handler.get_feature_kit(entry.category.data)

                selected.append(selected_kit)

            data[table_name] = df

        self.update_data(data)

        return {
            "categories": kits,
            "selected": selected
        }
    
    def parse(self) -> dict[str, pd.DataFrame]:
        data = self.data

        for table_name in ["feature_table", "cmo_table"]:
            if table_name not in data.keys():
                continue
            
            df = data[table_name]
            df["feature_kit_name"] = None
            df["feature_kit_id"] = None

            kits = df["kit"].unique().tolist()
            kits = [feature_kit if feature_kit and not pd.isna(feature_kit) else None for feature_kit in kits]

            for i, feature_kit in enumerate(kits):
                entry = self.input_fields[i]
                if (selected_id := entry.category.data) is not None:
                    if (selected_kit := db.db_handler.get_feature_kit(selected_id)) is None:
                        raise Exception(f"Feature kit with id '{selected_id}' does not exist.")
                    
                    df.loc[df["kit"] == feature_kit, "feature_kit_id"] = selected_id
                    df.loc[df["kit"] == feature_kit, "feature_kit_name"] = selected_kit.name

                else:
                    raise Exception("Feature kit not selected.")

            df["feature_id"] = None
            for i, row in df.iterrows():
                feature_kit_id = int(row["feature_kit_id"])
                feature_name = str(row["feature_name"])
                feature = db.db_handler.get_feature_from_kit_by_feature_name(feature_name, feature_kit_id)

                df.at[i, "feature_id"] = feature.id
                
            data[table_name] = df

        self.update_data(data)

        return data
            