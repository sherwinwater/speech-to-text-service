import importlib
import importlib.abc
import importlib.machinery
import sys
import types
from typing import Any, cast

import pytest

from api.config.settings import Settings
from api.config.settings_dev import DevSettings, settings as dev_settings
from api.config.settings_prod import ProdSettings, settings as prod_settings
from api.config.settings_qa import QaSettings, settings as qa_settings


def test_default_values():
    settings = Settings()

    assert settings.model_size == "small"
    assert settings.compute_type == "int8"
    assert settings.max_file_mb == 100
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


def test_base_settings_fallback(monkeypatch):
    fake_pydantic = cast(Any, types.ModuleType("pydantic"))

    class FakeBaseSettings:  # pragma: no cover - simple stub container
        pass

    fake_pydantic.BaseSettings = FakeBaseSettings
    monkeypatch.setitem(sys.modules, "pydantic", fake_pydantic)

    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pydantic_settings":
            raise ImportError("pydantic_settings missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    sys.modules.pop("api.config.settings", None)

    try:
        module = importlib.import_module("api.config.settings")
        assert issubclass(module.Settings, FakeBaseSettings)
    finally:
        sys.modules.pop("api.config.settings", None)


def test_get_settings_selects_env(monkeypatch):
    settings_module = importlib.import_module("api.config.settings")
    settings_module = importlib.reload(settings_module)
    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "qa")

    resolved = settings_module.get_settings()

    assert resolved.host == "0.0.0.0"
    assert resolved.port == 8080


def test_get_settings_invalid_env(monkeypatch):
    settings_module = importlib.import_module("api.config.settings")
    settings_module = importlib.reload(settings_module)
    settings_module.get_settings.cache_clear()

    with pytest.raises(ValueError, match="Unsupported APP_ENV 'staging'"):
        settings_module.get_settings("staging")


def test_get_settings_requires_appsettings(monkeypatch):
    settings_module = importlib.import_module("api.config.settings")
    settings_module = importlib.reload(settings_module)
    settings_module.get_settings.cache_clear()

    fake_module = types.ModuleType("api.config.settings_fake")

    class DummyLoader(importlib.abc.Loader):  # type: ignore[misc]
        def create_module(self, spec):
            return fake_module

        def exec_module(self, module):
            return None

    loader = DummyLoader()
    spec = importlib.machinery.ModuleSpec("api.config.settings_fake", loader)
    loader.create_module(spec)
    loader.exec_module(fake_module)
    fake_module.__spec__ = spec
    fake_module.__loader__ = loader
    setattr(fake_module, "settings", object())

    monkeypatch.setitem(sys.modules, "api.config.settings_fake", fake_module)
    monkeypatch.setitem(
        settings_module._SETTINGS_MODULES, "fake", "api.config.settings_fake"
    )
    real_reload = importlib.reload

    def _guarded_reload(module):
        if module is fake_module:
            return module
        return real_reload(module)

    monkeypatch.setattr(importlib, "reload", _guarded_reload)
    _guarded_reload(importlib.import_module("math"))

    with pytest.raises(TypeError, match="settings_fake"):
        settings_module.get_settings("fake")

    settings_module.get_settings.cache_clear()

def test_dev_settings_module_defaults():
    assert isinstance(dev_settings, DevSettings)
    assert dev_settings.host == "127.0.0.1"
    assert dev_settings.compute_type == "int8"


def test_qa_settings_module_defaults():
    assert isinstance(qa_settings, QaSettings)
    assert qa_settings.port == 8080
    assert qa_settings.model_size == "small"


def test_prod_settings_module_defaults():
    assert isinstance(prod_settings, ProdSettings)
    assert prod_settings.model_size == "large-v2"
    assert prod_settings.compute_type == "float32"
