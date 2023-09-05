from limbless.core import DBHandler
from limbless import categories


def create_sample_experiment(db_handler: DBHandler):
    user = db_handler.create_user(
        email="test@user.com",
        password="password",
        role=categories.UserRole.ADMIN
    )
    projects = [
        db_handler.create_project(
            name=f"Project_{i+1:02d}",
            description=f"Project_{i+1:02d} description"
        ) for i in range(10)
    ]

    db_handler.create_organism(
        tax_id=9606,
        scientific_name="Homo sapiens",
        common_name="human",
        category=categories.OrganismCategory.EUKARYOTA,
    )

    db_handler.create_organism(
        tax_id=10090,
        scientific_name="Mus musculus",
        common_name="house mouse",
        category=categories.OrganismCategory.EUKARYOTA,
    )

    for project in projects:
        db_handler.link_project_user(project.id, user.id, categories.ProjectRole.OWNER)

    samples = [
        db_handler.create_sample(
            f"Sample_{i+1:02d}",
            9606 if i < 100 else 10090,
            projects[i % len(projects)].id,
        ) for i in range(200)
    ]

    libs = [
        db_handler.create_library(
            f"Library_{i+1:02d}",
            categories.LibraryType.SC_RNA,
            (i % 5) + 1,
        ) for i in range(20)
    ]

    n_seqindices = db_handler.get_num_seqindices()
    for i, sample in enumerate(samples):
        db_handler.link_library_sample(
            libs[i % len(libs)].id, sample.id,
            seq_index_id=(i % n_seqindices) + 1
        )

    experiments = [
        db_handler.create_experiment(
            f"Experiment_{i+1:02d}",
            f"Flowcell_{i+1:02d}"
        ) for i in range(10)
    ]

    runs = []
    for i, experiment in enumerate(experiments):
        runs.append(
            db_handler.create_run(
                1, experiment.id, 1, 2, 3, 4,
            )
        )
        if i % 2 == 0:
            runs.append(
                db_handler.create_run(
                    2, experiment.id, 1, 2, 3, 4,
                )
            )

    for i, library in enumerate(libs):
        db_handler.link_run_library(runs[i % len(runs)].id, library.id)
