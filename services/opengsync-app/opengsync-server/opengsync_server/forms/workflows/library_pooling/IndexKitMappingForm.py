from typing import Optional
from flask import Response

import pandas as pd

from flask_wtf import FlaskForm
from wtforms import StringField, FieldList, FormField
from wtforms.validators import Optional as OptionalValidator

from opengsync_db import models
from opengsync_db.categories import BarcodeType, KitType
from opengsync_server.forms.MultiStepForm import StepFile

from .... import db, logger
from ...MultiStepForm import MultiStepForm
from ...SearchBar import SearchBar
from .CompleteLibraryPoolingForm import CompleteLibraryPoolingForm


class IndexKitSubForm(FlaskForm):
    raw_label = StringField("Raw Label", validators=[OptionalValidator()])
    index_kit = FormField(SearchBar, label="Select Index Kit")


class IndexKitMappingForm(MultiStepForm):
    _template_path = "workflows/library_pooling/index_kit-mapping.html"
    _workflow_name = "library_pooling"
    _step_name = "index_kit_mapping"

    input_fields = FieldList(FormField(IndexKitSubForm), min_entries=1)

    @staticmethod
    def is_applicable(current_step: MultiStepForm) -> bool:
        return current_step.tables["library_table"]["kit_i7"].notna().any()
        
    def __init__(self, lab_prep: models.LabPrep, uuid: str | None, previous_form: Optional[MultiStepForm] = None, formdata: dict = {}):
        MultiStepForm.__init__(
            self, workflow=IndexKitMappingForm._workflow_name,
            step_name=IndexKitMappingForm._step_name, uuid=uuid,
            formdata=formdata, previous_form=previous_form, step_args={}
        )
        self.lab_prep = lab_prep
        self._context["lab_prep"] = lab_prep

    def prepare(self):
        library_table = self.tables["library_table"]

        index_kits = list(set(library_table["kit_i7"].unique().tolist() + library_table["kit_i5"].unique().tolist()))
        index_kits = [kit for kit in index_kits if pd.notna(kit)]

        for i, index_kit in enumerate(index_kits):
            if i > len(self.input_fields) - 1:
                self.input_fields.append_entry()

            entry = self.input_fields[i]
            index_kit_search_field: SearchBar = entry.index_kit  # type: ignore
            entry.raw_label.data = index_kit

            if index_kit is None:
                selected_kit = None
            elif index_kit_search_field.selected.data is None:
                selected_kit = next(iter(db.query_kits(str(index_kit), limit=1, kit_type=KitType.INDEX_KIT)), None)
                index_kit_search_field.selected.data = selected_kit.id if selected_kit else None
                index_kit_search_field.search_bar.data = selected_kit.search_name() if selected_kit else None
            else:
                selected_kit = db.get_index_kit(index_kit_search_field.selected.data)
                index_kit_search_field.search_bar.data = selected_kit.search_name() if selected_kit else None

    def fill_previous_form(self, previous_form: StepFile):
        library_table = previous_form.tables["library_table"]

        kits = set()

        counter = 0
        for (label, kit_id), _ in library_table.groupby(["kit_i7", "kit_i7_id"]):
            if label in kits:
                continue
            kits.add(label)
            if counter > len(self.input_fields) - 1:
                self.input_fields.append_entry()

            entry: IndexKitSubForm = self.input_fields[counter]  # type: ignore
            entry.raw_label.data = label
            entry.index_kit.selected.data = kit_id
            entry.index_kit.search_bar.data = label
            counter += 1

        for (label, kit_id), _ in library_table.groupby(["kit_i5", "kit_i5_id"]):
            if label in kits:
                continue
            kits.add(label)
            if counter > len(self.input_fields) - 1:
                self.input_fields.append_entry()

            entry: IndexKitSubForm = self.input_fields[counter]  # type: ignore
            entry.raw_label.data = label
            entry.index_kit.selected.data = kit_id
            entry.index_kit.search_bar.data = label
            counter += 1

    def validate(self) -> bool:
        if not super().validate():
            return False
        
        library_table = self.tables["library_table"]
        library_table.loc[library_table["kit_i7"].notna(), "kit_i7"] = library_table.loc[library_table["kit_i7"].notna(), "kit_i7"].astype(str)
        library_table.loc[library_table["kit_i5"].notna(), "kit_i5"] = library_table.loc[library_table["kit_i5"].notna(), "kit_i5"].astype(str)
        library_table.loc[library_table["kit_i7_name"].notna(), "kit_i7_name"] = library_table.loc[library_table["kit_i7_name"].notna(), "kit_i7_name"].astype(str)
        library_table.loc[library_table["kit_i5_name"].notna(), "kit_i5_name"] = library_table.loc[library_table["kit_i5_name"].notna(), "kit_i5_name"].astype(str)

        kits: dict[int, tuple[models.IndexKit, pd.DataFrame]] = {}

        for i, entry in enumerate(self.input_fields):
            index_kit_search_field: SearchBar = entry.index_kit  # type: ignore
            if (kit_id := index_kit_search_field.selected.data) is None:
                logger.error(f"Index kit not found for {entry.raw_label.data}")
                raise ValueError()
            
            if (kit := db.get_index_kit(kit_id)) is None:
                index_kit_search_field.selected.errors = (f"Index kit {kit_id} not found",)
                return False

            if len(kit_df := db.get_index_kit_barcodes_df(kit_id, per_adapter=False)) == 0:
                logger.error(f"Index kit {kit_id} does not exist")
                raise ValueError()
            
            kits[kit_id] = (kit, kit_df)
            library_table.loc[library_table["kit_i7"] == entry.raw_label.data, "kit_i7_id"] = kit_id
            library_table.loc[library_table["kit_i5"] == entry.raw_label.data, "kit_i5_id"] = kit_id
            library_table.loc[library_table["kit_i7_id"] == kit_id, "kit_i7_name"] = kit.identifier
            library_table.loc[library_table["kit_i5_id"] == kit_id, "kit_i5_name"] = kit.identifier

            for _, row in library_table[library_table["kit_i7_id"] == kit_id].iterrows():
                if pd.notna(row["name_i7"]):
                    if row["name_i7"] not in kit_df["name"].values:
                        index_kit_search_field.selected.errors = (f"Index {row['name_i7']} not found in index kit {kit_id}",)
                        return False
                
                elif pd.notna(row["index_well"]):
                    if row["index_well"] not in kit_df["well"].values:
                        index_kit_search_field.selected.errors = (f"Well {row['index_well']} not found in index kit {kit_id}",)
                        return False
                    
            for _, row in library_table[library_table["kit_i5_id"] == kit_id].iterrows():
                if pd.notna(row["name_i5"]):
                    if row["name_i5"] not in kit_df["name"].values:
                        index_kit_search_field.selected.errors = (f"Index {row['name_i5']} not found in index kit {kit_id}",)
                        return False
                
                elif pd.notna(row["index_well"]):
                    if row["index_well"] not in kit_df["well"].values:
                        index_kit_search_field.selected.errors = (f"Well {row['index_well']} not found in index kit {kit_id}",)
                        return False

        index_kits = list(set(library_table["kit_i7_id"].unique().tolist() + library_table["kit_i5_id"].unique().tolist()))
        index_kits = [kit for kit in index_kits if pd.notna(kit)]

        barcode_table_data = {
            "library_id": [],
            "library_name": [],
            "pool": [],
            "sequence_i7": [],
            "sequence_i5": [],
            "kit_i7": [],
            "kit_i5": [],
            "name_i7": [],
            "name_i5": [],
        }

        library_table["kit_defined"] = library_table["kit_i7"].notna() | library_table["kit_i5"].notna()

        for idx, row in library_table[library_table["kit_defined"]].iterrows():
            kit_i7, kit_i7_df = kits[row["kit_i7_id"]]
            kit_i5, kit_i5_df = kits[row["kit_i5_id"]]

            i7_seqs = kit_i7_df.loc[kit_i7_df["type_id"] == BarcodeType.INDEX_I7.id]
            i5_seqs = kit_i5_df.loc[kit_i5_df["type_id"] == BarcodeType.INDEX_I5.id]

            if pd.notna(row["name_i7"]):
                barcodes_i7 = i7_seqs[i7_seqs["name"] == row["name_i7"]]["sequence"].values
                names_i7 = i7_seqs[i7_seqs["name"] == row["name_i7"]]["name"].values
            elif pd.notna(row["index_well"]):
                barcodes_i7 = i7_seqs[i7_seqs["well"] == row["index_well"]]["sequence"].values
                names_i7 = i7_seqs[i7_seqs["well"] == row["index_well"]]["name"].values
            else:
                raise ValueError()
            
            if pd.notna(row["name_i5"]):
                barcodes_i5 = i5_seqs[i5_seqs["name"] == row["name_i5"]]["sequence"].values
                names_i5 = i5_seqs[i5_seqs["name"] == row["name_i5"]]["name"].values
            elif pd.notna(row["index_well"]):
                barcodes_i5 = i5_seqs[i5_seqs["well"] == row["index_well"]]["sequence"].values
                names_i5 = i5_seqs[i5_seqs["well"] == row["index_well"]]["name"].values
            else:
                raise ValueError()
            
            for i in range(max(len(barcodes_i7), len(barcodes_i5))):
                barcode_table_data["library_id"].append(row["library_id"])
                barcode_table_data["library_name"].append(row["library_name"])
                barcode_table_data["pool"].append(row["pool"])
                barcode_table_data["sequence_i7"].append(barcodes_i7[i] if len(barcodes_i7) > i else None)
                barcode_table_data["sequence_i5"].append(barcodes_i5[i] if len(barcodes_i5) > i else None)
                barcode_table_data["kit_i7"].append(row["kit_i7_name"])
                barcode_table_data["kit_i5"].append(row["kit_i5_name"])
                barcode_table_data["name_i7"].append(names_i7[i] if len(names_i7) > i else None)
                barcode_table_data["name_i5"].append(names_i5[i] if len(names_i5) > i else None)

        for idx, row in library_table[~library_table["kit_defined"]].iterrows():
            seq_i7s = row["sequence_i7"].split(";") if pd.notna(row["sequence_i7"]) else []
            seq_i5s = row["sequence_i5"].split(";") if pd.notna(row["sequence_i5"]) else []

            for i in range(max(len(seq_i7s), len(seq_i5s))):
                barcode_table_data["library_id"].append(row["library_id"])
                barcode_table_data["library_name"].append(row["library_name"])
                barcode_table_data["pool"].append(row["pool"])
                barcode_table_data["sequence_i7"].append(seq_i7s[i] if len(seq_i7s) > i else None)
                barcode_table_data["sequence_i5"].append(seq_i5s[i] if len(seq_i5s) > i else None)
                barcode_table_data["name_i7"].append(row["name_i7"])
                barcode_table_data["name_i5"].append(row["name_i5"])
                barcode_table_data["kit_i7"].append(None)
                barcode_table_data["kit_i5"].append(None)

        self.barcode_table = pd.DataFrame(barcode_table_data)

        library_table["kit_i7"] = library_table["kit_i7_name"]
        library_table["kit_i5"] = library_table["kit_i5_name"]
        self.update_table("library_table", library_table)
 
        return True
        
    def process_request(self) -> Response:
        if not self.validate():
            return self.make_response()

        self.add_table("barcode_table", self.barcode_table)
        self.update_data()

        complete_pool_indexing_form = CompleteLibraryPoolingForm(lab_prep=self.lab_prep, previous_form=self, uuid=self.uuid)
        complete_pool_indexing_form.prepare()
        return complete_pool_indexing_form.make_response()