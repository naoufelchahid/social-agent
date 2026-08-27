"""Logging configuration without import-time side effects."""

import logging


def configure_logging(verbose: bool = False) -> None:
    """Configure concise application logging for an interactive CLI."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
