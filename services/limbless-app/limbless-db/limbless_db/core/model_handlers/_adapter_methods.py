import math
from typing import Optional

from sqlalchemy.sql.operators import and_

from ... import models, PAGE_LIMIT
from .. import exceptions


def create_adapter(
    self, index_kit_id: int,
    well: Optional[str] = None,
) -> models.Adapter:
    
    if not (persist_session := self._session is not None):
        self.open_session()

    if well is not None:
        if self._session.query(models.Adapter).where(
            and_(
                models.Adapter.well == well,
                models.Adapter.index_kit_id == index_kit_id
            )
        ).first():
            raise exceptions.NotUniqueValue(f"Adapter with plate_well '{well}', already exists.")

    adapter = models.Adapter(well=well, index_kit_id=index_kit_id,)

    self._session.add(adapter)
    self._session.commit()
    self._session.refresh(adapter)

    if not persist_session:
        self.close_session()

    return adapter


def get_adapter(self, id: int) -> Optional[models.Adapter]:
    if not (persist_session := self._session is not None):
        self.open_session()

    res = self._session.get(models.Adapter, id)

    if not persist_session:
        self.close_session()

    return res


def get_adapters(
    self, index_kit_id: Optional[int] = None,
    sort_by: Optional[str] = None, descending: bool = False,
    limit: Optional[int] = PAGE_LIMIT, offset: Optional[int] = None,

) -> tuple[list[models.Adapter], int]:
    
    if not (persist_session := self._session is not None):
        self.open_session()

    query = self._session.query(models.Adapter)

    if index_kit_id is not None:
        query = query.where(models.Adapter.index_kit_id == index_kit_id)

    n_pages: int = math.ceil(query.count() / limit) if limit is not None else 1

    if sort_by is not None:
        attr = getattr(models.Adapter, sort_by)
        if descending:
            attr = attr.desc()
        query = query.order_by(attr)

    if limit is not None:
        query = query.limit(limit)

    if offset is not None:
        query = query.offset(offset)

    res = query.all()

    if not persist_session:
        self.close_session()

    return res, n_pages