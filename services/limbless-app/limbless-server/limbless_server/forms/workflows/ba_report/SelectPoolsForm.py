import pandas as pd
import json

from flask import Response
from wtforms import StringField

from limbless_db import models, DBSession

from .... import db, logger
from ...HTMXFlaskForm import HTMXFlaskForm
from .BAInputForm import BAInputForm


class SelectPoolsForm(HTMXFlaskForm):
    _template_path = "workflows/ba_report/bar-1.html"
    _form_label = "ba_report_form"

    selected_library_ids = StringField()
    selected_pool_ids = StringField()

    error_dummy = StringField()

    def validate(self) -> bool:
        validated = super().validate()

        selected_pool_ids = self.selected_pool_ids.data
        selected_library_ids = self.selected_library_ids.data
        
        if not selected_pool_ids and not selected_library_ids:
            self.error_dummy.errors = ["Select at least one pool or library"]
            return False

        if selected_pool_ids:
            pool_ids = json.loads(selected_pool_ids)
        else:
            pool_ids = []

        if selected_library_ids:
            library_ids = json.loads(selected_library_ids)
        else:
            library_ids = []
        
        if len(pool_ids) + len(library_ids) == 0:
            self.selected_pool_ids.errors = ["Select at least one pool or library"]
            return False
        
        self.pool_ids = []
        try:
            for library_id in pool_ids:
                self.pool_ids.append(int(library_id))
        except ValueError:
            self.selected_pool_ids.errors = ["Invalid library id"]
            return False
        
        self.library_ids = []
        try:
            for library_id in library_ids:
                self.library_ids.append(int(library_id))
        except ValueError:
            self.selected_library_ids.errors = ["Invalid library id"]
            return False
        
        self._context["selected_pools"] = self.pool_ids
        self._context["selected_libraries"] = self.library_ids
        return validated

    def process_request(self) -> Response:
        if not self.validate():
            return self.make_response()
        
        pool_data = dict(
            id=[],
            name=[],
            avg_fragment_size=[],
        )

        library_data = dict(
            id=[],
            name=[],
            avg_fragment_size=[],
        )

        with DBSession(db) as session:
            for pool_id in self.pool_ids:
                if (pool := session.get_pool(pool_id)) is None:
                    logger.error(f"Pool {pool_id} not found")
                    raise ValueError(f"Pool {pool_id} not found")
                
                pool_data["id"].append(pool.id)
                pool_data["name"].append(pool.name)
                pool_data["avg_fragment_size"].append(pool.avg_fragment_size)

            for library_id in self.library_ids:
                if (library := session.get_library(library_id)) is None:
                    logger.error(f"Library {library_id} not found")
                    raise ValueError(f"Library {library_id} not found")

                library_data["id"].append(library.id)
                library_data["name"].append(library.name)
                library_data["avg_fragment_size"].append(library.avg_fragment_size)

        ba_input_form = BAInputForm()
        ba_input_form.metadata = {
            "workflow": "ba_report",
        }
        
        ba_input_form.add_table("pool_table", pd.DataFrame(pool_data))
        ba_input_form.add_table("library_table", pd.DataFrame(library_data))

        ba_input_form.update_data()
        ba_input_form.prepare()
        return ba_input_form.make_response()