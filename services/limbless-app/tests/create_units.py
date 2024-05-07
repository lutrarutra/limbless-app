import uuid

from limbless_db import DBHandler, DBSession, models
from limbless_db.categories import (
    LibraryType, DataDeliveryMode, UserRole, FeatureType, FlowCellType, ExperimentWorkFlow, ExperimentWorkFlowEnum, SequencerModel,
    ReadType
)


def create_user(db: DBHandler) -> models.User:
    _uuid = str(uuid.uuid1())
    return db.create_user(
        email=f"{_uuid}@email.com",
        first_name=_uuid,
        last_name=_uuid,
        role=UserRole.ADMIN,
        hashed_password=_uuid,
    )
    

def create_project(db: DBHandler, user: models.User) -> models.Project:
    _uuid = str(uuid.uuid1())
    return db.create_project(
        name=_uuid,
        description=_uuid,
        owner_id=user.id,
    )


def create_contact(db: DBHandler) -> models.Contact:
    _uuid = str(uuid.uuid1())
    return db.create_contact(
        name=_uuid,
    )


def create_seq_request(db: DBHandler, user: models.User) -> models.SeqRequest:
    _uuid = str(uuid.uuid1())
    contact = create_contact(db)
    organization = create_contact(db)
    return db.create_seq_request(
        name=_uuid,
        data_delivery_mode=DataDeliveryMode.ALIGNMENT,
        description=_uuid,
        requestor_id=user.id,
        read_type=ReadType.PAIRED_END,
        organization_contact_id=organization.id,
        contact_person_id=contact.id,
        billing_contact_id=contact.id,
    )


def create_sample(db: DBHandler, user: models.User, project: models.Project) -> models.Sample:
    _uuid = str(uuid.uuid1())
    return db.create_sample(
        name=_uuid,
        owner_id=user.id,
        project_id=project.id,
    )


def create_library(db: DBHandler, user: models.User, seq_request: models.SeqRequest) -> models.Library:
    _uuid = str(uuid.uuid1())
    return db.create_library(
        name=_uuid,
        owner_id=user.id,
        seq_request_id=seq_request.id,
        library_type=LibraryType.BULK_RNA_SEQ,
    )


def create_pool(db: DBHandler, user: models.User, seq_request: models.SeqRequest) -> models.Pool:
    _uuid = str(uuid.uuid1())
    return db.create_pool(
        name=_uuid,
        owner_id=user.id,
        contact_name=_uuid,
        contact_email=_uuid,
        seq_request_id=seq_request.id,
    )


def create_feature(db: DBHandler) -> models.Feature:
    return db.create_feature(
        name="name",
        sequence="sequence",
        pattern="pattern",
        read="read",
        type=FeatureType.ANTIBODY
    )


def create_sequencer(db: DBHandler) -> models.Sequencer:
    return db.create_sequencer(
        name="sequencer",
        model=SequencerModel.NOVA_SEQ_6000,
    )


def create_experiment(db: DBHandler, user: models.User, workflow: ExperimentWorkFlowEnum) -> models.Experiment:
    _uuid = str(uuid.uuid1())
    return db.create_experiment(
        name=_uuid[:5],
        workflow=workflow,
        sequencer_id=create_sequencer(db).id,
        r1_cycles=1,
        i1_cycles=1,
        operator_id=user.id,
        r2_cycles=1,
        i2_cycles=1,
    )