from typing import Any

import pytest

from api.main import app, app_lifespan


@pytest.mark.asyncio
async def test_app_lifespan_runs_logging(monkeypatch):
    captured: dict[str, Any] = {"messages": []}

    def fake_configure_logging():
        captured["configured"] = True

    class DummyLogger:
        def info(self, message: str):
            captured["messages"].append(message)

    monkeypatch.setattr("api.main.configure_logging", fake_configure_logging)
    monkeypatch.setattr("api.main.get_logger", lambda name: DummyLogger())

    async with app_lifespan(app):
        captured["entered"] = True

    assert captured["configured"] is True
    assert captured["entered"] is True
    assert any("Application starting up" in msg for msg in captured["messages"])  # ensure logging path hit
