from .settings_base import AppSettings


class DevSettings(AppSettings):
    """Development defaults optimized for local work."""

    host: str = "127.0.0.1"
    port: int = 8000
    model_size: str = "small"
    compute_type: str = "int8"


settings = DevSettings()
