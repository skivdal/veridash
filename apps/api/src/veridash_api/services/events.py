"""Authorized finite SSE streams backed by the durable project event log."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from veridash_api.db.sqlc.analyses import AsyncQuerier


def format_sse_event(*, event_id: int, event_type: str, data: object) -> bytes:
    """Encode one newline-safe SSE event with a durable replay cursor."""
    document = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"id: {event_id}\nevent: {event_type}\ndata: {document}\n\n".encode()


async def latest_project_event_id(
    engine: AsyncEngine,
    *,
    user_id: int,
    project_id: UUID,
) -> int:
    async with engine.connect() as connection:
        latest = await AsyncQuerier(connection).get_latest_project_event_id(
            project_id=project_id,
            user_id=user_id,
        )
    if latest is None:
        raise RuntimeError("project event cursor query returned no row")
    return latest


async def stream_project_events(
    engine: AsyncEngine,
    *,
    user_id: int,
    project_id: UUID,
    after_event_id: int,
    send_initial_sync: bool,
    poll_interval_seconds: float,
    keepalive_seconds: float,
    lifetime_seconds: float,
    batch_size: int,
) -> AsyncIterator[bytes]:
    """Replay committed events in order using only short database transactions."""
    cursor = after_event_id
    if send_initial_sync:
        cursor = await latest_project_event_id(
            engine,
            user_id=user_id,
            project_id=project_id,
        )
        yield format_sse_event(
            event_id=cursor,
            event_type="project-sync",
            data={"project_id": str(project_id)},
        )

    started_at = time.monotonic()
    last_sent_at = started_at
    while time.monotonic() - started_at < lifetime_seconds:
        async with engine.connect() as connection:
            events = [
                event
                async for event in AsyncQuerier(connection).list_project_events_after(
                    project_id=project_id,
                    user_id=user_id,
                    after_event_id=cursor,
                    batch_size=batch_size,
                )
            ]
        if events:
            for event in events:
                cursor = event.id
                yield format_sse_event(
                    event_id=event.id,
                    event_type="project-event",
                    data={
                        "id": event.id,
                        "event_type": event.event_type,
                        "payload_version": event.payload_version,
                        "payload": event.payload,
                    },
                )
            last_sent_at = time.monotonic()
            continue
        now = time.monotonic()
        if now - last_sent_at >= keepalive_seconds:
            yield b": keepalive\n\n"
            last_sent_at = now
        await asyncio.sleep(poll_interval_seconds)
