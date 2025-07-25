from typing import Optional, TYPE_CHECKING, ClassVar
from datetime import datetime
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.mutable import MutableDict

from . import links
from .Base import Base
from .SeqRequest import SeqRequest
from ..categories import (
    LibraryType, LibraryTypeEnum, LibraryStatus, LibraryStatusEnum, GenomeRef,
    GenomeRefEnum, AssayType, AssayTypeEnum, MUXType, MUXTypeEnum, IndexType, IndexTypeEnum
)

if TYPE_CHECKING:
    from .Pool import Pool
    from .User import User
    from .Feature import Feature
    from .SeqQuality import SeqQuality
    from .File import File
    from .LibraryIndex import LibraryIndex
    from .LabPrep import LabPrep
    from .Experiment import Experiment


@dataclass
class LibraryAdapter:
    name_i7: str
    _name_i5: str | None
    sequences_i7: list[str]
    sequences_i5: list[str | None]

    @property
    def name_i5(self) -> str:
        return self._name_i5 if self._name_i5 is not None else self.name_i7


class Library(Base):
    __tablename__ = "library"

    id: Mapped[int] = mapped_column(sa.Integer, default=None, primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(86), nullable=False)
    sample_name: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    clone_number: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=0)
    original_library_id: Mapped[Optional[int]] = mapped_column(sa.ForeignKey("library.id", ondelete="SET NULL"), nullable=True, default=None)

    type_id: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    status_id: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    genome_ref_id: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    assay_type_id: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    mux_type_id: Mapped[Optional[int]] = mapped_column(sa.SmallInteger, nullable=True, default=None)
    index_type_id: Mapped[Optional[int]] = mapped_column(sa.SmallInteger, nullable=True, default=None)

    timestamp_stored_utc: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(), nullable=True, default=None)

    nuclei_isolation: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    seq_depth_requested: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True, default=None)
    avg_fragment_size: Mapped[Optional[int]] = mapped_column(sa.Float, nullable=True, default=None)
    volume: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True, default=None)
    qubit_concentration: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True, default=None)

    num_samples: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    num_features: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)

    properties: Mapped[Optional[dict]] = mapped_column(MutableDict.as_mutable(JSONB), nullable=True, default=None)

    ba_report_id: Mapped[Optional[int]] = mapped_column(sa.ForeignKey("file.id"), nullable=True, default=None)
    ba_report: Mapped[Optional["File"]] = relationship("File", lazy="select")

    pool_id: Mapped[Optional[int]] = mapped_column(sa.ForeignKey("pool.id", ondelete="SET NULL"), nullable=True)
    pool: Mapped[Optional["Pool"]] = relationship(
        "Pool", back_populates="libraries", lazy="joined", cascade="save-update, merge"
    )

    experiment_id: Mapped[Optional[int]] = mapped_column(sa.ForeignKey("experiment.id"), nullable=True, default=None)
    experiment: Mapped[Optional["Experiment"]] = relationship("Experiment", lazy="select", back_populates="libraries")

    owner_id: Mapped[int] = mapped_column(sa.ForeignKey("lims_user.id"), nullable=False)
    owner: Mapped["User"] = relationship("User", back_populates="libraries", lazy="joined")
    
    seq_request_id: Mapped[int] = mapped_column(sa.ForeignKey("seq_request.id"), nullable=False)
    seq_request: Mapped["SeqRequest"] = relationship("SeqRequest", back_populates="libraries", lazy="select")
    
    lab_prep_id: Mapped[Optional[int]] = mapped_column(sa.ForeignKey("lab_prep.id"), nullable=True)
    lab_prep: Mapped[Optional["LabPrep"]] = relationship("LabPrep", back_populates="libraries", lazy="select")

    sample_links: Mapped[list[links.SampleLibraryLink]] = relationship(
        links.SampleLibraryLink, back_populates="library", lazy="select",
        cascade="save-update, merge, delete, delete-orphan"
    )
    features: Mapped[list["Feature"]] = relationship("Feature", secondary=links.LibraryFeatureLink.__tablename__, lazy="select", cascade="save-update, merge")
    plate_links: Mapped[list["links.SamplePlateLink"]] = relationship("SamplePlateLink", back_populates="library", lazy="select")
    indices: Mapped[list["LibraryIndex"]] = relationship("LibraryIndex", lazy="joined", cascade="all, save-update, merge, delete, delete-orphan")
    read_qualities: Mapped[list["SeqQuality"]] = relationship("SeqQuality", back_populates="library", lazy="select", cascade="all, save-update, merge, delete, delete-orphan")

    sortable_fields: ClassVar[list[str]] = ["id", "name", "type_id", "status_id", "owner_id", "pool_id", "adapter"]
    
    @property
    def status(self) -> LibraryStatusEnum:
        return LibraryStatus.get(self.status_id)
    
    @status.setter
    def status(self, value: LibraryStatusEnum):
        self.status_id = value.id

    @property
    def type(self) -> LibraryTypeEnum:
        return LibraryType.get(self.type_id)
    
    @type.setter
    def type(self, value: LibraryTypeEnum):
        self.type_id = value.id
    
    @property
    def genome_ref(self) -> GenomeRefEnum:
        return GenomeRef.get(self.genome_ref_id)
    
    @genome_ref.setter
    def genome_ref(self, value: GenomeRefEnum):
        self.genome_ref_id = value.id

    @property
    def assay_type(self) -> AssayTypeEnum:
        return AssayType.get(self.assay_type_id)
    
    @assay_type.setter
    def assay_type(self, value: AssayTypeEnum):
        self.assay_type_id = value.id

    @property
    def mux_type(self) -> MUXTypeEnum | None:
        if self.mux_type_id is None:
            return None
        return MUXType.get(self.mux_type_id)
    
    @mux_type.setter
    def mux_type(self, value: MUXTypeEnum | None):
        if value is None:
            self.mux_type_id = None
        else:
            self.mux_type_id = value.id

    @property
    def index_type(self) -> IndexTypeEnum | None:
        if self.index_type_id is None:
            return None
        return IndexType.get(self.index_type_id)
    
    @index_type.setter
    def index_type(self, value: IndexTypeEnum | None):
        if value is None:
            self.index_type_id = None
        else:
            self.index_type_id = value.id
    
    @property
    def qubit_concentration_str(self) -> str:
        if (q := self.qubit_concentration) is None:
            return ""
        return f"{q:.2f}"
    
    @property
    def molarity(self) -> float | None:
        if self.avg_fragment_size is None or self.qubit_concentration is None:
            return None
        return self.qubit_concentration / (self.avg_fragment_size * 660) * 1_000_000
    
    @property
    def molarity_str(self) -> str:
        if (m := self.molarity) is None:
            return ""
        return f"{m:.2f}"
    
    @property
    def timestamp_stored_str(self) -> str:
        return self.timestamp_stored_utc.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp_stored_utc is not None else ""
    
    def is_multiplexed(self) -> bool:
        return self.mux_type_id is not None
    
    def is_editable(self) -> bool:
        return self.status == LibraryStatus.DRAFT
    
    def is_indexed(self) -> bool:
        return len(self.indices) > 0
    
    def is_pooled(self) -> bool:
        return self.status == LibraryStatus.POOLED
    
    def __str__(self) -> str:
        return f"Library(id: {self.id}, name: {self.name}, type: {self.type})"
    
    def __repr__(self) -> str:
        return str(self)
    
    def adapters_i7(self) -> dict[tuple[int, str], list[str]]:
        adapters = {}
        for index in self.indices:
            idx = (index.index_kit_i7_id, index.name_i7)
            if idx not in adapters:
                adapters[idx] = []
            adapters[idx].append(index.sequence_i7)
        return adapters
    
    def adapters_i5(self) -> dict[tuple[int, str], list[str]]:
        adapters = {}
        for index in self.indices:
            if index.sequence_i5 is None:
                continue
            idx = (index.index_kit_i5_id, index.name_i5)
            if idx not in adapters:
                adapters[idx] = []
            adapters[idx].append(index.sequence_i5)
        return adapters

    def sequences_i7_str(self, sep: str = ", ") -> str:
        i7s = []
        for index in self.indices:
            if index.sequence_i7:
                i7s.append(index.sequence_i7)

        return sep.join(i7s)
    
    def sequences_i5_str(self, sep: str = ", ") -> str:
        i5s = []
        for index in self.indices:
            if index.sequence_i5:
                i5s.append(index.sequence_i5)

        return sep.join(i5s)
    
    def names_i7_str(self, sep: str = ", ") -> str:
        i7s = []
        for index in self.indices:
            if index.name_i7:
                i7s.append(index.name_i7)

        return sep.join(i7s)
    
    def names_i5_str(self, sep: str = ", ") -> str:
        i5s = []
        for index in self.indices:
            if index.name_i5:
                i5s.append(index.name_i5)

        return sep.join(i5s)