from datetime import datetime
from typing import Optional, List, TYPE_CHECKING, ClassVar

import sqlalchemy as sa
from sqlmodel import Field, SQLModel, Relationship

from ..core.categories import ExperimentStatus
from .Links import ExperimentPoolLink, SeqRequestExperimentLink, ExperimentFileLink

if TYPE_CHECKING:
    from .Pool import Pool
    from .Sequencer import Sequencer
    from .User import User
    from .SeqRequest import SeqRequest
    from .File import File


class Experiment(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    
    flowcell: str = Field(nullable=False, max_length=64)
    r1_cycles: int = Field(nullable=False)
    r2_cycles: Optional[int] = Field(nullable=True)
    i1_cycles: int = Field(nullable=False)
    i2_cycles: Optional[int] = Field(nullable=True)

    sequencing_person_id: int = Field(nullable=False, foreign_key="lims_user.id")
    sequencing_person: "User" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    
    num_lanes: int = Field(nullable=False, default=0)
    num_pools: int = Field(nullable=False, default=0)

    timestamp: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))

    status_id: int = Field(nullable=False, default=0)

    sequencer_id: int = Field(nullable=False, foreign_key="sequencer.id")
    sequencer: "Sequencer" = Relationship(sa_relationship_kwargs={"lazy": "joined"})

    pools: List["Pool"] = Relationship(
        back_populates="experiments", link_model=ExperimentPoolLink,
        sa_relationship_kwargs={"lazy": "select", "overlaps": "experiment_links,pool,experiment"},
    )
    pool_links: List["ExperimentPoolLink"] = Relationship(
        back_populates="experiment",
        sa_relationship_kwargs={"lazy": "select", "overlaps": "experiments,pools,experiment"},
    )

    seq_requests: List["SeqRequest"] = Relationship(
        back_populates="experiments", link_model=SeqRequestExperimentLink,
        sa_relationship_kwargs={"lazy": "select"},
    )

    sortable_fields: ClassVar[List[str]] = ["id", "flowcell", "timestamp", "status", "sequencer_id", "num_lanes", "num_libraries"]

    files: list["File"] = Relationship(
        link_model=ExperimentFileLink, sa_relationship_kwargs={"lazy": "select", "cascade": "delete"},
    )

    @property
    def status(self) -> ExperimentStatus:
        return ExperimentStatus.get(self.status_id)
    
    def is_deleteable(self) -> bool:
        return self.status == ExperimentStatus.DRAFT
    
    def is_editable(self) -> bool:
        return self.status == ExperimentStatus.DRAFT
    
    def is_submittable(self) -> bool:
        return self.status == ExperimentStatus.DRAFT
    
    def timestamp_to_str(self) -> str:
        return self.timestamp.strftime('%Y-%m-%d %H:%M')