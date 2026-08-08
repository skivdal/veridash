"""Worker supervisor process entrypoint."""

import argparse
import asyncio
import logging
import os
import socket
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import create_async_engine
from veridash_core.resources import ResourceClass, default_concurrency

from veridash_worker.config import Settings
from veridash_worker.supervisor import claim_once, supervise_attempt


def build_parser() -> argparse.ArgumentParser:
    """Build the worker command-line parser."""
    parser = argparse.ArgumentParser(description="Run a VeriDash worker pool")
    parser.add_argument(
        "--pool",
        choices=tuple(resource.value for resource in ResourceClass),
        default=ResourceClass.CPU.value,
    )
    parser.add_argument("--concurrency", type=int)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Give each pool slot one opportunity to claim a job, then exit.",
    )
    return parser


def validate_concurrency(pool: ResourceClass, concurrency: int | None) -> int:
    """Resolve and validate resource-pool concurrency."""
    resolved = concurrency or default_concurrency(pool)
    if resolved < 1:
        raise SystemExit("concurrency must be at least one")
    if pool is ResourceClass.GPU and resolved > 2:
        raise SystemExit("GPU concurrency cannot exceed the deployment limit of two")
    return resolved


async def run(
    *,
    pool: ResourceClass,
    concurrency: int,
    once: bool,
    settings: Settings,
) -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    identity = f"{socket.gethostname()}-{os.getpid()}-{pool.value}"

    async def run_slot(slot: int) -> None:
        worker_id = f"{identity}-{slot}"
        while True:
            claim = await claim_once(
                engine,
                resource_class=pool,
                worker_id=worker_id,
                settings=settings,
            )
            if claim is not None:
                outcome = await supervise_attempt(engine, claim, settings)
                logging.getLogger(__name__).info(
                    "analysis attempt finished",
                    extra={"job_id": str(outcome.job_id), "state": outcome.state},
                )
            if once:
                return
            if claim is None:
                await asyncio.sleep(settings.poll_interval_seconds)

    try:
        async with asyncio.TaskGroup() as group:
            for slot in range(concurrency):
                group.create_task(run_slot(slot), name=f"{pool.value}-worker-{slot}")
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> None:
    """Run a supervised worker pool for one resource class."""
    args = build_parser().parse_args(argv)
    pool = ResourceClass(args.pool)
    concurrency = validate_concurrency(pool, args.concurrency)

    logging.basicConfig(level=logging.INFO)
    asyncio.run(
        run(
            pool=pool,
            concurrency=concurrency,
            once=args.once,
            settings=Settings(),
        )
    )
