"""Worker supervisor process entrypoint."""

import argparse
import logging
from collections.abc import Sequence

from veridash_core.resources import ResourceClass, default_concurrency


def build_parser() -> argparse.ArgumentParser:
    """Build the worker command-line parser."""
    parser = argparse.ArgumentParser(description="Run a VeriDash worker pool")
    parser.add_argument(
        "--pool",
        choices=tuple(resource.value for resource in ResourceClass),
        default=ResourceClass.CPU.value,
    )
    parser.add_argument("--concurrency", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Validate worker-pool configuration for the initial scaffold."""
    args = build_parser().parse_args(argv)
    pool = ResourceClass(args.pool)
    concurrency = args.concurrency or default_concurrency(pool)
    if concurrency < 1:
        raise SystemExit("concurrency must be at least one")
    if pool is ResourceClass.GPU and concurrency > 2:
        raise SystemExit("GPU concurrency cannot exceed the deployment limit of two")

    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).info(
        "worker scaffold ready",
        extra={"pool": pool.value, "concurrency": concurrency},
    )
