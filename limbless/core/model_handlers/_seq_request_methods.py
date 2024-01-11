import math
from datetime import datetime
from typing import Optional

from sqlmodel import func, or_

from ... import models, PAGE_LIMIT, logger
from ...categories import SeqRequestStatus, SequencingType, FlowCellType
from .. import exceptions


def create_seq_request(
    self, name: str,
    description: Optional[str],
    requestor_id: int,
    technology: str,
    contact_person_id: int,
    billing_contact_id: int,
    seq_type: SequencingType,
    organization_name: str,
    organization_address: str,
    num_cycles_read_1: Optional[int] = None,
    num_cycles_index_1: Optional[int] = None,
    num_cycles_index_2: Optional[int] = None,
    num_cycles_read_2: Optional[int] = None,
    read_length: Optional[int] = None,
    num_lanes: Optional[int] = None,
    special_requirements: Optional[str] = None,
    sequencer: Optional[str] = None,
    flowcell_type: Optional[FlowCellType] = None,
    bioinformatician_contact_id: Optional[int] = None,
    organization_department: Optional[str] = None,
    billing_code: Optional[str] = None,
    commit: bool = True
) -> models.SeqRequest:

    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    if (requestor := self._session.get(models.User, requestor_id)) is None:
        raise exceptions.ElementDoesNotExist(f"User with id '{requestor_id}', not found.")

    if self._session.get(models.Contact, billing_contact_id) is None:
        raise exceptions.ElementDoesNotExist(f"Contact with id '{billing_contact_id}', not found.")

    if self._session.get(models.Contact, contact_person_id) is None:
        raise exceptions.ElementDoesNotExist(f"Contact with id '{contact_person_id}', not found.")

    if bioinformatician_contact_id is not None:
        if self._session.get(models.Contact, bioinformatician_contact_id) is None:
            raise exceptions.ElementDoesNotExist(f"Contact with id '{bioinformatician_contact_id}', not found.")
        
    seq_request = models.SeqRequest(
        name=name,
        description=description,
        requestor_id=requestor_id,
        technology=technology,
        sequencing_type_id=seq_type.value.id,
        num_cycles_read_1=num_cycles_read_1,
        num_cycles_index_1=num_cycles_index_1,
        num_cycles_index_2=num_cycles_index_2,
        num_cycles_read_2=num_cycles_read_2,
        read_length=read_length,
        num_lanes=num_lanes,
        special_requirements=special_requirements,
        sequencer=sequencer,
        flowcell_type_id=flowcell_type.value.id if flowcell_type is not None else None,
        billing_contact_id=billing_contact_id,
        contact_person_id=contact_person_id,
        bioinformatician_contact_id=bioinformatician_contact_id,
        status_id=SeqRequestStatus.DRAFT.value.id,
        submitted_time=None,
        organization_name=organization_name,
        organization_department=organization_department,
        organization_address=organization_address,
        billing_code=billing_code,
    )

    requestor.num_seq_requests += 1
    self._session.add(seq_request)
    if commit:
        self._session.commit()
        self._session.refresh(seq_request)

    if not persist_session:
        self.close_session()
    return seq_request


def get_seq_request(
    self, seq_request_id: int,
) -> models.SeqRequest:

    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    seq_request = self._session.get(models.SeqRequest, seq_request_id)

    if not persist_session:
        self.close_session()
    return seq_request


def get_seq_requests(
    self, limit: Optional[int] = PAGE_LIMIT, offset: Optional[int] = None,
    with_statuses: Optional[list[SeqRequestStatus]] = None,
    show_drafts: bool = True,
    sample_id: Optional[int] = None,
    experiment_id: Optional[int] = None,
    exclude_experiment_id: Optional[int] = None,
    sort_by: Optional[str] = None, descending: bool = False,
    user_id: Optional[int] = None
) -> tuple[list[models.SeqRequest], int]:

    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    query = self._session.query(models.SeqRequest)

    if user_id is not None:
        query = query.where(
            models.SeqRequest.requestor_id == user_id
        )

    if with_statuses is not None:
        status_ids = [status.value.id for status in with_statuses]
        query = query.where(
            models.SeqRequest.status_id.in_(status_ids)
        )

    if not show_drafts:
        query = query.where(
            models.SeqRequest.status_id != SeqRequestStatus.DRAFT.value.id
        )

    if sample_id is not None:
        query = query.join(
            models.SeqRequestLibraryLink,
            models.SeqRequestLibraryLink.seq_request_id == models.SeqRequest.id,
            isouter=True
        ).where(
            models.SeqRequestLibraryLink.library_id == sample_id
        )

    if experiment_id is not None:
        query = query.join(
            models.SeqRequestExperimentLink,
            models.SeqRequestExperimentLink.seq_request_id == models.SeqRequest.id,
            isouter=True
        ).where(
            models.SeqRequestExperimentLink.experiment_id == experiment_id
        )

    if exclude_experiment_id is not None:
        query = query.join(
            models.SeqRequestExperimentLink,
            models.SeqRequestExperimentLink.seq_request_id == models.SeqRequest.id,
            isouter=True
        ).where(
            or_(
                models.SeqRequestExperimentLink.experiment_id != exclude_experiment_id,
                models.SeqRequestExperimentLink.experiment_id == None
            )
        )

    if sort_by is not None:
        attr = getattr(models.SeqRequest, sort_by)
        if descending:
            attr = attr.desc()
        query = query.order_by(attr.nullslast())

    n_pages: int = math.ceil(query.count() / limit) if limit is not None else 1

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    seq_requests = query.all()

    if not persist_session:
        self.close_session()

    return seq_requests, n_pages


def get_num_seq_requests(
    self, user_id: Optional[int] = None,
    with_statuses: Optional[list[SeqRequestStatus]] = None,
) -> int:

    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    query = self._session.query(models.SeqRequest)

    if user_id is not None:
        query = query.where(
            models.SeqRequest.requestor_id == user_id
        )

    if with_statuses is not None:
        status_ids = [status.value.id for status in with_statuses]
        query = query.where(
            models.SeqRequest.status_id.in_(status_ids)
        )

    num_seq_requests = query.count()

    if not persist_session:
        self.close_session()
    return num_seq_requests


def submit_seq_request(
    self, seq_request_id: int,
    commit: bool = True
) -> models.SeqRequest:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    if (seq_request := self._session.get(models.SeqRequest, seq_request_id)) is None:
        raise exceptions.ElementDoesNotExist(f"SeqRequest with id '{seq_request}', not found.")

    seq_request.status_id = SeqRequestStatus.SUBMITTED.value.id
    seq_request.submitted_time = datetime.now()
    for library in seq_request.libraries:
        library.submitted = True
        self._session.add(library)

    if commit:
        self._session.commit()
        self._session.refresh(seq_request)

    if not persist_session:
        self.close_session()

    return seq_request


def update_seq_request(
    self, seq_request: models.SeqRequest,
    commit: bool = True
) -> models.SeqRequest:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    self._session.add(seq_request)

    if commit:
        self._session.commit()
        self._session.refresh(seq_request)
        self._session.refresh(seq_request.billing_contact)
        self._session.refresh(seq_request.contact_person)
        if seq_request.bioinformatician_contact_id is not None:
            self._session.refresh(seq_request.bioinformatician_contact)

    if not persist_session:
        self.close_session()

    return seq_request


def delete_seq_request(
    self, sample_id: int,
    commit: bool = True
) -> None:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    seq_request = self._session.get(models.SeqRequest, sample_id)
    if not seq_request:
        raise exceptions.ElementDoesNotExist(f"SeqRequest with id {sample_id} does not exist")

    links = self._session.query(models.SeqRequestLibraryLink).where(
        models.SeqRequestLibraryLink.seq_request_id == seq_request.id
    ).all()
    
    for link in links:
        self._session.delete(link)

    # self._session.delete(seq_request.contact_person)
    # self._session.delete(seq_request.billing_contact)
    # if seq_request.bioinformatician_contact_id is not None:
    #     self._session.delete(seq_request.bioinformatician_contact)

    self._session.delete(seq_request)
    if commit:
        self._session.commit()

    if not persist_session:
        self.close_session()


def query_seq_requests(
    self, word: str,
    user_id: Optional[int] = None,
    limit: Optional[int] = PAGE_LIMIT,
) -> list[models.SeqRequest]:
    persist_session = self._session is not None
    if not self._session:
        self.open_session()

    query = self._session.query(models.SeqRequest)

    if user_id is not None:
        query = query.where(
            models.SeqRequest.requestor_id == user_id
        )

    query = query.order_by(
        func.similarity(models.SeqRequest.name, word).desc()
    )

    if limit is not None:
        query = query.limit(limit)

    seq_requests = query.all()

    if not persist_session:
        self.close_session()
    return seq_requests