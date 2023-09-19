import os

import pandas as pd

from limbless.core import DBHandler
from limbless.categories import LibraryType


def add_index_kits(db_handler: DBHandler, datadir: str = ""):
    df = pd.read_csv(os.path.join(datadir, "10x_kits", "Dual_Index_Kit_NN_Set_A.csv"), comment="#", index_col=0)

    if (index_kit := db_handler.get_indexkit_by_name("10x Dual Index Kit NN Set A")) is None:
        index_kit = db_handler.create_indexkit(
            name="10x Dual Index Kit NN Set A",
            allowed_library_types=[LibraryType.SC_RNA]
        )

    for adapter, row in df.iterrows():
        for i, seq in enumerate(row.values):
            if (indices := db_handler.get_seqindices_by_adapter(adapter)) is not None:
                if seq in [i.sequence for i in indices]:
                    continue

            db_handler.create_seqindex(
                sequence=seq,
                adapter=adapter,
                index_kit_id=index_kit.id,
                type=df.columns[i],
            )

    df = pd.read_csv(os.path.join(datadir, "10x_kits", "Dual_Index_Kit_NT_Set_A.csv"), comment="#", index_col=0)

    if (index_kit := db_handler.get_indexkit_by_name("10x Dual Index Kit NT Set A")) is None:
        index_kit = db_handler.create_indexkit(
            name="10x Dual Index Kit NT Set A",
            allowed_library_types=[LibraryType.SC_RNA]
        )

    for adapter, row in df.iterrows():
        for i, seq in enumerate(row.values):
            if (indices := db_handler.get_seqindices_by_adapter(adapter)) is not None:
                if seq in [i.sequence for i in indices]:
                    continue
            db_handler.create_seqindex(
                sequence=seq,
                adapter=adapter,
                index_kit_id=index_kit.id,
                type=df.columns[i],
            )

    df = pd.read_csv(os.path.join(datadir, "10x_kits", "Dual_Index_Kit_TN_Set_A.csv"), comment="#", index_col=0)

    if (index_kit := db_handler.get_indexkit_by_name("10x Dual Index Kit TN Seq A")) is None:
        index_kit = db_handler.create_indexkit(
            name="10x Dual Index Kit TN Seq A",
            allowed_library_types=[LibraryType.SC_RNA]
        )

    for adapter, row in df.iterrows():
        for i, seq in enumerate(row.values):
            if (indices := db_handler.get_seqindices_by_adapter(adapter)) is not None:
                if seq in [i.sequence for i in indices]:
                    continue
            db_handler.create_seqindex(
                sequence=seq,
                adapter=adapter,
                index_kit_id=index_kit.id,
                type=df.columns[i],
            )

    df = pd.read_csv(os.path.join(datadir, "10x_kits", "Dual_Index_Kit_TT_Set_A.csv"), comment="#", index_col=0)

    if (index_kit := db_handler.get_indexkit_by_name("10x Dual Index Kit TT Seq A")) is None:
        index_kit = db_handler.create_indexkit(
            name="10x Dual Index Kit TT Seq A",
            allowed_library_types=[LibraryType.SC_RNA]
        )

    for adapter, row in df.iterrows():
        for i, seq in enumerate(row.values):
            if (indices := db_handler.get_seqindices_by_adapter(adapter)) is not None:
                if seq in [i.sequence for i in indices]:
                    continue
            db_handler.create_seqindex(
                sequence=seq,
                adapter=adapter,
                index_kit_id=index_kit.id,
                type=df.columns[i],
            )

    df = pd.read_csv(os.path.join(datadir, "10x_kits", "Single_Index_Kit_N_Set_A.csv"), index_col=0, header=None)

    if (index_kit := db_handler.get_indexkit_by_name("10x Single Index Kit N Seq A")) is None:
        index_kit = db_handler.create_indexkit(
            name="10x Single Index Kit N Seq A",
            allowed_library_types=[LibraryType.SC_ATAC]
        )

    for adapter, row in df.iterrows():
        cols = [f"Index {i}" for i in range(1, 5)]
        for i, seq in enumerate(row.values):
            if (indices := db_handler.get_seqindices_by_adapter(adapter)) is not None:
                if seq in [i.sequence for i in indices]:
                    continue
            db_handler.create_seqindex(
                sequence=seq,
                adapter=adapter,
                index_kit_id=index_kit.id,
                type=cols[i],
            )

    df = pd.read_csv(os.path.join(datadir, "10x_kits", "Single_Index_Kit_T_Set_A.csv"), index_col=0, header=None)

    if (index_kit := db_handler.get_indexkit_by_name("10x Single Index Kit T Seq A")) is None:
        index_kit = db_handler.create_indexkit(
            name="10x Single Index Kit T Seq A",
            allowed_library_types=[LibraryType.SC_ATAC]
        )

    for adapter, row in df.iterrows():
        cols = [f"Index {i}" for i in range(1, 5)]
        for i, seq in enumerate(row.values):
            if (indices := db_handler.get_seqindices_by_adapter(adapter)) is not None:
                if seq in [i.sequence for i in indices]:
                    continue
            db_handler.create_seqindex(
                sequence=seq,
                adapter=adapter,
                index_kit_id=index_kit.id,
                type=cols[i],
            )
