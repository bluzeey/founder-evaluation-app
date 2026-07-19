import logging
import os
import sys


def configure_logging() -> None:
    """Configure a consistent stdout log format for the whole backend."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = (
        "%(asctime)s | %(levelname)s | %(name)s | "
        "%(message)s"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid adding duplicate handlers when this is imported multiple times.
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)

    # Make sure third-party libraries are not too noisy unless requested.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO if level <= logging.INFO else level)
