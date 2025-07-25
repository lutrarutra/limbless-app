import math
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..DBHandler import DBHandler

from ...categories import IndexTypeEnum, LabProtocolEnum, KitType
from ... import models, PAGE_LIMIT
from .. import exceptions


def create_index_kit(
    self: "DBHandler", identifier: str, name: str,
    supported_protocols: list[LabProtocolEnum],
    type: IndexTypeEnum,
    flush: bool = True
) -> models.IndexKit:
    if not (persist_session := self._session is not None):
        self.open_session()

    if self.session.query(models.IndexKit).where(models.IndexKit.name == name).first():
        raise exceptions.NotUniqueValue(f"index_kit with name '{name}', already exists.")

    seq_kit = models.IndexKit(
        identifier=identifier.strip(),
        name=name.strip(),
        type_id=type.id,
        kit_type_id=KitType.INDEX_KIT.id,
        supported_protocol_ids=[p.id for p in supported_protocols]
    )
    self.session.add(seq_kit)

    if flush:
        self.session.flush()

    if not persist_session:
        self.close_session()
    return seq_kit


def get_index_kit(self: "DBHandler", id: int) -> models.IndexKit | None:
    if not (persist_session := self._session is not None):
        self.open_session()

    res = self.session.get(models.IndexKit, id)

    if not persist_session:
        self.close_session()

    return res


def get_index_kit_by_name(self: "DBHandler", name: str) -> models.IndexKit | None:
    if not (persist_session := self._session is not None):
        self.open_session()

    res = self.session.query(models.IndexKit).where(models.IndexKit.name == name).first()

    if not persist_session:
        self.close_session()
    return res


def get_index_kit_by_identifier(
    self: "DBHandler", identifier: str
) -> models.IndexKit | None:
    if not (persist_session := self._session is not None):
        self.open_session()

    res = self.session.query(models.IndexKit).where(models.IndexKit.identifier == identifier).first()

    if not persist_session:
        self.close_session()
    return res


def remove_all_barcodes_from_kit(
    self: "DBHandler", index_kit_id: int, flush: bool = True
) -> models.IndexKit:
    if not (persist_session := self._session is not None):
        self.open_session()

    if (index_kit := self.session.get(models.IndexKit, index_kit_id)) is None:
        raise exceptions.ElementDoesNotExist(f"IndexKit with id '{index_kit_id}' not found.")
    
    for adapter in index_kit.adapters:
        for barcode in adapter.barcodes_i7:
            self.session.delete(barcode)
            
        for barcode in adapter.barcodes_i5:
            self.session.delete(barcode)

        self.session.delete(adapter)

    if flush:
        self.session.flush()

    if not persist_session:
        self.close_session()
    return index_kit


def get_index_kits(
    self: "DBHandler", type_in: Optional[list[IndexTypeEnum]] = None,
    limit: Optional[int] = PAGE_LIMIT, offset: Optional[int] = None,
    sort_by: Optional[str] = None, descending: bool = False,
    count_pages: bool = False
) -> tuple[list[models.IndexKit], int | None]:
    if not (persist_session := self._session is not None):
        self.open_session()

    query = self.session.query(models.IndexKit)

    if type_in is not None:
        query = query.where(models.IndexKit.type_id.in_([t.id for t in type_in]))

    n_pages = None if not count_pages else math.ceil(query.count() / limit) if limit is not None else None

    if sort_by is not None:
        attr = getattr(models.IndexKit, sort_by)
        if descending:
            attr = attr.desc()
        query = query.order_by(attr)

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    res = query.all()

    if not persist_session:
        self.close_session()

    return res, n_pages


def update_index_kit(self: "DBHandler", index_kit: models.IndexKit) -> models.IndexKit:
    if not (persist_session := self._session is not None):
        self.open_session()

    self.session.add(index_kit)

    if not persist_session:
        self.close_session()
    return index_kit
