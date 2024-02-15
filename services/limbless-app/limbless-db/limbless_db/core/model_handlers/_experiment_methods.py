import math
from datetime import datetime
from typing import Optional

from ... import models, PAGE_LIMIT
from .. import exceptions


def create_experiment(
    self, flowcell: str, sequencer_id: int, num_lanes: int,
    r1_cycles: int, i1_cycles: int, sequencing_person_id: int,
    r2_cycles: Optional[int] = None, i2_cycles: Optional[int] = None,
    commit: bool = True
) -> models.Experiment:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    if self._session.get(models.Sequencer, sequencer_id) is None:
        raise exceptions.ElementDoesNotExist(f"Sequencer with id {sequencer_id} does not exist")

    experiment = models.Experiment(
        flowcell=flowcell,
        timestamp=datetime.now(),
        sequencer_id=sequencer_id,
        r1_cycles=r1_cycles,
        r2_cycles=r2_cycles,
        i1_cycles=i1_cycles,
        i2_cycles=i2_cycles,
        num_lanes=num_lanes,
        sequencing_person_id=sequencing_person_id
    )

    self._session.add(experiment)
    if commit:
        self._session.commit()
        self._session.refresh(experiment)

    if not persist_session:
        self.close_session()

    return experiment


def get_experiment(self, experiment_id: int) -> models.Experiment:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    res = self._session.get(models.Experiment, experiment_id)
    if not persist_session:
        self.close_session()
    return res


def get_experiments(
    self, limit: Optional[int] = PAGE_LIMIT, offset: Optional[int] = None,
    sort_by: Optional[str] = None, descending: bool = False
) -> tuple[list[models.Experiment], int]:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    query = self._session.query(models.Experiment)

    if sort_by is not None:
        attr = getattr(models.Experiment, sort_by)
        if descending:
            attr = attr.desc()
        query = query.order_by(attr)

    n_pages = math.ceil(query.count() / limit)

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    experiments = query.all()

    if not persist_session:
        self.close_session()

    return experiments, n_pages


def get_num_experiments(self) -> int:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    res = self._session.query(models.Experiment).count()
    if not persist_session:
        self.close_session()
    return res


def delete_experiment(
    self, experiment_id: int,
    commit: bool = True
) -> None:

    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    experiment = self._session.get(models.Experiment, experiment_id)
    if not experiment:
        raise exceptions.ElementDoesNotExist(f"Experiment with id {experiment_id} does not exist")

    for link in self._session.query(models.ExperimentPoolLink).where(
        models.ExperimentPoolLink.experiment_id == experiment_id
    ).all():
        self._session.delete(link)

    for link in self._session.query(models.SeqRequestExperimentLink).where(
        models.SeqRequestExperimentLink.experiment_id == experiment_id
    ).all():
        self._session.delete(link)

    self._session.delete(experiment)
    
    if commit:
        self._session.commit()

    if not persist_session:
        self.close_session()


def update_experiment(
    self, experiment: models.Experiment, commit: bool = True
) -> models.Experiment:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    self._session.add(experiment)

    if commit:
        self._session.commit()
        self._session.refresh(experiment)

    if not persist_session:
        self.close_session()
    return experiment


def add_file_to_experiment(
    self, experiment_id: int, file_id: int,
    commit: bool = True
) -> models.ExperimentFileLink:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    if (_ := self._session.get(models.Experiment, experiment_id)) is None:
        raise exceptions.ElementDoesNotExist(f"Experiment with id '{experiment_id}', not found.")

    if (_ := self._session.get(models.File, file_id)) is None:
        raise exceptions.ElementDoesNotExist(f"File with id '{file_id}', not found.")
    
    file_link = models.ExperimentFileLink(
        experiment_id=experiment_id,
        file_id=file_id
    )
    self._session.add(file_link)

    if commit:
        self._session.commit()
        self._session.refresh(file_link)

    if not persist_session:
        self.close_session()

    return file_link


def remove_file_from_experiment(self, experiment_id: int, file_id: int, commit: bool = True) -> None:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    if (experiment := self._session.get(models.Experiment, experiment_id)) is None:
        raise exceptions.ElementDoesNotExist(f"Experiment with id '{experiment_id}', not found.")

    if (file := self._session.get(models.File, file_id)) is None:
        raise exceptions.ElementDoesNotExist(f"File with id '{file_id}', not found.")
    
    experiment.files.remove(file)
    self._session.add(experiment)

    if commit:
        self._session.commit()

    if not persist_session:
        self.close_session()
    return None