# limbless
Web app for NGS sample/library/project tracking

## Installation
    - `pip install -r requirements.txt`

## Run flask debug server
    - `docker compose up`
    - `flask run`

## pgAdmin Interface
    - `http://localhost:5050`
    - username: `$(PGADMIN_EMAIL)`
    - password: `$(PGADMIN_PASSWORD)`

## pgAdmin Server Setup
    - host: `host.docker.internal`
    - port: `5432`
    - username: `$(POSTGRES_USER)`
    - password: `$(POSTGRES_PASSWORD)`

If host `host.docker.internal` does not work, try `docker inspect limbless_postgres_1 | grep IPAddress` and use the IP address of the container:
    - `docker ps`
    - `docker inspect <container_id> | grep IPAddress`