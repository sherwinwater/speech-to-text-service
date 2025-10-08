try:
    from pydantic_settings import BaseSettings  # type: ignore
except ImportError:
    from pydantic import BaseSettings  # type: ignore


class AppSettings(BaseSettings):
    """Common application settings with sensible defaults."""

    model_size: str = "small"
    compute_type: str = "int8"
    max_file_mb: int = 100
    max_duration_sec: int = 3600
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_prefix = ""
