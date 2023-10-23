from typing import Optional

from sqlmodel import Field, SQLModel

from ..tools.SearchResult import SearchResult


class Organism(SQLModel, table=True):
    tax_id: int = Field(default=None, primary_key=True)
    scientific_name: str = Field(nullable=False, max_length=128, index=True)
    common_name: Optional[str] = Field(nullable=True, max_length=128, index=True)
    category: int = Field(nullable=False)

    def __str__(self) -> str:
        _val = f"{self.scientific_name} [{self.tax_id}]"
        if self.common_name:
            _val += f" ({self.common_name})"
        return _val

    @property
    def id(self):
        return self.tax_id
    
    def to_search_result(self) -> SearchResult:
        return SearchResult(
            value=self.tax_id,
            name=self.scientific_name,
            description=self.common_name,
            show_value=True,
            name_class="latin",
        )
