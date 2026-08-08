"""Scheduler process entrypoint."""

import argparse
import logging
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build the scheduler command-line parser."""
    parser = argparse.ArgumentParser(description="Run the VeriDash scheduler")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one reconciliation pass once the scheduler is implemented.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Validate process configuration for the initial scaffold."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).info("scheduler scaffold ready", extra={"once": args.once})
