from typing import Optional

import pandas as pd

from flask import Response, flash, url_for
from flask_wtf import FlaskForm
from flask_htmx import make_response
from wtforms import FloatField, IntegerField, FieldList, FormField
from wtforms.validators import NumberRange, DataRequired

from opengsync_db.categories import PoolStatus, LibraryStatus

from .... import db, logger
from ...MultiStepForm import MultiStepForm


class SubForm(FlaskForm):
    obj_id = IntegerField(validators=[DataRequired()])
    qubit_concentration = FloatField(validators=[DataRequired(), NumberRange(min=0)])


class CompleteQubitMeasureForm(MultiStepForm):
    _template_path = "workflows/qubit_measure/qubit-1.html"
    _workflow_name = "qubit_measure"
    _step_name = "complete_qubit_measure"

    sample_fields = FieldList(FormField(SubForm), min_entries=0)
    library_fields = FieldList(FormField(SubForm), min_entries=0)
    pool_fields = FieldList(FormField(SubForm), min_entries=0)
    lane_fields = FieldList(FormField(SubForm), min_entries=0)

    def __init__(self, uuid: str | None, formdata: dict = {}):
        MultiStepForm.__init__(
            self, workflow=CompleteQubitMeasureForm._workflow_name,
            step_name=CompleteQubitMeasureForm._step_name, uuid=uuid,
            formdata=formdata, step_args={}
        )
        self._context["enumerate"] = enumerate
        
    def prepare(self):
        sample_table = self.tables["sample_table"]
        pool_table = self.tables["pool_table"]
        library_table = self.tables["library_table"]
        lane_table = self.tables["lane_table"]

        for i, (idx, row) in enumerate(sample_table.iterrows()):
            if i > len(self.sample_fields) - 1:
                self.sample_fields.append_entry()

            self.sample_fields[i].obj_id.data = row["id"]

            if pd.notna(sample_table.at[idx, "qubit_concentration"]):
                self.sample_fields[i].qubit_concentration.data = sample_table.at[idx, "qubit_concentration"]

        for i, (idx, row) in enumerate(library_table.iterrows()):
            if i > len(self.library_fields) - 1:
                self.library_fields.append_entry()

            self.library_fields[i].obj_id.data = row["id"]

            if pd.notna(library_table.at[idx, "qubit_concentration"]):
                self.library_fields[i].qubit_concentration.data = library_table.at[idx, "qubit_concentration"]

        for i, (idx, row) in enumerate(pool_table.iterrows()):
            if i > len(self.pool_fields) - 1:
                self.pool_fields.append_entry()

            self.pool_fields[i].obj_id.data = int(row["id"])

            if pd.notna(pool_table.at[idx, "qubit_concentration"]):
                self.pool_fields[i].qubit_concentration.data = pool_table.at[idx, "qubit_concentration"]

        for i, (idx, row) in enumerate(lane_table.iterrows()):
            if i > len(self.lane_fields) - 1:
                self.lane_fields.append_entry()

            self.lane_fields[i].obj_id.data = row["id"]

            if pd.notna(lane_table.at[idx, "qubit_concentration"]):
                self.lane_fields[i].qubit_concentration.data = lane_table.at[idx, "qubit_concentration"]

        self._context["sample_table"] = sample_table
        self._context["library_table"] = library_table
        self._context["pool_table"] = pool_table
        self._context["lane_table"] = lane_table
    
    def process_request(self) -> Response:
        if not self.validate():
            return self.make_response(
                pool_table=self.tables["pool_table"],
                library_table=self.tables["library_table"],
                lane_table=self.tables["lane_table"]
            )
        
        library_table = self.tables["library_table"]
        pool_table = self.tables["pool_table"]
        lane_table = self.tables["lane_table"]
        metadata = self.metadata.copy()

        for sub_form in self.library_fields:
            if (library := db.get_library(sub_form.obj_id.data)) is None:
                logger.error(f"{self.uuid}: Library {sub_form.obj_id.data} not found")
                raise ValueError(f"{self.uuid}: Library {sub_form.obj_id.data} not found")
            
            library.qubit_concentration = sub_form.qubit_concentration.data
            library = db.update_library(library)

            library_table.loc[library_table["id"] == library.id, "qubit_concentration"] = library.qubit_concentration

        for sub_form in self.pool_fields:
            if (pool := db.get_pool(sub_form.obj_id.data)) is None:
                logger.error(f"{self.uuid}: Pool {sub_form.obj_id.data} not found")
                raise ValueError(f"{self.uuid}: Pool {sub_form.obj_id.data} not found")
            
            pool.qubit_concentration = sub_form.qubit_concentration.data

            if pool.qubit_concentration is not None:
                for library in pool.libraries:
                    if library.is_pooled():
                        library.status = LibraryStatus.POOLED

            if pool.status == PoolStatus.ACCEPTED:
                pool.status = PoolStatus.STORED

            pool = db.update_pool(pool)

            pool_table.loc[pool_table["id"] == pool.id, "qubit_concentration"] = pool.qubit_concentration

        for sub_form in self.lane_fields:
            if (lane := db.get_lane(sub_form.obj_id.data)) is None:
                logger.error(f"{self.uuid}: Lane {sub_form.obj_id.data} not found")
                raise ValueError(f"{self.uuid}: Lane {sub_form.obj_id.data} not found")
            
            lane.original_qubit_concentration = sub_form.qubit_concentration.data
            lane = db.update_lane(lane)

            lane_table.loc[lane_table["id"] == lane.id, "qubit_concentration"] = lane.original_qubit_concentration

        self.complete()
        flash("Qubit Measurements saved!", "success")
        if (experiment_id := metadata.get("experiment_id")) is not None:
            return make_response(redirect=url_for("experiments_page.experiment", experiment_id=experiment_id))
        
        return make_response(redirect=url_for("dashboard"))