import uuid
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("veridash")


app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()

        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket

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
            data = await websocket.receive_text()
            logger.debug(f"Message received from {client_id}: {data}")


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = await manager.connect(websocket)
    try:
        await manager.receive_message(websocket, client_id)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.debug(f"Connection with {client_id} closed")

