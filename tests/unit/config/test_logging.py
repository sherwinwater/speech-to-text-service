import logging
from typing import Any, TypedDict, cast

import pytest

from api.config.logging import configure_logging, get_logger


class _LoggerState(TypedDict):
    handlers: list[logging.Handler]
    level: int
    propagate: bool


@pytest.fixture(autouse=True)
def reset_logging():
    root = logging.getLogger()
    original_level = root.level
    original_handlers = list(root.handlers)

    watched_loggers: dict[str, _LoggerState] = {}
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "websockets.protocol", "websockets.server"]:
        logger = logging.getLogger(name)
        watched_loggers[name] = {
            "handlers": list(logger.handlers),
            "level": logger.level,
            "propagate": logger.propagate,
        }

    yield

    root.handlers[:] = []
    for handler in original_handlers:
        root.addHandler(handler)
    root.setLevel(original_level)

    for name, state in watched_loggers.items():
        logger = logging.getLogger(name)
        logger.handlers = list(state["handlers"])
        logger.setLevel(int(state["level"]))
        logger.propagate = bool(state["propagate"])


def test_configure_logging_sets_level_and_handler():
    configure_logging(level="DEBUG")

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert any(isinstance(handler, logging.StreamHandler) for handler in root.handlers)


def test_get_logger_returns_namespaced_logger():
    configure_logging()
    logger = get_logger("transcription")

    assert isinstance(logger, logging.Logger)
    assert logger.name == "server.transcription"


def test_uvicorn_loggers_are_configured():
    configure_logging()

    uvicorn_logger = logging.getLogger("uvicorn")
    assert uvicorn_logger.handlers
    assert not uvicorn_logger.propagate


def test_log_format_is_applied():
    configure_logging()

    root = logging.getLogger()
    handler = root.handlers[0]
    formatter = handler.formatter
    assert formatter is not None
    style = getattr(formatter, "_style", None)
    assert style is not None
    fmt = cast(str, getattr(style, "_fmt", ""))
    assert "%(levelname)" in fmt
    assert "%(name)" in fmt
