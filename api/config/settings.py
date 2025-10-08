
import importlib
import os
import sys
from functools import lru_cache
from typing import Dict

from . import settings_base as _settings_base

if "api.config.settings_base" in sys.modules:
    _settings_base = importlib.reload(_settings_base)

AppSettings = _settings_base.AppSettings


class Settings(AppSettings):
    """Backward-compatible base settings class."""

_SETTINGS_MODULES: Dict[str, str] = {
    "dev": "api.config.settings_dev",
    "qa": "api.config.settings_qa",
    "prod": "api.config.settings_prod",
}


def _load_settings(env: str) -> AppSettings:
    """Import the environment-specific settings module and return its instance."""
    module_path = _SETTINGS_MODULES.get(env)
    if module_path is None:
        available = ", ".join(sorted(_SETTINGS_MODULES))
        raise ValueError(f"Unsupported APP_ENV '{env}'. Choose one of: {available}.")

    module = importlib.import_module(module_path)
    module = importlib.reload(module)
    env_settings = getattr(module, "settings", None)
    if not isinstance(env_settings, AppSettings):
        raise TypeError(
            f"Module '{module_path}' must expose a 'settings' instance of AppSettings."
        )
    return env_settings


@lru_cache(maxsize=None)
def get_settings(env: str | None = None) -> AppSettings:
    """Resolve settings for the requested environment or the current APP_ENV."""
    selected_env = (env or os.getenv("APP_ENV", "dev")).lower()
    return _load_settings(selected_env)


settings = get_settings()
