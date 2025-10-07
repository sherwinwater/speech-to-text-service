import pytest

from api.config.settings import Settings


def test_default_values():
    settings = Settings()

    assert settings.model_size == "small"
    assert settings.compute_type == "int8"
    assert settings.max_file_mb == 30
    assert settings.max_duration_sec == 3600
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000


def test_environment_override(monkeypatch):
    monkeypatch.setenv("MODEL_SIZE", "large")
    monkeypatch.setenv("COMPUTE_TYPE", "float16")
    monkeypatch.setenv("MAX_FILE_MB", "10")
    monkeypatch.setenv("MAX_DURATION_SEC", "120")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9000")

    settings = Settings()

    assert settings.model_size == "large"
    assert settings.compute_type == "float16"
    assert settings.max_file_mb == 10
    assert settings.max_duration_sec == 120
    assert settings.host == "127.0.0.1"
    assert settings.port == 9000


def test_numeric_environment_coercion(monkeypatch):
    monkeypatch.setenv("MAX_FILE_MB", "42")
    monkeypatch.setenv("MAX_DURATION_SEC", "360")
    monkeypatch.setenv("PORT", "1234")

    settings = Settings()

    assert isinstance(settings.max_file_mb, int)
    assert isinstance(settings.max_duration_sec, int)
    assert isinstance(settings.port, int)
    assert settings.max_file_mb == 42
    assert settings.max_duration_sec == 360
    assert settings.port == 1234
