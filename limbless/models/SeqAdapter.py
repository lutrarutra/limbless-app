from typing import Optional, TYPE_CHECKING, ClassVar, List

from sqlmodel import Field, SQLModel, Relationship

from ..tools import SearchResult

if TYPE_CHECKING:
    from .IndexKit import IndexKit
    from .SeqIndex import SeqIndex


class SeqAdapter(SQLModel, SearchResult, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, max_length=128, index=True)

    index_kit_id: int = Field(nullable=False, foreign_key="indexkit.id")
    index_kit: "IndexKit" = Relationship(
        back_populates="adapters",
        sa_relationship_kwargs={"lazy": "joined"},
    )

    indices: list["SeqIndex"] = Relationship(
        back_populates="adapter",
        sa_relationship_kwargs={"lazy": "joined"},
    )

    sortable_fields: ClassVar[List[str]] = ["id", "name", "index_kit_id"]

    def search_value(self) -> int:
        return self.id
    
    def search_name(self) -> str:
        return self.name
    
    def search_description(self) -> Optional[str]:
        return None