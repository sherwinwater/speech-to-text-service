from .settings_base import AppSettings


class ProdSettings(AppSettings):
    """Production defaults tuned for throughput."""

    host: str = "0.0.0.0"
    port: int = 8000
    model_size: str = "large-v2"
    compute_type: str = "float32"


settings = ProdSettings()
