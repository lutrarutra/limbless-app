from typing import Optional
from flask import Response
import pandas as pd

from flask_wtf import FlaskForm
from wtforms import StringField, FieldList, FormField
from wtforms.validators import Optional as OptionalValidator

from ... import db
from ..TableDataForm import TableDataForm

from ..HTMXFlaskForm import HTMXFlaskForm

from .PoolMappingForm import PoolMappingForm
from .BarcodeCheckForm import BarcodeCheckForm
from ..SearchBar import SearchBar


class FeatureKitSubForm(FlaskForm):
    raw_label = StringField("Raw Label", validators=[OptionalValidator()])
    feature_kit = FormField(SearchBar, label="Select Feature Kit")


class FeatureKitMappingForm(HTMXFlaskForm, TableDataForm):
    _template_path = "components/popups/seq_request/sas-7.html"

    input_fields = FieldList(FormField(FeatureKitSubForm), min_entries=1)

    def __init__(self, formdata: dict = {}, uuid: Optional[str] = None):
        if uuid is None:
            uuid = formdata.get("file_uuid")
        HTMXFlaskForm.__init__(self, formdata=formdata)
        TableDataForm.__init__(self, uuid=uuid)

    def validate(self) -> bool:
        validated = super().validate()
        if not validated:
            return False
        
        data = self.get_data()
        for table_name in ["feature_table", "cmo_table"]:
            if table_name not in data.keys():
                continue
            df = data[table_name]
        
            kits = df["kit"].unique().tolist()
            kits = [feature_kit if feature_kit and not pd.isna(feature_kit) else None for feature_kit in kits]
            
            for i, entry in enumerate(self.input_fields):
                raw_feature_kit_label = kits[i]

                if (feature_kit_id := entry.feature_kit.selected.data) is None:
                    entry.feature_kit.selected.errors = ("Not valid feature kit selected")
                    return False
                
                if (selected_kit := db.get_feature_kit(feature_kit_id)) is None:
                    entry.feature_kit.selected.errors = ("Not valid feature kit selected")
                    return False
                
                _df = df[df["kit"] == raw_feature_kit_label]
                for _, row in _df.iterrows():
                    feature_name = str(row["feature_name"])
                    if (_ := db.get_feature_from_kit_by_feature_name(feature_name, selected_kit.id)) is None:
                        entry.feature_kit.selected.errors = (f"Unknown feature '{feature_name}' does not belong to this feature kit.",)
                        return False

        return validated
    
    def prepare(self, data: Optional[dict[str, pd.DataFrame]] = None) -> dict:
        if data is None:
            data = self.get_data()

        kits = []

        for table_name in ["feature_table", "cmo_table"]:
            if table_name not in data.keys():
                continue
            df = data[table_name]

            kits.extend([feature_kit if feature_kit and not pd.isna(feature_kit) else None for feature_kit in df["kit"].unique().tolist()])

            for i, raw_feature_kit_label in enumerate(kits):
                if i > len(self.input_fields) - 1:
                    self.input_fields.append_entry()

                entry = self.input_fields[i]
                entry.raw_label.data = raw_feature_kit_label

                if raw_feature_kit_label is None:
                    selected_kit = None
                elif entry.feature_kit.selected.data is None:
                    selected_kit = next(iter(db.query_feature_kits(raw_feature_kit_label, 1)), None)
                    entry.feature_kit.selected.data = selected_kit.id if selected_kit else None
                    entry.feature_kit.search_bar.data = selected_kit.search_name() if selected_kit else None
                else:
                    selected_kit = db.get_feature_kit(entry.feature_kit.selected.data)
                    entry.feature_kit.search_bar.data = selected_kit.search_name() if selected_kit else None

            data[table_name] = df

        self.update_data(data)

        return {}
    
    def __parse(self) -> dict[str, pd.DataFrame]:
        data = self.get_data()

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
                if (selected_id := entry.feature_kit.selected.data) is not None:
                    if (selected_kit := db.get_feature_kit(selected_id)) is None:
                        raise Exception(f"Feature kit with id '{selected_id}' does not exist.")
                    
                    df.loc[df["kit"] == feature_kit, "feature_kit_id"] = selected_id
                    df.loc[df["kit"] == feature_kit, "feature_kit_name"] = selected_kit.name

                else:
                    raise Exception("Feature kit not selected.")

            df["feature_id"] = None
            for i, row in df.iterrows():
                feature_kit_id = int(row["feature_kit_id"])
                feature_name = str(row["feature_name"])
                feature = db.get_feature_from_kit_by_feature_name(feature_name, feature_kit_id)

                df.at[i, "feature_id"] = feature.id
                
            data[table_name] = df

        self.update_data(data)

        return data
            
    def process_request(self, **context) -> Response:
        validated = self.validate()
        if not validated:
            return self.make_response(**context)

        data = self.__parse()

        if "pool" in data["library_table"].columns:
            pool_mapping_form = PoolMappingForm(uuid=self.uuid)
            context = pool_mapping_form.prepare(data) | context
            return pool_mapping_form.make_response(**context)

        barcode_check_form = BarcodeCheckForm(uuid=self.uuid)
        context = barcode_check_form.prepare(data)
        return barcode_check_form.make_response(**context)