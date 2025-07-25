from opengsync_db import DBHandler
from opengsync_db.categories import ExperimentWorkFlow

from .create_units import (
    create_user, create_seq_request, create_library, create_pool,
    create_experiment
)  # noqa


def test_experiment_lanes(db: DBHandler):
    user = create_user(db)
    seq_request = create_seq_request(db, user)

    NUM_LIBRARIES = 10
    NUM_POOLS = 5
    PREV_NUM_LANES = len(db.get_lanes(limit=None)[0])

    libraries = []

    for _ in range(NUM_LIBRARIES):
        library = create_library(db, user, seq_request)
        libraries.append(library)

    pools = []

    for i in range(NUM_POOLS):
        pool = create_pool(db, user, seq_request)
        db.add_library_to_pool(libraries[i % NUM_LIBRARIES].id, pool.id)
        pools.append(pool)

    seq_request = db.get_seq_request(seq_request.id)
    assert seq_request is not None
    assert len(seq_request.pools) == NUM_POOLS

    for pool in pools:
        pool = db.get_pool(pool.id)
        assert pool is not None
        assert pool.num_libraries == len(pool.libraries)

    experiment = create_experiment(db, user, ExperimentWorkFlow.NOVASEQ_S4_XP)

    assert ExperimentWorkFlow.NOVASEQ_S4_XP.flow_cell_type.num_lanes == experiment.num_lanes
    assert experiment.num_lanes == len(db.get_lanes(limit=None)[0]) - PREV_NUM_LANES

    for pool in pools:
        db.link_pool_experiment(experiment.id, pool.id)

    experiment = db.get_experiment(experiment.id)
    assert experiment is not None
    assert len(experiment.lanes) == experiment.num_lanes
    assert experiment.num_lanes == experiment.flowcell_type.num_lanes
    assert experiment.num_lanes == ExperimentWorkFlow.NOVASEQ_S4_XP.flow_cell_type.num_lanes

    empty_pool = create_pool(db, user, seq_request)
    db.link_pool_experiment(experiment.id, empty_pool.id)
    lane = db.add_pool_to_lane(experiment.id, pool_id=empty_pool.id, lane_num=1)
    db.refresh(lane)

    assert len(lane.pool_links) == 1

    experiment = db.get_experiment(experiment.id)
    assert experiment is not None
    assert len(experiment.pools) == NUM_POOLS + 1

    experiment = db.get_experiment(experiment.id)
    db.refresh(experiment)
    assert experiment is not None
    for _lane in experiment.lanes:
        if _lane.number == 1:
            assert _lane.id == lane.id
            assert len(_lane.pool_links) == 1
        else:
            assert _lane.id != lane.id
            assert len(_lane.pool_links) == 0

    lane = db.remove_pool_from_lane(experiment.id, empty_pool.id, 1)
    db.refresh(lane)
    assert len(lane.pool_links) == 0

    experiment = db.get_experiment(experiment.id)
    assert experiment is not None
    assert len(experiment.pools) == NUM_POOLS + 1

    experiment = db.get_experiment(experiment.id)
    db.refresh(experiment)
    assert experiment is not None
    for lane in experiment.lanes:
        assert len(lane.pool_links) == 0

    for i, pool in enumerate(pools):
        db.add_pool_to_lane(experiment.id, pool.id, (i % experiment.num_lanes) + 1)

    counter = 0
    experiment = db.get_experiment(experiment.id)
    db.refresh(experiment)
    assert experiment is not None
    for lane in experiment.lanes:
        db.refresh(lane)
        counter += len(lane.pool_links)

    assert counter == len(pools)

    # Decrease number of lanes
    experiment.workflow_id = ExperimentWorkFlow.NOVASEQ_S2_XP.id
    experiment = db.update_experiment(experiment)
    db.refresh(experiment)
    assert len(db.get_lanes(limit=None)[0]) == PREV_NUM_LANES + ExperimentWorkFlow.NOVASEQ_S2_XP.flow_cell_type.num_lanes

    experiment = db.get_experiment(experiment.id)
    db.refresh(experiment)
    assert experiment is not None
    assert experiment.workflow == ExperimentWorkFlow.NOVASEQ_S2_XP
    assert experiment.num_lanes == ExperimentWorkFlow.NOVASEQ_S2_XP.flow_cell_type.num_lanes
    assert experiment.num_lanes == len(experiment.lanes)

    # Increase number of lanes
    experiment.workflow_id = ExperimentWorkFlow.NOVASEQ_S4_XP.id
    experiment = db.update_experiment(experiment)
    db.flush()
    db.refresh(experiment)
    assert len(db.get_lanes(limit=None)[0]) == PREV_NUM_LANES + ExperimentWorkFlow.NOVASEQ_S4_XP.flow_cell_type.num_lanes

    experiment = db.get_experiment(experiment.id)
    db.refresh(experiment)
    assert experiment is not None
    assert experiment.workflow == ExperimentWorkFlow.NOVASEQ_S4_XP
    assert experiment.num_lanes == ExperimentWorkFlow.NOVASEQ_S4_XP.flow_cell_type.num_lanes
    assert experiment.num_lanes == len(experiment.lanes)

    # STD workflow - combined lanes
    experiment.workflow_id = ExperimentWorkFlow.NOVASEQ_S4_STD.id
    experiment = db.update_experiment(experiment)
    db.flush()
    db.refresh(experiment)
    assert len(db.get_lanes(limit=None)[0]) == PREV_NUM_LANES + ExperimentWorkFlow.NOVASEQ_S4_STD.flow_cell_type.num_lanes
    experiment = db.get_experiment(experiment.id)
    db.refresh(experiment)
    assert experiment is not None
    assert experiment.workflow == ExperimentWorkFlow.NOVASEQ_S4_STD
    assert experiment.num_lanes == ExperimentWorkFlow.NOVASEQ_S4_STD.flow_cell_type.num_lanes

    for pool in experiment.pools:
        db.refresh(pool)
        assert len(pool.lane_links) == ExperimentWorkFlow.NOVASEQ_S4_STD.flow_cell_type.num_lanes

    # Decrease Lanes
    experiment.workflow_id = ExperimentWorkFlow.NOVASEQ_S1_STD.id
    experiment = db.update_experiment(experiment)

    assert len(db.get_lanes(limit=None)[0]) == PREV_NUM_LANES + ExperimentWorkFlow.NOVASEQ_S1_STD.flow_cell_type.num_lanes
    experiment = db.get_experiment(experiment.id)
    db.refresh(experiment)
    assert experiment is not None
    assert experiment.workflow == ExperimentWorkFlow.NOVASEQ_S1_STD
    assert experiment.num_lanes == ExperimentWorkFlow.NOVASEQ_S1_STD.flow_cell_type.num_lanes

    for pool in experiment.pools:
        db.refresh(pool)
        assert len(pool.lane_links) == ExperimentWorkFlow.NOVASEQ_S1_STD.flow_cell_type.num_lanes

    # Delete experiment
    db.delete_experiment(experiment.id)
    assert len(db.get_lanes(limit=None)[0]) == PREV_NUM_LANES

    for pool in pools:
        db.refresh(pool)
        assert pool is not None
        assert len(pool.lane_links) == 0