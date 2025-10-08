from .settings_base import AppSettings


class QaSettings(AppSettings):
    """QA defaults aligned with staging validation."""

    host: str = "0.0.0.0"
    port: int = 8080
    model_size: str = "small"
    compute_type: str = "int8"


settings = QaSettings()
