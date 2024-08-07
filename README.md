# veridash

Video fact checking and verification dashboard

Currently in development

## TODO:

- [ ] Docs for local setup
- [ ] Sattelite maps (maybe multiple maps to choose from)
- [ ] Stitching
- [ ] Object detection (from lifelog?)
- [ ] OSM-tag extraction (object detection + bellingcat)
- [ ] Dependent tasks specified in comments
- [x] Loading indicators / animations
    - [ ] Actually show progress
- [ ] Multiuser authentication (zitadel/authentik?)
- [ ] Beta deployment (desktop computer + proxy)
- [ ] Production deployment
    - [ ] Dockerfiles for frontend and backend
    - [ ] Backend entrypoint script (worker or server)
    - [x] Backend more extensive settings
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
You will need *Python 3.12* and *ffmpeg* installed on your system.

We also depend on three services, PostgreSQL as a database, Valkey (Redis fork) for handling job scheduling and semaphores, and Minio as a file storage service.
Further, we use the OpenAI API for doing translations using GPT.
Credentials for these services should be defined in the backend `.env` file.

### Local services

#### PostgreSQL

#### Valkey (redis)

#### Minio

### Running the backend

#### Configuring the environment

Copy the file `backend/.env.template` to `backend/.env`.
This is a [dotenv](https://pypi.org/project/python-dotenv/) file,
that stores key-value pairs that will be added to the process environment.

Add your own OpenAI information, minio password, and do any other changes that apply.

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

