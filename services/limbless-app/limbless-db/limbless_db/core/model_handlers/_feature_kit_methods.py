import math
from typing import Optional

import sqlalchemy as sa

from ... import models, PAGE_LIMIT
from .. import exceptions
from ...categories import FeatureTypeEnum


def create_feature_kit(
    self, name: str,
    type: FeatureTypeEnum,
) -> models.FeatureKit:
    if not (persist_session := self._session is not None):
        self.open_session()

    if self._session.query(models.FeatureKit).where(models.FeatureKit.name == name).first():
        raise exceptions.NotUniqueValue(f"Feature kit with name '{name}', already exists.")

    feature_kit = models.FeatureKit(
        name=name.strip(),
        type_id=type.id,
    )
    self._session.add(feature_kit)
    self._session.commit()
    self._session.refresh(feature_kit)

    if not persist_session:
        self.close_session()
    return feature_kit


def get_feature_kit(self, id: int) -> Optional[models.FeatureKit]:
    if not (persist_session := self._session is not None):
        self.open_session()

    res = self._session.get(models.FeatureKit, id)

    if not persist_session:
        self.close_session()

    return res


def get_feature_kit_by_name(self, name: str) -> models.FeatureKit:
    if not (persist_session := self._session is not None):
        self.open_session()

    res = self._session.query(models.FeatureKit).where(models.FeatureKit.name == name).first()
    if not persist_session:
        self.close_session()
    return res


def get_feature_kits(
    self,
    limit: Optional[int] = PAGE_LIMIT, offset: Optional[int] = None,
    sort_by: Optional[str] = None, descending: bool = False,
) -> tuple[list[models.FeatureKit], int]:
    if not (persist_session := self._session is not None):
        self.open_session()

    query = self._session.query(models.FeatureKit)

    if sort_by is not None:
        sort_attr = getattr(models.FeatureKit, sort_by)
        if descending:
            sort_attr = sort_attr.desc()
        query = query.order_by(sort_attr)

    n_pages: int = math.ceil(query.count() / limit) if limit is not None else 1

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    feature_kits = query.all()

    if not persist_session:
        self.close_session()

    return feature_kits, n_pages


def update_feature_kit(
    self, feature_kit: models.FeatureKit,
    commit: bool = True,
) -> models.FeatureKit:
    if not (persist_session := self._session is not None):
        self.open_session()

    self._session.add(feature_kit)
    if commit:
        self._session.commit()
        self._session.refresh(feature_kit)

    if not persist_session:
        self.close_session()

    return feature_kit


def delete_feature_kit(
    self, feature_kit_id: int,
    commit: bool = True
):
    if not (persist_session := self._session is not None):
        self.open_session()

    feature_kit = self._session.get(models.FeatureKit, feature_kit_id)
    
    for feature in feature_kit.features:
        self._session.delete(feature)

    self._session.delete(feature_kit)
    if commit:
        self._session.commit()

    if not persist_session:
        self.close_session()


def query_feature_kits(
    self, word: str, limit: Optional[int] = PAGE_LIMIT
) -> list[models.FeatureKit]:
    
    if not (persist_session := self._session is not None):
        self.open_session()

    query = self._session.query(models.FeatureKit)

    query = query.order_by(
        sa.func.similarity(models.FeatureKit.name, word).desc(),
    )

    if limit is not None:
        query = query.limit(limit)

    feature_kits = query.all()

    if not persist_session:
        self.close_session()

    return feature_kits