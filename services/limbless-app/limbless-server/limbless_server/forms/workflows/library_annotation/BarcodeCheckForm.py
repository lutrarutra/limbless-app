import os
from typing import Optional
from flask import Response
import pandas as pd

from flask import url_for, flash
from flask_htmx import make_response

from limbless_db import models, DBSession
from limbless_db.categories import LibraryType, FeatureType, GenomeRef

from .... import db, logger
from ...TableDataForm import TableDataForm
from ...HTMXFlaskForm import HTMXFlaskForm


class BarcodeCheckForm(HTMXFlaskForm, TableDataForm):
    _template_path = "workflows/library_annotation/sas-10.html"

    def __init__(self, formdata: dict = {}, uuid: Optional[str] = None):
        if uuid is None:
            uuid = formdata.get("file_uuid")
        HTMXFlaskForm.__init__(self, formdata=formdata)
        TableDataForm.__init__(self, dirname="library_annotation", uuid=uuid)
    
    def prepare(self, data: Optional[dict[str, pd.DataFrame | dict]] = None) -> dict:
        if data is None:
            data = self.get_data()

        data = self.get_data()
        df: pd.DataFrame = self.get_data()["library_table"]  # type: ignore

        samples_data: list[dict[str, str | int | None]] = []

        indices_present = []
        if "index_1" in df.columns:
            indices_present.append("index_1")
        if "index_2" in df.columns:
            indices_present.append("index_2")
        if "index_3" in df.columns:
            indices_present.append("index_3")
        if "index_4" in df.columns:
            indices_present.append("index_4")
        
        reused_barcodes = (df[indices_present].duplicated(keep=False)) & (~df[indices_present].isna().all(axis=1))

        for i, row in df.iterrows():
            # Check if sample names are unique in project
            _data = {
                "id": row["sample_id"],
                "name": row["library_name"],
                "library_type": row["library_type"],
                "genome": GenomeRef.get(row["genome_id"]).display_name,
                "error": None,
                "warning": "",
                "info": "",
            }
            if "index_1" in row:
                _data["index_1"] = row["index_1"]
            
            if "index_2" in row:
                _data["index_2"] = row["index_2"]

            if "index_3" in row:
                _data["index_3"] = row["index_3"]

            if "index_4" in row:
                _data["index_4"] = row["index_4"]

            if "adapter" in row:
                _data["adapter"] = row["adapter"]

            if reused_barcodes.at[i]:
                _data["warning"] += "Index combination is reused in two or more libraries. "

            samples_data.append(_data)

        data["library_table"] = df
        self.update_data(data)

        return {
            "samples_data": samples_data,
            "show_index_1": "index_1" in df.columns and not df["index_1"].isna().all(),
            "show_index_2": "index_2" in df.columns and not df["index_2"].isna().all(),
            "show_index_3": "index_3" in df.columns and not df["index_3"].isna().all(),
            "show_index_4": "index_4" in df.columns and not df["index_4"].isna().all(),
        }
    
    def process_request(self, **context) -> Response:
        validated = self.validate()
        if not validated:
            return self.make_response(**context)
        
        user_id: int = context["user_id"]
        seq_request: models.SeqRequest = context["seq_request"]

        data = self.get_data()

        library_table: pd.DataFrame = data["library_table"]  # type: ignore
        cmo_table: Optional[pd.DataFrame] = data["cmo_table"] if "cmo_table" in data else None  # type: ignore
        visium_ref: Optional[pd.DataFrame] = data["visium_ref"] if "visium_ref" in data else None  # type: ignore
        feature_table: Optional[pd.DataFrame] = data["feature_table"] if "feature_table" in data else None  # type: ignore

        n_added = 0
        n_new_samples = 0

        with DBSession(db) as session:
            projects: dict[int | str, models.Project] = {}
            for project_id, project_name in library_table[["project_id", "project_name"]].drop_duplicates().values.tolist():
                if not pd.isnull(project_id):
                    project_id = int(project_id)
                    if (project := session.get_project(project_id)) is None:
                        raise Exception(f"Project with id {project_id} does not exist.")
                    
                    projects[project_id] = project
                else:
                    project = session.create_project(
                        name=project_name,
                        description="",
                        owner_id=user_id
                    )
                    projects[project.id] = project
                    library_table.loc[library_table["project_name"] == project_name, "project_id"] = project.id

            if library_table["project_id"].isna().any():
                raise Exception("Project id is None (should not be).")

        with DBSession(db) as session:
            pools: dict[str, models.Pool] = {}

            if "pool" in library_table.columns:
                for pool_label, _df in library_table.groupby("pool"):
                    pool_label = str(pool_label)
                    pool = session.create_pool(
                        name=pool_label,
                        owner_id=user_id,
                        seq_request_id=seq_request.id,
                        num_m_reads_requested=_df["num_m_reads"].iloc[0],
                        contact_name=_df["contact_person_name"].iloc[0],
                        contact_email=_df["contact_person_email"].iloc[0],
                        contact_phone=_df["contact_person_phone"].iloc[0],
                    )
                    pools[pool_label] = pool

            for (sample_name, sample_id, project_id, is_cmo_sample), _df in library_table.groupby(["sample_name", "sample_id", "project_id", "is_cmo_sample"], dropna=False):
                if cmo_table is not None:
                    feature_ref = cmo_table.loc[cmo_table["sample_pool"] == sample_name, :]
                else:
                    feature_ref = pd.DataFrame()
                library_samples: list[tuple[models.Sample, Optional[models.CMO]]] = []

                sample_id = int(sample_id) if not pd.isna(sample_id) else None
                project_id = int(project_id)

                if is_cmo_sample:
                    for _, row in feature_ref.iterrows():
                        feature = session.get_feature(row["feature_id"])
                        sample = session.create_sample(
                            name=row["demux_name"],
                            owner_id=user_id,
                            project_id=project_id,
                        )
                        # Temporary data object
                        cmo = models.CMO(
                            sequence=feature.sequence,
                            pattern=feature.pattern,
                            read=feature.read,
                            sample_id=0,
                            library_id=0,
                        )
                        
                        library_samples.append((sample, cmo))
                        n_new_samples += 1
                else:
                    
                    if sample_id is None:
                        sample = session.create_sample(
                            name=sample_name,
                            project_id=project_id,
                            owner_id=user_id
                        )
                        library_samples.append((sample, None))
                        n_new_samples += 1
                    else:
                        if (sample := session.get_sample(sample_id)) is None:
                            logger.error(f"Sample with id {sample_id} does not exist.")
                            raise Exception(f"Sample with id {sample_id} does not exist.")
                        library_samples.append((sample, None))

                for _, row in _df.iterrows():
                    library_type = LibraryType.get(row["library_type_id"])
                    genome_ref = GenomeRef.get(row["genome_id"])

                    library_name = row["library_name"]
                    index_kit_id = int(row["index_kit_id"]) if "index_kit_id" in row and not pd.isna(row["index_kit_id"]) else None
                    adapter = row["adapter"].strip() if "adapter" in row and not pd.isna(row["adapter"]) else None
                    index_1_sequence = row["index_1"].strip() if "index_1" in row and not pd.isna(row["index_1"]) else None
                    index_2_sequence = row["index_2"].strip() if "index_2" in row and not pd.isna(row["index_2"]) else None
                    index_3_sequence = row["index_3"].strip() if "index_3" in row and not pd.isna(row["index_3"]) else None
                    index_4_sequence = row["index_4"].strip() if "index_4" in row and not pd.isna(row["index_4"]) else None

                    if library_type == LibraryType.SPATIAL_TRANSCRIPTOMIC:
                        if visium_ref is None:
                            raise Exception("Visium reference table not found.")    # this should not happen
                        
                        visium_row = visium_ref[visium_ref["library_name"] == library_name].iloc[0]
                        visium_annotation = db.create_visium_annotation(
                            area=visium_row["area"],
                            image=visium_row["image"],
                            slide=visium_row["slide"],
                        )
                        visium_annotation_id = visium_annotation.id
                    else:
                        visium_annotation_id = None

                    library = session.create_library(
                        name=library_name,
                        seq_request_id=seq_request.id,
                        library_type=library_type,
                        index_kit_id=index_kit_id,
                        owner_id=user_id,
                        genome_ref=genome_ref,
                        index_1_sequence=index_1_sequence if index_1_sequence else None,
                        index_2_sequence=index_2_sequence if index_2_sequence else None,
                        index_3_sequence=index_3_sequence if index_3_sequence else None,
                        index_4_sequence=index_4_sequence if index_4_sequence else None,
                        adapter=adapter if adapter else None,
                        visium_annotation_id=visium_annotation_id,
                    )

                    if feature_table is not None:
                        feature_ref = feature_table[(feature_table["library_name"] == library_name) | feature_table["library_name"].isna()]
                        for _, feature_row in feature_ref.iterrows():
                            if pd.isna(feature_id := feature_row["feature_id"]):
                                _feature = session.create_feature(
                                    name=feature_row["feature_name"],
                                    sequence=feature_row["sequence"],
                                    pattern=feature_row["pattern"],
                                    target_id=feature_row["feature_name"],
                                    target_name=feature_row["feature_name"],
                                    read=feature_row["read"],
                                    type=FeatureType.ANTIBODY
                                )
                            else:
                                _feature = session.get_feature(feature_id)
                            
                            session.link_feature_library(
                                feature_id=_feature.id,
                                library_id=library.id
                            )

                    n_added += 1
                
                    for sample, cmo in library_samples:
                        if cmo is not None:
                            _cmo = session.create_cmo(
                                sequence=cmo.sequence,
                                pattern=cmo.pattern,
                                read=cmo.read,
                                sample_id=sample.id,
                                library_id=library.id,
                            )
                            session.link_sample_library(
                                sample_id=sample.id,
                                library_id=library.id,
                                cmo_id=_cmo.id,
                            )
                        else:
                            session.link_sample_library(
                                sample_id=sample.id,
                                library_id=library.id,
                            )

                    if "pool" in row.keys() and not pd.isna(row["pool"]):
                        session.link_library_pool(
                            library_id=library.id,
                            pool_id=pools[row["pool"]].id
                        )

        if "comments" in data:
            comments_df = data["comments"]
            for _, row in comments_df[comments_df["context"] == "visium_instructions"].iterrows():
                comment = session.create_comment(
                    text=row["text"],
                    author_id=user_id,
                )
                session.add_seq_request_comment(
                    seq_request_id=seq_request.id,
                    comment_id=comment.id
                )

        if n_added == 0:
            flash("No libraries added.", "warning")
        else:
            flash(f"Added {n_added} libraries to sequencing request.", "success")

        if os.path.exists(self.path):
            os.remove(self.path)

        return make_response(
            redirect=url_for(
                "seq_requests_page.seq_request_page",
                seq_request_id=context["seq_request"].id
            )
        )