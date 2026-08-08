"""Scheduler process entrypoint."""

import argparse
import asyncio
import logging
from collections.abc import Sequence
from dataclasses import asdict

from sqlalchemy.ext.asyncio import create_async_engine

from veridash_scheduler.config import Settings
from veridash_scheduler.reconcile import reconcile_once


def build_parser() -> argparse.ArgumentParser:
    """Build the scheduler command-line parser."""
    parser = argparse.ArgumentParser(description="Run the VeriDash scheduler")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one reconciliation pass and exit.",
    )
    return parser


async def run(*, once: bool, settings: Settings) -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    logger = logging.getLogger(__name__)
    try:
        while True:
            counts = await reconcile_once(engine, settings)
            count_values = asdict(counts)
            if any(count_values.values()):
                logger.info("scheduler reconciliation completed", extra=count_values)
            if once:
                return
            await asyncio.sleep(settings.poll_interval_seconds)
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> None:
    """Run the dependency and liveness reconciler."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(once=args.once, settings=Settings()))
