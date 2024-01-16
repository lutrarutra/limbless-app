import math
from typing import Optional

from sqlmodel import func

from ... import PAGE_LIMIT, models
from .. import exceptions


def create_pool(
    self, name: str,
    owner_id: int,
    contact_name: str,
    contact_email: str,
    index_kit_id: Optional[int] = None,
    contact_phone: Optional[str] = None,
    commit: bool = True
) -> models.Pool:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    if (user := self._session.get(models.User, owner_id)) is None:
        raise exceptions.ElementDoesNotExist(f"User with id {owner_id} does not exist")
    
    if index_kit_id is not None:
        if (_ := self._session.get(models.IndexKit, index_kit_id)) is None:
            raise exceptions.ElementDoesNotExist(f"Index kit with id {index_kit_id} does not exist")
    
    pool = models.Pool(
        name=name,
        owner_id=owner_id,
        index_kit_id=index_kit_id,
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
    )
    self._session.add(pool)
    user.num_pools += 1

    if commit:
        self._session.commit()
        self._session.refresh(pool)

    if not persist_session:
        self.close_session()

    return pool


def get_pool(self, pool_id: int) -> models.Pool:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    pool = self._session.get(models.Pool, pool_id)
    if not persist_session:
        self.close_session()
    return pool


def get_pools(
    self,
    user_id: Optional[int] = None,
    library_id: Optional[int] = None,
    experiment_id: Optional[int] = None,
    sort_by: Optional[str] = None, descending: bool = False,
    limit: Optional[int] = PAGE_LIMIT, offset: Optional[int] = None,
) -> tuple[list[models.Pool], int]:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    query = self._session.query(models.Pool)
    if user_id is not None:
        query = query.where(
            models.Pool.owner_id == user_id
        )

    if library_id is not None:
        query = query.join(
            models.LibraryPoolLink,
            models.Pool.id == models.LibraryPoolLink.pool_id,
            isouter=True
        ).where(
            models.Library.id == library_id
        )

    if experiment_id is not None:
        query = query.join(
            models.ExperimentPoolLink,
            models.Pool.id == models.ExperimentPoolLink.pool_id,
            isouter=True
        ).where(
            models.ExperimentPoolLink.experiment_id == experiment_id
        )

    if sort_by is not None:
        attr = getattr(models.Pool, sort_by)
        if descending:
            attr = attr.desc()
        query = query.order_by(attr)

    n_pages: int = math.ceil(query.count() / limit) if limit is not None else 1
    
    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    pools = query.all()

    if not persist_session:
        self.close_session()

    return pools, n_pages


def delete_pool(
    self, pool_id: int,
    commit: bool = True
) -> None:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    if (pool := self._session.get(models.Pool, pool_id)) is None:
        raise exceptions.ElementDoesNotExist(f"Pool with id {pool_id} does not exist")

    pool.owner.num_pools -= 1
    for sample in pool.samples:
        sample.num_pools -= 1
        
    self._session.delete(pool)
    if commit:
        self._session.commit()

    if not persist_session:
        self.close_session()


def update_pool(
    self, pool_id: int,
    name: Optional[str] = None,
    commit: bool = True
) -> models.Pool:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    pool = self._session.get(models.Pool, pool_id)
    if not pool:
        raise exceptions.ElementDoesNotExist(f"Pool with id {pool_id} does not exist")

    if name is not None:
        _lib = self._session.query(models.Pool).where(
            models.Pool.name == name
        ).first()
        if _lib is not None and _lib.id != pool_id:
            raise exceptions.NotUniqueValue(f"Pool with name {name} already exists")

    if name is not None:
        pool.name = name

    if commit:
        self._session.commit()
        self._session.refresh(pool)

    if not persist_session:
        self.close_session()
    return pool


def query_pools(
    self, word: str,
    user_id: Optional[int] = None,
    library_id: Optional[int] = None,
    limit: Optional[int] = PAGE_LIMIT,
) -> list[models.Pool]:

    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    query = self._session.query(models.Pool)

    if user_id is not None:
        if self._session.get(models.User, user_id) is None:
            raise exceptions.ElementDoesNotExist(f"User with id {user_id} does not exist")
        query = query.where(
            models.Pool.owner_id == user_id
        )

    if library_id is not None:
        query = query.join(
            models.Library,
            models.LibraryPoolLink.pool_id == models.Pool.id,
            isouter=True
        ).where(
            models.LibraryPoolLink.library_id == library_id
        )

    query = query.order_by(
        func.similarity(models.Pool.name, word).desc()
    )

    if limit is not None:
        query = query.limit(limit)

    pools = query.all()

    if not persist_session:
        self.close_session()

    return pools