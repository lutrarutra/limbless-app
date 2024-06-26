import os
import shutil
from typing import Optional

import pandas as pd

from flask import Response, url_for, flash, current_app
from flask_htmx import make_response

from limbless_db import models, DBSession
from limbless_db.categories import FileType, SampleStatus

from .... import logger, db, tools
from ...TableDataForm import TableDataForm
from ...HTMXFlaskForm import HTMXFlaskForm


class CompleteLibraryIndexingForm(HTMXFlaskForm, TableDataForm):
    _template_path = "workflows/pool_indexing/indexing-3.html"
    _form_label = "pool_indexing_form"

    def __init__(self, previous_form: Optional[TableDataForm] = None, formdata: dict = {}, uuid: Optional[str] = None):
        if uuid is None:
            uuid = formdata.get("file_uuid")
        HTMXFlaskForm.__init__(self, formdata=formdata)
        TableDataForm.__init__(self, dirname="pool_indexing", uuid=uuid, previous_form=previous_form)

    def prepare(self):
        barcode_table = self.tables["barcode_table"]
        barcode_table = tools.check_indices(barcode_table)

        barcode_table["library_type"] = None
        barcode_table["genome_ref"] = None

        with DBSession(db) as session:
            for idx, row in barcode_table.iterrows():
                if (library := session.get_library(row["library_id"])) is None:
                    logger.error(f"{self.uuid}: Library {row['library_id']} not found")
                    raise ValueError(f"Library {row['library_id']} not found")
                
                barcode_table.at[idx, "library_type"] = library.type.name
                barcode_table.at[idx, "genome_ref"] = library.genome_ref.display_name if library.genome_ref is not None else None

        self._context["barcode_table"] = barcode_table
        self._context["show_index_1"] = barcode_table["index_1"].notna().any()
        self._context["show_index_2"] = barcode_table["index_2"].notna().any()
        self._context["show_index_3"] = barcode_table["index_3"].notna().any()
        self._context["show_index_4"] = barcode_table["index_4"].notna().any()
        self._context["show_adapter"] = barcode_table["adapter"].notna().any()

    def validate(self) -> bool:
        validated = super().validate()
        return validated

    def process_request(self, user: models.User) -> Response:
        if not self.validate():
            return self.make_response()

        barcode_table = self.tables["barcode_table"]

        if (pool_id := self.metadata.get("pool_id")) is None:
            logger.error(f"{self.uuid}: Pool id not found")
            raise ValueError(f"{self.uuid}: Pool id not found")
        
        if (pool := db.get_pool(pool_id)) is None:
            logger.error(f"{self.uuid}: Pool {pool_id} not found")
            raise ValueError(f"{self.uuid}: Pool {pool_id} not found")
        
        with DBSession(db) as session:
            for _, row in barcode_table.iterrows():
                if (library := session.get_library(row["library_id"])) is None:
                    logger.error(f"{self.uuid}: Library {row['library_id']} not found")
                    raise ValueError(f"{self.uuid}: Library {row['library_id']} not found")
                
                library.index_1_sequence = row["index_1"] if pd.notna(row["index_1"]) else None
                library.index_2_sequence = row["index_2"] if pd.notna(row["index_2"]) else None
                library.index_3_sequence = row["index_3"] if pd.notna(row["index_3"]) else None
                library.index_4_sequence = row["index_4"] if pd.notna(row["index_4"]) else None
                library.adapter = row["adapter"] if pd.notna(row["adapter"]) else None
                for sample_link in library.sample_links:
                    sample_is_prepped = True
                    for library_link in sample_link.sample.library_links:
                        if library_link.library != library and not library_link.library.is_indexed():
                            sample_is_prepped = False
                            break
                    if sample_is_prepped:
                        sample_link.sample.status_id = SampleStatus.PREPARED.id
                library = db.update_library(library)

        flash("Libraries pooled!", "success")
        logger.info(f"{self.uuid}: Libraries pooled")

        newdir = os.path.join(current_app.config["MEDIA_FOLDER"], FileType.POOL_INDEXING_TABLE.dir, str(pool.id))
        os.makedirs(newdir, exist_ok=True)
        shutil.copy(self.path, os.path.join(newdir, f"{self.uuid}.csv"))
        os.remove(self.path)

        if (seq_request_id := self.metadata.get("seq_request_id")) is not None:
            return make_response(redirect=url_for("seq_requests_page.seq_request_page", seq_request_id=seq_request_id))

        return make_response(redirect=url_for("pools_page.pool_page", pool_id=pool.id))