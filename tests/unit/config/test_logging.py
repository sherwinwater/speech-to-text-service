import logging

import pytest

from api.config.logging import configure_logging, get_logger


@pytest.fixture(autouse=True)
def reset_logging():
    root = logging.getLogger()
    original_level = root.level
    original_handlers = root.handlers[:]

    watched_loggers = {}
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "websockets.protocol", "websockets.server"]:
        logger = logging.getLogger(name)
        watched_loggers[name] = {
            "handlers": logger.handlers[:],
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
        logger.handlers = state["handlers"]
        logger.setLevel(state["level"])
        logger.propagate = state["propagate"]


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
    formatter = root.handlers[0].formatter

    assert "%(levelname)" in formatter._style._fmt
    assert "%(name)" in formatter._style._fmt
