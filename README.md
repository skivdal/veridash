# veridash

Video fact checking and verification dashboard

## Developing

Ensure you have a working development setup by following the guide for [local development setup](#Local-development-setup).

Development plans and task allocation is done using Github Issues in this repository, connected to [this Github project](https://github.com/users/skivdal/projects/1).
The life of a new feature will look something like this:
1. Feature is imagined, and an issue is created in the repo
2. This issue is assigned to a person, and added to the "veridash - development" project board with the status of 'ready'.
3. The feature is described in sufficient detail
4. Issue assignee creates a branch out of main for this feature, and moves the issue to the 'in progress' column of the project board.
5. Assignee implements the feature on their branch
6. Assignee creates a pull request documenting how the issue was solved, and marks it with "closing #\[issue number\]"
7. Assignee merges the pull request into the main branch. Alternatively, for larger features, another participant can review the pull request first.
8. Assignee moves the issue to the 'Done' column of the project board.


### TODO

This list is for tasks not yet added as an Issue to the project board.

- [ ] Sattelite maps (maybe multiple maps to choose from)
- [ ] Stitching
- [ ] Object detection (from lifelog?)
- [ ] OSM-tag extraction (object detection + bellingcat)
- [ ] Dependent tasks specified in comments
- [ ] Multiuser authentication (zitadel/authentik?)
- [ ] Production deployment
    - [ ] Dockerfiles for frontend and backend
    - [ ] Backend entrypoint script (worker or server)
    - [ ] nginx config
    - [ ] docker-compose with all services
- [ ] "Go back to a case" user video archive
- [ ] Redundant upload reduction with hash matching

## Local development setup

This project is divided into two subdirectories: `frontend/` and `backend/`.

The frontend is a Next.js (React) appliation that requires Node and NPM.
I'm using *Node v20.11.0*, and *npm 10.2.4*. Node v20 or later should work. NPM version is probably not too important.

The backend is written in Python, divided into a FastAPI application for handling requests and responses over a WebSocket.
There's also a Celery application responsible for handling heavy tasks. 
You will need *Python 3.12*, *ffmpeg*, and a *postgresql client library* installed on your system.

We also depend on three services, PostgreSQL as a database, Valkey (Redis fork) for handling job scheduling and semaphores, and Minio as a file storage service.
Further, we use the OpenAI API for doing translations using GPT.
Credentials for these services should be defined in the backend `.env` file.

### Local services

The local services required can be ran in docker containers. To do this, first ensure you have docker installed:
[https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/).

The containers will forward ports. If you see an error when creating the containers, you might already have a service running on that port.
When coming back to your computer to develop at a later date, ensure docker and the containers are running.

#### PostgreSQL

1. Ensure you have the appropriate Postgres client library on your computer (this is needed for step 4 and the Python driver).
2. Create a container running the service: `docker run --name veridash-postgres -e POSTGRES_PASSWORD=mysecretpassword -e POSTGRES_DB=veridash -p 127.0.0.1:5432:5432 -d postgres:16-alpine`
3. Go to the backend directory of this repository: `cd backend/`
4. Access the database through the CLI: `psql --host 127.0.0.1 --user postgres`
5. Enter the password from the POSTGRES_PASSWORD variable in the command at step 2.
6. Change to the veridash database: `\c veridash;`
7. Load the database schema: `\i schema.sql;`
8. Create a dummy user in the database: `INSERT INTO users (email, password_hash, totp_key) VALUES ('dummy@example.com', 'todo', 'todo');`
9. Exit the CLI with Ctrl+D. Alternatively, do: `\d;` to list the objects in the schema and explore the database.
10. Add the following entry to the .env file in the backend directory: `POSTGRES_CONN_STR="host=127.0.0.1 dbname=veridash user=postgres password=mysecretpassword"`

#### Valkey (redis)

1. Create a container running the service: `docker run --name veridash-valkey -p 127.0.0.1:6379:6379 -d valkey/valkey:7-alpine`
2. Add the following entries to the .env file in the backend directory:
```
REDIS_HOST="localhost"
REDIS_PORT=6379
REDIS_DB=0
```

#### Minio

1. Create a container running the service: `docker run --name veridash-minio -p 127.0.0.1:9000:9000 -p 127.0.0.1:9001:9001 -d minio/minio:RELEASE.2024-08-03T04-33-23Z server /data --console-address ":9001"`
2. Get a shell in the container: `docker exec -it veridash-minio bash`
3. Set the CLI credentials in the container: `mc alias set local http://localhost:9000 minioadmin minioadmin`
4. Create the "veridash" bucket for storing files: `mc mb local/veridash`
5. Exit the CLI with Ctrl+D
6. Add the following entires to the .env file in the backend directory:
```
MINIO_HOST="localhost:9000"
MINIO_SECURE=false
MINIO_USER="minioadmin"
MINIO_PASS="minioadmin"
MINIO_BUCKET="veridash"
```

You can access an admin interface at [localhost:9001](http://localhost:9001) with the credentials minioadmin minioadmin.
Use this to periodically delete files from the veridash bucket if you need to reclaim disk space.

### Running the backend

#### Configuring the environment

Concider the the file `backend/.env.template` in comparison to `backend/.env`.
This is a [dotenv](https://pypi.org/project/python-dotenv/) file,
that stores key-value pairs that will be added to the process environment.

Add any missing information. If you've followed the instructions to run services in docker containers, you'll be missing the following:
```
TEMP_STORAGE_DIR="/tmp/veridash"

OPENAI_ORG=""
OPENAI_PROJECT=""
OPENAI_API_KEY=""
```

The OpenAI credentials are not a requirement, but is needed to provide translations for video transcripts, and other GPT-based modules.

`TEMP_STORAGE_DIR` might need a different value if on Windows, and there might be some bugs pertaining to how file paths are made that can cause errors if running the program there. Fixes should be simple enough.

Note that the reccomended value `/tmp` is stored in memory (RAM) on most Linux systems. Consider changing the path if you experience problems related to low RAM availiability. MacOS users should not experience this issue.

#### Installing dependencies

You will need the [Poetry](https://python-poetry.org/) package manager for Python.
If you don't have it installed, follow [this guide](https://python-poetry.org/docs/#installation).

Navigate to the `backend/` directory. Executing `poetry install` should create a virtual environment and add all dependencies.

Adding additional dependencies in the future can be done with the `poetry add [package-name]` command.

#### Running FastAPI

With all dependencies installed, in the `backend/` directory, run `poetry shell` to activate the virtual environment.

Then run `uvicorn veridash_backend.webserver.app:app --reload` to start the application.
This will automatically reload when the source files change.

#### Running Celery

With all dependencies installed, in the `backend/` directory, run `poetry shell` to activate the virtual environment.

Then run `celery -A veridash_backend.worker.app worker` to start the backend worker processes.
This **won't** automatically reload when the source files change.
Remember to stop the process with ^C (Ctrl+C), and rerun the command if you change the backend task code.

Transcription task might take a while the first time as the Whisper model will have to be downloaded. This happens automatically.

### Running the frontend

#### Installing dependencies

Navigate to the `frontend/` directory. Executing `npm install` should grab all required dependencies.

If you want to add an additional dependency in the future: `npm install -S [package-name]`.
Remembering the `-S` is important as this saves the dependency in `package.json` for other people to install later.

#### Running Next

In the frontend directory: `npm run dev`.
This starts a development server, that will automatically reload the page on file changes.
The page should be accessible on [localhost:3000](http://localhost:3000)

Note that initial connection to the backend websocket can be shaky with the development server,
I recommend manually reloading the page on first visit.

