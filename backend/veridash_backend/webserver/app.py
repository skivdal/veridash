import uuid
import json
import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from celery.result import AsyncResult
from .actions import Handler
from veridash_backend.commons.db import Database
from veridash_backend.worker.app import get_objects


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("veridash")


db = Database()
app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        # connection id -> {message type -> (task id, video id)}
        self.active_tasks: dict[str, dict[str, tuple[str, str]]] = {}


    async def connect(self, websocket: WebSocket):
        await websocket.accept()

        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket
        self.active_tasks[client_id] = {}

        logger.debug(f"Connection with {client_id} established")

        return client_id


    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]


    async def send_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_text(message)


    async def receive_message(self, websocket: WebSocket, client_id: str):
        while True:
            res = None

            data = await websocket.receive_json()
            logger.debug(f"Message received from {client_id}: {data}")

            try:
                res = Handler.handle_message(1, data)
            except KeyError as e:
                # likely no messageType present
                err = json.dumps({"error": str(e)})
                await self.send_message(err, client_id)
            except (ValueError, NotImplementedError) as e:
                err = json.dumps({"messageType": data["messageType"], "videoId": data["videoId"], "error": str(e)})
                await self.send_message(err, client_id)

            if res is None:
                continue

            if isinstance(res, tuple):
                # job handling
                task_id, message_type, video_id = res
                self.active_tasks[client_id][message_type] = (task_id, video_id)
            elif isinstance(res, dict):
                # we've got a message to pass to the user
                await self.send_message(json.dumps(res), client_id)


    async def handle_job_updates(self, websocket: WebSocket, client_id: str):
        while True:
            deletions = []
            additions = []

            for message_type, (task_id, video_id) in self.active_tasks[client_id].items():
                result = AsyncResult(task_id)
                if not result.ready():
                    continue

                if result.status == "SUCCESS":
                    if "error" not in result.result and message_type not in ("keyframes", "objectdetection"):
                        db.store_job_result(video_id, message_type, result.result)

                    await websocket.send_json({"messageType": message_type, "videoId": video_id, **result.result})

                    match message_type:
                        case "transcription":
                            pass  # TODO: rerun map task
                        case "keyframes":
                            new_id: str = get_objects.apply_async((video_id, )).id # ignore the error on this line
                            new_triple = ("objectdetection", new_id, video_id)
                            additions.append(new_triple)
                        case "objectdetection":
                            pass  # TODO: rerun osm
                elif result.status == "FAILED":
                    await websocket.send_json({"messageType": message_type, "videoId": video_id, "error": str(result.result)})

                result.forget()
                deletions.append(message_type)

            for d in deletions:
                del self.active_tasks[client_id][d]

            for message_type, task_id, video_id in additions:
                self.active_tasks[client_id][message_type] = (task_id, video_id)

            await asyncio.sleep(0.25)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = await manager.connect(websocket)
    try:
        await asyncio.gather(
                manager.receive_message(websocket, client_id),
                manager.handle_job_updates(websocket, client_id),
        )
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.debug(f"Connection with {client_id} closed")

