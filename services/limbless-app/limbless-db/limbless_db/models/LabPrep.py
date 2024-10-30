from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from limbless_db.categories import LabProtocol, LabProtocolEnum, PrepStatus, PrepStatusEnum, FileType
from limbless_db.models import links, Project

from .Base import Base

if TYPE_CHECKING:
    from .User import User
    from .Library import Library
    from .Plate import Plate
    from .File import File
    from .Pool import Pool
    from .Comment import Comment


class LabPrep(Base):
    __tablename__ = "lab_prep"

    id: Mapped[int] = mapped_column(sa.Integer, default=None, primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    protocol_id: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    status_id: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=0)

    creator_id: Mapped[int] = mapped_column(sa.Integer, sa.ForeignKey("lims_user.id"), nullable=False)
    creator: Mapped["User"] = relationship("User", back_populates="preps", lazy="joined")

    plate_id: Mapped[Optional[int]] = mapped_column(sa.Integer, sa.ForeignKey("plate.id"), nullable=True)
    plate: Mapped[Optional["Plate"]] = relationship("Plate", lazy="select")

    prep_file: Mapped[Optional["File"]] = relationship(
        "File", lazy="joined", viewonly=True,
        primaryjoin=f"and_(LabPrep.id == File.lab_prep_id, File.type_id == {FileType.LIBRARY_PREP_FILE.id})",
    )

    libraries: Mapped[list["Library"]] = relationship("Library", back_populates="lab_prep", lazy="select", order_by="Library.id")
    pools: Mapped[list["Pool"]] = relationship("Pool", back_populates="lab_prep", lazy="select")
    files: Mapped[list["File"]] = relationship("File", lazy="select", cascade="all, delete-orphan")
    comments: Mapped[list["Comment"]] = relationship("Comment", lazy="select", cascade="all, delete-orphan", order_by="Comment.timestamp_utc.desc()")
    
    @property
    def protocol(self) -> LabProtocolEnum:
        return LabProtocol.get(self.protocol_id)
    
    @protocol.setter
    def protocol(self, value: LabProtocolEnum):
        self.protocol_id = value.id

    @property
    def status(self) -> PrepStatusEnum:
        return PrepStatus.get(self.status_id)
    
    @status.setter
    def status(self, value: PrepStatusEnum):
        self.status_id = value.id