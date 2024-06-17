import os
import shutil
from typing import Optional

import pandas as pd
import numpy as np

from flask import Response, url_for, flash, current_app
from flask_htmx import make_response

from limbless_db import models, DBSession
from limbless_db.categories import GenomeRef, LibraryType, FeatureType, FileType

from .... import db, logger
from ...TableDataForm import TableDataForm
from ...HTMXFlaskForm import HTMXFlaskForm


class CompleteSASForm(HTMXFlaskForm, TableDataForm):
    _template_path = "workflows/library_annotation/sas-complete.html"
    _form_label = "complete_sas_form"

    def __init__(self, previous_form: Optional[TableDataForm] = None, formdata: dict = {}, uuid: Optional[str] = None, seq_request: Optional[models.SeqRequest] = None):
        if uuid is None:
            uuid = formdata.get("file_uuid")
        HTMXFlaskForm.__init__(self, formdata=formdata)
        TableDataForm.__init__(self, dirname="library_annotation", uuid=uuid, previous_form=previous_form)
        
        if seq_request is not None:
            self.seq_request = seq_request
            self._context["seq_request"] = seq_request
        else:
            if (seq_request_id := self.metadata.get("seq_request_id")) is not None:
                if (seq_request := db.get_seq_request(seq_request_id)) is None:
                    logger.error(f"{self.uuid}: SeqRequest with id {seq_request_id} not found.")
                    raise ValueError(f"SeqRequest with id {seq_request_id} not found.")
                
                self._context["seq_request"] = seq_request
                self.seq_request = seq_request

    def prepare(self):
        library_table = self.tables["library_table"]
        pool_table = self.tables.get("pool_table")
        feature_table = self.tables.get("feature_table")
        cmo_table = self.tables.get("cmo_table")
        visium_table = self.tables.get("visium_table")
        flex_table = self.tables.get("flex_table")
        comment_table = self.tables.get("comment_table")

        sample_table = self.get_sample_table(library_table, cmo_table, flex_table)
        self.add_table("sample_table", sample_table)
        self.update_data()

        self._context["library_table"] = library_table
        self._context["pool_table"] = pool_table
        self._context["feature_table"] = feature_table
        self._context["cmo_table"] = cmo_table
        self._context["visium_table"] = visium_table
        self._context["flex_table"] = flex_table
        self._context["comment_table"] = comment_table
        self._context["sample_table"] = sample_table

        input_type = "raw" if "pool" not in library_table.columns else "pooled"

        LINK_WIDTH_UNIT = 1
        nodes = []
        links = []

        project_node = {
            "node": 0,
            "name": self.metadata["project_name"],
        }
        nodes.append(project_node)
        node_idx = 1
        pool_nodes = {}

        for sample_name, _df in library_table.groupby("sample_name"):
            sample_pool = []
            for _, row in sample_table[sample_table["sample_pool"] == sample_name].iterrows():
                sample_node = {
                    "node": node_idx,
                    "name": row["sample_name"],
                }
                sample_pool.append(sample_node)
                nodes.append(sample_node)
                node_idx += 1

                links.append({
                    "source": project_node["node"],
                    "target": sample_node["node"],
                    "value": LINK_WIDTH_UNIT * len(library_table[library_table["sample_name"] == sample_name]),
                })

            for _, row in _df.iterrows():
                library_node = {
                    "node": node_idx,
                    "name": f"{LibraryType.get(row['library_type_id']).abbreviation} - {row['library_name']}",
                }
                nodes.append(library_node)
                node_idx += 1
                for sample_node in sample_pool:
                    links.append({
                        "source": sample_node["node"],
                        "target": library_node["node"],
                        "value": LINK_WIDTH_UNIT,
                    })
                if input_type == "raw":
                    continue
                
                if (pool_node := pool_nodes.get(row["pool"])) is None:
                    pool_node = {
                        "node": node_idx,
                        "name": row["pool"],
                    }
                    nodes.append(pool_node)
                    node_idx += 1
                    pool_nodes[row["pool"]] = pool_node

                links.append({
                    "source": library_node["node"],
                    "target": pool_node["node"],
                    "value": LINK_WIDTH_UNIT * len(sample_pool),
                })

        self._context["nodes"] = nodes
        self._context["links"] = links

    def get_sample_table(
        self, library_table: pd.DataFrame,
        cmo_table: Optional[pd.DataFrame], flex_table: Optional[pd.DataFrame]
    ) -> pd.DataFrame:
        sample_data = {
            "sample_name": [],
            "sample_pool": [],
            "library_types": [],
            "is_cmo_sample": [],
            "is_flex_sample": [],
            "cmo_sequence": [],
            "cmo_pattern": [],
            "cmo_read": [],
            "flex_barcode": [],
        }

        def add_sample(
            sample_name: str,
            sample_pool: str,
            is_cmo_sample: bool,
            is_flex_sample: bool,
            library_types: list[str],
            cmo_sequence: Optional[str] = None,
            cmo_pattern: Optional[str] = None,
            cmo_read: Optional[str] = None,
            flex_barcode: Optional[str] = None
        ):
            sample_data["sample_name"].append(sample_name)
            sample_data["sample_pool"].append(sample_pool)
            sample_data["library_types"].append(library_types)
            sample_data["is_cmo_sample"].append(is_cmo_sample)
            sample_data["is_flex_sample"].append(is_flex_sample)
            sample_data["cmo_sequence"].append(cmo_sequence)
            sample_data["cmo_pattern"].append(cmo_pattern)
            sample_data["cmo_read"].append(cmo_read)
            sample_data["flex_barcode"].append(flex_barcode)

        for (sample_name, is_cmo_sample, is_flex_sample), _df in library_table.groupby(["sample_name", "is_cmo_sample", "is_flex_sample"], dropna=False):
            library_types = [LibraryType.get(library_type_id).abbreviation for library_type_id in _df["library_type_id"].unique()]
            if is_cmo_sample:
                if cmo_table is None:
                    logger.error(f"{self.uuid}: CMO reference table not found.")
                    raise Exception("CMO reference should not be None.")
                
                for _, cmo_row in cmo_table[cmo_table["sample_name"] == sample_name].iterrows():
                    add_sample(
                        sample_name=cmo_row["demux_name"],
                        sample_pool=sample_name,
                        library_types=library_types,
                        is_cmo_sample=True,
                        is_flex_sample=False,
                        cmo_sequence=cmo_row["sequence"],
                        cmo_pattern=cmo_row["pattern"],
                        cmo_read=cmo_row["read"],
                    )
            elif is_flex_sample:
                if flex_table is None:
                    logger.error(f"{self.uuid}: flex reference table not found.")
                    raise Exception("flex reference should not be None.")
                
                for (sample_name, library_name, barcode_id), _ in flex_table.groupby(["sample_name", "library_name", "barcode_id"], dropna=False):
                    sample_pool = library_table[library_table["library_name"] == library_name].iloc[0]["sample_name"]
                    add_sample(
                        sample_name=sample_name,
                        sample_pool=sample_pool,
                        is_flex_sample=True,
                        is_cmo_sample=False,
                        library_types=library_types,
                        flex_barcode=barcode_id
                    )
            else:
                add_sample(
                    sample_name=sample_name,
                    sample_pool=sample_name,
                    library_types=library_types,
                    is_cmo_sample=False,
                    is_flex_sample=False,
                )

        return pd.DataFrame(sample_data).fillna(np.nan)
    
    def __update_data(
        self, sample_table: pd.DataFrame, library_table: pd.DataFrame,
        pool_table: Optional[pd.DataFrame], visium_table: Optional[pd.DataFrame],
        cmo_table: Optional[pd.DataFrame]
    ):
        self.update_table("sample_table", sample_table, False)
        self.update_table("library_table", library_table, False)
        if pool_table is not None:
            self.update_table("pool_table", pool_table, False)
        if visium_table is not None:
            self.update_table("visium_table", visium_table, False)
        if cmo_table is not None:
            self.update_table("cmo_table", cmo_table, False)

        self.update_data()

    def process_request(self, user: models.User) -> Response:
        if not self.validate():
            self.prepare()
            return self.make_response()

        library_table = self.tables["library_table"]
        sample_table = self.tables["sample_table"]
        pool_table = self.tables.get("pool_table")
        feature_table = self.tables.get("feature_table")
        cmo_table = self.tables.get("cmo_table")
        visium_table = self.tables.get("visium_table")
        comment_table = self.tables.get("comment_table")

        if current_app.debug:
            self.__update_data(
                sample_table=sample_table,
                library_table=library_table,
                pool_table=pool_table,
                visium_table=visium_table,
                cmo_table=cmo_table
            )

        if visium_table is not None:
            visium_table["id"] = None
            with DBSession(db) as session:
                for idx, visium_row in visium_table.iterrows():
                    visium_annotation = db.create_visium_annotation(
                        area=visium_row["area"],
                        image=visium_row["image"],
                        slide=visium_row["slide"],
                    )
                    visium_table.at[idx, "id"] = visium_annotation.id

            visium_table["id"] = visium_table["id"].astype(int)

        if (project_id := self.metadata.get("project_id")) is not None:
            if (project := db.get_project(project_id)) is None:
                logger.error(f"{self.uuid}: Project with id {project_id} not found.")
                raise ValueError(f"Project with id {project_id} not found.")
        else:
            project = db.create_project(
                name=self.metadata["project_name"],
                description=self.metadata["project_description"],
                owner_id=user.id
            )

        with DBSession(db) as session:
            for idx, row in sample_table.iterrows():
                sample = session.create_sample(
                    name=row["sample_name"],
                    project_id=project.id,
                    owner_id=user.id
                )
                sample_table.at[idx, "sample_id"] = sample.id

            sample_table["sample_id"] = sample_table["sample_id"].astype(int)

        if pool_table is not None:
            pool_table["pool_id"] = None
            with DBSession(db) as session:
                for idx, row in pool_table.iterrows():
                    pool = session.create_pool(
                        name=row["name"],
                        owner_id=user.id,
                        seq_request_id=self.seq_request.id,
                        num_m_reads_requested=row["num_m_reads"],
                        contact_name=row["contact_person_name"],
                        contact_email=row["contact_person_email"],
                        contact_phone=row["contact_person_phone"] if pd.notna(row["contact_person_phone"]) else None,
                    )
                    pool_table.at[idx, "pool_id"] = pool.id

            pool_table["pool_id"] = pool_table["pool_id"].astype(int)

        with DBSession(db) as session:
            library_table["library_id"] = None
            for idx, row in library_table.iterrows():
                if visium_table is not None:
                    visium_row = visium_table[visium_table["library_name"] == row["library_name"]].iloc[0]
                    visium_annotation_id = int(visium_row["id"])
                else:
                    visium_annotation_id = None

                if pool_table is not None:
                    pool_row = pool_table[pool_table["name"] == row["pool"]].iloc[0]
                    pool_id = int(pool_row["pool_id"])
                else:
                    pool_id = None

                library = session.create_library(
                    name=row["library_name"],
                    seq_request_id=self.seq_request.id,
                    library_type=LibraryType.get(row["library_type_id"]),
                    owner_id=user.id,
                    genome_ref=GenomeRef.get(row["genome_id"]),
                    index_1_sequence=row["index_1"].strip() if "index_1" in row and pd.notna(row["index_1"]) else None,
                    index_2_sequence=row["index_2"].strip() if "index_2" in row and pd.notna(row["index_2"]) else None,
                    index_3_sequence=row["index_3"].strip() if "index_3" in row and pd.notna(row["index_3"]) else None,
                    index_4_sequence=row["index_4"].strip() if "index_4" in row and pd.notna(row["index_4"]) else None,
                    adapter=row["adapter"].strip() if "adapter" in row and pd.notna(row["adapter"]) else None,
                    visium_annotation_id=visium_annotation_id,
                    pool_id=pool_id,
                    seq_depth_requested=row["seq_depth"] if "seq_depth" in row and pd.notna(row["seq_depth"]) else None,
                )
                library_table.at[idx, "library_id"] = library.id
                library_samples = sample_table[sample_table["sample_pool"] == row["sample_name"]]
                for idx, sample_row in library_samples.iterrows():
                    session.link_sample_library(
                        sample_id=sample_row["sample_id"],
                        library_id=library.id,
                        cmo_sequence=sample_row["cmo_sequence"] if pd.notna(sample_row["cmo_sequence"]) else None,
                        cmo_pattern=sample_row["cmo_pattern"] if pd.notna(sample_row["cmo_pattern"]) else None,
                        cmo_read=sample_row["cmo_read"] if pd.notna(sample_row["cmo_read"]) else None,
                        flex_barcode=sample_row["flex_barcode"] if pd.notna(sample_row["flex_barcode"]) else None,
                    )

            library_table["library_id"] = library_table["library_id"].astype(int)

        if feature_table is not None:
            custom_features = feature_table[feature_table["feature_id"].isna()]
            with DBSession(db) as session:
                for (feature, pattern, read, sequence), _df in custom_features.groupby(["feature", "pattern", "read", "sequence"]):
                    feature = session.create_feature(
                        name=feature,
                        sequence=sequence,
                        pattern=pattern,
                        read=read,
                        type=FeatureType.ANTIBODY
                    )
                    feature_id = feature.id
                    feature_table.loc[_df.index, "feature_id"] = feature_id

            with DBSession(db) as session:
                for _, feature_row in feature_table.iterrows():
                    libraries = library_table[library_table["library_name"] == feature_row["library_name"]]
                    for _, library_row in libraries.iterrows():
                        session.link_feature_library(
                            feature_id=feature_row["feature_id"],
                            library_id=library_row["library_id"]
                        )

            feature_table["feature_id"] = feature_table["feature_id"].astype(int)
            
        if comment_table is not None:
            for _, row in comment_table.iterrows():
                if row["context"] == "visium_instructions":
                    comment = session.create_comment(
                        text=f"Visium data instructions: {row['text']}",
                        author_id=user.id,
                    )
                elif row["context"] == "custom_genome_reference":
                    comment = session.create_comment(
                        text=f"Custom genome reference: {row['text']}",
                        author_id=user.id,
                    )
                elif row["context"] == "assay_tech_selection":
                    comment = session.create_comment(
                        text=f"Additional info from assay selection: {row['text']}",
                        author_id=user.id,
                    )
                else:
                    raise ValueError(f"Unknown comment context: {row['context']}")
                    
                session.add_seq_request_comment(
                    seq_request_id=self.seq_request.id,
                    comment_id=comment.id
                )

        self.__update_data(
            sample_table=sample_table,
            library_table=library_table,
            pool_table=pool_table,
            visium_table=visium_table,
            cmo_table=cmo_table
        )

        flash(f"Added {library_table.shape[0]} libraries to sequencing request.", "success")
        logger.info(f"{self.uuid}: added libraries to sequencing request.")

        newdir = os.path.join(current_app.config["MEDIA_FOLDER"], FileType.LIBRARY_ANNOTATION.dir, str(self.seq_request.id))
        os.makedirs(newdir, exist_ok=True)
        shutil.copy(self.path, os.path.join(newdir, f"{self.uuid}.tsv"))
        os.remove(self.path)

        return make_response(redirect=url_for("seq_requests_page.seq_request_page", seq_request_id=self.seq_request.id))