from typing import Optional, List, TYPE_CHECKING
from pydantic import PrivateAttr

from sqlmodel import Field, SQLModel, Relationship

from ..categories import LibraryType

if TYPE_CHECKING:
    from .SeqIndex import SeqIndex


class IndexKit(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, max_length=64, index=True, unique=True)

    seq_indices: List["SeqIndex"] = Relationship(back_populates="seq_kit")
    # library_type_ids: List[LibraryType] = Relationship(
    #     sa_relationship_kwargs={"lazy": "joined"},
    # )

    _library_types: list[LibraryType] = PrivateAttr(0)

    def __str__(self):
        return self.name
