FROM python:3.11.3-slim-buster

# set work directory
WORKDIR /usr/src/app

# install dependencies
RUN apt update
RUN apt install build-essential -y
RUN apt install libpq-dev -y
RUN apt install curl -y
RUN apt install postgresql-client -y
RUN apt install fuse -y
RUN apt install rclone -y
RUN pip install --upgrade pip
COPY . /usr/src/app/
RUN pip install -r /usr/src/app/limbless-db/requirements.txt
RUN pip install /usr/src/app/limbless-db
RUN pip install -r /usr/src/app/limbless-server/requirements.txt
RUN pip install /usr/src/app/limbless-server
RUN chmod +x /usr/src/app/entrypoint.sh

ENTRYPOINT ["/usr/src/app/entrypoint.sh"]